"""Subagents (milestones-1-2.md, row 2.12): the harness side of the `spawn` command.

Off unless `agent run --spawn on` (config.json `spawn`, SpawnSettings.config; the batch manifest
field `spawn`). When on, every command of the agent gets a SPAWN_FD channel, as it gets CLAIM_FD:
a SOCK_SEQPACKET socketpair whose other end a thread here reads (CommandChannel). Inside the
sandbox `spawn --task "..." [--files a.md,b.md] [--steps N]` (agent/spawn_client.py) sends one
request per message, with the write end of a pipe it made, and blocks on the read end until the
subagent's result comes back; several spawns in one command share the channel (`spawn ... &
spawn ... & wait`) because each reply goes to its own pipe.

SpawnService runs the subagents, at most `max_concurrent` (2) at once: one worker thread per
sub-model replica (rundir.SUBAGENTS: sub-model-1 on one, sub-model-2 on the other); the rest
wait in a queue, in the order they came. A subagent (SubAgent) is the research loop
(loop.ResearchAgent) with the sub model (32,768 context), its own small budget (15 steps /
300,000 tokens; --steps may lower the steps), its own prompts (agent/prompts/sub-v1.txt, and
sub-v1-baseline.txt in a claim_off run), its own scratch directory (sub/<id>/scratch, outside
the parent's, so neither can change the other's files) and trajectory (sub/<id>/trajectory.json),
`claim` iff the run is claim_on, and no spawn (depth 1). Its result is {"summary"} as its final
json block; the harness adds the claims it recorded, read from the broker's log, not from it.

Records, all in the run's one hash chain:
- the parent's `spawn` record when a subagent starts (status started, used.task/files/steps,
  generated.agent_id and model; parent_task_id the parent's model call), and another when it
  returns (status finished, cancelled or error; generated.exit_status, result_sha256 of
  sub/<id>/result.json, the result as sent; custom_metadata steps, model_calls, tokens), or one
  saying why a request was refused (spawn_limit, unknown_file, ...; status refused);
- the subagent's own model calls, commands, claims and coverage, with agent_id sub-NN,
  source_agent_id main and custom_metadata.spawned_by_step = the parent's step; its first model
  call points at the start record. Step ids come from the run's StepCounter, so they stay unique
  in the run (out/step-NNNN.txt) while the parent's spawn command runs.

Cost: the parent's budget counts its own calls only (each subagent has its own); `agent verify`
reports the run's total and each agent's (verify.stats `agents`).

Time: a command that calls spawn gets `command_timeout_s` (1,800 s, recorded) instead of 120 s
(loop.SandboxEnvironment.timeout_for). When a command ends, subagents it started that are still
queued or running are cancelled (nobody can read their result): a running one stops at its next
model call or command, and its running command is killed. SIGTERM (row 2.9) stops them the same
way, before the broker closes.

Subagent n uses the run's temperature and seed + n.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import socket
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from minisweagent.exceptions import LimitsExceeded

from . import prompts, stopping
from .broker import Corpus, Rejected
from .canonical import canonical_bytes, sha256_hex
from .loop import (Broker, LoopSettings, OrchestratorModel, ResearchAgent, SandboxEnvironment, StepCounter,
                   claim_records)
from .rundir import SUBAGENTS, RunDir, utc_now

SUB_DIR = "sub"  # runs/<id>/sub/<agent id>/: scratch/, trajectory.json, result.json
SUB_PROMPT_VERSION = "v1"
MAX_REQUEST = 64 * 1024  # bytes of one request message
MAX_TASK = 8_000  # characters of a task
MAX_FILES = 50
SUMMARY_MAX = 4_000  # characters of a summary passed to the parent
FINISH_WAIT_S = 10.0  # how long a stopping harness waits for cancelled subagents
SUMMARY_SCHEMA: dict[str, Any] = {"type": "object", "additionalProperties": False, "required": ["summary"],
                                  "properties": {"summary": {"type": "string"}}}
RAN = ("submitted", "budget", "context_full", "repeats")  # exit statuses of a subagent that ran its course
logger = logging.getLogger("agent.spawn")


@dataclass(frozen=True)
class SpawnSettings:
    """The spawn command's settings; config() goes into config.json `spawn`."""

    enabled: bool = False
    steps: int = 15  # a subagent's budget; `spawn --steps N` may lower the steps
    tokens: int = 300_000
    max_concurrent: int = len(SUBAGENTS)  # one worker per sub-model replica
    max_subagents: int = 20  # per run: subagent tokens are outside the parent's budget, so they are capped here
    command_timeout_s: int = 1_800  # a command that calls spawn
    max_tokens: int = 4_096  # a subagent's reply limit
    prompt_version: str = SUB_PROMPT_VERSION

    def __post_init__(self) -> None:
        if not 1 <= self.max_concurrent <= len(SUBAGENTS):
            raise ValueError(f"max_concurrent must be between 1 and {len(SUBAGENTS)} (one per sub-model)")
        if min(self.steps, self.tokens, self.max_subagents, self.command_timeout_s, self.max_tokens) < 1:
            raise ValueError("spawn budgets and limits must be positive")

    def loop(self, run_loop: LoopSettings) -> LoopSettings:
        """A subagent's loop: the run's conclude decoding, masking fitted to a 32k context, no draft."""
        return LoopSettings(conclude_replies=1, conclude_decoding=run_loop.conclude_decoding, conclude_max_tokens=None,
                            mask_keep=4, mask_keep_tight=2, mask_tight_above=20_000, budget_warnings=(75, 90),
                            repeat_stop=4, draft_file=None)

    def config(self, condition: str, run_loop: LoopSettings) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False}
        prompt = prompts.load_sub(self.prompt_version, condition)
        return {"enabled": True, "budget": {"steps": self.steps, "tokens": self.tokens, "announced": True},
                "max_concurrent": self.max_concurrent, "max_subagents": self.max_subagents,
                "command_timeout_s": self.command_timeout_s,
                "models": [s["alias"] for s in SUBAGENTS[:self.max_concurrent]], "max_tokens": self.max_tokens,
                "claim": condition == "claim_on",
                "prompt": {"version": prompt.version, "sha256": prompt.sha256, "files": prompt.files},
                "loop": self.loop(run_loop).config()}

    def template_vars(self) -> dict[str, Any]:
        """Values for the spawn block of the parent's system prompt (prompts.load(spawn=True))."""
        if not self.enabled:
            return {}
        return {"spawn_steps": self.steps, "spawn_tokens": self.tokens, "spawn_max": self.max_subagents,
                "spawn_concurrent": self.max_concurrent, "spawn_minutes": self.command_timeout_s // 60,
                "spawn_context": SUBAGENTS[0]["context_tokens"]}


