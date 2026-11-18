"""The synth3 system runs of the plan page (which built folder a plan is run on) and the system API of the one-page UI:
read-only, the domains with their questions and plan states, the four rows of a plan run (find, pull, combine, answer)
and a paper with the run's items marked. No row shows a sub-question."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Response

from evidence.kindtext import RULE_TEXT, kind_lines, plan_names
from evidence.plan import Plan, load_plan
from evidence.planner.plan import RULES
from evidence.protocol import parse
from evidence.readable import NOT_COMPLETE, NotRebuilt, program_of_run, refusal
from evidence.rundir import ANSWER_FILE, FUNNEL_FILE, PLAN_FILE, PROTOCOL_FILE, SEAL_FILE, PaperIndex, RunDir
from evidence.written import STAGE, fact_budget, fact_lines
from modelcall.pins import ORCHESTRATOR
from synth3.questions import Question
from synth3.system import plan_path, plan_stale

from .evfiles import EvidenceFiles, segments
from .evmodels import Base, Segment
from .evreview import ReviewFiles
from .files import Conflict, NotFound, check_id, inside
from .settings import Settings


def synth3_folder(settings: Settings, domain: str, seed: int) -> Path:
    """The built folder `<synth3>/built/<domain>/s<seed>`: NotFound for a bad id or a seed that is not built, a
    Conflict (409) naming why when the folder does not load or does not match its spec."""
    check_id(domain, "domain")
    files = ReviewFiles(settings)
    if seed not in files.built_seeds(domain):
        raise NotFound(f"no built folder s{seed} of {domain!r}")
    return files.folder(domain, seed, files.spec(domain)).path


# --- the system API for the one-page UI: read-only -------------------------------------------------------------------

class SysQuestion(Base):
    id: str
    question: str
    sub_questions: list[str]
    kind: str
    target: str | None
    plan: str   # of the batch plan file: missing, draft, confirmed or stale


class SysDomain(Base):
    domain: str
    seeds: list[int]
    questions: list[SysQuestion]
    error: str | None


class FindPaper(Base):
    paper: str
    kept: bool
    why: str


class FindRow(Base):
    count: int
    papers: list[FindPaper]


class PullFact(Base):
    n: int
    item: str
    paper: str
    type: str
    text: str


class PullRow(Base):
    count: int
    left_out: int
    facts: list[PullFact]


class CombineLine(Base):
    text: str
    facts: list[int]


class CombineRow(Base):
    rule: str
    count: int
    rows: list[CombineLine]


class AnswerRow(Base):
    text: str
    status: str
    problems: list[str]
    lines: list[CombineLine]


class SystemSteps(Base):
    """The four rows of a plan run (find, pull, combine, answer)."""
    status: Literal["running", "failed", "done"]
    error: str | None
    answer_by: str
    question: str
    find: FindRow
    pull: PullRow
    combine: CombineRow
    answer: AnswerRow
    program_refused: str | None   # why no readable program can be made for the run; None when it can


class SystemPaper(Base):
    paper: str
    text: str
    segments: list[Segment]


def plan_state(plans: Path, domain: str, q: Question) -> str:
    """The batch plan's state: missing, draft (a decision no person confirmed, or the file is damaged), confirmed or
    stale (made for another version of the question)."""
    path = plan_path(plans, domain, q.id)
    if not path.is_file():
        return "missing"
    try:
        plan = load_plan(path)
    except ValueError:
        return "draft"
    if plan_stale(plan, q) is not None:
        return "stale"
    return "draft" if any(d.confirmed_by is None for d in plan.decisions) else "confirmed"


def system_run(settings: Settings, rid: str) -> Path:
    """The folder of a plan run under the runs root: NotFound unless it is an engine run holding plan.json."""
    check_id(rid, "run")
    if settings.ev_runs_dir is None:
        raise NotFound(f"no such run: {rid!r}")
    path = inside(settings.ev_runs_dir, rid)
    rd = RunDir(path)
    if not path.is_dir() or rd.kind != "engine" or not rd.file(PLAN_FILE).is_file():
        raise NotFound(f"no such plan run: {rid!r}")
    return path


def _rule_text(plan: Plan) -> str:
    if plan.answer_by == "lines":
        return RULE_TEXT["lines"].format(rule=RULES[plan.main_rule])
    return RULE_TEXT[plan.answer_by]


def _pulled(rd: RunDir, plan: Plan, written: dict[str, Any] | None) -> tuple[list[PullFact], int]:
    """The facts and how many the budget left out: a written run's own (the numbers its writer saw), else the same
    numbering rule over the run's items."""
    if written is not None:
        cut = written.get("cut") or {}
        rows = written.get("facts") or []
        return ([PullFact(**{k: f[k] for k in PullFact.model_fields}) for f in rows],
                sum((cut.get("left_out") or {}).values()))
    settings = rd.settings
    if settings is None or not settings.corpus:
        return [], 0
    facts, cut = fact_lines(PaperIndex.of_corpus(settings.corpus).group(rd.items()), plan,
                            fact_budget(int(ORCHESTRATOR["context_tokens"])))
    return [PullFact(**f.model_dump()) for f in facts], sum(cut["left_out"].values())


