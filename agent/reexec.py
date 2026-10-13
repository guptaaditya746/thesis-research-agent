"""Re-execution (milestones-1-2.md row 2.13, test C5): run a run's recorded commands again and compare outputs.

`agent reexec <run> [--steps 1,2]` takes the run's `agent_tool` records in chain order (every agent
and origin, or only the given step ids) and runs each recorded command again
- in one fresh, empty scratch directory for the whole sequence, so a file an earlier command wrote
  is there for a later one, as it was in the run;
- with the run's sandbox mode, agent root and command limits (config.json), and the run's `claim`
  setting: on for claim_on runs and for the attach step's commands (origin attach), off otherwise;
- against the frozen corpus: its manifest must be the one in config.json, and the corpus files the
  commands name must still match it.

`claim` calls go to a dry broker: the same request checks and anchor search as the run's broker
(agent/broker.py) and the same reply, with claim ids numbered on from the claims the run had
accepted before that command, so a command that claims prints byte for byte what it printed in the
run when the verdicts are the same. Its records go only to <run>/reexec.jsonl, each with the
claim the run recorded at that place; nothing is appended to the run's chain, and the run's own
files are only read.

Each new output's sha256 is compared with the recorded `output_sha256`. <run>/reexec.json holds
{steps, identical, differing: [{step, recorded, now, first_diff_line, ...}], errors, claims}; the
new output of each differing command is kept in <run>/reexec/ to look at.

Differences to expect: output that depends on time, randomness, process ids or the scratch path
(`date`, `$RANDOM`, `pwd`), and with `--steps` a command that reads a file a skipped command wrote.
In mode unsandboxed (tests only) a command can also reach the run's own scratch directory by its
absolute path; Landlock allows only the fresh one.
"""
from __future__ import annotations

import json
import re
import shutil
import socket
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from . import sandbox
from .anchor import AnchorError, find
from .broker import Broker, Channel, Corpus, Rejected, serve_claims
from .canonical import canonical_bytes, file_sha256, sha256_hex, write_json
from .chain import verify
from .rundir import COMMAND_LIMITS, RunDir, utc_now

REEXEC_FILE = "reexec.json"
CLAIMS_FILE = "reexec.jsonl"
OUT_DIR = "reexec"
SHOWN = 200  # characters of a differing line kept in reexec.json


class ReexecError(RuntimeError):
    pass


def parse_steps(text: str) -> list[int]:
    """'1,2,5-7' -> [1, 2, 5, 6, 7]."""
    steps: set[int] = set()
    for part in filter(None, (p.strip() for p in text.split(","))):
        match = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not match:
            raise ValueError(f"--steps: {part!r} is not a step id or a range like 3-5")
        first, last = int(match.group(1)), int(match.group(2) or match.group(1))
        steps.update(range(first, last + 1))
    return sorted(steps)


class DryBroker:
    """The broker's claim check without its log: verdicts go to reexec.jsonl only (serve_claims calls claim())."""

    def __init__(self, corpus: Corpus, log: BinaryIO, recorded: dict[tuple[int, str], list[dict[str, Any]]]) -> None:
        self.corpus = corpus
        self.log = log
        self.recorded = recorded  # the run's claim records per (step, agent), in chain order
        self.next_claim = 1
        self.sent: dict[tuple[int, str], int] = {}
        self.counts = {"sent": 0, "accepted": 0, "rejected": 0, "same_as_recorded": 0}
        self._lock = threading.Lock()

    def claim(self, channel: Channel, raw: bytes) -> dict[str, Any]:
        meta: dict[str, Any] = {}
        anchor = None
        try:
            request = Broker._parse(raw, meta)
            name = self.corpus.name(request["file"])
            anchor = find(self.corpus.index(name), request["quote"], file=name).json()
            status, reason = "accepted", None
        except (Rejected, AnchorError) as exc:
            status, reason = "rejected", exc.reason
        with self._lock:
            claim_id = None
            if status == "accepted":
                claim_id = f"claim-{self.next_claim:06d}"
                self.next_claim += 1
            key = (channel.step_id, channel.agent_id)
            n = self.sent.get(key, 0)
            self.sent[key] = n + 1
            old = self.recorded.get(key, [])[n] if n < len(self.recorded.get(key, [])) else None
            recorded = None if old is None else {
                "status": old["status"], "claim_id": old["generated"].get("claim_id"),
                "reason": old["custom_metadata"].get("reason"), "request_sha256": old["custom_metadata"].get("request_sha256")}
            same = recorded == {"status": status, "claim_id": claim_id, "reason": reason,
                                "request_sha256": meta.get("request_sha256")}
            self.counts["sent"] += 1
            self.counts[status] += 1
            self.counts["same_as_recorded"] += same
            self.log.write(canonical_bytes({
                "step_id": channel.step_id, "agent_id": channel.agent_id, "origin": channel.origin,
                "request_sha256": meta.get("request_sha256"), "status": status, "reason": reason,
                "claim_id": claim_id, "anchor": anchor, "recorded": recorded, "same_as_recorded": same}) + b"\n")
            self.log.flush()
        return {"ok": True, "claim_id": claim_id} if claim_id else {"ok": False, "reason": reason}


