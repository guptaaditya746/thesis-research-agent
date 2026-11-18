"""The plan API under /api/ev/plan (general evidence system, W7): a person confirms one plan on one page.

    POST   /plan                          {question}  -> {id, question, clarifications, plan, how, problems, ready}; the
                                                          plan is null while clarifying questions are open
    POST   /plan/{id}/clarify             {answers: [{question, answer}]} -> the plan, made with the answers (409 when
                                                          the plan exists; each answer must be an option asked)
    POST   /plan/{id}/decision/{did}      {confirm: true} | {change: value} -> the plan (a change is the person's
                                                          choice, so it also confirms that decision)
    POST   /plan/{id}/confirm-all         -> the plan with every decision confirmed (flagged ones too)
    POST   /plan/{id}/main-rule           {rule} -> the main-answer rule (one of evidence.planner.RULES), confirmed
    DELETE /plan/{id}/line/{lid}          -> the plan (409 for the oversell line)
    POST   /plan/{id}/answer              {answer_by, target?} -> the plan with that answer kind (the kind is chosen on
                                                          /system; 400 for a bad one, 409 for a batch plan, whose kind
                                                          comes from the question file, and, with no plan yet, until
                                                          the clarifying questions are answered: the kind is kept and
                                                          applied when the plan is made)
    POST   /plan/batch/{domain}/{qid}     -> the plan view of the batch plan file `<synth3>/plans/<domain>/<qid>.json`
                                                          (404 with no file); every later change is written back to
                                                          that file as well as to `$EV/plans/<id>/`
    POST   /plan/{id}/run                 {domain?, seed?} -> {run}; 409 until ready (every decision confirmed and no
                                                          problem found by the code checks, answer kind included) and
                                                          while a run is starting or done; with a domain and a seed the
                                                          run is on that built synth3 folder
    GET    /plan/{id}/result              -> the run's lines and answer (W4's after_run result, with the reruns)
    POST   /run/{rid}/links               {accepted, rejected} -> W2's review, then W4's rerun

The model steps are the planner's (evidence/planner), run on the backend's `lm` (a RecordedLM, or a factory of one
per request) given to this request's thread only (`planner.using`, no lock: two requests never share a model);
without an `lm` the endpoints that need a model answer 501. create_app wires the real parts (webapp/planwire.py). The word writer (W1; it takes `lm=`), the SPARQL templates, the run (W4)
and the links review (W2) are wired by the integration; a missing one answers 501. A request that plans (clarify,
propose, critic, word writer) runs inside one HTTP request and can take minutes: put a long proxy timeout in front.

A plan can also be started with sub-questions and an answer kind (`answer_by`, `target`; see evidence.plan). A
`written` plan's result shows the written answer's text. Plans are kept in memory and, with `$EV`, saved under
`$EV/plans/<id>/` (a batch plan also in its batch plan file; `plan.json`; at run time
`plan.frozen.json` and `protocol.json`: decisions, who, when, clarifications), written BEFORE the run starts. Every
change of a plan is made under that plan's lock; a plan is `open`, then `running` (a second run is a 409), then
`frozen`."""
from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import dspy
from fastapi import APIRouter
from pydantic import BaseModel

from evidence.plan import ANSWER_BY, TARGETS, Plan, WordList, load_plan, with_answer, write_plan
from evidence.plankinds import answer_problems
from evidence.planner import MAIN_RULE_ID, OVERSELL_ID, check_plan, clarify, confirm_all, critic, how_sentences
from evidence.planner import propose, set_rule, using
from jsonio import write_text_atomic

from synth3.system import plan_path, plan_stale

from .evreview import ReviewFiles
from .evsystem import synth3_folder
from .files import BadRequest, Conflict, NotFound, check_id
from .settings import Settings


class NotWired(RuntimeError):
    """A part another workstream provides (a model, the word writer, run, links review) is not connected: 501."""


def _w1_words(question: str, things: list[str], *, lm: Any) -> WordList:
    try:
        from evidence.words.write import write_words  # W1; absent until integrated
    except ImportError as exc:
        raise NotWired("the word writer (evidence.words.write) is not wired in") from exc
    return write_words(question, things, lm=lm)


