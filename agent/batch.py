"""Batch runner (milestones-1-2.md, row 2.9): `agent batch <manifest>`.

A run manifest (agent/schemas/batch.schema.json; sample agent/manifests/m4-72.json) names
questions (each with its frozen concept.json), conditions and repeats. Each (question, condition,
repeat) is one run key, e.g. q01-claim_off-r2, with seed = seed_base + 100 * question number +
repeat, so both conditions of a question and repeat share a seed. Keys run in the order repeat,
question, condition: a job that ends early leaves whole repeats behind, with both conditions.

Each attempt at a key is its own run directory <runs_root>/<key>-a<N>. Per key, in order:
- an attempt that is finished (verified complete: `agent verify` passes, no cut or run_error
  coverage record, and for claim_off a finished attach step) -> the key is skipped;
- a claim_off attempt whose run finished but whose attach step never started -> only the attach
  step runs, in that directory;
- otherwise (cut, failed, or left incomplete by a job that died without marking it) -> a new
  attempt in a fresh run directory, up to `max_attempts` per key. A partly done run or attach step
  is never resumed in place: a cut run's chain stays as it was, ends with the cut, and is kept.

Runs and attach steps run sequentially as child processes (`python -m agent.cli run|attach`,
with the manifest's budget, prompt version, conclude decoding and spawn switch (row 2.12) when it
gives them), inside the job's time limit: `--deadline` (ISO time or epoch seconds), `--time-limit` (seconds from
now) or $SLURM_JOB_END_TIME (epoch seconds, set by Slurm), whichever comes first. A child still
running `--margin` seconds before the deadline gets SIGTERM (which `agent run` and `agent attach`
turn into a clean stop: broker closed, sandboxed command killed), then SIGKILL after a grace
period; the runner then appends a `coverage` record (agent "batch", reason job_time_limit) to that
run's chain, so the next job reruns the key. No run starts with less than `--min-start` seconds
left. An attempt found incomplete and unmarked (the job was killed outright) is marked
`interrupted` when the next job sees it. SIGTERM to the runner itself (Slurm's warning signal,
e.g. `#SBATCH --signal=B:TERM@300`) is passed to the running child and handled the same way.

Exit status: 0 when every key is finished, 2 when the job's time ran out with keys left (submit
the next job), 1 when a key gave up after `max_attempts` or the manifest is invalid.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import schema
from .broker import Broker
from .canonical import sha256_hex
from .rundir import RunDir, attach_state, utc_now

CUT_REASONS = ("job_time_limit", "interrupted")
MAX_ATTEMPTS = 3
GRACE_S = 30


@dataclass(frozen=True)
class Entry:
    question_id: str
    question_number: int
    concept: Path
    condition: str
    repeat: int
    seed: int

    @property
    def key(self) -> str:
        return f"{self.question_id}-{self.condition}-r{self.repeat}"


@dataclass(frozen=True)
class Manifest:
    data: dict[str, Any]
    path: Path

    @classmethod
    def load(cls, path: Path) -> Manifest:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        problems = schema.check("batch", data)
        if problems:
            raise ValueError(f"invalid run manifest {path}: {problems}")
        ids = [q["id"] for q in data["questions"]]
        if len(ids) != len(set(ids)):
            raise ValueError(f"invalid run manifest {path}: duplicate question ids")
        return cls(data, Path(path))

    def plan(self) -> list[Entry]:
        d = self.data
        return [Entry(q["id"], n, Path(q["concept"]), condition, r, d["seed_base"] + 100 * n + r)
                for r in range(1, d["repeats"] + 1)
                for n, q in enumerate(d["questions"], 1)
                for condition in d["conditions"]]

    @property
    def runs_root(self) -> Path:
        return Path(self.data["runs_root"])

    def corpus(self, override: Path | None = None) -> tuple[Path, Path]:
        corpus = override or self.data.get("corpus") or os.environ.get("CORPUS")
        if not corpus:
            raise ValueError("no corpus: set it in the manifest, pass --corpus or set $CORPUS")
        manifest = self.data.get("corpus_manifest") or Path(corpus) / "manifest.json"
        return Path(corpus), Path(manifest)


# --- deadline ----------------------------------------------------------------------------------------

def parse_deadline(text: str) -> float:
    """Epoch seconds, or an ISO-8601 time (a time without zone is UTC)."""
    if re.fullmatch(r"\d+(\.\d+)?", text.strip()):
        return float(text)
    stamp = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.timestamp()


def job_deadline(deadline: str | None = None, time_limit: float | None = None,
                 environ: dict[str, str] | None = None) -> float | None:
    """The earliest of --deadline, now + --time-limit and $SLURM_JOB_END_TIME; None if none is given."""
    env = os.environ if environ is None else environ
    found = []
    if deadline:
        found.append(parse_deadline(deadline))
    if time_limit is not None:
        found.append(time.time() + time_limit)
    if env.get("SLURM_JOB_END_TIME", "").strip().isdigit():
        found.append(float(env["SLURM_JOB_END_TIME"]))
    return min(found) if found else None


def _iso(epoch: float | None) -> str | None:
    return None if epoch is None else datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- run state -----------------------------------------------------------------------------------------

def _records(run: RunDir) -> list[dict[str, Any]]:
    out = []
    for raw in run.events.read_bytes().splitlines() if run.events.is_file() else []:
        try:
            out.append(json.loads(raw))
        except ValueError:
            break  # a torn last line; verify reports it
    return out


def run_state(run: RunDir, corpus: Path, manifest: Path) -> tuple[str, str]:
    """(state, detail): finished, attach_pending, cut, failed or incomplete."""
    from .verify import verify_run

    if not run.config.is_file():
        return "incomplete", "no config.json"
    # The run's own coverage (main agent, attach step, this runner): a subagent's (row 2.12) never
    # fails the run; it records its failure as subagent_error, and the parent goes on.
    reasons = [r["generated"].get("reason") for r in _records(run)
               if r["subtype"] == "coverage" and r["agent_id"] in ("main", "batch")]
    cut = [r for r in reasons if r in CUT_REASONS]
    if cut:
        return "cut", cut[-1]
    if not run.answer.is_file():
        return "incomplete", "no answer.json"
    if "run_error" in reasons:
        return "failed", "run_error"
    if "attach_failed" in reasons:
        return "failed", "attach_failed"
    attach = attach_state(run)
    if attach == "pending":
        return "attach_pending", "the run finished; its attach step has not started"
    if attach == "cut":
        return "incomplete", "the attach step started but did not finish"
    report = verify_run(run, corpus, manifest)
    return ("finished", "") if report.ok else ("failed", report.errors[0])


def attempts(runs_root: Path, key: str) -> list[RunDir]:
    pattern = re.compile(rf"^{re.escape(key)}-a(\d+)$")
    found = [(int(m.group(1)), p) for p in Path(runs_root).glob(f"{key}-a*") if (m := pattern.match(p.name))]
    return [RunDir(p) for _, p in sorted(found)]


def mark_cut(run: RunDir, reason: str, detail: dict[str, Any]) -> bool:
    """Append a coverage record saying why the run stopped. False if the chain cannot be extended."""
    if not run.events.is_file():
        return False
    try:
        broker = Broker(run, corpus=None)
    except RuntimeError as exc:  # a torn or broken chain: leave it as it is
        print(f"batch: cannot mark {run.run_id}: {exc}", flush=True)
        return False
    try:
        step = max((r["step_id"] for r in _records(run)), default=0)
        reply = broker.record({"subtype": "coverage", "step_id": step, "agent_id": "batch",
                               "used": {"raw_output_sha256": sha256_hex(b"")},
                               "generated": {"reason": reason, "detail": detail}, "status": "not_run",
                               "custom_metadata": {"origin": "batch"}})
    finally:
        broker.close()
    return bool(reply.get("ok"))


# --- the runner ----------------------------------------------------------------------------------------

class Batch:
    def __init__(self, manifest: Manifest, *, deadline: float | None, margin_s: float = 300, min_start_s: float = 900,
                 corpus: Path | None = None, python: str = sys.executable, grace_s: float = GRACE_S) -> None:
        self.manifest = manifest
        self.deadline = deadline
        self.margin_s = margin_s
        self.min_start_s = min_start_s
        self.corpus, self.corpus_manifest = manifest.corpus(corpus)
        self.python = python
        self.grace_s = grace_s
        self.child: subprocess.Popen[bytes] | None = None
        self.stopping = ""  # why the job is ending: "", deadline, sigterm

    def log(self, text: str) -> None:
        print(f"batch {utc_now()} {text}", flush=True)

    # time

    def left(self) -> float:
        return float("inf") if self.deadline is None else self.deadline - time.time()

    def _cut_at(self) -> float | None:
        return None if self.deadline is None else self.deadline - self.margin_s

    # children

    def _common(self) -> list[str]:
        d = self.manifest.data
        out = ["--corpus", str(self.corpus), "--manifest", str(self.corpus_manifest),
               "--broker", d.get("broker", "auto")]
        if d.get("base_url"):
            out += ["--base-url", d["base_url"]]
        agent_root = d.get("agent_root") or os.environ.get("AGENT_ROOT")
        if agent_root:
            out += ["--agent-root", agent_root]
        for extra in d.get("path_extra", []):
            out += ["--path-extra", extra]
        return out

    def run_argv(self, entry: Entry, run_id: str) -> list[str]:
        d = self.manifest.data
        budget = d.get("budget", {})
        argv = [self.python, "-m", "agent.cli", "run", "--concept", str(entry.concept), "--run-id", run_id,
                "--runs-root", str(self.manifest.runs_root), "--condition", entry.condition,
                "--temperature", repr(float(d["temperature"])), "--seed", str(entry.seed),
                "--sandbox", d.get("sandbox", "landlock"), *self._common()]
        for key in ("steps", "tokens"):
            if key in budget:
                argv += [f"--{key}", str(budget[key])]
        if "spawn" in d:  # row 2.12; the attach step never spawns
            argv += ["--spawn", d["spawn"]]
        return argv + self._loop_args()

    def attach_argv(self, run: RunDir) -> list[str]:
        budget = self.manifest.data.get("attach_budget", {})
        argv = [self.python, "-m", "agent.cli", "attach", str(run.root), *self._common()]
        if "sandbox" in self.manifest.data:
            argv += ["--sandbox", self.manifest.data["sandbox"]]
        for key in ("steps", "tokens"):
            if key in budget:
                argv += [f"--{key}-per-fact", str(budget[key])]
        return argv + self._loop_args()

    def _loop_args(self) -> list[str]:
        """Prompt version and conclude decoding, for the run and its attach step alike (rows 1.13)."""
        d, out = self.manifest.data, []
        if "prompt_version" in d:
            out += ["--prompt-version", d["prompt_version"]]
        if "conclude_decoding" in d:  # e.g. guided_json if the cluster's vLLM predates structured_outputs
            out += ["--conclude-decoding", d["conclude_decoding"]]
        return out

    def _child(self, argv: list[str]) -> tuple[int | None, str]:
        """Run one child; (exit code, "") or (None, why it was stopped)."""
        self.child = subprocess.Popen(argv)
        stopped = ""
        try:
            while True:
                try:
                    return self.child.wait(timeout=0.5), stopped
                except subprocess.TimeoutExpired:
                    pass
                cut_at = self._cut_at()
                if not stopped and (self.stopping or (cut_at is not None and time.time() >= cut_at)):
                    stopped = self.stopping or "deadline"
                    self.stopping = stopped
                    self.log(f"stopping child {self.child.pid} ({stopped})")
                    self.child.send_signal(signal.SIGTERM)
                    try:
                        self.child.wait(timeout=self.grace_s)
                    except subprocess.TimeoutExpired:
                        self.child.kill()
                    self.child.wait()
                    return None, stopped
        finally:
            self.child = None

    def on_sigterm(self, signum: int, frame: Any) -> None:
        """Only note it: the wait loop in _child stops the running child (once) within half a second."""
        self.stopping = "sigterm"

    # per key

    def _cut(self, run: RunDir, phase: str, why: str) -> None:
        detail = {"phase": phase, "stopped_by": why, "deadline": _iso(self.deadline)}
        if mark_cut(run, "job_time_limit", detail):
            self.log(f"{run.run_id}: cut ({why}, {phase}); marked job_time_limit, the next job reruns it")

    def _attach(self, run: RunDir) -> str:
        self.log(f"{run.run_id}: attach step")
        code, stopped = self._child(self.attach_argv(run))
        if stopped:
            self._cut(run, "attach", stopped)
            return "cut"
        state, detail = run_state(run, self.corpus, self.corpus_manifest)
        self.log(f"{run.run_id}: attach exit {code}; {state} {detail}".rstrip())
        return state

    def do_key(self, entry: Entry) -> str:
        """Bring one key to finished if time allows. Returns its state at the end."""
        max_attempts = self.manifest.data.get("max_attempts", MAX_ATTEMPTS)
        while True:
            done = attempts(self.manifest.runs_root, entry.key)
            states = [(run, *run_state(run, self.corpus, self.corpus_manifest)) for run in done]
            finished = [run for run, state, _ in states if state == "finished"]
            if finished:
                return "finished"
            if self.stopping or self.left() < self.min_start_s + self.margin_s:
                self.stopping = self.stopping or "deadline"
                return "waiting"
            for run, state, detail in states:
                if state == "incomplete" and mark_cut(run, "interrupted", {"found": detail, "by": "batch"}):
                    self.log(f"{run.run_id}: found incomplete ({detail}); marked interrupted")
            pending = [run for run, state, _ in states if state == "attach_pending"]
            if pending:
                state = self._attach(pending[-1])
                if state in ("finished", "cut"):
                    continue
                if state == "attach_pending":  # the attach step failed before it started; do not loop on it
                    mark_cut(pending[-1], "attach_failed", {"by": "batch"})
                    continue
            if len(done) >= max_attempts:
                self.log(f"{entry.key}: gave up after {len(done)} attempts")
                return "gave_up"
            run_id = f"{entry.key}-a{len(done) + 1}"
            self.log(f"{run_id}: start (seed {entry.seed}, {self.left():.0f} s left)")
            code, stopped = self._child(self.run_argv(entry, run_id))
            run = RunDir(self.manifest.runs_root / run_id)
            if stopped:
                self._cut(run, "research", stopped)
                continue  # the loop head sees self.stopping and returns
            if not run.config.is_file():  # e.g. a missing concept file: rerunning will not help
                self.log(f"{run_id}: run exit {code} and no run directory; giving up on {entry.key}")
                return "gave_up"
            state, detail = run_state(run, self.corpus, self.corpus_manifest)
            self.log(f"{run_id}: run exit {code}; {state} {detail}".rstrip())

    def run(self) -> int:
        previous = signal.signal(signal.SIGTERM, self.on_sigterm)
        try:
            plan = self.manifest.plan()
            self.log(f"{self.manifest.data['name']}: {len(plan)} runs, deadline {_iso(self.deadline) or 'none'}")
            results: dict[str, str] = {}
            for entry in plan:
                results[entry.key] = self.do_key(entry)
                if self.stopping:
                    break
            left = [e.key for e in plan if results.get(e.key) != "finished"]
            gave_up = [k for k, v in results.items() if v == "gave_up"]
            self.log(f"done: {len(plan) - len(left)}/{len(plan)} finished, {len(gave_up)} gave up"
                     + (f", stopped ({self.stopping})" if self.stopping else ""))
            if gave_up:
                return 1
            return 0 if not left else 2
        finally:
            signal.signal(signal.SIGTERM, previous)

    def status(self) -> list[dict[str, Any]]:
        """Every key with its attempts and their states, without running anything."""
        out = []
        for entry in self.manifest.plan():
            runs = attempts(self.manifest.runs_root, entry.key)
            out.append({"key": entry.key, "seed": entry.seed, "attempts": [
                {"run_id": r.run_id, "state": s, "detail": d}
                for r in runs for s, d in [run_state(r, self.corpus, self.corpus_manifest)]]})
        return out
