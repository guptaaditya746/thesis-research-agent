"""Concept step and pick (docs/earlier-work.md, build rows 2.1 and 2.2).

`propose`: question -> 1 to 5 concept briefs in the 1.3 schema (agent/schemas/concept.schema.json).
The model (`orch-model`, the loop's OrchestratorModel: same LiteLLM settings, thinking off, the
session's temperature and seed, key from $LITELLM_MASTER_KEY only) sees the question and the
versioned prompt agent/prompts/concept-<version>.txt, never the corpus: the session has no corpus
and its broker accepts no claims. The model decides how many briefs; more than MAX_BRIEFS are cut
to the first MAX_BRIEFS (`capped_from` records how many came). Output that does not validate gets
REPAIR_ROUNDS repair round(s) with the problems listed; if it still does not validate the step
fails with ConceptStepError and writes no proposal.

A session whose proposal failed is continued by the next `propose` (same chain, later step ids),
also under another commit, proxy or seed: the question, model, prompt and limits define the
session and must stay the same; sampling, git commit and proxy belong to each attempt and are
listed in session.json (`attempts`; the top-level ones are the latest attempt's). Seeded sampling
tends to repeat a failure, so retrying with another seed is the usual way out.

`pick`: one brief is picked by number; it is written as concept.json (canonical JSON, the bytes
RunDir.create writes, so its hash is the run's concept_sha256) and concept.sha256. Who picked is
recorded (`picked_by`: user, claude, or provisional-first, the rule that takes brief 1 until the
user has looked; docs/earlier-work.md, "Concepts and pick"), with a reason. A pick is frozen; only an
explicit `replace` changes it (the web app's "change the pick before gold is built"), and the new
pick record names the concept it replaces. A replace is refused once anything of the question's
gold build exists in $GOLD/<qid>/ (`gold_files`, the web app's rule too), unless forced; a forced
replace records the gold files it went past.

All 12 questions (row 2.3): `load_questions` reads questions/questions.json
(agent/schemas/questions.schema.json); `propose_all` proposes for every question whose session has
no proposal yet (one failure does not stop the rest), `pick_all` applies a rule to every proposed
question not yet picked, and `status` gives one line per question. $CONCEPTS/picks.json indexes
the current pick of every session (docs/earlier-work.md, "Concepts and pick"); it is rebuilt from the sessions'
chains after each pick, so it never disagrees with them.

These functions are also the web app's (FastAPI runs sync handlers in a thread pool), so writers
take a lock (filelock: flock on Linux, released if the process dies): the session's for propose
and pick, since two writers would extend its chain from the same head and fork it; the concepts
root's for rebuilding picks.json, so an older rebuild never replaces a newer one.

Everything is logged as PROV-AGENT records in one hash chain, through the broker core
(agent/broker.py), in the concept-session directory concepts/<question-id>/:
- each model call: `ai_model_invocation`, agent `main`, custom_metadata.origin "concept";
- output that does not validate: `coverage` (reason invalid_concepts, with the problems);
- the pick: `concept_pick`, agent = who picked (`user` by default), parent = the model call whose
  briefs were shown.

Files: session.json (question, model settings, prompt hashes, attempts), events.jsonl, claims.jsonl
(always empty), proposal.json (the briefs), concept.json and concept.sha256 after the pick.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from filelock import FileLock, Timeout

from . import schema
from .broker import Broker
from jsonio import canonical_bytes, file_sha256, sha256_hex, write_json
from .chain import verify
from .concept import validate_concept
from .parse import parse_reply
from .prompts import PROMPT_DIR
from .rundir import ORCHESTRATOR, RunDir, utc_now
from .schema import SCHEMA_DIR

MAX_BRIEFS = 5
REPAIR_ROUNDS = 1
SESSION_FILE = "session.json"
PROPOSAL_FILE = "proposal.json"
CONCEPT_FILE = "concept.json"
CONCEPT_HASH_FILE = "concept.sha256"
PICKS_FILE = "picks.json"  # in the concepts root: the current pick of every session
LOCK_FILE = ".lock"  # in a session and in the concepts root: one writer at a time
LOCK_WAIT_S = 30.0
GOLD_ROOT = "gold-data"  # $GOLD's default (docs/earlier-work.md, Environment)
# What defines a session's proposal: a failed session is continued only with the same values. The
# rest of the settings (sampling, git_commit, base_url) belong to each attempt.
IDENTITY = ("schema_version", "question_id", "question", "question_sha256", "model", "prompt", "max_briefs",
            "repair_rounds")
ATTEMPT = ("sampling", "git_commit", "base_url")
QUESTIONS_FILE = Path("questions/questions.json")
QUESTION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
PICKED_BY = ("user", "claude", "provisional-first")
PICK_RULES = ("first",)
RULE_REASON = {"first": "provisional: rule 'first' takes brief 1 until the user has looked at the briefs "
                        "(docs/earlier-work.md, Concepts and pick)"}


class Model(Protocol):
    """OrchestratorModel (agent/loop.py) or a scripted stand-in."""

    settings: dict[str, Any]

    def query(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]: ...


class ConceptStepError(RuntimeError):
    def __init__(self, message: str, problems: list[str] | None = None) -> None:
        super().__init__(message)
        self.problems = list(problems or [])


@dataclass(frozen=True)
class ConceptPrompt:
    version: str
    system: str
    name: str
    files: dict[str, str]  # file name -> sha256 (the prompt template and the schema it embeds)

    @property
    def sha256(self) -> str:
        return self.files[self.name]


def load_prompt(version: str = "v1", max_briefs: int = MAX_BRIEFS) -> ConceptPrompt:
    name = f"concept-{version}.txt"
    raw = (PROMPT_DIR / name).read_bytes()
    schema_path = SCHEMA_DIR / "concept.schema.json"
    schema_raw = schema_path.read_bytes()
    system = (raw.decode("utf-8").replace("{{max_briefs}}", str(max_briefs))
              .replace("{{concept_schema}}", schema_raw.decode("utf-8").strip()))
    return ConceptPrompt(version, system, name, {name: sha256_hex(raw), schema_path.name: sha256_hex(schema_raw)})


def question_message(question: str) -> str:
    return f"Question: {question.strip()}"


def parse_briefs(content: str, max_briefs: int = MAX_BRIEFS) -> tuple[list[dict[str, Any]] | None, list[str], int | None]:
    """The briefs in one reply: (briefs numbered c1.., [], capped_from) or (None, problems, capped_from).

    Accepts {"concepts": [...]} or a bare list, in a json block (or the parser's lenient forms).
    Briefs past `max_briefs` are dropped before validation; any id the model gave is replaced.
    """
    parsed = parse_reply(content)
    if parsed.kind != "answer":
        text = (content or "").strip()
        if text.startswith("["):  # a bare list is not an "answer" to the reply parser
            payload = text
        else:
            return None, ['no json block: reply with EXACTLY ONE fenced json block {"concepts": [...]}'], None
    else:
        payload = parsed.answer
    try:
        given = json.loads(payload)
    except ValueError as exc:
        return None, [f"the json block is not valid JSON: {exc}"], None
    if isinstance(given, dict):
        unexpected = sorted(k for k in given if k != "concepts")
        if unexpected or "concepts" not in given:
            return None, [f'the json block must be {{"concepts": [...]}} (got keys {sorted(given)})'], None
        given = given["concepts"]
    if not isinstance(given, list) or not given:
        return None, ['"concepts" must be a non-empty list of briefs'], None
    capped_from = len(given) if len(given) > max_briefs else None
    briefs, problems = [], []
    for n, brief in enumerate(given[:max_briefs], 1):
        if not isinstance(brief, dict):
            problems.append(f"concepts/{n - 1}: a brief must be a JSON object")
            continue
        brief = {k: v for k, v in brief.items() if k != "id"}
        problems += [f"concepts/{n - 1}" + (p.removeprefix("<root>") if p.startswith("<root>:") else f"/{p}")
                     for p in validate_concept(brief)]
        briefs.append({"id": f"c{n}", **brief})
    bodies = [canonical_bytes({k: v for k, v in b.items() if k != "id"}) for b in briefs]
    problems += [f"concepts/{i}: same brief as concepts/{bodies.index(b)}" for i, b in enumerate(bodies)
                 if bodies.index(b) != i]
    return (None if problems else briefs), problems, capped_from


def show(briefs: list[dict[str, Any]]) -> str:
    """The briefs as numbered plain text, for the terminal."""
    out = []
    for n, brief in enumerate(briefs, 1):
        m = brief["measure"]
        measure = f"{m['operation']} {m['of']}" + "".join(
            f", {k.replace('_', ' ')} {m[k]}" for k in ("group_by", "filter", "order", "limit") if k in m)
        shape = brief["answer_shape"]
        if shape["kind"] == "table":
            form = "table: " + ", ".join(f"{c['name']} ({c['type']})" for c in shape["columns"])
        else:
            form = "graph: " + "; ".join(f"{e['source']} -{e['predicate']}-> {e['target']}" for e in shape["edges"])
        lines = [f"[{n}] {brief['title']}", f"    definition: {brief['definition']}", f"    measure:    {measure}"]
        lines += [f"    scope:      {k}: {v}" for k, v in brief["scope"].items()]
        lines.append(f"    answer:     {form}")
        lines += [f"    asks:       {q}" for q in brief["competency_questions"]]
        out.append("\n".join(lines))
    return "\n\n".join(out)


# --- session directory -----------------------------------------------------------------------------

@dataclass(frozen=True)
class Session:
    root: Path

    @property
    def run(self) -> RunDir:
        """The broker's view: events.jsonl and claims.jsonl here; the question id is the workflow id."""
        return RunDir(self.root)

    @property
    def question_id(self) -> str:
        return self.root.name

    def path(self, name: str) -> Path:
        return self.root / name

    def load(self, name: str) -> dict[str, Any]:
        return json.loads(self.path(name).read_text(encoding="utf-8"))


@contextmanager
def _locked(directory: Path, what: str) -> Iterator[None]:
    """Hold `directory`'s lock while `what` writes there (threads and processes alike)."""
    lock = FileLock(Path(directory) / LOCK_FILE, timeout=LOCK_WAIT_S)
    try:
        lock.acquire()
    except Timeout:
        raise ConceptStepError(f"{directory} is busy: {what} waited {LOCK_WAIT_S:g} s for another writer") from None
    try:
        yield
    finally:
        lock.release()


def _broker(session: Session) -> Broker:
    """The broker core on the session's chain (verified on open). No corpus: no claim can be anchored."""
    return Broker(session.run, corpus=None)


def _record(broker: Broker, record: dict[str, Any]) -> str:
    meta = {"origin": "concept", **record.get("custom_metadata", {})}
    reply = broker.record({"agent_id": "main", **record, "custom_metadata": meta})
    if not reply.get("ok"):
        raise ConceptStepError(f"broker refused a record: {reply.get('reason')}")
    return reply["task_id"]


def _last_step(session: Session) -> int:
    lines = session.run.events.read_bytes().splitlines() if session.run.events.exists() else []
    return max((json.loads(raw)["step_id"] for raw in lines), default=0)


def propose(concepts_root: Path, question_id: str, question: str, model: Model, *, temperature: float, seed: int,
            git_commit: str, base_url: str, prompt_version: str = "v1", max_briefs: int = MAX_BRIEFS,
            repair_rounds: int = REPAIR_ROUNDS) -> tuple[Session, dict[str, Any]]:
    """Ask the model for briefs; write proposal.json and the records. Returns the session and the proposal.

    A session whose earlier proposal failed is continued (same chain, later step ids), also under
    another commit, proxy or seed (each attempt's are listed in session.json); one that already
    has a proposal, or was started for another question, model, prompt or limits, is refused.
    """
    if not QUESTION_ID.fullmatch(question_id):
        raise ValueError(f"question id {question_id!r} must match {QUESTION_ID.pattern}")
    if not question.strip():
        raise ValueError("the question is empty")
    if not 1 <= max_briefs <= MAX_BRIEFS:
        raise ValueError(f"max_briefs must be 1..{MAX_BRIEFS}")
    session = Session(Path(concepts_root) / question_id)
    prompt = load_prompt(prompt_version, max_briefs)
    settings = {
        "schema_version": 1, "question_id": question_id, "question": question,
        "question_sha256": sha256_hex(question.encode("utf-8")), "model": dict(ORCHESTRATOR),
        "sampling": {"temperature": temperature, "seed": seed},
        "prompt": {"version": prompt_version, "sha256": prompt.sha256, "files": prompt.files},
        "max_briefs": max_briefs, "repair_rounds": repair_rounds, "git_commit": git_commit, "base_url": base_url,
    }
    attempt = {"started_at": utc_now(), **{k: settings[k] for k in ATTEMPT}}
    session.root.mkdir(parents=True, exist_ok=True)
    with _locked(session.root, "propose"):
        if session.path(SESSION_FILE).is_file():
            if session.path(PROPOSAL_FILE).exists():
                raise ValueError(f"{session.root} already has a proposal; pick from it, or move the session "
                                 "aside to propose again")
            old = session.load(SESSION_FILE)
            changed = [k for k in IDENTITY if old.get(k) != settings[k]]
            if changed:
                raise ValueError(f"{session.root} was started with other settings ({', '.join(changed)}); move "
                                 "the session aside to start the question again")
            attempts = old.get("attempts") or [{"started_at": old.get("created_at"), **{k: old.get(k) for k in ATTEMPT}}]
            write_json(session.path(SESSION_FILE), {**old, **settings, "attempts": [*attempts, attempt]})
        else:
            write_json(session.path(SESSION_FILE), {**settings, "created_at": attempt["started_at"],
                                                    "attempts": [attempt]})
            session.run.events.touch()
            session.run.claims.touch()
        return _propose(session, question_id, question, model, prompt, settings["question_sha256"], max_briefs,
                        repair_rounds)


def _propose(session: Session, question_id: str, question: str, model: Model, prompt: ConceptPrompt,
             question_sha: str, max_briefs: int, repair_rounds: int) -> tuple[Session, dict[str, Any]]:
    """propose()'s model calls and records, under the session's lock."""
    broker = _broker(session)
    try:
        step = _last_step(session)
        messages: list[dict[str, Any]] = [{"role": "system", "content": prompt.system},
                                          {"role": "user", "content": question_message(question)}]
        problems: list[str] = []
        for attempt in range(repair_rounds + 1):
            step += 1
            message = model.query(messages)
            call = message["extra"]["call"]
            content = message.get("content") or ""
            briefs, problems, capped_from = parse_briefs(content, max_briefs)
            task = _record(broker, {
                "subtype": "ai_model_invocation", "step_id": step,
                "used": {"prompt_sha256": call["prompt_sha256"], "messages": call["messages"], **model.settings,
                         "prompt_files": prompt.files, "question_sha256": question_sha},
                "generated": {k: call[k] for k in ("response_sha256", "reasoning_sha256", "finish_reason", "usage",
                                                   "served_model")}
                | {"briefs": len(briefs) if briefs else 0, "valid": briefs is not None, "capped_from": capped_from},
                "started_at": call["started_at"], "ended_at": call["ended_at"],
                "custom_metadata": {"phase": "propose" if attempt == 0 else "repair", "seconds": call["seconds"]},
            })
            if briefs is not None:
                proposal = {"question_id": question_id, "question": question, "briefs": briefs,
                            "capped_from": capped_from, "model_call": task, "rounds": attempt + 1,
                            "prompt_sha256": prompt.sha256, "response_sha256": call["response_sha256"]}
                write_json(session.path(PROPOSAL_FILE), proposal)
                return session, proposal
            _record(broker, {"subtype": "coverage", "step_id": step, "parent_task_id": task,
                             "used": {"raw_output_sha256": sha256_hex(content.encode("utf-8"))},
                             "generated": {"reason": "invalid_concepts", "detail": problems[:20]},
                             "status": "not_run", "custom_metadata": {"phase": "propose" if attempt == 0 else "repair"}})
            messages += [{"role": "assistant", "content": content},
                         {"role": "user", "content": "These briefs are not valid and were not saved:\n- "
                          + "\n- ".join(problems[:20]) + "\nReply with the corrected briefs: one sentence and "
                          'EXACTLY ONE fenced json block {"concepts": [...]}.'}]
        raise ConceptStepError(f"no valid briefs after {repair_rounds} repair round(s)", problems)
    finally:
        broker.close()


def gold_root(root: Path | None = None) -> Path:
    """The gold working directory: `root`, else $GOLD, else gold-data."""
    return Path(root or os.environ.get("GOLD") or GOLD_ROOT)


def gold_files(qid: str, root: Path | None = None) -> list[str]:
    """What the gold build has written for the question ($GOLD/<qid>/); once anything is there, its pick is in use."""
    folder = gold_root(root) / qid
    return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []


def pick(session_dir: Path, choice: int, *, picked_by: str = "user", reason: str | None = "",
         replace: bool = False, gold: Path | None = None, force: bool = False) -> tuple[dict[str, Any], str]:
    """Write the chosen brief (1-based `choice`) as concept.json and log the pick. Returns (concept, sha256).

    `picked_by` is recorded as the pick record's agent. A picked concept is frozen: picking again
    needs `replace=True`, which is for changing a pick before gold is built: it is refused once
    `gold_files` finds anything for the question under `gold` ($GOLD), unless `force`, and then
    the pick records those files. $CONCEPTS/picks.json is rewritten afterwards.
    """
    if picked_by not in PICKED_BY:
        raise ValueError(f"picked_by must be one of {PICKED_BY}")
    session = Session(Path(session_dir))
    if not session.path(PROPOSAL_FILE).is_file():
        raise ValueError(f"{session.root} has no proposal; run `agent concepts propose` first")
    with _locked(session.root, "pick"):
        replaces, past_gold = None, []
        if session.path(CONCEPT_FILE).exists():
            if not replace:
                raise ValueError(f"{session.path(CONCEPT_FILE)} exists: the concept is frozen "
                                 "(change it only before gold is built, with replace)")
            past_gold = gold_files(session.question_id, gold)
            if past_gold and not force:
                raise ValueError(f"the gold build for {session.question_id} has started on the current concept "
                                 f"({gold_root(gold) / session.question_id}: {', '.join(past_gold)}); the pick can no "
                                 "longer change (force it only with that gold moved aside or to be rebuilt)")
            replaces = file_sha256(session.path(CONCEPT_FILE))
        proposal = session.load(PROPOSAL_FILE)
        briefs = proposal["briefs"]
        if not 1 <= choice <= len(briefs):
            raise ValueError(f"choice must be 1..{len(briefs)}")
        concept = briefs[choice - 1]
        problems = validate_concept(concept)
        if problems:
            raise ConceptStepError("the chosen brief does not validate", problems)
        broker = _broker(session)
        try:
            sha = write_json(session.path(CONCEPT_FILE), concept)
            session.path(CONCEPT_HASH_FILE).write_bytes(f"{sha}  {CONCEPT_FILE}\n".encode("ascii"))
            now = utc_now()
            used = {"proposal_sha256": file_sha256(session.path(PROPOSAL_FILE)), "briefs": len(briefs),
                    "choice": choice, "brief_id": concept["id"], "brief_sha256": sha256_hex(canonical_bytes(concept)),
                    "picked_by": picked_by, "reason": reason or ""}
            if replaces:
                used["replaces_concept_sha256"] = replaces
            if past_gold:
                used["forced_past_gold"] = past_gold
            _record(broker, {
                "subtype": "concept_pick", "step_id": _last_step(session) + 1, "agent_id": picked_by,
                "parent_task_id": proposal["model_call"], "used": used,
                "generated": {"concept_file": CONCEPT_FILE, "concept_sha256": sha},
                "started_at": now, "ended_at": now, "custom_metadata": {"title": concept["title"]},
            })
        finally:
            broker.close()
    write_picks(session.root.parent)
    return concept, sha


def _pick_records(session: Session) -> list[dict[str, Any]]:
    out = []
    for raw in session.run.events.read_bytes().splitlines() if session.run.events.is_file() else []:
        try:
            record = json.loads(raw)
        except ValueError:
            break  # a record being written by a pick right now; that pick rebuilds picks.json after it
        if record["subtype"] == "concept_pick":
            out.append(record)
    return out


def check_session(session_dir: Path) -> list[str]:
    """Problems with a concept session: chain, proposal, and the frozen concept against its hash and last pick."""
    session = Session(Path(session_dir))
    report = verify(session.run.events, session.run.claims)
    problems = [f"chain: {e}" for e in report.errors]
    if report.claims:
        problems.append("chain: a concept session has no claims")
    if not session.path(CONCEPT_FILE).is_file():
        return problems + ["no concept.json yet"]
    sha = file_sha256(session.path(CONCEPT_FILE))
    recorded = session.path(CONCEPT_HASH_FILE).read_text(encoding="ascii").split()[0] \
        if session.path(CONCEPT_HASH_FILE).is_file() else None
    if recorded != sha:
        problems.append("concept.sha256 differs from concept.json")
    picks = _pick_records(session)
    if not picks or picks[-1]["generated"].get("concept_sha256") != sha:
        problems.append("concept.json is not the one the pick record names")
    problems += [f"concept.json {p}" for p in validate_concept(session.load(CONCEPT_FILE))]
    return problems


# --- all questions (row 2.3) ---------------------------------------------------------------------------

def load_questions(path: Path = QUESTIONS_FILE) -> list[dict[str, Any]]:
    """The questions of questions/questions.json, checked against agent/schemas/questions.schema.json."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = schema.check("questions", data)
    if problems:
        raise ValueError(f"invalid questions file {path}: {problems}")
    ids = [q["id"] for q in data["questions"]]
    if len(ids) != len(set(ids)):
        raise ValueError(f"invalid questions file {path}: duplicate question ids")
    return data["questions"]


def question_sha256(question: str) -> str:
    return sha256_hex(question.encode("utf-8"))


@dataclass
class Result:
    """What happened to one question in propose_all, pick_all or status."""
    id: str
    state: str
    detail: str = ""
    problems: list[str] = field(default_factory=list)

    def line(self) -> str:
        return f"{self.id} {self.state:<9}{self.detail}".rstrip()


def _stale(session: Session, question: dict[str, Any]) -> bool:
    """The session was started for another wording of the question (docs/earlier-work.md, Questions)."""
    if not session.path(SESSION_FILE).is_file():
        return False
    return session.load(SESSION_FILE).get("question_sha256") != question_sha256(question["question"])


STALE = "the question changed since its session started: move the session, its gold and its runs aside"


def propose_all(questions: list[dict[str, Any]], concepts_root: Path, model: Model, *, temperature: float,
                seed: int, git_commit: str, base_url: str, prompt_version: str = "v1",
                max_briefs: int = MAX_BRIEFS, log: Any = None) -> list[Result]:
    """Propose briefs for every question whose session has no proposal yet.

    A question that fails (invalid briefs after the repair round, a model or proxy error) is
    reported and the next one is tried; running it again retries only those (a failed session is
    continued, propose(), also after a new commit or with another seed, which a question that
    failed on its briefs usually needs). `log` (e.g. print) gets one line per question as it finishes.
    """
    results = []
    for q in questions:
        session = Session(Path(concepts_root) / q["id"])
        if _stale(session, q):
            result = Result(q["id"], "stale", STALE)
        elif session.path(PROPOSAL_FILE).is_file():
            result = Result(q["id"], "skipped", f"has a proposal ({len(session.load(PROPOSAL_FILE)['briefs'])} briefs)")
        else:
            try:
                _, proposal = propose(concepts_root, q["id"], q["question"], model, temperature=temperature,
                                      seed=seed, git_commit=git_commit, base_url=base_url,
                                      prompt_version=prompt_version, max_briefs=max_briefs)
                capped = f", capped from {proposal['capped_from']}" if proposal["capped_from"] else ""
                result = Result(q["id"], "proposed", f"{len(proposal['briefs'])} briefs in {proposal['rounds']} "
                                f"round(s){capped}")
            except Exception as exc:  # one question's failure must not stop the others
                result = Result(q["id"], "failed", f"{type(exc).__name__}: {exc}"[:300],
                                list(getattr(exc, "problems", [])))
        results.append(result)
        if log:
            log(result.line())
    return results


def pick_all(questions: list[dict[str, Any]], concepts_root: Path, *, rule: str = "first",
             picked_by: str = "provisional-first", reason: str | None = None) -> list[Result]:
    """Pick by `rule` in every question that has a proposal and no pick yet; picked ones are left as they are."""
    if rule not in PICK_RULES:
        raise ValueError(f"rule must be one of {PICK_RULES}")
    results = []
    for q in questions:
        session = Session(Path(concepts_root) / q["id"])
        if _stale(session, q):
            results.append(Result(q["id"], "stale", STALE))
        elif session.path(CONCEPT_FILE).is_file():
            current = picks(concepts_root).get(q["id"], {})
            results.append(Result(q["id"], "skipped", f"already picked [{current.get('choice')}] by "
                                  f"{current.get('picked_by')}"))
        elif not session.path(PROPOSAL_FILE).is_file():
            results.append(Result(q["id"], "missing", "no proposal: run `agent concepts propose-all` first"))
        else:
            try:
                concept, sha = pick(session.root, 1, picked_by=picked_by, reason=reason or RULE_REASON[rule])
                results.append(Result(q["id"], "picked", f"[1] {concept['title']} sha256={sha[:12]}"))
            except (ConceptStepError, ValueError, OSError) as exc:
                results.append(Result(q["id"], "failed", str(exc), list(getattr(exc, "problems", []))))
    return results


def picks(concepts_root: Path) -> dict[str, dict[str, Any]]:
    """The current pick of every session under `concepts_root`: the last concept_pick record of each."""
    out: dict[str, dict[str, Any]] = {}
    root = Path(concepts_root)
    for directory in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []:
        session = Session(directory)
        if not session.path(CONCEPT_FILE).is_file():
            continue
        records = _pick_records(session)
        if not records:
            continue
        last = records[-1]
        out[session.question_id] = {
            "choice": last["used"]["choice"], "title": last["custom_metadata"].get("title"),
            "picked_by": last["used"].get("picked_by", last["agent_id"]), "reason": last["used"].get("reason", ""),
            "concept_sha256": last["generated"]["concept_sha256"]}
    return out


def write_picks(concepts_root: Path) -> Path:
    """Rewrite $CONCEPTS/picks.json from the sessions, atomically (readers never see half a file) and one
    rebuild at a time (the last one to finish read every pick made before it)."""
    root = Path(concepts_root)
    path = root / PICKS_FILE
    with _locked(root, f"rebuilding {PICKS_FILE}"):
        fd, tmp = tempfile.mkstemp(dir=root, prefix=f".{PICKS_FILE}.", suffix=".tmp")
        os.close(fd)
        try:
            write_json(Path(tmp), picks(root))
            os.replace(tmp, path)
        finally:
            Path(tmp).unlink(missing_ok=True)  # gone after os.replace; left only when writing failed
    return path


def status(questions: list[dict[str, Any]], concepts_root: Path) -> list[Result]:
    """One Result per question: none, failed (tried, no proposal), proposed, picked or stale."""
    current = picks(concepts_root)
    results = []
    for q in questions:
        session = Session(Path(concepts_root) / q["id"])
        if not session.path(SESSION_FILE).is_file():
            results.append(Result(q["id"], "none"))
        elif _stale(session, q):
            results.append(Result(q["id"], "stale", STALE))
        elif not session.path(PROPOSAL_FILE).is_file():
            calls = sum(1 for raw in session.run.events.read_bytes().splitlines()
                        if json.loads(raw)["subtype"] == "ai_model_invocation")
            results.append(Result(q["id"], "failed", f"{calls} model call(s), no valid briefs yet"))
        elif not session.path(CONCEPT_FILE).is_file():
            results.append(Result(q["id"], "proposed", f"{len(session.load(PROPOSAL_FILE)['briefs'])} briefs, "
                                  "none picked"))
        else:
            p = current.get(q["id"], {})
            problems = check_session(session.root)
            n = len(session.load(PROPOSAL_FILE)["briefs"])
            results.append(Result(q["id"], "picked", f"[{p.get('choice')}/{n}] {p.get('title')} (by "
                                  f"{p.get('picked_by')}) sha256={str(p.get('concept_sha256'))[:12]}"
                                  + (" CHECK FAILED" if problems else ""), problems))
    return results
