"""Jobs: the evidence-level commands the web app runs for the user, as subprocesses of the server.

A job is a list of steps, each one command line (webapp/evjobs.py builds them from fixed templates), run in
order by an asyncio task in the server's event loop. Every job is in one of two lanes: `model` (it calls a
model: an engine run with LLM extractors, a baseline, the proposal flow's model steps) or `cpu` (a template
corpus, a regex-only run, a score, a freeze). At most `model_jobs` jobs of the model lane run at a time (1 by
default: one model behind the gateway, so its jobs queue in the order they were submitted), and at most
`cpu_jobs` of the cpu lane, beside them.

Every step's output goes to the job's log, `$EV/.jobs/<id>.log`, after a `$ <command>` line; the job's state
is `$EV/.jobs/<id>.json`, rewritten (atomically) at every change, so a restarted server (and a reloaded page)
still lists old jobs. A job that was queued or running when the server stopped is marked failed when the next
server starts: its subprocess is no longer ours to watch.

A step one of whose `needs` files is missing is skipped (the proposal flow's later steps after a failed one);
a failed step does not stop the next ones, but a failed `required` step fails the job, and a failed optional
one adds a warning to it. Cancelling a queued job ends it at once; a running one gets SIGTERM (then SIGKILL
after a grace period at server stop) and skips its remaining steps.

The request handlers read the jobs from the server's thread pool while the event loop adds them, so every
read iterates over a snapshot (`list(...)`, which copies without yielding).

Commands are argv lists (no shell). The subprocess environment is the server's (the model gateway's URL and
key come from there: start the server with llm-setup's `.env` sourced, README "Web app") plus the settings'
gateway URL, agent root and the agentic extractor's work directory; API keys reach the children only through
that inherited environment and never appear in an argv, a log line or a state file.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import shlex
import signal
import subprocess
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.rundir import utc_now

from .files import Conflict, NotFound, check_id, read_json, write_json_atomic
from .models import Job, JobStep, Lane
from .settings import REPO, Settings

ACTIVE = ("queued", "running")
STOP_GRACE_S = 30
TAIL_BYTES = 256 * 1024   # the log tail reads at most this much from the end


def step(name: str, argv: list[str], *, required: bool = True,
         needs: Path | str | list[Path | str] | None = None) -> JobStep:
    argv = [str(a) for a in argv]
    needs = [] if needs is None else [needs] if isinstance(needs, (str, Path)) else needs
    return JobStep(name=name, argv=argv, command=shlex.join(argv), required=required, needs=[str(n) for n in needs])


class JobManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.jobs: dict[str, Job] = {}
        self._lanes: dict[str, asyncio.Semaphore] = {}
        self._procs: dict[str, asyncio.subprocess.Process] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._cancelled: dict[str, str] = {}  # job id -> why

    @property
    def dir(self) -> Path | None:
        return self.settings.jobs_dir

    def env(self) -> dict[str, str]:
        s = self.settings
        extra = {"LITELLM_BASE_URL": s.litellm_base_url, "AGENT_ROOT": s.agent_root,
                 "EVIDENCE_AGENT_WORK_DIR": s.agent_work_dir, "PYTHONUNBUFFERED": "1"}
        return {**os.environ, **{k: str(v) for k, v in extra.items() if v is not None}}

    # --- state ---------------------------------------------------------------------------------------

    def load(self) -> None:
        """Read the jobs of earlier servers; any still queued or running lost its process."""
        if self.dir is None or not self.dir.is_dir():
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
        assert self.dir is not None
        write_json_atomic(self.dir / f"{job.id}.json", job.model_dump(mode="json"))

    def list(self) -> list[Job]:
        return sorted(list(self.jobs.values()), key=lambda j: (j.created_at, j.id), reverse=True)

    def get(self, job_id: str) -> Job:
        job = self.jobs.get(check_id(job_id, "job"))
        if job is None:
            raise NotFound(f"no such job: {job_id!r}")
        return job

    def log_path(self, job: Job) -> Path:
        assert self.dir is not None
        return self.dir / f"{job.id}.log"

    def tail(self, job_id: str, lines: int = 200) -> str:
        """The last `lines` lines of the job's log (empty before its first step starts)."""
        job = self.get(job_id)
        try:
            with open(self.log_path(job), "rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                fh.seek(max(0, size - TAIL_BYTES))
                data = fh.read()
        except OSError:
            return ""
        text = data.decode("utf-8", errors="replace")
        if size > TAIL_BYTES:   # the first line read is a part of a line
            text = text.split("\n", 1)[1] if "\n" in text else ""
        return "\n".join(deque(text.splitlines(), maxlen=lines)) + ("\n" if text.endswith("\n") else "")

    def active(self, kind: str | None = None) -> list[Job]:
        return [j for j in list(self.jobs.values()) if j.state in ACTIVE and kind in (None, j.kind)]

    def busy(self, ref: str, value: str) -> Job | None:
        """The queued or running job that writes `ref` (corpus, run, score, proposal) `value`, if any."""
        return next((j for j in self.active() if j.refs.get(ref) == value), None)

    # --- running ---------------------------------------------------------------------------------------

    def _lane(self, lane: Lane) -> asyncio.Semaphore:
        if lane not in self._lanes:
            self._lanes[lane] = asyncio.Semaphore(self.settings.model_jobs if lane == "model" else self.settings.cpu_jobs)
        return self._lanes[lane]

    def submit(self, kind: str, args: dict[str, Any], steps: list[JobStep], *, lane: Lane = "cpu",
               refs: dict[str, str] | None = None) -> Job:
        """Queue a job; call from the event loop (an async endpoint)."""
        if self.dir is None:
            raise Conflict("no $EV configured: jobs keep their state in $EV/.jobs and write into the $EV layout")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        job = Job(id=f"{stamp}-{kind}-{secrets.token_hex(3)}", kind=kind, lane=lane, args=args, refs=refs or {},
                  state="queued", created_at=utc_now(), steps=steps)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.jobs[job.id] = job
        self._save(job)
        task = asyncio.get_running_loop().create_task(self._run(job.id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def _run(self, job_id: str) -> None:
        job = self.jobs[job_id]
        async with self._lane(job.lane):
            if job.state != "queued":  # cancelled while it waited
                return
            job.state, job.started_at = "running", utc_now()
            self._save(job)
            try:
                with open(self.log_path(job), "ab", buffering=0) as log:
                    for s in job.steps:
                        await self._step(job, s, log)
            except OSError as exc:  # the log or the state file cannot be written
                self._finish(job, error=f"{type(exc).__name__}: {exc}")
                return
            failed = [s for s in job.steps if s.required and s.state == "failed"]
            self._finish(job, exit_code=failed[0].exit_code if failed else 0, error=self._cancelled.get(job_id))

    async def _step(self, job: Job, s: JobStep, log: Any) -> None:
        if job.id in self._cancelled:
            s.state = "skipped"
            return
        missing = [n for n in s.needs if not Path(n).exists()]
        if missing:
            s.state = "skipped"
            log.write(f"# skipped {s.name}: {', '.join(missing)} does not exist\n".encode())
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
        if code != 0 and not s.required and job.id not in self._cancelled:
            job.warnings.append(f"{s.name} failed (exit {code}); see the log")
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