class Refused(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def send_reply(fd: int, reply: dict[str, Any]) -> bytes:
    """Write `reply` (one canonical JSON line) to the requester's pipe and close it; returns the bytes.

    A requester that is gone (its command ended) is not an error.
    """
    data = canonical_bytes(reply) + b"\n"
    try:
        with os.fdopen(fd, "wb") as pipe:
            pipe.write(data)
    except OSError:
        pass
    return data


@dataclass(eq=False)  # compared and hashed by identity: jobs live in a set
class SpawnJob:
    """One accepted spawn request, from the queue to its result."""

    agent_id: str
    number: int
    channel: CommandChannel
    task: str
    files: list[str]
    steps: int
    steps_requested: int | None
    reply_fd: int | None  # the requester's pipe; None once the reply is sent (the descriptor is closed)
    requested_at: float = field(default_factory=time.monotonic)
    cancel: threading.Event = field(default_factory=threading.Event)
    done: threading.Event = field(default_factory=threading.Event)
    started: bool = False

    @property
    def step_id(self) -> int:
        return self.channel.step_id

    def reply(self, reply: dict[str, Any]) -> bytes:
        """Send the reply once: a second call must not write to a descriptor number reused since."""
        fd, self.reply_fd = self.reply_fd, None
        return send_reply(fd, reply) if fd is not None else canonical_bytes(reply) + b"\n"


class CommandChannel:
    """One command's SPAWN_FD: a SEQPACKET socketpair; a thread reads requests from the harness end."""

    def __init__(self, service: SpawnService, step_id: int, parent_task_id: str | None) -> None:
        self.service = service
        self.step_id = step_id
        self.parent_task_id = parent_task_id
        self.harness_end, self.sandbox_end = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.jobs: list[SpawnJob] = []
        self.ended = False
        self.thread = threading.Thread(target=self._listen, daemon=True, name=f"spawn-step-{step_id}")
        self.thread.start()

    def _listen(self) -> None:
        while True:
            try:
                msg, fds, flags, _ = socket.recv_fds(self.harness_end, MAX_REQUEST, 1)
            except OSError:
                return
            if not msg and not fds:  # every copy of the sandbox end is closed: the command has ended
                return
            try:
                self.service.request(self, msg, fds, truncated=bool(flags & getattr(socket, "MSG_TRUNC", 0)))
            except Exception:  # noqa: BLE001 - keep reading this command's requests
                logger.exception("spawn request at step %s failed", self.step_id)

    def finish(self) -> list[str]:
        """After the command: take no more requests, cancel its subagents still queued or running.

        Returns the ids of the subagents it started. Normally all are done (the command waited
        for them). A process that left the command's session and still holds SPAWN_FD cannot
        keep the channel open: after 2 s the harness end is shut down.
        """
        self.ended = True
        self.thread.join(timeout=2)
        if self.thread.is_alive():
            try:
                self.harness_end.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.thread.join()
        self.harness_end.close()
        for job in self.jobs:
            if not job.done.is_set():
                job.cancel.set()
        for job in self.jobs:
            job.done.wait(timeout=FINISH_WAIT_S if stopping.requested() else None)
        return [job.agent_id for job in self.jobs if job.started]


class SubAgent(ResearchAgent):
    """The research loop as a subagent: its result is {"summary"}, kept for the parent, not answer.json."""

    reply_shape = '{"summary": "..."}'

    def __init__(self, model: OrchestratorModel, env: SandboxEnvironment, *, broker: Broker, run: RunDir,
                 concept: dict[str, Any], prompt: prompts.Prompt, budget: dict[str, Any], settings: LoopSettings,
                 job: SpawnJob, spawn_task_id: str, next_step: Callable[[], int]) -> None:
        super().__init__(model, env, broker=broker, run=run, concept=concept, prompt=prompt, budget=budget,
                         settings=settings, agent_id=job.agent_id, source_agent_id="main",
                         record_meta={"spawned_by_step": job.step_id}, parent_task_id=spawn_task_id,
                         next_step=next_step, trajectory=run.root / SUB_DIR / job.agent_id / "trajectory.json")
        self.cancel = job.cancel
        self.reply_schema = SUMMARY_SCHEMA
        self.reply_schema_sha256 = sha256_hex(canonical_bytes(SUMMARY_SCHEMA))
        files = ", ".join(job.files)
        self.extra_template_vars |= {
            "sub_task": job.task,
            "sub_files": (f"Start with these corpus files: {files}." if files else
                          "The agent named no files; find the papers you need in $CORPUS.")}

    def _check_answer(self, text: str) -> tuple[dict[str, Any] | None, list[str]]:
        """The result block: an object with a string "summary" (other keys are ignored: claims come from the log)."""
        try:
            given = json.loads(text)
        except (ValueError, RecursionError) as exc:
            return None, [f"the json block is not valid JSON: {exc}"[:300]]
        if not isinstance(given, dict) or not isinstance(given.get("summary"), str):
            return None, ['the json block must be one object {"summary": "..."}']
        return {"summary": given["summary"]}, []

    def _submit(self, answer: dict[str, Any]) -> None:
        self.answer, self.answer_from = answer, "final"

    def query(self) -> dict[str, Any]:
        if self.cancel.is_set():
            raise LimitsExceeded(self._exit("cancelled"))
        return super().query()

    def _run_command(self, step: int, parsed: Any) -> dict[str, Any]:
        if self.cancel.is_set():  # the parent's command ended: nobody reads the result any more
            self._coverage(step, "command_not_run", parsed.command, {"why": "cancelled"})
            raise LimitsExceeded(self._exit("cancelled"))
        return super()._run_command(step, parsed)


def run_subagent(agent: SubAgent) -> str:
    """Run a subagent to its end; its exit status (an error or the harness stopping included, never raised)."""
    try:
        return agent.run(task="").get("exit_status", "") or "no_result"
    except BaseException as exc:  # noqa: BLE001 - a worker thread must outlive any subagent
        status = "stopped" if stopping.requested() or isinstance(exc, SystemExit) else "error"
        if status == "error":
            logger.exception("subagent %s failed", agent.agent_id)
        try:
            agent._coverage(agent.step_id, "run_error", "", {"error": f"{type(exc).__name__}: {exc}"[:500],
                                                          "exit_status": status})
        except Exception:  # noqa: BLE001 - the broker may be closing
            pass
        return status


class SpawnService:
    """Runs the subagents of one run: requests from CommandChannels, `max_concurrent` worker threads."""

    def __init__(self, run: RunDir, broker: Broker, settings: SpawnSettings, *, concept: dict[str, Any], corpus: Path,
                 manifest: Path, condition: str, sandbox_mode: str, agent_root: Path | None = None,
                 extra_path: tuple[str, ...] = (), base_url: str, temperature: float, seed: int,
                 loop: LoopSettings, next_step: StepCounter,
                 model_factory: Callable[[SpawnJob, dict[str, Any], int], OrchestratorModel] | None = None) -> None:
        self.run = run
        self.broker = broker
        self.settings = settings
        self.concept = concept
        self.corpus = Path(corpus)
        self.files = Corpus(corpus, manifest)  # file names as the broker accepts them (p12, p12.md, ...)
        self.claim = condition == "claim_on"
        self.sandbox = {"mode": sandbox_mode, "agent_root": agent_root, "extra_path": tuple(extra_path)}
        self.base_url = base_url
        self.temperature = temperature
        self.seed = seed
        self.loop = settings.loop(loop)
        self.prompt = prompts.load_sub(settings.prompt_version, condition)
        self.next_step = next_step
        self.model_factory = model_factory or self._model
        self.count = 0  # subagent numbers given out
        self.started = 0  # subagents that ran
        self.tokens = 0  # their tokens
        self.closed = False
        self._lock = threading.Lock()
        self._queue: queue.Queue[SpawnJob | None] = queue.Queue()
        self._live: set[SpawnJob] = set()
        self._workers = [threading.Thread(target=self._work, args=(slot,), daemon=True, name=slot["alias"])
                         for slot in SUBAGENTS[:settings.max_concurrent]]
        for worker in self._workers:
            worker.start()

    # the parent's side

    def channel(self, step_id: int, parent_task_id: str | None) -> CommandChannel:
        """A SPAWN_FD channel for one command of the parent (SandboxEnvironment.execute)."""
        return CommandChannel(self, step_id, parent_task_id)

    def close(self, timeout: float = 30.0) -> None:
        """Cancel what is left and stop the workers (before the broker closes)."""
        with self._lock:
            self.closed = True
            for job in self._live:
                job.cancel.set()
        for _ in self._workers:
            self._queue.put(None)
        for worker in self._workers:
            worker.join(timeout=timeout)

    def request(self, channel: CommandChannel, msg: bytes, fds: list[int], truncated: bool) -> None:
        """One request from a CommandChannel's thread: queue a SpawnJob, or refuse it (record and reply)."""
        for extra in fds[1:]:
            os.close(extra)
        reply_fd = fds[0] if fds else None
        shown: dict[str, Any] = {}
        try:
            if truncated or len(msg) > MAX_REQUEST:
                raise Refused("bad_request: the request is over 64 KB")
            body = self._body(msg)
            shown = {"task": body["task"], "files": body["files"], "steps": body["steps"]}
            if reply_fd is None:
                raise Refused("bad_request: no reply pipe")
            files = []
            for name in body["files"]:
                try:
                    files.append(self.files.name(name))
                except Rejected as exc:  # unknown_file, file_outside_corpus
                    raise Refused(f"{exc.reason}: {name}") from None
            steps = min(body["steps"] or self.settings.steps, self.settings.steps)
            with self._lock:
                if channel.ended:
                    raise Refused("command_ended")
                if self.closed or stopping.requested():
                    raise Refused("stopped")
                if self.count >= self.settings.max_subagents:
                    raise Refused(f"spawn_limit: this run has started its {self.settings.max_subagents} subagents")
                self.count += 1
                job = SpawnJob(f"sub-{self.count:02d}", self.count, channel, body["task"], files, steps,
                               body["steps"], reply_fd)
                self._live.add(job)
            channel.jobs.append(job)
            self._queue.put(job)
        except Refused as exc:
            self._refuse(channel, reply_fd, shown, exc.reason)

    @staticmethod
    def _body(msg: bytes) -> dict[str, Any]:
        try:
            body = json.loads(msg.decode("utf-8"))
        except (ValueError, RecursionError):
            raise Refused("bad_request: the request is not JSON") from None
        if not isinstance(body, dict) or set(body) - {"task", "files", "steps"}:
            raise Refused("bad_request: the request must be {task, files, steps}")
        task, files, steps = body.get("task"), body.get("files", []), body.get("steps")
        if not isinstance(task, str) or not task.strip():
            raise Refused("bad_request: --task is empty")
        if len(task) > MAX_TASK:
            raise Refused(f"bad_request: the task is over {MAX_TASK:,} characters")
        if not isinstance(files, list) or len(files) > MAX_FILES or not all(isinstance(f, str) and f for f in files):
            raise Refused(f"bad_request: --files must name at most {MAX_FILES} corpus files")
        if steps is not None and (not isinstance(steps, int) or isinstance(steps, bool) or steps < 1):
            raise Refused("bad_request: --steps must be a positive number")
        return {"task": task, "files": files, "steps": steps}

    def _refuse(self, channel: CommandChannel, reply_fd: int | None, shown: dict[str, Any], reason: str) -> None:
        self._spawn_record(channel.step_id, channel.parent_task_id, used=shown, generated={"reason": reason},
                           status="refused", meta={"event": "refused"})
        if reply_fd is not None:
            send_reply(reply_fd, {"ok": False, "reason": reason})

    def _spawn_record(self, step: int, parent: str | None, *, used: dict[str, Any], generated: dict[str, Any],
                      status: str, meta: dict[str, Any], started_at: str | None = None) -> str | None:
        record = {"subtype": "spawn", "step_id": step, "agent_id": "main", "parent_task_id": parent, "used": used,
                  "generated": generated, "status": status, "custom_metadata": {"origin": "research", **meta}}
        if started_at:
            record["started_at"] = started_at
        try:
            return self.broker.record(record)["task_id"]
        except Exception:  # noqa: BLE001 - the broker closed under a stopping harness
            logger.exception("spawn record not written")
            return None

    # the workers

    def _work(self, slot: dict[str, Any]) -> None:
        while True:
            job = self._queue.get()
            if job is None:
                return
            try:
                self._run(job, slot)
            except BaseException:  # noqa: BLE001 - keep the worker for the next job
                logger.exception("spawn %s failed", job.agent_id)
            finally:
                job.reply({"ok": False, "reason": "spawn_failed"})  # no-op once the result was sent
                with self._lock:
                    self._live.discard(job)
                job.done.set()

    def _model(self, job: SpawnJob, slot: dict[str, Any], seed: int) -> OrchestratorModel:
        return OrchestratorModel(base_url=self.base_url, temperature=self.temperature, seed=seed, alias=slot["alias"],
                                 max_tokens=self.settings.max_tokens, name=slot["name"], revision=slot["revision"],
                                 context_tokens=slot["context_tokens"])

    def _run(self, job: SpawnJob, slot: dict[str, Any]) -> None:
        """Start record, the subagent, result.json, return record, reply: the return record is written whatever happens."""
        shown = {"task": job.task, "files": job.files, "steps": job.steps, "steps_requested": job.steps_requested}
        if job.cancel.is_set() or self.closed:  # its command ended (or the run stops) before a worker was free
            self._spawn_record(job.step_id, job.channel.parent_task_id, used=shown,
                               generated={"agent_id": job.agent_id, "reason": "cancelled before it started"},
                               status="cancelled", meta={"event": "cancelled"})
            job.reply({"ok": False, "reason": "cancelled"})
            return
        seed = self.seed + job.number
        started_at, t0 = utc_now(), time.monotonic()
        start = self._spawn_record(
            job.step_id, job.channel.parent_task_id, used=shown,
            generated={"agent_id": job.agent_id, "model": slot["alias"], "model_name": slot["name"],
                       "revision": slot["revision"], "seed": seed},
            status="started", meta={"event": "start", "queued_seconds": round(t0 - job.requested_at, 3),
                                    "budget": {"steps": job.steps, "tokens": self.settings.tokens}})
        job.started = True
        root = self.run.root / SUB_DIR / job.agent_id
        agent: SubAgent | None = None
        status = "error"
        try:
            (root / "scratch").mkdir(parents=True)
            env = SandboxEnvironment(self.run, corpus=self.corpus, mode=self.sandbox["mode"], claim=self.claim,
                                     agent_root=self.sandbox["agent_root"], extra_path=self.sandbox["extra_path"],
                                     agent_id=job.agent_id, scratch=root / "scratch", cancel=job.cancel,
                                     channel_meta={"source_agent_id": "main", "spawned_by_step": job.step_id})
            agent = SubAgent(self.model_factory(job, slot, seed), env, broker=self.broker, run=self.run,
                             concept=self.concept, prompt=self.prompt,
                             budget={"steps": job.steps, "tokens": self.settings.tokens}, settings=self.loop, job=job,
                             spawn_task_id=start or "", next_step=self.next_step)
            status = run_subagent(agent)
        finally:
            result = self._result(job, agent, status)
            data = canonical_bytes(result) + b"\n"
            root.mkdir(parents=True, exist_ok=True)
            (root / "result.json").write_bytes(data)
            cost = {"steps": agent.research_steps, "model_calls": agent.n_calls, "tokens": agent.tokens} if agent else {
                "steps": 0, "model_calls": 0, "tokens": 0}
            with self._lock:
                self.started += 1
                self.tokens += cost["tokens"]
            self._spawn_record(
                job.step_id, start, used={}, status="finished" if status in RAN else status, started_at=started_at,
                generated={"agent_id": job.agent_id, "exit_status": status,
                           "result_file": f"{SUB_DIR}/{job.agent_id}/result.json", "result_sha256": sha256_hex(data),
                           "claims": [c["claim_id"] for c in result.get("claims", [])]},
                meta={"event": "return", **cost, "seconds": round(time.monotonic() - t0, 3)})
            job.reply(result)

    def _result(self, job: SpawnJob, agent: SubAgent | None, status: str) -> dict[str, Any]:
        """What the parent's spawn prints: the summary, how it ended, and (claim_on) the claims it recorded."""
        summary = ((agent.answer if agent else None) or {}).get("summary", "")
        if len(summary) > SUMMARY_MAX:
            summary = summary[:SUMMARY_MAX] + f" [summary cut at {SUMMARY_MAX:,} characters]"
        result: dict[str, Any] = {"ok": status in RAN, "agent_id": job.agent_id, "status": status, "summary": summary,
                                  "steps": agent.research_steps if agent else 0, "tokens": agent.tokens if agent else 0}
        if status not in RAN:
            result["reason"] = status
        if self.claim:
            result["claims"] = [
                {"claim_id": r["generated"]["claim_id"], "s": r["custom_metadata"]["s"], "p": r["custom_metadata"]["p"],
                 "o": r["custom_metadata"]["o"], "file": r["used"]["anchor"]["file"]}
                for r in claim_records(self.run) if r["agent_id"] == job.agent_id and r["status"] == "accepted"]
        return result
