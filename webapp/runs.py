"""Run directories as the API shows them: summaries, steps, claims, the claim walk and the live stream.

Everything is read from the files the agent writes (agent/rundir.py layout) with the agent's own
functions: cost figures from agent.verify.stats, the check from agent.verify.verify_run, the
attach state from agent.rundir.attach_state, the graph from agent.kg, anchors from agent.anchor.
Nothing here writes into a run directory.

- `exit_status` is not a file: it is read from the records. A `job_time_limit`/`interrupted`
  coverage record (agent/batch.py) means cut; `run_error` means error; `no_final_answer` carries
  the loop's exit status (budget, context_full, ...); a model call marked `final_answer` means
  submitted. Without answer.json the run is running (live) or incomplete.
- `live`: a web-app job is working on the run, or the run has no answer.json yet (or its attach
  step has started and not finished) and events.jsonl changed within `live_window_s`, which covers
  runs the batch runner starts on the cluster.
- `qid`: the question whose picked concept ($CONCEPTS/<qid>/concept.json) has the run's concept
  hash, else the run id's prefix (`q01-claim_on-r1-a1`, the batch runner's names).
- `verify` runs agent.verify.verify_run, which re-reads the corpus files the claims cite, so its
  result is cached by the signature of the files it reads; the run list only shows cached results
  unless asked to compute them (`?verify=true`).
"""
from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from sse_starlette import ServerSentEvent

from agent import kg
from agent.anchor import Selector, resolve
from agent.batch import CUT_REASONS
from agent.canonical import file_sha256
from agent.rundir import ATTACH_FILE, RunDir, attach_state
from agent.timeline import HEAD_LINES
from agent.verify import stats, verify_run

from .corpus import Corpus
from .files import Conflict, NotFound, check_id, inside, read_json, read_jsonl, signature
from .models import (Anchor, Answer, AnswerRow, Claim, ClaimRef, ConceptBrief, Fact, FactWalk, ModelCall, Passage,
                     RunDetail, RunSummary, ScoreSummary, Step, Verification, WalkClaim)
from .settings import Settings

HEAD_BYTES = 4096
WALK_CONTEXT = 1500
QID_PREFIX = re.compile(r"^(q\d+)[-_]")