def _not_wired(what: str) -> Callable[..., Any]:
    def missing(*_a: Any, **_k: Any) -> Any:
        raise NotWired(f"{what} is not wired in")
    return missing


@dataclass
class PlanBackend:
    """What the routes call; tests pass fakes, the integration passes the real parts.

    `lm`: the RecordedLM the planner steps run on (W1 needs the pinned orchestrator alias), or a no-argument factory
    that makes one per request. `clarify`, `propose` and `critic` replace the planner steps (tests)."""

    lm: Any = None
    templates: Mapping[str, str] = field(default_factory=dict)   # saved SPARQL template name -> text (W4)
    write_words: Callable[..., WordList] | None = None            # (question, things, *, lm) -> WordList (W1)
    clarify: Callable[[str], list[dict[str, Any]]] | None = None
    propose: Callable[..., tuple[Plan, dict[str, list[str]]]] | None = None   # (question, answers[, sub_questions=])
    critic: Callable[[Plan], Plan] | None = None
    run: Callable[..., str] = field(default_factory=lambda: _not_wired("the run (W4)"))   # (plan, folder[, corpus=])
    result: Callable[[str], dict[str, Any]] = field(default_factory=lambda: _not_wired("the run's result (W4)"))
    links: Callable[[str, list[str], list[str]], dict[str, Any]] = field(
        default_factory=lambda: _not_wired("the links review and rerun (W2, W4)"))

    def model(self) -> Any:
        if self.lm is None:
            raise NotWired("no model is configured for the planner (PlanBackend.lm)")
        return self.lm if isinstance(self.lm, dspy.BaseLM) else self.lm()

    def do_clarify(self, question: str) -> list[dict[str, Any]]:
        if self.clarify is not None:
            return self.clarify(question)
        with using(self.model()):
            return clarify(question)

    def do_propose(self, question: str, answers: list[dict[str, str]],
                   sub_questions: Sequence[str] = ()) -> tuple[Plan, dict[str, list[str]]]:
        if self.propose is not None:
            if sub_questions:
                return self.propose(question, answers, sub_questions=list(sub_questions))
            return self.propose(question, answers)
        lm = self.model()
        words = self.write_words or _w1_words
        with using(lm):
            return propose(question, answers, write_words=lambda q, things: words(q, things, lm=lm),
                           templates=self.templates, sub_questions=list(sub_questions))

    def do_critic(self, plan: Plan) -> Plan:
        if self.critic is not None:
            return self.critic(plan)
        with using(self.model()):
            return critic(plan)


def check_kind(answer_by: str, target: str | None) -> None:
    """The checks `with_answer` makes, for a kind given before there is a plan (ValueError with its text)."""
    if answer_by not in ANSWER_BY:
        raise ValueError(f"unknown answer_by {answer_by!r}")
    if target is not None and target not in TARGETS:
        raise ValueError(f"unknown target {target!r}")
    if target is not None and answer_by != "inventory":
        raise ValueError("target is only for an inventory answer")


class PlanStart(BaseModel):
    question: str
    sub_questions: list[str] = []
    answer_by: str = "lines"
    target: str | None = None


class AnswerRequest(BaseModel):
    answer_by: str
    target: str | None = None


class PlanRunRequest(BaseModel):
    domain: str | None = None
    seed: int | None = None


class Answer(BaseModel):
    question: str
    answer: str


class ClarifyRequest(BaseModel):
    answers: list[Answer]


class DecisionRequest(BaseModel):
    confirm: bool = False
    change: Any = None


class RuleRequest(BaseModel):
    rule: str


class LinksRequest(BaseModel):
    accepted: list[str] = []
    rejected: list[str] = []


class PlanView(BaseModel):
    id: str
    question: str
    clarifications: list[dict[str, Any]]
    plan: Plan | None
    how: dict[str, list[str]] = {}   # per line id: plain sentences for "how?" (never code)
    problems: list[str] = []         # what the code checks found wrong; the plan cannot run while any
    ready: bool = False              # every decision confirmed and no problem
    frozen: bool = False
    run: str | None = None
    sub_questions: list[str] = []
    batch: str | None = None         # "<domain>/<qid>" for a batch plan


