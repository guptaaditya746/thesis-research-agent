"""Questions, their concept sessions and picks (docs/e2e-build-plan.md, "Concepts"; rows 2.1, 2.2).

The question list is questions/questions.json (`{"schema_version": 1, "questions": [...]}`); while
it does not exist, the questions are those with a concept session ($CONCEPTS/<qid>/session.json).
A session is `proposed` once it has proposal.json and `picked` once it has concept.json; who
picked, and why, is in $CONCEPTS/picks.json (`{"<qid>": {choice, title, picked_by, reason,
concept_sha256}}`), and a pick without an entry there was made with `agent concepts pick`, by
the user.

Picking goes through agent.concept_step.pick, which freezes the brief as concept.json and logs a
`concept_pick` record in the session's hash chain. The user may change a pick until the gold
build for the question has started: the frozen concept.json and concept.sha256 are kept as
concept.replaced-<n>.json / .sha256 and the new brief is picked the same way, so the chain holds
one `concept_pick` record per pick, in order, and the last one names the current concept.json.
"""
from __future__ import annotations

import inspect
import threading
from pathlib import Path
from typing import Any

from agent import concept_step
from agent.canonical import canonical_bytes, file_sha256

from . import goldstate
from .files import BadRequest, Conflict, NotFound, check_id, inside, read_json, write_json_atomic
from .models import ConceptBrief, ConceptStatus, Pick, PickRequest, Question, QuestionDetail, RunCounts
from .settings import Settings

PICKS_FILE = "picks.json"


class Questions:
    def __init__(self, settings: Settings, run_index: Any, gold_building: Any = lambda qid: False) -> None:
        """`run_index()` gives (run_id, qid, condition) per run; `gold_building(qid)` whether a gold job runs."""
        self.settings = settings
        self.run_index = run_index
        self.gold_building = gold_building
        self._lock = threading.Lock()

    @property
    def concepts(self) -> Path:
        return self.settings.concepts

    # --- reading ---------------------------------------------------------------------------------------

    def load(self) -> list[dict[str, Any]]:
        data = read_json(self.settings.questions)
        if isinstance(data, dict) and isinstance(data.get("questions"), list):
            return [q for q in data["questions"] if isinstance(q, dict) and q.get("id")]
        found = []
        for session in sorted(self.concepts.glob("*/session.json")) if self.concepts.is_dir() else []:
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

    def picks(self) -> dict[str, Any]:
        data = read_json(self.concepts / PICKS_FILE)
        return data if isinstance(data, dict) else {}

    def picked(self, qid: str, briefs: list[dict[str, Any]] | None = None) -> Pick | None:
        session = self.session(qid)
        concept = read_json(session / concept_step.CONCEPT_FILE)
        entry = self.picks().get(qid)
        if not isinstance(concept, dict):
            return None
        sha = file_sha256(session / concept_step.CONCEPT_FILE)
        if isinstance(entry, dict) and entry.get("concept_sha256") in (None, sha):
            return Pick(choice=int(entry.get("choice") or choice_of(concept, briefs or [])),
                        title=entry.get("title") or concept.get("title"), picked_by=str(entry.get("picked_by") or "user"),
                        reason=entry.get("reason"), concept_sha256=sha)
        return Pick(choice=choice_of(concept, briefs or self.briefs(qid)), title=concept.get("title"), picked_by="user",
                    reason=None, concept_sha256=sha)

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
        out: dict[str, RunCounts] = {}
        for _, qid, condition in self.run_index():
            if qid and condition in ("claim_on", "claim_off"):
                counts = out.setdefault(qid, RunCounts())
                setattr(counts, condition, getattr(counts, condition) + 1)
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
            if current is None or current.choice != request.choice:
                moved = self._set_aside(session) if current is not None else []
                try:
                    _pick(session, request.choice, request.picked_by, request.reason)
                except (concept_step.ConceptStepError, ValueError, RuntimeError) as exc:
                    for old, new in moved:  # put the current pick back
                        new.rename(old)
                    raise Conflict(str(exc)) from exc
            concept = read_json(session / concept_step.CONCEPT_FILE) or {}
            picks = self.picks()
            picks[qid] = {"choice": request.choice, "title": concept.get("title"), "picked_by": request.picked_by,
                          "reason": request.reason,
                          "concept_sha256": file_sha256(session / concept_step.CONCEPT_FILE)}
            write_json_atomic(self.concepts / PICKS_FILE, picks)
        return self.detail(qid)

    @staticmethod
    def _set_aside(session: Path) -> list[tuple[Path, Path]]:
        """Keep the replaced concept.json and concept.sha256 as concept.replaced-<n>.*; returns the moves."""
        n = 1 + sum(1 for _ in session.glob("concept.replaced-*.json"))
        moved = []
        for name, suffix in ((concept_step.CONCEPT_FILE, "json"), (concept_step.CONCEPT_HASH_FILE, "sha256")):
            path = session / name
            if path.exists():
                moved.append((path, path.rename(session / f"concept.replaced-{n}.{suffix}")))
        return moved


def _pick(session: Path, choice: int, picked_by: str, reason: str | None) -> None:
    """agent.concept_step.pick, passing who picked and why when its signature takes them."""
    params = inspect.signature(concept_step.pick).parameters
    extra = {k: v for k, v in (("picked_by", picked_by), ("reason", reason)) if k in params}
    concept_step.pick(session, choice, **extra)


def choice_of(concept: dict[str, Any], briefs: list[dict[str, Any]]) -> int:
    """1-based number of the brief a concept.json was picked from (by brief id, else by content)."""
    cid = str(concept.get("id", ""))
    if cid.startswith("c") and cid[1:].isdigit():
        return int(cid[1:])
    body = canonical_bytes(concept)
    return next((n for n, b in enumerate(briefs, 1) if canonical_bytes(b) == body), 0)