class Runs:
    """The runs root ($RUNS). `active_run(run_id)` tells whether a web-app job works on a run."""

    def __init__(self, settings: Settings, corpus: Corpus,
                 active_run: Callable[[str], bool] = lambda run_id: False) -> None:
        self.settings = settings
        self.corpus = corpus
        self.active_run = active_run
        self._verify: dict[str, tuple[tuple, Verification]] = {}
        self._concepts: tuple[tuple, dict[str, str]] | None = None
        self._lock = threading.Lock()

    @property
    def root(self) -> Path:
        return self.settings.runs

    # --- finding runs -------------------------------------------------------------------------------

    def run(self, run_id: str) -> RunDir:
        """The run directory of `run_id`; NotFound unless it has a config.json."""
        path = inside(self.root, check_id(run_id, "run"))
        if not (path / "config.json").is_file():
            raise NotFound(f"no such run: {run_id!r}")
        return RunDir(path)

    def run_dirs(self) -> list[RunDir]:
        if not self.root.is_dir():
            return []
        return [RunDir(p) for p in sorted(self.root.iterdir())
                if p.is_dir() and not p.name.startswith(".") and (p / "config.json").is_file()]

    def concept_qids(self) -> dict[str, str]:
        """concept sha256 -> question id, from the picked concepts in $CONCEPTS/<qid>/concept.json."""
        files = sorted(self.settings.concepts.glob("*/concept.json")) if self.settings.concepts.is_dir() else []
        key = tuple((f, signature(f)) for f in files)
        with self._lock:
            if self._concepts and self._concepts[0] == key:
                return self._concepts[1]
        found = {file_sha256(f): f.parent.name for f in files}
        with self._lock:
            self._concepts = (key, found)
        return found

    def qid(self, run_id: str, config: dict[str, Any], by_concept: dict[str, str] | None = None) -> str | None:
        sha = (config.get("hashes") or {}).get("concept_sha256")
        found = (by_concept if by_concept is not None else self.concept_qids()).get(sha)
        if found:
            return found
        match = QID_PREFIX.match(run_id)
        return match.group(1) if match else None

    def index(self) -> list[tuple[str, str | None, str]]:
        """(run_id, qid, condition) of every run, from config.json alone (cheap)."""
        by_concept = self.concept_qids()
        out = []
        for run in self.run_dirs():
            config = read_json(run.config) or {}
            out.append((run.run_id, self.qid(run.run_id, config, by_concept), str(config.get("condition", ""))))
        return out

    # --- state ---------------------------------------------------------------------------------------

    def attach_running(self, run: RunDir, config: dict[str, Any]) -> bool:
        return config.get("condition") == "claim_off" and "attach" in config and not (run.root / ATTACH_FILE).is_file()

    def live(self, run: RunDir, config: dict[str, Any] | None = None, records: list[dict[str, Any]] | None = None) -> bool:
        if self.active_run(run.run_id):
            return True
        config = config if config is not None else (read_json(run.config) or {})
        if run.answer.is_file() and not self.attach_running(run, config):
            return False
        records = records if records is not None else read_jsonl(run.events)
        if any(_coverage(r) in CUT_REASONS for r in records):
            return False
        try:
            return time.time() - run.events.stat().st_mtime < self.settings.live_window_s
        except OSError:
            return False

    @staticmethod
    def exit_status(run: RunDir, records: list[dict[str, Any]], live: bool) -> str:
        reasons = [_coverage(r) for r in records if r.get("subtype") == "coverage"]
        if any(r in CUT_REASONS for r in reasons):
            return "cut"
        if not run.answer.is_file():
            return "running" if live else "incomplete"
        if "run_error" in reasons:
            return "error"
        for r in records:
            if r.get("subtype") == "coverage" and _coverage(r) == "no_final_answer":
                detail = r["generated"].get("detail") or {}
                return str(detail.get("exit_status") or "no_answer") if isinstance(detail, dict) else "no_answer"
        if any(r.get("subtype") == "ai_model_invocation" and (r.get("custom_metadata") or {}).get("final_answer")
               for r in records):
            return "submitted"
        return "unknown"

    def verification(self, run: RunDir, *, compute: bool = True) -> Verification | None:
        """agent verify's result (cached by file signatures); None without a corpus or while live."""
        manifest = self.corpus.manifest
        if manifest is None or not manifest.is_file():
            return None
        key = signature(run.events, run.claims, run.answer, run.config, run.root / ATTACH_FILE, manifest)
        with self._lock:
            hit = self._verify.get(run.run_id)
        if hit and hit[0] == key:
            return hit[1]
        if not compute or self.live(run):
            return None
        report = verify_run(run, self.corpus.root, manifest)
        result = Verification(ok=report.ok, errors=report.errors, stats=report.stats)
        with self._lock:
            self._verify[run.run_id] = (key, result)
        return result

    # --- summaries and details -------------------------------------------------------------------------

    def summary(self, run: RunDir, *, verify: bool = False, by_concept: dict[str, str] | None = None) -> RunSummary:
        config = read_json(run.config) or {}
        records = read_jsonl(run.events)
        live = self.live(run, config, records)
        cost = stats(records)
        answer = read_json(run.answer) if run.answer.is_file() else None
        rows = answer.get("rows") if isinstance(answer, dict) else None
        check = self.verification(run, compute=verify)
        sampling = config.get("sampling") or {}
        try:
            attach = attach_state(run)
        except (OSError, ValueError, KeyError):
            attach = "not_applicable"
        return RunSummary(
            run_id=run.run_id, qid=self.qid(run.run_id, config, by_concept), condition=str(config.get("condition", "")),
            seed=sampling.get("seed"), temperature=sampling.get("temperature"), created_at=config.get("created_at"),
            exit_status=self.exit_status(run, records, live), steps=cost["steps"], model_calls=cost["model_calls"],
            tokens=cost["tokens"], seconds=cost["seconds"],
            tokens_without_attach=cost["without_attach"]["tokens"] if "without_attach" in cost else None,
            seconds_without_attach=cost["without_attach"]["seconds"] if "without_attach" in cost else None,
            rows=len(rows) if isinstance(rows, list) else None,
            facts=sum(len(r.get("facts", [])) for r in rows) if isinstance(rows, list) else None,
            claims_accepted=cost["claims_accepted"], claims_rejected=cost["claims_rejected"], attach=attach,
            verify="unknown" if check is None else ("ok" if check.ok else "failed"),
            score=score_summary(read_json(run.root / "score.json")), live=live)

    def summaries(self, qid: str | None = None, condition: str | None = None, verify: bool = False) -> list[RunSummary]:
        by_concept = self.concept_qids()
        out = []
        for run in self.run_dirs():
            config = read_json(run.config) or {}
            if condition and config.get("condition") != condition:
                continue
            if qid and self.qid(run.run_id, config, by_concept) != qid:
                continue
            out.append(self.summary(run, verify=verify, by_concept=by_concept))
        return out

    def detail(self, run_id: str) -> RunDetail:
        run = self.run(run_id)
        summary = self.summary(run, verify=True)
        concept = read_json(run.concept)
        answer = read_json(run.answer) if run.answer.is_file() else None
        return RunDetail(summary=summary, config=read_json(run.config) or {},
                         concept=ConceptBrief.model_validate(concept) if isinstance(concept, dict) else None,
                         answer=Answer.model_validate(answer) if isinstance(answer, dict) else None,
                         verify=self.verification(run, compute=False))

    # --- steps, claims, graph ----------------------------------------------------------------------------

    def steps(self, run_id: str) -> list[Step]:
        run = self.run(run_id)
        return steps_of(run, read_jsonl(run.events))

    def output_file(self, run_id: str, step: int, agent_id: str | None = None) -> Path:
        """The full output of the step's command (out/step-NNNN.txt), from the agent_tool record."""
        run = self.run(run_id)
        for r in read_jsonl(run.events):
            if r.get("subtype") == "agent_tool" and r.get("step_id") == step and agent_id in (None, r.get("agent_id")):
                name = r["generated"].get("output_file")
                if name:
                    path = inside(run.root, name)
                    if path.is_file():
                        return path
                raise NotFound(f"step {step} of {run_id} has no output file")
        raise NotFound(f"step {step} of {run_id} ran no command")

    def claims(self, run_id: str) -> list[Claim]:
        run = self.run(run_id)
        return [claim_of(r) for r in read_jsonl(run.claims)]

    def graph(self, run_id: str) -> dict[str, Any]:
        """graph.json as written; for a run without one (still live), built in memory (agent.kg)."""
        run = self.run(run_id)
        data = read_json(run.root / kg.GRAPH_FILE)
        if isinstance(data, dict):
            return data
        manifest = self.corpus.manifest
        if manifest is None or not manifest.is_file():
            raise NotFound(f"{run_id} has no graph.json (and no corpus manifest to build one)")
        try:
            return kg.build(run, manifest)
        except (ValueError, KeyError, OSError) as exc:
            raise Conflict(f"cannot build the graph of {run_id}: {exc}") from exc

    def score(self, run_id: str) -> dict[str, Any]:
        data = read_json(self.run(run_id).root / "score.json")
        if not isinstance(data, dict):
            raise NotFound(f"{run_id} has no score.json yet")
        return data

    # --- the claim walk ----------------------------------------------------------------------------------

    def walk(self, run_id: str, fact_id: str) -> FactWalk:
        """Fact -> its claims -> the step each was sent from -> the passage, highlighted (no verdicts)."""
        run = self.run(run_id)
        answer = read_json(run.answer)
        if not isinstance(answer, dict):
            raise NotFound(f"{run_id} has no answer.json yet")
        found = [(row, fact) for row in answer.get("rows", []) for fact in row.get("facts", [])
                 if fact.get("id") == fact_id]
        if not found:
            raise NotFound(f"{run_id} has no fact {fact_id!r}")
        row, fact = found[0]
        records = read_jsonl(run.events)
        by_step = {(s.agent_id, s.step): s for s in steps_of(run, records)}
        accepted = {r["generated"].get("claim_id"): r for r in records
                    if r.get("subtype") == "claim" and r.get("status") == "accepted"}
        items = []
        for claim_id in fact.get("claims", []):
            record = accepted.get(claim_id)
            if record is None:
                items.append(WalkClaim(claim_id=claim_id, claim=None, step=None, passage=None, anchor_status="missing"))
                continue
            passage, status = self._passage(record["used"].get("anchor") or {})
            items.append(WalkClaim(claim_id=claim_id, claim=claim_of(record),
                                   step=by_step.get((record["agent_id"], record["step_id"])),
                                   passage=passage, anchor_status=status))
        return FactWalk(run_id=run.run_id, fact=Fact.model_validate(fact), row_id=row["id"],
                        row=AnswerRow.model_validate(row), claims=items, support=None)

    def _passage(self, anchor: dict[str, Any]) -> tuple[Passage | None, str]:
        """(passage around the anchor as it resolves in today's corpus, resolution status)."""
        if self.corpus.root is None:
            return None, "unknown"
        try:
            selector = Selector(**anchor)
            paper = self.corpus.paper_id(Path(selector.file).name)
            text = self.corpus.text(paper)
        except (TypeError, NotFound):
            return None, "broken"
        result = resolve(selector, text, self.corpus.manifest_hash(paper) or "")
        if result.selector is None:
            return None, result.status
        return self.corpus.passage(paper, result.selector.start, result.selector.end, WALK_CONTEXT), result.status

    # --- live stream ---------------------------------------------------------------------------------

    def exists_or_pending(self, run_id: str) -> Path:
        """The run's directory; a run a job is about to create may not exist yet."""
        path = inside(self.root, check_id(run_id, "run"))
        if not (path / "config.json").is_file() and not self.active_run(run_id):
            raise NotFound(f"no such run: {run_id!r}")
        return path

    async def stream(self, run_id: str, after: int = 0) -> AsyncIterator[ServerSentEvent]:
        """`record` per events.jsonl line (id = line number) as it is appended, then `done`.

        Done when the run is no longer live: answer.json written (and no attach step or web-app
        job still at work on it), cut, or left incomplete. `after` skips lines already seen (the
        browser's Last-Event-ID on reconnect).
        """
        run = RunDir(self.exists_or_pending(run_id))
        offset, line_no, pending = 0, 0, b""
        while True:
            # Look at the state before reading: every record written before the end is then read.
            # A run a job was to create but never did (the run failed to start) ends with the job.
            finished = not self.live(run) if run.config.is_file() else not self.active_run(run.run_id)
            try:
                with open(run.events, "rb") as fh:
                    fh.seek(offset)
                    chunk = fh.read()
            except OSError:
                chunk = b""
            offset += len(chunk)
            *lines, pending = (pending + chunk).split(b"\n")
            for raw in lines:
                line_no += 1
                if line_no > after and raw.strip():
                    yield ServerSentEvent(raw.decode("utf-8", errors="replace"), event="record", id=str(line_no))
            if finished:
                records = read_jsonl(run.events)
                yield ServerSentEvent(json.dumps({"run_id": run.run_id, "records": line_no,
                                                  "exit_status": self.exit_status(run, records, False)}), event="done")
                return
            await asyncio.sleep(self.settings.poll_s)