@dataclass(frozen=True)
class _Dirs:
    """What SandboxEnvironment reads of a run directory: the run's out/ (read-only) and a fresh scratch."""
    out: Path
    scratch: Path


def first_diff(recorded: bytes, now: bytes) -> tuple[int, str, str]:
    """(1-based line number, recorded line, new line) of the first line that differs."""
    a, b = recorded.splitlines(keepends=True), now.splitlines(keepends=True)
    for i in range(max(len(a), len(b))):
        x, y = (a[i] if i < len(a) else b""), (b[i] if i < len(b) else b"")
        if x != y:
            return i + 1, x.decode("utf-8", errors="replace")[:SHOWN], y.decode("utf-8", errors="replace")[:SHOWN]
    return max(len(a), len(b)), "", ""


def _records(run: RunDir) -> list[dict[str, Any]]:
    out = []
    for raw in run.events.read_bytes().splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            break  # a torn last line; the chain check reports it
    return out


def _claims_before(records: list[dict[str, Any]]) -> dict[str, int]:
    """Per agent_tool task id: the accepted claims the run's broker had counted before the command's first claim."""
    out, accepted = {}, 0
    own: dict[tuple[int, str], int] = {}
    for r in records:
        if r["subtype"] == "claim" and r["status"] == "accepted":
            accepted += 1
            key = (r["step_id"], r["agent_id"])
            own[key] = own.get(key, 0) + 1
        elif r["subtype"] == "agent_tool":
            out[r["task_id"]] = accepted - own.pop((r["step_id"], r["agent_id"]), 0)
    return out


def _execute(env: Any, command: str, *, step: int, agent_id: str, origin: str, dry: DryBroker | None,
             scratch: Path, timeout_s: int) -> sandbox.Result:
    """One command, as SandboxEnvironment.execute runs it, with the dry broker on the claim channel."""
    sock = thread = None
    if dry is not None:
        broker_end, sock = socket.socketpair()
        thread = threading.Thread(target=serve_claims, args=(dry, broker_end, Channel(step, agent_id, origin)),
                                  daemon=True)
        thread.start()
    fds = (sock.fileno(),) if sock else ()
    try:
        return sandbox.run_command(env.argv(command), env=env.environment(fds[0] if fds else None), cwd=str(scratch),
                                   timeout_s=timeout_s, pass_fds=fds, before_wait=sock.close if sock else None)
    finally:
        if sock:
            sock.close()
        if thread:
            thread.join(timeout=60)  # every claim answered and logged before the next command


