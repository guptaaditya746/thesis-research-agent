"""Concept step and pick (milestones-1-2.md, rows 2.1 and 2.2).

`propose`: question -> 1 to 5 concept briefs in the 1.3 schema (agent/schemas/concept.schema.json).
The model (`orch-model`, the loop's OrchestratorModel: same LiteLLM settings, thinking off, the
session's temperature and seed, key from $LITELLM_MASTER_KEY only) sees the question and the
versioned prompt agent/prompts/concept-<version>.txt, never the corpus: the session has no corpus
and its broker accepts no claims. The model decides how many briefs; more than MAX_BRIEFS are cut
to the first MAX_BRIEFS (`capped_from` records how many came). Output that does not validate gets
REPAIR_ROUNDS repair round(s) with the problems listed; if it still does not validate the step
fails with ConceptStepError and writes no proposal.

`pick`: the user picks one brief by number; it is written as concept.json (canonical JSON, the
bytes RunDir.create writes, so its hash is the run's concept_sha256) and concept.sha256.

Everything is logged as PROV-AGENT records in one hash chain, through the broker core
(agent/broker.py), in the concept-session directory concepts/<question-id>/:
- each model call: `ai_model_invocation`, agent `main`, custom_metadata.origin "concept";
- output that does not validate: `coverage` (reason invalid_concepts, with the problems);
- the pick: `concept_pick`, agent `user`, parent = the model call whose briefs were shown.

Files: session.json (question, model settings, prompt hashes), events.jsonl, claims.jsonl (always
empty), proposal.json (the briefs), concept.json and concept.sha256 after the pick.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .broker import Broker
from .canonical import canonical_bytes, file_sha256, sha256_hex, write_json
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
QUESTION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


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

    A session whose earlier proposal failed is continued (same chain, later step ids); one that
    already has a proposal is refused.
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
    if session.path(SESSION_FILE).is_file():
        if session.path(PROPOSAL_FILE).exists():
            raise ValueError(f"{session.root} already has a proposal; pick from it, or use a new question id")
        old = session.load(SESSION_FILE)
        if {k: old.get(k) for k in settings} != settings:
            raise ValueError(f"{session.root} was started with other settings; use a new question id")
    else:
        session.root.mkdir(parents=True, exist_ok=True)
        write_json(session.path(SESSION_FILE), {**settings, "created_at": utc_now()})
        session.run.events.touch()
        session.run.claims.touch()
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
                         "prompt_files": prompt.files, "question_sha256": settings["question_sha256"]},
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


def pick(session_dir: Path, choice: int) -> tuple[dict[str, Any], str]:
    """Write the chosen brief (1-based `choice`) as concept.json and log the pick. Returns (concept, sha256)."""
    session = Session(Path(session_dir))
    if not session.path(PROPOSAL_FILE).is_file():
        raise ValueError(f"{session.root} has no proposal; run `agent concepts propose` first")
    if session.path(CONCEPT_FILE).exists():
        raise ValueError(f"{session.path(CONCEPT_FILE)} exists: the concept is frozen")
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
        _record(broker, {
            "subtype": "concept_pick", "step_id": _last_step(session) + 1, "agent_id": "user",
            "parent_task_id": proposal["model_call"],
            "used": {"proposal_sha256": file_sha256(session.path(PROPOSAL_FILE)), "briefs": len(briefs),
                     "choice": choice, "brief_id": concept["id"], "brief_sha256": sha256_hex(canonical_bytes(concept))},
            "generated": {"concept_file": CONCEPT_FILE, "concept_sha256": sha},
            "started_at": now, "ended_at": now, "custom_metadata": {"title": concept["title"]},
        })
    finally:
        broker.close()
    return concept, sha


def check_session(session_dir: Path) -> list[str]:
    """Problems with a concept session: chain, proposal, and the frozen concept against its hash and pick."""
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
    picks = [json.loads(raw) for raw in session.run.events.read_bytes().splitlines()]
    picks = [r for r in picks if r["subtype"] == "concept_pick"]
    if len(picks) != 1 or picks[0]["generated"].get("concept_sha256") != sha:
        problems.append("concept.json is not the one the pick record names")
    problems += [f"concept.json {p}" for p in validate_concept(session.load(CONCEPT_FILE))]
    return problems