def _find(rd: RunDir, facts: list[PullFact]) -> FindRow:
    funnel = rd.try_json(FUNNEL_FILE)
    docs = (funnel.get("documents") if isinstance(funnel, dict) else None) or {}
    papers: list[FindPaper] = []
    for paper, doc in docs.items():
        doc = doc if isinstance(doc, dict) else {}
        kept = not doc.get("skipped")
        why = "screened out" if not kept else "kept by the screen" if doc.get("screen") else "no screen"
        papers.append(FindPaper(paper=paper, kept=kept, why=why))
    have = {f.paper for f in facts}
    return FindRow(count=sum(1 for p in papers if p.kept and p.paper in have), papers=papers)


def _kind_rows(numbers: dict[str, int], lines: list[Any]) -> list[CombineLine]:
    return [CombineLine(text=ln.text, facts=sorted({numbers[i] for i in ln.items if i in numbers})) for ln in lines]


def _refused(run: Path) -> str | None:
    """Why no readable program can be made for the run, None when it can: a run with no seal is still running (its
    folder may already read as complete), otherwise the refusal of `evidence.readable`. It never raises."""
    if not isinstance(RunDir(run).try_json(SEAL_FILE), dict):
        return NOT_COMPLETE.format(state="running")
    return refusal(run)


def steps_of(run: Path) -> SystemSteps:
    """The four rows of the plan run in `run`. No seal: running (the seal is written last); sealed failed: its
    reason. Both with every row empty."""
    rd = RunDir(run)
    plan = load_plan(rd.file(PLAN_FILE))
    seal = rd.try_json(SEAL_FILE)
    head = {"error": None, "answer_by": plan.answer_by, "question": plan.question, "program_refused": _refused(run)}
    find, pull = FindRow(count=0, papers=[]), PullRow(count=0, left_out=0, facts=[])
    rule = _rule_text(plan)
    combine, answer = CombineRow(rule=rule, count=0, rows=[]), AnswerRow(text="", status="", problems=[], lines=[])
    if not isinstance(seal, dict):
        return SystemSteps(status="running", **head, find=find, pull=pull, combine=combine, answer=answer)
    if seal.get("status") == "failed":
        head["error"] = str(seal.get("error") or "the run failed")
        return SystemSteps(status="failed", **head, find=find, pull=pull, combine=combine, answer=answer)
    written = rd.try_json(f"{STAGE}.json") if plan.answer_by == "written" else None
    written = written if isinstance(written, dict) else None
    if written is not None and "failed" in written:   # the writer's model call failed: no answer to show
        head["error"] = f"the written answer's model call failed: {written['failed']}"
        return SystemSteps(status="failed", **head, find=find, pull=pull, combine=combine, answer=answer)
    facts, left_out = _pulled(rd, plan, written)
    by_n = {f.n: f for f in facts}
    numbers = {f.item: f.n for f in facts}
    done = rd.try_json(ANSWER_FILE)
    done = done if isinstance(done, dict) else {}
    if plan.answer_by == "written":
        w = written or {}
        sentences = [CombineLine(text=str(s.get("text", "")), facts=[int(n) for n in s.get("facts") or []])
                     for s in w.get("sentences") or []]
        cited = list(dict.fromkeys(n for s in sentences for n in s.facts if n in by_n))
        rows = [CombineLine(text=by_n[n].text, facts=[n]) for n in cited]
        answer = AnswerRow(text=str(w.get("answer_text") or ""), status=str(w.get("status") or ""),
                           problems=[str(p) for p in w.get("problems") or []], lines=sentences)
    elif plan.answer_by == "lines":
        rows = [CombineLine(text=f"{ln.get('question')}: {len(ln.get('rows') or [])} found", facts=[])
                for ln in done.get("lines") or []]
        answer = AnswerRow(text=str((done.get("answer") or {}).get("text") or ""), status="ok", problems=[], lines=[])
    else:
        protocol = parse(rd.file(PROTOCOL_FILE).read_text(encoding="utf-8"))
        lines = kind_lines(protocol, done.get("synthesis") or {}, plan_names(plan))
        rows = _kind_rows(numbers, [ln for ln in lines if ln.study])
        answer = AnswerRow(text="\n".join(ln.text for ln in lines), status="ok", problems=[],
                           lines=_kind_rows(numbers, [ln for ln in lines if not ln.study]))
    return SystemSteps(status="done", **head, find=_find(rd, facts),
                       pull=PullRow(count=len(facts), left_out=left_out, facts=facts),
                       combine=CombineRow(rule=rule, count=len(rows), rows=rows), answer=answer)


