"""The plan API under /api/ev/plan (general evidence system, W7): a person confirms one plan on one page.

    POST   /plan                          {question}  -> {id, question, clarifications, plan}; the plan is null
                                                          while clarifying questions are open
    POST   /plan/{id}/clarify             {answers: [{question, answer}]} -> the plan, made with the answers
    POST   /plan/{id}/decision/{did}      {confirm: true} | {change: value} -> the plan (a change is the person's
                                                          choice, so it also confirms that decision)
    POST   /plan/{id}/confirm-all         -> the plan with every decision confirmed (flagged ones too)
    DELETE /plan/{id}/line/{lid}          -> the plan (409 for the oversell line)
    POST   /plan/{id}/run                 -> {run}; 409 until Plan.ready(); freezes the plan and saves the protocol
    POST   /run/{rid}/links               {accepted, rejected} -> W2's review, then W4's rerun

The model steps are the planner's (evidence/planner), the run and the links review are injected (`PlanBackend`):
the word writer (W1), the SPARQL templates and the run (W4) and the review (W2) are wired by the integration; a
missing one answers 501. Plans are kept in memory and, with `$EV`, saved under `$EV/plans/<id>/` (`plan.json`;
after the run `plan.frozen.json` and `protocol.json`: decisions, who, when, clarifications)."""
from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from evidence.plan import Plan, write_plan
from evidence.planner import OVERSELL_ID, clarify, confirm_all, critic, propose
from jsonio import write_text_atomic

from .files import BadRequest, Conflict, NotFound, check_id
from .settings import Settings


class NotWired(RuntimeError):
    """A part another workstream provides (word writer, run, links review) is not connected: 501."""


def _no_words(question: str, things: list[str], *, step: Any = None) -> Any:
    try:
        from evidence.words.write import write_words  # W1; absent until integrated
    except ImportError as exc:
        raise NotWired("the word writer (evidence.words.write) is not wired in") from exc
    return write_words(question, things, step=step)


def _not_wired(what: str) -> Callable[..., Any]:
    def missing(*_a: Any, **_k: Any) -> Any:
        raise NotWired(f"{what} is not wired in")
    return missing


@dataclass
class PlanBackend:
    """What the routes call; tests pass fakes, the integration passes the real steps."""

    clarify: Callable[[str], list[dict[str, Any]]] = clarify
    propose: Callable[[str, list[dict[str, str]]], Plan] = lambda q, c: propose(q, c, write_words=_no_words)
    critic: Callable[[Plan], Plan] = critic
    run: Callable[[Plan, Path | None], str] = field(default_factory=lambda: _not_wired("the run (W4)"))
    links: Callable[[str, list[str], list[str]], dict[str, Any]] = field(
        default_factory=lambda: _not_wired("the links review and rerun (W2, W4)"))


class PlanStart(BaseModel):
    question: str


class Answer(BaseModel):
    question: str
    answer: str


class ClarifyRequest(BaseModel):
    answers: list[Answer]


class DecisionRequest(BaseModel):
    confirm: bool = False
    change: Any = None


class LinksRequest(BaseModel):
    accepted: list[str] = []
    rejected: list[str] = []


class PlanView(BaseModel):
    id: str
    question: str
    clarifications: list[dict[str, Any]]
    plan: Plan | None
    frozen: bool = False
    run: str | None = None


class RunStarted(BaseModel):
    run: str


@dataclass
class Entry:
    id: str
    question: str
    asked: list[dict[str, Any]]
    plan: Plan | None = None
    run: str | None = None