# --- record helpers ----------------------------------------------------------------------------------------

def _coverage(record: dict[str, Any]) -> str | None:
    return (record.get("generated") or {}).get("reason") if record.get("subtype") == "coverage" else None


def score_summary(score: Any) -> ScoreSummary | None:
    """support_share, row F1 and fact F1 from score.json; fact F1 is the soft (judged) match,
    else the normalised, else the strict one, whichever the file has."""
    if not isinstance(score, dict):
        return None
    facts = score.get("facts") or {}
    fact_f1 = next(((facts.get(k) or {}).get("f1") for k in ("soft", "normalised", "strict")
                    if (facts.get(k) or {}).get("f1") is not None), None)
    return ScoreSummary(support_share=(score.get("support") or {}).get("support_share"), fact_f1=fact_f1,
                        row_f1=(score.get("rows") or {}).get("f1"))


def paper_of(file: str | None) -> str | None:
    if not file:
        return None
    name = Path(str(file).replace("\\", "/")).name
    return name[:-3] if name.endswith(".md") else name


def claim_of(record: dict[str, Any]) -> Claim:
    meta, used = record.get("custom_metadata") or {}, record.get("used") or {}
    accepted = record.get("status") == "accepted"
    anchor = used.get("anchor") if accepted else None
    file = anchor["file"] if anchor else used.get("file")
    return Claim(claim_id=(record.get("generated") or {}).get("claim_id"), task_id=record["task_id"],
                 status="accepted" if accepted else "rejected", reason=meta.get("reason"),
                 s=meta.get("s"), p=meta.get("p"), o=meta.get("o"), file=file, paper_id=paper_of(file),
                 quote=anchor["exact"] if anchor else (meta.get("quote") or used.get("quote")),
                 quote_submitted=meta.get("quote"), step=record["step_id"], agent_id=record["agent_id"],
                 origin=meta.get("origin", "research"),
                 anchor=Anchor(start=anchor["start"], end=anchor["end"]) if anchor else None)