def evsystem_router(settings: Settings) -> APIRouter:
    """The read-only system API under /api/ev/system: the folders and questions with their plan states, the four rows
    of a plan run, a paper of the run's corpus with the run's items marked."""
    api = APIRouter(generate_unique_id_function=lambda route: route.name)
    review = ReviewFiles(settings)

    @api.get("/system/domains", response_model=list[SysDomain], tags=["system"])
    def system_domains() -> list[SysDomain]:
        plans = Path(settings.synth3_data) / "plans"
        out: list[SysDomain] = []
        for domain, why in review.domains():
            seeds = review.built_seeds(domain)
            if why is not None:
                out.append(SysDomain(domain=domain, seeds=seeds, questions=[], error=why))
                continue
            try:
                qs = review.questions(domain, review.spec(domain))
            except (Conflict, NotFound) as err:
                out.append(SysDomain(domain=domain, seeds=seeds, questions=[], error=str(err)))
                continue
            out.append(SysDomain(domain=domain, seeds=seeds, error=None, questions=[
                SysQuestion(id=q.id, question=q.question, sub_questions=q.sub_questions, kind=q.kind,
                            target=q.target, plan=plan_state(plans, domain, q)) for q in qs.questions]))
        return out

    @api.get("/system/runs/{rid}/steps", response_model=SystemSteps, tags=["system"])
    def system_steps(rid: str) -> SystemSteps:
        return steps_of(system_run(settings, rid))

    @api.get("/system/runs/{rid}/program", response_class=Response, tags=["system"],
             responses={200: {"content": {"text/x-python": {}}}})
    def system_program(rid: str) -> Response:
        """The run's readable program as a download; 409 with the refusal text when the run cannot be rebuilt.
        Nothing is written into the run folder."""
        run = system_run(settings, rid)
        why = _refused(run)
        if why is not None:
            raise Conflict(why)
        try:
            data = program_of_run(run).encode("utf-8")
        except NotRebuilt as exc:
            raise Conflict(str(exc)) from exc
        except Exception as exc:   # a run that cannot be read or a text that cannot be encoded: a refusal, never a 500
            raise Conflict(refusal(run) or f"{type(exc).__name__}: {exc}") from exc
        return Response(data, media_type="text/x-python; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{rid}-answer.py"'})

    @api.get("/system/runs/{rid}/papers/{doc}", response_model=SystemPaper, tags=["system"])
    def system_paper(rid: str, doc: str) -> SystemPaper:
        run = system_run(settings, rid)
        check_id(doc, "paper")
        rd = RunDir(run)
        corpus = rd.settings.corpus if rd.settings else None
        if not corpus or not (Path(corpus) / "manifest.json").is_file():
            raise NotFound(f"run {rid!r} names no corpus")
        _entry, text = EvidenceFiles(settings)._paper_text(Path(corpus), doc)
        index = PaperIndex.of_corpus(corpus)
        marks = [(int(sp.selector["start"]), int(sp.selector["end"]), i.item_id, sp.role)
                 for i in rd.items() if index.find(i) == doc for sp in i.spans]
        return SystemPaper(paper=doc, text=text, segments=segments(text, marks))

    return api
