"""Run directories as the API shows them: summaries, steps, claims, the claim walk and the live stream.

Everything is read from the files the agent writes (agent/rundir.py layout) with the agent's own
functions: cost figures from agent.verify.stats, the check from agent.verify.verify_run, the
attach state from agent.rundir.attach_state, the graph from agent.kg, anchors from agent.anchor.
Nothing here writes into a run directory.

- Which runs: every directory with a config.json directly in $RUNS, and one level down, in the
  batch roots the batch runner writes ($RUNS/<manifest name>/<key>-aN) and in $RUNS/web/ (the web
  app's own runs). A run one level down has the id `<batch>~<name>`, since batch runs of two
  manifests (e2e-smoke, m4-72) share names.
- `exit_status`: how the research run ended, by scoring's rules (scoring/run_score.py, so the API and
  score.json agree), from the records of the research run (attach records left out): a
  `job_time_limit`/`interrupted` coverage record (agent/batch.py) means cut; `run_error` means error;
  `no_final_answer` and `answer_from_draft` (WP A: the harness took the agent's draft) carry the
  loop's exit status (budget, context_full, ...); a model call marked `final_answer` means submitted;
  else trajectory.json's info.exit_status (mini-swe-agent's own). Without answer.json the run is
  running (live) or incomplete. `answer_from` says whose answer answer.json is: final, draft or none.
- `live`: the agent is still writing the run. For a run a web-app job works on, the job knows (its
  `run` or `attach` step is pending or running); `post_processing` is the job's later steps (verify
  ... score) on a finished run. Any other run is live while it has no answer.json (or its attach
  step has started and not finished), is not cut, and events.jsonl changed within `live_window_s`,
  which covers runs the batch runner starts on the cluster.
- `qid` and `concept_current`: every concept a question has had picked (the `concept_pick` records
  of $CONCEPTS/<qid>/events.jsonl, replaced picks included) maps to that question; a run whose
  concept is none of them gets its question from its name's prefix (`q01-claim_on-r1-a1`). The run
  is current when its concept is the question's current concept.json; runs on a replaced (or
  another) concept are listed with concept_current false and left out of the question's counts
  and of `?qid=` unless asked for, so they never sit next to runs on the current pick.
- `verify` runs agent.verify.verify_run, which re-reads the corpus files the claims cite, so its
  result is cached by the signature of the files it reads; the run list only shows cached results
  unless asked to compute them (`?verify=true`). What a summary needs from events.jsonl (a
  Digest) is cached too, until the file changes, so listing many runs reads each log once.
"""
from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

from sse_starlette import ServerSentEvent

from agent import kg
from agent.anchor import Selector, resolve
from agent.batch import CUT_REASONS
from agent.canonical import file_sha256
from agent.rundir import ATTACH_FILE, RunDir, attach_state
from agent.timeline import HEAD_LINES
from agent.verify import stats, verify_run

from . import judge
from .corpus import Corpus
from .files import ID, RUN_SEP, Conflict, NotFound, inside, read_json, read_jsonl, run_parts, signature
from .jobs import STEP_ACTIVE
from .models import (Anchor, Answer, AnswerRow, Claim, ClaimRef, ConceptBrief, Fact, FactWalk, ModelCall, Passage,
                     RunDetail, RunSummary, ScoreSummary, Step, Verification, WalkClaim)
from .settings import Settings

HEAD_BYTES = 4096
WALK_CONTEXT = 1500
QID_PREFIX = re.compile(r"^(q\d+)[-_]")
REPORT_DIR = "report"  # score batch's output in a runs root, not a batch
WRITERS = ("run", "attach")  # the job steps that write into the run directory
DRAFTED = {"no_final_answer": "none", "answer_from_draft": "draft"}  # coverage reason -> answer_from


@dataclass(frozen=True)
class Digest:
    """What a run summary needs from events.jsonl: small enough to cache for every run."""

    cost: dict[str, Any]  # agent.verify.stats
    reasons: tuple[str, ...]  # coverage reasons, in chain order
    research: tuple[str, ...]  # the same without the attach step's (scoring's exit_status rules)
    loop_exit: str | None  # the exit status a no_final_answer / answer_from_draft record carries
    answer_from: str | None  # final, draft, none
    final_answer: bool  # a model call's reply became answer.json

    @property
    def cut(self) -> bool:
        return any(r in CUT_REASONS for r in self.reasons)

    @classmethod
    def of(cls, records: list[dict[str, Any]]) -> Digest:
        reasons, research, loop_exit, answer_from = [], [], None, None
        for r in records:
            if r.get("subtype") != "coverage":
                continue
            reason = str(_coverage(r))
            reasons.append(reason)
            if (r.get("custom_metadata") or {}).get("origin") == "attach":
                continue
            research.append(reason)
            if reason in DRAFTED and loop_exit is None:
                detail = r["generated"].get("detail")
                loop_exit = str((detail if isinstance(detail, dict) else {}).get("exit_status") or "no_answer")
                answer_from = DRAFTED[reason]
        final = any(r.get("subtype") == "ai_model_invocation" and (r.get("custom_metadata") or {}).get("final_answer")
                    for r in records)
        return cls(stats(records), tuple(reasons), tuple(research), loop_exit,
                   answer_from or ("final" if final else None), final)