def output_head(run: RunDir, name: str | None) -> str | None:
    """The first HEAD_LINES lines (at most HEAD_BYTES) of a command's output file."""
    if not name:
        return None
    try:
        with open(inside(run.root, name), "rb") as fh:
            data = fh.read(HEAD_BYTES)
    except (OSError, NotFound):
        return None
    return "\n".join(data.decode("utf-8", errors="replace").splitlines()[:HEAD_LINES])


def steps_of(run: RunDir, records: list[dict[str, Any]]) -> list[Step]:
    """One Step per (agent, step id), in chain order: its model call, command, claims, coverage, spawns."""
    steps: dict[tuple[str, int], dict[str, Any]] = {}
    for r in records:
        key = (r.get("agent_id") or "main", int(r.get("step_id", 0)))
        meta, used, gen = r.get("custom_metadata") or {}, r.get("used") or {}, r.get("generated") or {}
        step = steps.setdefault(key, {"step": key[1], "agent_id": key[0], "origin": meta.get("origin", "research"),
                                      "claims": [], "coverage": [], "spawned": [], "times": []})
        step["times"] += [t for t in (r.get("started_at"), r.get("ended_at")) if t]
        if meta.get("fact_id"):
            step["fact_id"] = meta["fact_id"]
        kind = r.get("subtype")
        if kind == "ai_model_invocation":
            usage = gen.get("usage") or {}
            step["phase"] = meta.get("phase")
            step["model_call"] = ModelCall(
                task_id=r["task_id"], status=r.get("status", "finished"), tokens=usage.get("total_tokens"),
                prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
                seconds=meta.get("seconds"), parse=gen.get("parse"), reply=gen.get("reply"),
                finish_reason=gen.get("finish_reason"), final_answer=bool(meta.get("final_answer")),
                error=gen.get("error"))
        elif kind == "agent_tool":
            step.update(command=used.get("command"), exit_code=gen.get("exit_code"),
                        timed_out=bool(gen.get("timed_out")), output_bytes=gen.get("output_bytes"),
                        output_file=gen.get("output_file"), output_head=output_head(run, gen.get("output_file")),
                        repeat=meta.get("repeat"))
            step.setdefault("phase", meta.get("phase"))
        elif kind == "claim":
            step["claims"].append(ClaimRef(claim_id=gen.get("claim_id"), status="accepted" if r.get("status") == "accepted"
                                           else "rejected", reason=meta.get("reason"), s=meta.get("s"),
                                           p=meta.get("p"), o=meta.get("o")))
        elif kind == "coverage":
            step["coverage"].append(str(gen.get("reason")))
        elif kind == "spawn" and isinstance(gen.get("agent_id"), str):
            step["spawned"].append(gen["agent_id"])
    out = []
    for step in steps.values():
        times = step.pop("times")
        out.append(Step(**step, started_at=min(times, default=None), ended_at=max(times, default=None)))
    return out
