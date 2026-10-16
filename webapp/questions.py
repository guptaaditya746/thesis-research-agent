"""Questions, their concept sessions and picks (docs/earlier-work.md, "Concepts and pick"; rows 2.1, 2.2).

The question list is questions/questions.json (`{"schema_version": 1, "questions": [...]}`); while
it does not exist, the questions are those with a concept session ($CONCEPTS/<qid>/session.json).
A session is `proposed` once it has proposal.json and `picked` once it has concept.json.

Picking belongs to agent/concept_step.py (WP B), and this module only calls it: `pick(session,
choice, picked_by=, reason=, replace=)` freezes the brief as concept.json and logs a `concept_pick`
record (who picked, why, and the concept it replaces) in the session's hash chain, and rewrites
$CONCEPTS/picks.json from the chains. So the chain is the one record of every pick, `agent
concepts check` passes after any of them, and the pick shown here is read from the last
`concept_pick` record. A confirmation of the current brief is a pick like any other.

The user may change a pick until the gold build for the question has started, and only with
`force` once runs used the current concept (they would then be runs on a replaced concept,
webapp/runs.py). concept_step.pick gets $GOLD too, so its own rule (no replace once $GOLD/<qid>/
holds anything) applies as well.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent import concept_step
from agent.canonical import canonical_bytes, file_sha256

from . import goldstate
from .files import ID, BadRequest, Conflict, NotFound, check_id, inside, read_json, read_jsonl
from .models import ConceptBrief, ConceptStatus, Pick, PickRequest, Question, QuestionDetail, RunCounts
from .settings import Settings


class Questions:
    def __init__(self, settings: Settings, run_index: Callable[[], list[Any]],
                 gold_building: Callable[[str], bool] = lambda qid: False) -> None:
        """`run_index()` gives (run_id, qid, condition, concept_current) per run (webapp/runs.py
        Runs.index); `gold_building(qid)` whether a gold job runs."""
        self.settings = settings
        self.run_index = run_index
        self.gold_building = gold_building
        self._lock = threading.Lock()

    @property
    def concepts(self) -> Path:
        return self.settings.concepts

    # --- reading ---------------------------------------------------------------------------------------

    def load(self) -> list[dict[str, Any]]:
        """The questions (plain ids only: anything else could not be addressed)."""
        data = read_json(self.settings.questions)
        if isinstance(data, dict) and isinstance(data.get("questions"), list):
            return [q for q in data["questions"] if isinstance(q, dict) and ID.fullmatch(str(q.get("id") or ""))]
        found = []
        for session in sorted(self.concepts.glob("*/session.json")) if self.concepts.is_dir() else []:
            if ID.fullmatch(session.parent.name):
                info = read_json(session) or {}
                found.append({"id": session.parent.name, "question": info.get("question", "")})
        return found

    def find(self, qid: str) -> dict[str, Any]:
        check_id(qid, "question")
        for q in self.load():
            if q["id"] == qid:
                return q
        raise NotFound(f"no such question: {qid!r}")

    def session(self, qid: str) -> Path:
        return inside(self.concepts, check_id(qid, "question"))

    def picked(self, qid: str, briefs: list[dict[str, Any]] | None = None) -> Pick | None:
        """The current pick: concept.json, as the session's last concept_pick record names it."""
        session = self.session(qid)
        concept = read_json(session / concept_step.CONCEPT_FILE)
        if not isinstance(concept, dict):
            return None
        sha = file_sha256(session / concept_step.CONCEPT_FILE)
        records = [r for r in read_jsonl(session / "events.jsonl") if r.get("subtype") == "concept_pick"]
        last = records[-1] if records else {}
        used, generated = last.get("used") or {}, last.get("generated") or {}
        if generated.get("concept_sha256") != sha:  # no record names this concept.json (`agent concepts check` fails)
            used, last = {}, {}
        return Pick(choice=int(used.get("choice") or choice_of(concept, briefs if briefs is not None else self.briefs(qid))),
                    title=(last.get("custom_metadata") or {}).get("title") or concept.get("title"),
                    picked_by=str(used.get("picked_by") or last.get("agent_id") or "user"),
                    reason=used.get("reason") or None, concept_sha256=sha,
                    replaces_concept_sha256=used.get("replaces_concept_sha256"))

    def briefs(self, qid: str) -> list[dict[str, Any]]:
        proposal = read_json(self.session(qid) / concept_step.PROPOSAL_FILE)
        return proposal.get("briefs", []) if isinstance(proposal, dict) else []

    def concept_status(self, qid: str) -> ConceptStatus:
        session = self.session(qid)
        pick = self.picked(qid)
        if pick is not None:
            return ConceptStatus(status="picked", title=pick.title, picked_by=pick.picked_by)
        if (session / concept_step.PROPOSAL_FILE).is_file():
            return ConceptStatus(status="proposed")
        return ConceptStatus(status="none")

    def question(self, q: dict[str, Any], counts: dict[str, RunCounts]) -> Question:
        qid = q["id"]
        return Question(id=qid, category=q.get("category"), question=str(q.get("question", "")),
                        source=q.get("source"), notes=q.get("notes"), concept=self.concept_status(qid),
                        gold=goldstate.status(self.settings.gold, qid, self.gold_building(qid)),
                        runs=counts.get(qid, RunCounts()))

    def run_counts(self) -> dict[str, RunCounts]:
        """Runs per question and condition, on the question's current concept only."""
        out: dict[str, RunCounts] = {}
        for r in self.run_index():
            if r.qid and r.condition in ("claim_on", "claim_off") and r.current is not False:
                counts = out.setdefault(r.qid, RunCounts())
                setattr(counts, r.condition, getattr(counts, r.condition) + 1)
        return out

    def list(self) -> list[Question]:
        counts = self.run_counts()
        return [self.question(q, counts) for q in self.load()]

    def detail(self, qid: str) -> QuestionDetail:
        q = self.find(qid)
        base = self.question(q, self.run_counts())
        briefs = self.briefs(qid)
        concept = read_json(self.session(qid) / concept_step.CONCEPT_FILE)
        return QuestionDetail(**base.model_dump(), briefs=[ConceptBrief.model_validate(b) for b in briefs],
                              picked=self.picked(qid, briefs),
                              concept_brief=ConceptBrief.model_validate(concept) if isinstance(concept, dict) else None)

    # --- picking ---------------------------------------------------------------------------------------

    def pick(self, qid: str, request: PickRequest) -> QuestionDetail:
        self.find(qid)
        session = self.session(qid)
        briefs = self.briefs(qid)
        if not briefs:
            raise Conflict(f"{qid} has no proposed briefs yet; propose first")
        if not 1 <= request.choice <= len(briefs):
            raise BadRequest(f"choice must be 1..{len(briefs)}")
        if goldstate.started(self.settings.gold, qid) or self.gold_building(qid):
            raise Conflict(f"the gold build for {qid} has started on the current pick; it can no longer change")
        with self._lock:
            current = self.picked(qid, briefs)
            try:
                concept_step.pick(session, request.choice, picked_by=request.picked_by,
                                  reason=self._reason(qid, request, current), replace=current is not None,
                                  gold=self.settings.gold)
            except (concept_step.ConceptStepError, ValueError) as exc:
                raise Conflict(str(exc)) from exc
        return self.detail(qid)

    def _reason(self, qid: str, request: PickRequest, current: Pick | None) -> str:
        """The request's reason; changing a pick that runs used needs `force`, and says so."""
        reason = request.reason or ""
        if current is None or request.choice == current.choice:
            return reason
        used = [r for r in self.run_index() if r.qid == qid and r.current is True]
        if not used:
            return reason
        if not request.force:
            raise Conflict(f"{len(used)} run(s) used {qid}'s current concept; changing the pick leaves them on a "
                           "replaced concept (set force to change it anyway)")
        return f"{reason} [changed with {len(used)} run(s) on the replaced concept]".strip()


def choice_of(concept: dict[str, Any], briefs: list[dict[str, Any]]) -> int:
    """1-based number of the brief a concept.json was picked from (by brief id, else by content)."""
    cid = str(concept.get("id", ""))
    if cid.startswith("c") and cid[1:].isdigit():
        return int(cid[1:])
    body = canonical_bytes(concept)
    return next((n for n, b in enumerate(briefs, 1) if canonical_bytes(b) == body), 0)