@dataclass(frozen=True)
class ConceptIndex:
    """Picked concepts: every concept sha256 a question has had picked -> qid, and each question's current one."""

    by_sha: dict[str, str] = field(default_factory=dict)
    current: dict[str, str] = field(default_factory=dict)


class Indexed(NamedTuple):
    run_id: str
    qid: str | None
    condition: str
    current: bool | None


class Runs:
    """The runs root ($RUNS). `job_steps(run_id)` gives {step: state} of the web-app job working on a
    run (None when no job is), from webapp/jobs.py."""

    def __init__(self, settings: Settings, corpus: Corpus,
                 job_steps: Callable[[str], dict[str, str] | None] = lambda run_id: None) -> None:
        self.settings = settings
        self.corpus = corpus
        self.job_steps = job_steps
        self._verify: dict[str, tuple[tuple, Verification]] = {}
        self._digests: dict[str, tuple[tuple, Digest]] = {}
        self._trajectory: dict[str, tuple[tuple, str | None]] = {}
        self._concepts: tuple[tuple, ConceptIndex] | None = None
        self._lock = threading.Lock()

    @property
    def root(self) -> Path:
        return self.settings.runs

    # --- finding runs -------------------------------------------------------------------------------

    def key(self, run: RunDir) -> str:
        """The API's id of a run: its directory below $RUNS, `batch~name` one level down."""
        try:
            return RUN_SEP.join(run.root.relative_to(self.root).parts)
        except ValueError:
            return run.run_id

    def run(self, run_id: str) -> RunDir:
        """The run directory of `run_id`; NotFound unless it has a config.json."""
        path = inside(self.root, *run_parts(run_id))
        if not (path / "config.json").is_file():
            raise NotFound(f"no such run: {run_id!r}")
        return RunDir(path)

    def run_dirs(self) -> list[RunDir]:
        """Runs directly in $RUNS, then those one level down (batch roots, web/), each sorted by name."""
        if not self.root.is_dir():
            return []
        top, nested = [], []
        for p in sorted(self.root.iterdir()):
            if not p.is_dir() or p.name.startswith(".") or p.name == REPORT_DIR or not ID.fullmatch(p.name):
                continue
            if (p / "config.json").is_file():
                top.append(RunDir(p))
                continue
            nested += [RunDir(q) for q in sorted(p.iterdir())
                       if q.is_dir() and ID.fullmatch(q.name) and (q / "config.json").is_file()]
        return top + nested

    def batch(self, run: RunDir) -> str | None:
        parts = self.key(run).split(RUN_SEP)
        return parts[0] if len(parts) == 2 else None

    def concept_index(self) -> ConceptIndex:
        """Every picked concept of $CONCEPTS/<qid>/ (from its pick records) and each question's current one."""
        files = sorted(self.settings.concepts.glob("*/concept.json")) if self.settings.concepts.is_dir() else []
        key = tuple((f, signature(f, f.parent / "events.jsonl")) for f in files)
        with self._lock:
            if self._concepts and self._concepts[0] == key:
                return self._concepts[1]
        index = ConceptIndex()
        for f in files:
            qid = f.parent.name
            for r in read_jsonl(f.parent / "events.jsonl"):
                if r.get("subtype") == "concept_pick":
                    for sha in ((r.get("generated") or {}).get("concept_sha256"),
                                (r.get("used") or {}).get("replaces_concept_sha256")):
                        if sha:
                            index.by_sha.setdefault(sha, qid)
        for f in files:  # a question's current concept is that question's, whatever an older pick said
            index.current[f.parent.name] = sha = file_sha256(f)
            index.by_sha[sha] = f.parent.name
        with self._lock:
            self._concepts = (key, index)
        return index

    def question_of(self, run: RunDir, config: dict[str, Any],
                    index: ConceptIndex | None = None) -> tuple[str | None, bool | None]:
        """(qid, concept_current) of a run: by its concept's hash, else by its name's prefix."""
        index = index or self.concept_index()
        sha = (config.get("hashes") or {}).get("concept_sha256")
        qid = index.by_sha.get(sha)
        if qid is None:
            match = QID_PREFIX.match(run.root.name)
            qid = match.group(1) if match else None
        if qid is None or qid not in index.current:
            return qid, None
        return qid, index.current[qid] == sha

    def index(self) -> list[Indexed]:
        """(run_id, qid, condition, concept_current) of every run, from config.json alone (cheap)."""
        concepts = self.concept_index()
        out = []
        for run in self.run_dirs():
            config = read_json(run.config) or {}
            qid, current = self.question_of(run, config, concepts)
            out.append(Indexed(self.key(run), qid, str(config.get("condition", "")), current))
        return out

    # --- state ---------------------------------------------------------------------------------------

    def digest(self, run: RunDir) -> Digest:
        """What the summary needs from events.jsonl, cached until the file changes."""
        key, sig = self.key(run), signature(run.events)
        with self._lock:
            hit = self._digests.get(key)
        if hit and hit[0] == sig:
            return hit[1]
        found = Digest.of(read_jsonl(run.events))
        with self._lock:
            self._digests[key] = (sig, found)
        return found

    def trajectory_exit(self, run: RunDir) -> str | None:
        """mini-swe-agent's info.exit_status in trajectory.json (cached: the file holds every message)."""
        path, key = run.root / "trajectory.json", self.key(run)
        sig = signature(path)
        with self._lock:
            hit = self._trajectory.get(key)
        if hit and hit[0] == sig:
            return hit[1]
        data = read_json(path)
        info = data.get("info") if isinstance(data, dict) else None
        found = str(info["exit_status"]) if isinstance(info, dict) and info.get("exit_status") else None
        with self._lock:
            self._trajectory[key] = (sig, found)
        return found

    def attach_running(self, run: RunDir, config: dict[str, Any]) -> bool:
        return config.get("condition") == "claim_off" and "attach" in config and not (run.root / ATTACH_FILE).is_file()

    def live(self, run: RunDir, config: dict[str, Any] | None = None) -> bool:
        steps = self.job_steps(self.key(run))
        if steps is not None:  # a web-app job works on the run: it knows whether the agent still writes it
            return any(steps.get(name) in STEP_ACTIVE for name in WRITERS)
        config = config if config is not None else (read_json(run.config) or {})
        if run.answer.is_file() and not self.attach_running(run, config):
            return False
        if self.digest(run).cut:
            return False
        try:
            return time.time() - run.events.stat().st_mtime < self.settings.live_window_s
        except OSError:
            return False

    def live_elsewhere(self) -> list[str]:
        """Runs being written that no web-app job works on: a batch on the cluster."""
        return [self.key(run) for run in self.run_dirs() if self.job_steps(self.key(run)) is None and self.live(run)]

    @staticmethod
    def exit_status(run: RunDir, digest: Digest, live: bool) -> str:
        """From the records (scoring's rules); `unknown` when they do not tell (see status())."""
        if any(r in CUT_REASONS for r in digest.research):
            return "cut"
        if not run.answer.is_file():
            return "running" if live else "incomplete"
        if "run_error" in digest.research:
            return "error"
        if digest.loop_exit is not None:
            return digest.loop_exit
        return "submitted" if digest.final_answer else "unknown"

    def status(self, run: RunDir, digest: Digest, live: bool) -> str:
        found = self.exit_status(run, digest, live)
        return (self.trajectory_exit(run) or found) if found == "unknown" else found

    def verification(self, run: RunDir, *, compute: bool = True) -> Verification | None:
        """agent verify's result (cached by file signatures); None without a corpus or while live."""
        manifest = self.corpus.manifest
        if manifest is None or not manifest.is_file():
            return None
        key = self.key(run)
        sig = signature(run.events, run.claims, run.answer, run.config, run.root / ATTACH_FILE, manifest)
        with self._lock:
            hit = self._verify.get(key)
        if hit and hit[0] == sig:
            return hit[1]
        if not compute or self.live(run):
            return None
        report = verify_run(run, self.corpus.root, manifest)
        result = Verification(ok=report.ok, errors=report.errors, stats=report.stats)
        with self._lock:
            self._verify[key] = (sig, result)
        return result

    # --- summaries and details -------------------------------------------------------------------------

    def summary(self, run: RunDir, *, verify: bool = False, concepts: ConceptIndex | None = None) -> RunSummary:
        config = read_json(run.config) or {}
        digest = self.digest(run)
        live = self.live(run, config)
        cost = digest.cost
        answer = read_json(run.answer) if run.answer.is_file() else None
        rows = answer.get("rows") if isinstance(answer, dict) else None
        check = self.verification(run, compute=verify)
        sampling = config.get("sampling") or {}
        qid, current = self.question_of(run, config, concepts)
        try:
            attach = attach_state(run)
        except (OSError, ValueError, KeyError):
            attach = "not_applicable"
        return RunSummary(
            run_id=self.key(run), batch=self.batch(run), qid=qid,
            concept_sha256=(config.get("hashes") or {}).get("concept_sha256"), concept_current=current,
            condition=str(config.get("condition", "")), seed=sampling.get("seed"),
            temperature=sampling.get("temperature"), created_at=config.get("created_at"),
            exit_status=self.status(run, digest, live), answer_from=digest.answer_from if answer is not None else None,
            steps=cost["steps"], model_calls=cost["model_calls"], tokens=cost["tokens"], seconds=cost["seconds"],
            tokens_without_attach=cost["without_attach"]["tokens"] if "without_attach" in cost else None,
            seconds_without_attach=cost["without_attach"]["seconds"] if "without_attach" in cost else None,
            rows=len(rows) if isinstance(rows, list) else None,
            facts=sum(len(r.get("facts", [])) for r in rows) if isinstance(rows, list) else None,
            claims_accepted=cost["claims_accepted"], claims_rejected=cost["claims_rejected"], attach=attach,
            verify="unknown" if check is None else ("ok" if check.ok else "failed"),
            score=score_summary(read_json(run.root / "score.json")), live=live,
            post_processing=not live and self.job_steps(self.key(run)) is not None)

    def summaries(self, qid: str | None = None, condition: str | None = None, verify: bool = False,
                  include_stale: bool = False) -> list[RunSummary]:
        """Every run, or a question's runs on its current concept (with include_stale: on any of its concepts)."""
        concepts = self.concept_index()
        out = []
        for run in self.run_dirs():
            config = read_json(run.config) or {}
            if condition and config.get("condition") != condition:
                continue
            if qid:
                found, current = self.question_of(run, config, concepts)
                if found != qid or (current is False and not include_stale):
                    continue
            out.append(self.summary(run, verify=verify, concepts=concepts))
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
        """Fact -> its claims -> the step each was sent from -> the passage, highlighted; with the
        verdicts score.json counted, when the run is scored (webapp/judge.py)."""
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
        walk = FactWalk(run_id=self.key(run), fact=Fact.model_validate(fact), row_id=row["id"],
                        row=AnswerRow.model_validate(row), claims=items, support=None,
                        label=None if any(item.claim for item in items) else "unsourced")
        judge.add_scored(walk, read_json(run.root / "score.json"))
        return walk

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
        path = inside(self.root, *run_parts(run_id))
        if not (path / "config.json").is_file() and self.job_steps(run_id) is None:
            raise NotFound(f"no such run: {run_id!r}")
        return path

    async def stream(self, run_id: str, after: int = 0) -> AsyncIterator[ServerSentEvent]:
        """`record` per events.jsonl line (id = line number) as it is appended, then `done`.

        Done when the agent no longer writes the run: answer.json written (and, for claim_off, the
        attach step finished, failed or skipped), cut, or left incomplete; a web-app job's later
        steps (verify ... score) do not hold it open. `after` skips lines already seen (the
        browser's Last-Event-ID on reconnect).
        """
        run = RunDir(self.exists_or_pending(run_id))
        offset, line_no, pending = 0, 0, b""
        while True:
            # Look at the state before reading: every record written before the end is then read.
            # A run a job was to create but never did (the run failed to start) ends with its step.
            if run.config.is_file():
                finished = not self.live(run)
            else:
                steps = self.job_steps(run_id)
                finished = steps is None or steps.get("run") not in STEP_ACTIVE
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
                yield ServerSentEvent(json.dumps({"run_id": run_id, "records": line_no,
                                                  "exit_status": self.status(run, self.digest(run), False)}),
                                      event="done")
                return
            await asyncio.sleep(self.settings.poll_s)


# --- record helpers ----------------------------------------------------------------------------------------

def _coverage(record: dict[str, Any]) -> str | None:
    return (record.get("generated") or {}).get("reason") if record.get("subtype") == "coverage" else None


def score_summary(score: Any) -> ScoreSummary | None:
    """support_share, row F1 and fact F1 from score.json; fact F1 is the soft (judged) match,
    else the normalised, else the strict one, whichever the file has. A score against the draft key
    is `provisional` (scoring's flag, else read from the key version)."""
    if not isinstance(score, dict):
        return None
    facts = score.get("facts") or {}
    fact_f1 = next(((facts.get(k) or {}).get("f1") for k in ("soft", "normalised", "strict")
                    if (facts.get(k) or {}).get("f1") is not None), None)
    version = score.get("key_version")
    provisional = score.get("provisional")
    if provisional is None and version is not None:
        provisional = str(version).endswith("-draft")
    return ScoreSummary(support_share=(score.get("support") or {}).get("support_share"), fact_f1=fact_f1,
                        row_f1=(score.get("rows") or {}).get("f1"), key_version=version,
                        provisional=bool(provisional) if provisional is not None else None)


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