def reexec_run(run_dir: Path, corpus: Path, manifest: Path, *, steps: list[int] | None = None,
               sandbox_mode: str | None = None, agent_root: Path | None = None, extra_path: tuple[str, ...] = (),
               keep_scratch: bool = False, python: str = sys.executable) -> dict[str, Any]:
    """Re-execute the run's commands (or those at `steps`); write and return reexec.json's content."""
    from .loop import SandboxEnvironment  # imports LiteLLM and mini-swe-agent: slow, so only here

    run = RunDir(Path(run_dir))
    config = run.load_config()
    if file_sha256(manifest) != config["hashes"]["corpus_manifest_sha256"]:
        raise ReexecError(f"{manifest} is not the corpus manifest the run used (config.json hashes)")
    sandbox_mode = sandbox_mode or config.get("sandbox", {}).get("mode", "landlock")
    if sandbox_mode == "landlock" and sandbox.landlock_abi() is None:
        raise ReexecError("Landlock is not available here; pass sandbox mode 'unsandboxed' explicitly")
    if agent_root is None and config.get("sandbox", {}).get("agent_root"):
        agent_root = Path(config["sandbox"]["agent_root"])
    limits = {**COMMAND_LIMITS, **config.get("command_limits", {})}

    errors = [f"chain: {e}" for e in verify(run.events, run.claims).errors]
    records = _records(run)
    tools = [r for r in records if r["subtype"] == "agent_tool"]
    if steps is not None:
        errors += [f"step {s}: the run recorded no command at this step" for s in steps
                   if s not in {t["step_id"] for t in tools}]
        tools = [t for t in tools if t["step_id"] in steps]
    corpus_index = Corpus(corpus, manifest)
    for name in sorted({f for t in tools for f in t["used"].get("files_read", [])}):
        if name not in corpus_index.hashes:
            continue  # a name the command mentions that is not a corpus file
        path = Path(corpus) / name
        if not path.is_file() or file_sha256(path) != corpus_index.hashes[name]:
            errors.append(f"corpus: {name} differs from the manifest (the corpus is not the frozen one)")
    recorded: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for r in records:
        if r["subtype"] == "claim":
            recorded.setdefault((r["step_id"], r["agent_id"]), []).append(r)
    before = _claims_before(records)

    claim_on = config["condition"] == "claim_on"
    scratch = Path(tempfile.mkdtemp(prefix=f"reexec-{run.run_id}-"))
    envs: dict[bool, Any] = {}  # one sandbox environment per claim setting
    out_dir = run.root / OUT_DIR
    shutil.rmtree(out_dir, ignore_errors=True)  # only this re-execution's differing outputs are kept
    report: dict[str, Any] = {
        "schema_version": 1, "run_id": run.run_id, "started_at": utc_now(), "ended_at": None,
        "sandbox": sandbox_mode, "agent_root": str(agent_root) if agent_root else None,
        "corpus_manifest_sha256": config["hashes"]["corpus_manifest_sha256"], "selected_steps": steps,
        "scratch": str(scratch) if keep_scratch else None, "steps": 0, "identical": 0, "identical_steps": [],
        "differing": [], "claims": {}, "errors": errors}
    with open(run.root / CLAIMS_FILE, "wb") as log:
        dry = DryBroker(corpus_index, log, recorded)
        try:
            for record in tools:
                origin = (record.get("custom_metadata") or {}).get("origin", "research")
                claim = claim_on or origin == "attach"
                if claim not in envs:
                    envs[claim] = SandboxEnvironment(
                        _Dirs(run.out, scratch), corpus=corpus, mode=sandbox_mode, claim=claim,  # type: ignore[arg-type]
                        agent_root=agent_root, limits=limits, extra_path=extra_path, python=python)
                env = envs[claim]
                dry.next_claim = before.get(record["task_id"], 0) + 1
                _compare(run, record, _execute(env, record["used"]["command"], step=record["step_id"],
                                               agent_id=record["agent_id"], origin=origin, dry=dry if claim else None,
                                               scratch=scratch, timeout_s=int(limits["timeout_s"])), out_dir, report)
        finally:
            if not keep_scratch:
                shutil.rmtree(scratch, ignore_errors=True)
        report["claims"] = dict(dry.counts)
    report["ended_at"] = utc_now()
    write_json(run.root / REEXEC_FILE, report)
    return report


def _compare(run: RunDir, record: dict[str, Any], result: sandbox.Result, out_dir: Path, report: dict[str, Any]) -> None:
    generated = record["generated"]
    step = record["step_id"]
    now = sha256_hex(result.output)
    report["steps"] += 1
    if now == generated.get("output_sha256"):
        report["identical"] += 1
        report["identical_steps"].append(step)
        return
    path = run.root / str(generated.get("output_file"))
    old = path.read_bytes() if path.is_file() else b""
    if not path.is_file() or sha256_hex(old) != generated.get("output_sha256"):
        report["errors"].append(f"step {step}: {generated.get('output_file')} is missing or not the recorded output")
    line, was, is_now = first_diff(old, result.output)
    out_dir.mkdir(exist_ok=True)
    kept = out_dir / Path(str(generated.get("output_file") or f"step-{step:04d}.txt")).name
    kept.write_bytes(result.output)
    report["differing"].append({
        "step": step, "agent_id": record["agent_id"], "command": record["used"]["command"][:500],
        "recorded": generated.get("output_sha256"), "now": now, "first_diff_line": line,
        "recorded_line": was.rstrip("\n"), "now_line": is_now.rstrip("\n"),
        "exit_code": {"recorded": generated.get("exit_code"), "now": result.exit_code},
        "output_file": kept.relative_to(run.root).as_posix()})