class RunStarted(BaseModel):
    run: str


class LineResult(BaseModel):
    id: str
    question: str
    status: Literal["done", "failed"]
    rows: list[dict[str, Any]]
    text: str


class AnswerResult(BaseModel):
    text: str
    main_rule: str | None = None
    rule_met: bool | None = None
    found: list[str] = []
    missing: list[str] = []


class PlanResult(BaseModel):
    """The run's result: W4's after_run output (evidence.planner.lines.run_lines) with the reruns."""
    status: Literal["running", "done"] = "done"
    lines: list[LineResult]
    answer: AnswerResult
    reruns: list[dict[str, Any]] = []
    labels: dict[str, str] = {}          # line id -> "solid" | "same direction" | "depends on <field>" | "too few to tell"
    links: list[dict[str, Any]] = []     # builds-on links; a cited work not in the corpus says "outside the set"


@dataclass
class Entry:
    id: str
    question: str
    asked: list[dict[str, Any]]
    plan: Plan | None = None
    fresh: dict[str, list[str]] = field(default_factory=dict)
    state: Literal["open", "running", "frozen"] = "open"
    run: str | None = None
    sub_questions: list[str] = field(default_factory=list)
    answer_by: str = "lines"
    target: str | None = None
    batch: tuple[str, str] | None = None   # (domain, question id) of a batch plan, bound to its file
    batch_file: Path | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


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
    entries: dict[str, Entry] = {}
    runs: dict[str, str] = {}   # run id -> plan id
    index_lock = threading.Lock()
    known = be.templates or None   # unknown template names are only a problem once templates are wired

    def folder(pid: str) -> Path | None:
        return None if settings.ev is None else Path(settings.ev) / "plans" / pid

    def save(e: Entry) -> None:
        if e.plan is None or e.state != "open":
            return
        d = folder(e.id)
        if d is not None:
            d.mkdir(parents=True, exist_ok=True)
            write_plan(e.plan, d / "plan.json")
        if e.batch_file is not None:
            write_text_atomic(e.batch_file, e.plan.model_dump_json(indent=2))

    def stale(e: Entry) -> list[str]:
        if e.batch is None or e.plan is None:
            return []
        rf = ReviewFiles(settings)
        try:
            qs = rf.questions(e.batch[0], rf.spec(e.batch[0]))
            why = plan_stale(e.plan, rf.question(qs, e.batch[1]))
        except (NotFound, Conflict) as exc:
            return [f"the question file cannot be read: {exc}"]
        return [why] if why else []

    def view(e: Entry) -> PlanView:
        if e.plan is None:
            return PlanView(id=e.id, question=e.question, clarifications=e.asked, plan=None)
        problems = [*check_plan(e.plan, known), *answer_problems(e.plan), *stale(e)]
        how = {x.id: how_sentences(x, e.plan, be.templates.get(x.template) if x.template else None, e.fresh.get(x.id))
               for x in e.plan.lines}
        return PlanView(id=e.id, question=e.question, clarifications=e.asked, plan=e.plan, how=how, problems=problems,
                        ready=e.plan.ready() and not problems, frozen=e.state != "open", run=e.run,
                        sub_questions=list(e.plan.sub_questions),
                        batch=None if e.batch is None else "/".join(e.batch))

    def get(pid: str) -> Entry:
        check_id(pid, "plan")
        if pid not in entries:
            raise NotFound(f"no plan {pid!r}")
        return entries[pid]

    @contextmanager
    def editing(pid: str) -> Iterator[Entry]:
        """The plan, locked, only while it is open and made."""
        e = get(pid)
        with e.lock:
            if e.state != "open":
                raise Conflict("the plan was run and is frozen" if e.state == "frozen" else "the plan is starting a run")
            yield e

    def need_plan(e: Entry) -> Plan:
        if e.plan is None:
            raise Conflict("answer the clarifying questions first")
        return e.plan

    def make(e: Entry, answers: list[dict[str, str]]) -> None:
        plan, fresh = be.do_propose(e.question, answers, e.sub_questions)
        plan = be.do_critic(plan)
        try:
            e.plan = with_answer(plan, e.answer_by, e.target)
        except ValueError as exc:
            raise BadRequest(str(exc)) from exc
        e.fresh = fresh
        save(e)

    @api.post("/plan", response_model=PlanView, tags=["plan"])
    def start(req: PlanStart) -> PlanView:
        question = req.question.strip()
        if not question:
            raise BadRequest("the question is empty")
        subs = [q.strip() for q in req.sub_questions]
        if any(not q for q in subs):
            raise BadRequest("a sub-question is empty")
        try:
            check_kind(req.answer_by, req.target)
        except ValueError as exc:
            raise BadRequest(str(exc)) from exc
        e = Entry(uuid.uuid4().hex[:8], question, be.do_clarify(question), sub_questions=subs,
                  answer_by=req.answer_by, target=req.target)
        with e.lock:
            with index_lock:
                entries[e.id] = e
            if not e.asked:
                make(e, [])
            return view(e)

    @api.post("/plan/batch/{domain}/{qid}", response_model=PlanView, tags=["plan"])
    def open_batch(domain: str, qid: str) -> PlanView:
        check_id(domain, "domain")
        check_id(qid, "question")
        path = plan_path(Path(settings.synth3_data) / "plans", domain, qid)
        if not path.is_file():
            raise NotFound(f"no batch plan for {domain}/{qid}")
        try:
            plan = load_plan(path)
        except ValueError as exc:
            raise Conflict(f"{domain}/{qid}: the plan file is damaged ({exc})") from exc
        e = Entry(uuid.uuid4().hex[:8], plan.question, [], plan=plan, sub_questions=list(plan.sub_questions),
                  answer_by=plan.answer_by, target=plan.target, batch=(domain, qid), batch_file=path)
        with index_lock:
            entries[e.id] = e
        with e.lock:
            return view(e)

    @api.post("/plan/{pid}/answer", response_model=PlanView, tags=["plan"])
    def set_answer(pid: str, req: AnswerRequest) -> PlanView:
        with editing(pid) as e:
            if e.batch is not None:
                raise Conflict("a batch plan's answer kind comes from the question file")
            try:
                if e.plan is None:
                    check_kind(req.answer_by, req.target)
                else:
                    e.plan = with_answer(e.plan, req.answer_by, req.target)
            except ValueError as exc:
                raise BadRequest(str(exc)) from exc
            e.answer_by, e.target = req.answer_by, req.target
            if e.plan is None:
                raise Conflict("answer the clarifying questions first")
            save(e)
            return view(e)

    @api.post("/plan/{pid}/clarify", response_model=PlanView, tags=["plan"])
    def answer(pid: str, req: ClarifyRequest) -> PlanView:
        with editing(pid) as e:
            if e.plan is not None:
                raise Conflict("the plan is already made; start a new plan to answer differently")
            options = {c["question"]: c["options"] for c in e.asked}
            given = {a.question: a.answer for a in req.answers}
            bad = [q for q in options if given.get(q) not in options[q]]
            if bad or set(given) - set(options):
                raise BadRequest(f"answer every question with one of its options: {bad or sorted(set(given) - set(options))}")
            make(e, [a.model_dump() for a in req.answers])
            return view(e)

    @api.post("/plan/{pid}/decision/{did}", response_model=PlanView, tags=["plan"])
    def decide(pid: str, did: str, req: DecisionRequest) -> PlanView:
        with editing(pid) as e:
            plan = need_plan(e)
            if not req.confirm and req.change is None:
                raise BadRequest("give confirm: true or a change")
            if did not in {d.id for d in plan.decisions}:
                raise NotFound(f"no decision {did!r}")
            if did == MAIN_RULE_ID and req.change is not None:
                try:
                    e.plan = set_rule(plan, str(req.change), settings.user)
                except ValueError as exc:
                    raise BadRequest(str(exc)) from exc
            else:
                change: dict[str, Any] = {"confirmed_by": settings.user, "confirmed_at": now()}
                if req.change is not None:
                    change["value"] = req.change
                e.plan = plan.model_copy(update={"decisions": [
                    d.model_copy(update=change) if d.id == did else d for d in plan.decisions]})
            save(e)
            return view(e)

    @api.post("/plan/{pid}/confirm-all", response_model=PlanView, tags=["plan"])
    def confirm(pid: str) -> PlanView:
        with editing(pid) as e:
            e.plan = confirm_all(need_plan(e), settings.user)
            save(e)
            return view(e)

    @api.post("/plan/{pid}/main-rule", response_model=PlanView, tags=["plan"])
    def main_rule(pid: str, req: RuleRequest) -> PlanView:
        with editing(pid) as e:
            try:
                e.plan = set_rule(need_plan(e), req.rule.strip(), settings.user)
            except ValueError as exc:
                raise BadRequest(str(exc)) from exc
            save(e)
            return view(e)

    @api.delete("/plan/{pid}/line/{lid}", response_model=PlanView, tags=["plan"])
    def drop_line(pid: str, lid: str) -> PlanView:
        with editing(pid) as e:
            plan = need_plan(e)
            line = next((x for x in plan.lines if x.id == lid), None)
            if line is None:
                raise NotFound(f"no line {lid!r}")
            if lid == OVERSELL_ID or not line.removable:
                raise Conflict("the oversell line cannot be removed")
            e.plan = plan.model_copy(update={"lines": [x for x in plan.lines if x.id != lid]})
            save(e)
            return view(e)

    @api.post("/plan/{pid}/run", response_model=RunStarted, tags=["plan"])
    def run(pid: str, req: PlanRunRequest | None = None) -> RunStarted:
        req = req or PlanRunRequest()
        if (req.domain is None) != (req.seed is None):
            raise BadRequest("give both domain and seed, or neither")
        e = get(pid)
        with e.lock:   # check, freeze and mark in one step: a second run (or a late edit) sees "running"
            if e.state != "open":
                raise Conflict("the plan is already running or was run")
            if e.plan is None:
                raise Conflict("answer the clarifying questions first")
            problems = [*check_plan(e.plan, known), *answer_problems(e.plan), *stale(e)]
            if problems:
                raise Conflict(f"the plan has problems: {'; '.join(problems)}")
            if not e.plan.ready():
                raise Conflict("confirm every decision before the run")
            plan = e.plan.model_copy(deep=True)   # what runs is this copy
            e.state = "running"
        d = folder(pid)
        try:
            if d is not None:   # written before the run starts, so the run can read them
                d.mkdir(parents=True, exist_ok=True)
                write_plan(plan, d / "plan.frozen.json")
                write_text_atomic(d / "protocol.json", json.dumps(protocol_record(plan, ""), indent=2))
            if req.domain is None:
                rid = be.run(plan, d)
            else:
                rid = be.run(plan, d, corpus=synth3_folder(settings, req.domain, int(req.seed or 0)))
            if d is not None:
                write_text_atomic(d / "protocol.json", json.dumps(protocol_record(plan, rid), indent=2))
        except BaseException:
            with e.lock:
                e.state = "open"
            if d is not None:
                for name in ("plan.frozen.json", "protocol.json"):
                    (d / name).unlink(missing_ok=True)
            raise
        with e.lock:
            e.run, e.state = rid, "frozen"
        runs[rid] = pid
        return RunStarted(run=rid)

    @api.get("/plan/{pid}/result", response_model=PlanResult, tags=["plan"])
    def result(pid: str) -> PlanResult:
        e = get(pid)
        if e.run is None:
            raise Conflict("the plan has not been run")
        return PlanResult.model_validate(be.result(e.run))

    @api.post("/run/{rid}/links", tags=["plan"])
    def links(rid: str, req: LinksRequest) -> dict[str, Any]:
        check_id(rid, "run")
        if rid not in runs:
            raise NotFound(f"no run {rid!r} started from a plan")
        return be.links(rid, req.accepted, req.rejected)

    return api