class Plans:
    """The plans of the app: in memory, mirrored to `$EV/plans/<id>/` when there is an `$EV`."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.entries: dict[str, Entry] = {}
        self.lock = threading.Lock()

    def dir(self, pid: str) -> Path | None:
        return None if self.settings.ev is None else Path(self.settings.ev) / "plans" / pid

    def save(self, e: Entry) -> None:
        d = self.dir(e.id)
        if d is not None and e.plan is not None and e.run is None:
            d.mkdir(parents=True, exist_ok=True)
            write_plan(e.plan, d / "plan.json")

    def get(self, pid: str) -> Entry:
        check_id(pid, "plan")
        if pid not in self.entries:
            raise NotFound(f"no plan {pid!r}")
        return self.entries[pid]

    def open(self, pid: str) -> Entry:
        e = self.get(pid)
        if e.run is not None:
            raise Conflict("the plan was run and is frozen")
        return e

    def view(self, e: Entry) -> PlanView:
        return PlanView(id=e.id, question=e.question, clarifications=e.asked, plan=e.plan, frozen=e.run is not None,
                        run=e.run)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def protocol_record(plan: Plan, run: str) -> dict[str, Any]:
    """The protocol record saved with the frozen plan."""
    return {"plan_sha256": plan.sha256, "run": run, "frozen_at": now(), "clarifications": plan.clarifications,
            "main_rule": plan.main_rule,
            "decisions": [{"id": d.id, "type": d.type, "value": d.value, "flagged": d.flagged,
                           "confirmed_by": d.confirmed_by, "confirmed_at": d.confirmed_at} for d in plan.decisions]}


def evplan_router(settings: Settings, backend: PlanBackend | None = None) -> APIRouter:
    api = APIRouter(generate_unique_id_function=lambda route: route.name)
    be = backend or PlanBackend()
    plans = Plans(settings)
    runs: dict[str, str] = {}   # run id -> plan id

    def make(e: Entry, answers: list[dict[str, str]]) -> None:
        e.plan = be.critic(be.propose(e.question, answers))
        plans.save(e)

    def update(e: Entry, plan: Plan) -> PlanView:
        e.plan = plan
        plans.save(e)
        return plans.view(e)

    @api.post("/plan", response_model=PlanView, tags=["plan"])
    def start(req: PlanStart) -> PlanView:
        if not req.question.strip():
            raise BadRequest("the question is empty")
        e = Entry(uuid.uuid4().hex[:8], req.question.strip(), be.clarify(req.question.strip()))
        with plans.lock:
            plans.entries[e.id] = e
        if not e.asked:
            make(e, [])
        return plans.view(e)

    @api.post("/plan/{pid}/clarify", response_model=PlanView, tags=["plan"])
    def answer(pid: str, req: ClarifyRequest) -> PlanView:
        e = plans.open(pid)
        make(e, [a.model_dump() for a in req.answers])
        return plans.view(e)

    @api.post("/plan/{pid}/decision/{did}", response_model=PlanView, tags=["plan"])
    def decide(pid: str, did: str, req: DecisionRequest) -> PlanView:
        e = plans.open(pid)
        if e.plan is None:
            raise Conflict("answer the clarifying questions first")
        if not req.confirm and req.change is None:
            raise BadRequest("give confirm: true or a change")
        if did not in {d.id for d in e.plan.decisions}:
            raise NotFound(f"no decision {did!r}")
        update_to: dict[str, Any] = {"confirmed_by": settings.user, "confirmed_at": now()}
        if req.change is not None:
            update_to["value"] = req.change
        return update(e, e.plan.model_copy(update={"decisions": [
            d.model_copy(update=update_to) if d.id == did else d for d in e.plan.decisions]}))

    @api.post("/plan/{pid}/confirm-all", response_model=PlanView, tags=["plan"])
    def confirm(pid: str) -> PlanView:
        e = plans.open(pid)
        if e.plan is None:
            raise Conflict("answer the clarifying questions first")
        return update(e, confirm_all(e.plan, settings.user))

    @api.delete("/plan/{pid}/line/{lid}", response_model=PlanView, tags=["plan"])
    def drop_line(pid: str, lid: str) -> PlanView:
        e = plans.open(pid)
        if e.plan is None:
            raise Conflict("answer the clarifying questions first")
        line = next((x for x in e.plan.lines if x.id == lid), None)
        if line is None:
            raise NotFound(f"no line {lid!r}")
        if lid == OVERSELL_ID or not line.removable:
            raise Conflict("the oversell line cannot be removed")
        return update(e, e.plan.model_copy(update={"lines": [x for x in e.plan.lines if x.id != lid]}))

    @api.post("/plan/{pid}/run", response_model=RunStarted, tags=["plan"])
    def run(pid: str) -> RunStarted:
        e = plans.open(pid)
        if e.plan is None or not e.plan.ready():
            raise Conflict("confirm every decision before the run")
        d = plans.dir(pid)
        rid = be.run(e.plan, d)
        if d is not None:
            d.mkdir(parents=True, exist_ok=True)
            write_plan(e.plan, d / "plan.frozen.json")
            write_text_atomic(d / "protocol.json", json.dumps(protocol_record(e.plan, rid), indent=2))
        e.run = rid
        runs[rid] = pid
        return RunStarted(run=rid)

    @api.post("/run/{rid}/links", tags=["plan"])
    def links(rid: str, req: LinksRequest) -> dict[str, Any]:
        check_id(rid, "run")
        if rid not in runs:
            raise NotFound(f"no run {rid!r} started from a plan")
        return be.links(rid, req.accepted, req.rejected)

    return api
