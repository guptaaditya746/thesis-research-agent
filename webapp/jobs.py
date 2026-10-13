"""Jobs: CLI commands the web app runs for the user, as subprocesses of the server.

A job is a list of steps, each one command line (`python -m agent.cli run ...`, then the post
steps), run in order by an asyncio task in the server's event loop. Jobs of one kind run one at
a time, in the order they were submitted (an asyncio.Lock per kind); different kinds run side by
side. Every step's output goes to the job's log, $RUNS/.jobs/<id>.log, after a `$ <command>`
line; the job's state is $RUNS/.jobs/<id>.json, rewritten (atomically) at every change, so a
restarted server still lists old jobs. A job that was queued or running when the server stopped
is marked failed when the next server starts: its subprocess is no longer ours to watch.

A step whose `needs` file is missing is skipped (e.g. no post steps when the run never started);
a failed step does not stop the next ones (the post steps of a run that ran out of budget are
still useful), but a failed `required` step fails the job. Cancelling sends SIGTERM to the
running step (`agent run` and `agent attach` stop cleanly on it) and skips the rest.

Commands are argv lists (no shell). The subprocess environment is the server's plus the roots of
the settings; API keys reach the children only through that inherited environment and never
appear in an argv, a log line or a state file.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import shlex
import signal
import subprocess
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sse_starlette import ServerSentEvent

from agent.rundir import utc_now

from .files import NotFound, check_id, read_json, write_json_atomic
from .models import Job, JobStep
from .settings import REPO, Settings

ACTIVE = ("queued", "running")
STOP_GRACE_S = 30


def step(name: str, argv: list[str], *, required: bool = True, needs: Path | str | None = None) -> JobStep:
    argv = [str(a) for a in argv]
    return JobStep(name=name, argv=argv, command=shlex.join(argv), required=required,
                   needs=str(needs) if needs is not None else None)


class JobManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.jobs: dict[str, Job] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._procs: dict[str, asyncio.subprocess.Process] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._cancelled: dict[str, str] = {}  # job id -> why

    @property
    def dir(self) -> Path:
        return self.settings.jobs_dir

    def env(self) -> dict[str, str]:
        s = self.settings
        extra = {"CORPUS": s.corpus, "RUNS": s.runs, "GOLD": s.gold, "CONCEPTS": s.concepts,
                 "LITELLM_BASE_URL": s.litellm_base_url, "AGENT_ROOT": s.agent_root, "PYTHONUNBUFFERED": "1"}
        return {**os.environ, **{k: str(v) for k, v in extra.items() if v is not None}}

    # --- state ---------------------------------------------------------------------------------------

    def load(self) -> None:
        """Read the jobs of earlier servers; any still queued or running lost its process."""
        if not self.dir.is_dir():
            return
        for path in sorted(self.dir.glob("*.json")):
            data = read_json(path)
            try:
                job = Job.model_validate(data)
            except ValueError:
                continue
            if job.state in ACTIVE:
                job.state, job.error, job.ended_at = "failed", f"the server stopped while the job was {job.state}", utc_now()
                for s in job.steps:
                    if s.state in ("pending", "running"):
                        s.state = "skipped" if s.state == "pending" else "failed"
                self._save(job)
            self.jobs[job.id] = job

    def _save(self, job: Job) -> None:
        write_json_atomic(self.dir / f"{job.id}.json", job.model_dump(mode="json"))

    def list(self) -> list[Job]:
        return sorted(self.jobs.values(), key=lambda j: (j.created_at, j.id), reverse=True)

    def get(self, job_id: str) -> Job:
        job = self.jobs.get(check_id(job_id, "job"))
        if job is None:
            raise NotFound(f"no such job: {job_id!r}")
        return job

    def log_path(self, job_id: str) -> Path:
        return self.dir / f"{self.get(job_id).id}.log"

    def active(self, kind: str | None = None, *, run_id: str | None = None, qid: str | None = None) -> list[Job]:
        return [j for j in self.jobs.values() if j.state in ACTIVE and kind in (None, j.kind)
                and run_id in (None, j.run_id) and qid in (None, j.qid)]

    def active_run(self, run_id: str) -> bool:
        return bool(self.active(run_id=run_id))

    # --- running ---------------------------------------------------------------------------------------

    def submit(self, kind: str, args: dict[str, Any], steps: list[JobStep], *, run_id: str | None = None,
               qid: str | None = None) -> Job:
        """Queue a job; call from the event loop (an async endpoint)."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        job = Job(id=f"{stamp}-{kind}-{secrets.token_hex(3)}", kind=kind, args=args, state="queued",
                  created_at=utc_now(), run_id=run_id, qid=qid, steps=steps)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.jobs[job.id] = job
        self._save(job)
        task = asyncio.get_running_loop().create_task(self._run(job.id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def _run(self, job_id: str) -> None:
        job = self.jobs[job_id]
        async with self._locks.setdefault(job.kind, asyncio.Lock()):
            if job.state != "queued":  # cancelled while it waited
                return
            job.state, job.started_at = "running", utc_now()
            self._save(job)
            try:
                with open(self.dir / f"{job.id}.log", "ab", buffering=0) as log:
                    for s in job.steps:
                        await self._step(job, s, log)
            except OSError as exc:  # the log or the state file cannot be written
                self._finish(job, error=f"{type(exc).__name__}: {exc}")
                return
            failed = [s for s in job.steps if s.required and s.state == "failed"]
            self._finish(job, exit_code=failed[0].exit_code if failed else 0,
                         error=self._cancelled.get(job_id))

    async def _step(self, job: Job, s: JobStep, log: Any) -> None:
        if job.id in self._cancelled:
            s.state = "skipped"
            return
        if s.needs and not Path(s.needs).exists():
            s.state = "skipped"
            log.write(f"# skipped {s.name}: {s.needs} does not exist\n".encode())
            self._save(job)
            return
        log.write(f"$ {s.command}\n".encode())
        s.state, s.started_at = "running", utc_now()
        self._save(job)
        try:
            proc = await asyncio.create_subprocess_exec(
                *s.argv, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, cwd=REPO, env=self.env(),
                start_new_session=True)  # a Ctrl-C at the server's terminal is not sent to the child
        except OSError as exc:
            log.write(f"# cannot start {s.name}: {exc}\n".encode())
            code = 127
        else:
            self._procs[job.id] = proc
            try:
                code = await proc.wait()
            finally:
                self._procs.pop(job.id, None)
        log.write(f"# {s.name} exit {code}\n".encode())
        s.exit_code, s.ended_at = code, utc_now()
        s.state = "done" if code == 0 else "failed"
        self._save(job)

    def _finish(self, job: Job, *, exit_code: int | None = None, error: str | None = None) -> None:
        for s in job.steps:
            if s.state == "pending":
                s.state = "skipped"
        job.exit_code, job.error, job.ended_at = exit_code, error, utc_now()
        job.state = "failed" if error or (exit_code or 0) != 0 else "done"
        self._save(job)

    def cancel(self, job_id: str, why: str = "cancelled") -> Job:
        """A queued job ends at once; a running one gets SIGTERM and skips its remaining steps."""
        job = self.get(job_id)
        if job.state not in ACTIVE:
            return job
        self._cancelled[job.id] = why
        if job.state == "queued":
            self._finish(job, error=why)
            return job
        proc = self._procs.get(job.id)
        if proc is not None and proc.returncode is None:
            proc.send_signal(signal.SIGTERM)
        return job

    async def shutdown(self) -> None:
        """Server stop: SIGTERM to running steps (SIGKILL after a grace period); the jobs fail."""
        for job in self.active():
            self.cancel(job.id, "the server stopped")
        for proc in list(self._procs.values()):
            try:
                await asyncio.wait_for(proc.wait(), STOP_GRACE_S)
            except TimeoutError:
                proc.kill()
        if self._tasks:
            await asyncio.wait(list(self._tasks), timeout=5)
        for job in self.active():
            self._finish(job, error="the server stopped")

    # --- log stream ----------------------------------------------------------------------------------

    async def log_stream(self, job_id: str, after: int = 0) -> AsyncIterator[ServerSentEvent]:
        """`line` per log line (id = line number) as it is written, then `done` with the job."""
        job = self.get(job_id)
        path = self.dir / f"{job.id}.log"
        offset, line_no, pending = 0, 0, b""
        while True:
            finished = job.state not in ACTIVE
            try:
                with open(path, "rb") as fh:
                    fh.seek(offset)
                    chunk = fh.read()
            except OSError:
                chunk = b""
            offset += len(chunk)
            *lines, pending = (pending + chunk).split(b"\n")
            if finished and pending:
                lines, pending = [*lines, pending], b""
            for raw in lines:
                line_no += 1
                if line_no > after:
                    yield ServerSentEvent(raw.decode("utf-8", errors="replace"), event="line", id=str(line_no))
            if finished:
                yield ServerSentEvent(job.model_dump_json(), event="done")
                return
            await asyncio.sleep(self.settings.poll_s)
