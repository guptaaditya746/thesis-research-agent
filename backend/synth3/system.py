"""The system under test: the evidence plan run, answering the benchmark questions. One part plans every question
(a draft per question, kept on a second run); the other collects a finished plan run into the judge's `AnswerRecord`
(the text only; no sub-question and no system name reaches a judge)."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from evaluation.planbatch import PLANNER_CACHE, orch_lm, saved_templates  # noqa: F401  (tests replace orch_lm)
from evidence.kindtext import kind_lines, plan_names
from evidence.plan import Plan, load_plan, with_answer, write_plan
from evidence.plankinds import answer_problems
from evidence.planner import check_plan, critic, propose, using
from evidence.words.write import write_words
from modelcall import ModelCallError, redact
from evidence.protocol import parse
from evidence.rundir import ANSWER_FILE, PLAN_FILE, PROTOCOL_FILE, RUN_FILE, RunDir
from synth3.answers import MAX_TEXT, AnswerRecord, PaperIndex, cited_papers, pulled_facts
from synth3.questions import Question, answer_by_of, asked_sha256, question_sha256, target_of
from synth3.questions import QuestionSet
from synth3.sheetfacts import Folder
from synth3.spec import SPECS

SYSTEM = "system"
WRITTEN_FILE = "written-answer.json"
PLANS = SPECS / "plans"


def plan_path(root: Path, domain: str, qid: str) -> Path:
    return root / domain / f"{qid}.json"


def auto_path(root: Path, domain: str, qid: str) -> Path:
    return root / domain / "auto" / f"{qid}.json"


def draft_plan(q: Question, lm, templates: Mapping[str, str]) -> Plan:
    """The planner's draft for one question, with its sub-questions and its answer kind. No clarifying questions
    (a batch has no one to answer them; the plan page asks them). Nothing is confirmed."""
    with using(lm):
        plan, _how = propose(q.question, [], sub_questions=q.sub_questions,
                             write_words=lambda t, th: write_words(t, th, lm=lm), templates=templates)
        plan = critic(plan)
    return with_answer(plan, answer_by_of(q), target_of(q))


def plan_stale(plan: Plan, q: Question) -> str | None:
    if plan.question != q.question or plan.sub_questions != q.sub_questions:
        return "the question changed after planning"
    return None


def _move_aside(path: Path) -> Path:
    """Move a plan file to `<qid>.stale-<n>.json` beside it; never deletes."""
    n = 1
    while (dest := path.with_name(f"{path.stem}.stale-{n}.json")).exists():
        n += 1
    path.replace(dest)
    return dest


def plan_domain(domain: str, qs: QuestionSet, root: Path, lm, templates: Mapping[str, str], *,
                redo: set[str] = frozenset(), redo_lm=None) -> dict:
    """Draft a plan for each question that has none (or a stale one, or is in `redo`); keep the rest. A changed
    kind or target is set in place (the planner's work does not depend on it; confirmations stay)."""
    out: dict = {"drafted": [], "kept": [], "rekinded": [], "failed": {}, "problems": {}}
    for q in qs.questions:
        path = plan_path(root, domain, q.id)
        try:
            old = load_plan(path) if path.is_file() else None
            if old is None or q.id in redo or plan_stale(old, q) is not None:
                if old is not None:
                    _move_aside(path)
                plan = draft_plan(q, redo_lm if q.id in redo else lm, templates)
                path.parent.mkdir(parents=True, exist_ok=True)
                write_plan(plan, path)
                out["drafted"].append(q.id)
            elif (old.answer_by, old.target) != (answer_by_of(q), target_of(q)):
                write_plan(with_answer(old, answer_by_of(q), target_of(q)), path)
                out["rekinded"].append(q.id)
            else:
                out["kept"].append(q.id)
        except (ModelCallError, ValueError, RuntimeError) as err:
            out["failed"][q.id] = redact(str(err))
    for q in qs.questions:
        path = plan_path(root, domain, q.id)
        if not path.is_file():
            continue
        try:
            plan = load_plan(path)
        except ValueError as err:
            out["problems"][q.id] = [redact(str(err))]
            continue
        found = [*check_plan(plan, templates), *answer_problems(plan)]
        if found:
            out["problems"][q.id] = found
    return out


def is_plan_run(run: Path) -> bool:
    """True when run.json says the run is a plan run (`settings.stage_set == "plan"`)."""
    record = RunDir(run).try_json(RUN_FILE)
    settings = record.get("settings") if isinstance(record, dict) else None
    return isinstance(settings, dict) and settings.get("stage_set") == "plan"


def confirmed_by(plan: Plan) -> str:
    """"system" when any decision was confirmed by the system, else "person"."""
    return "system" if any(d.confirmed_by == SYSTEM for d in plan.decisions) else "person"


def _refuse(run: Path, why: str) -> ValueError:
    return ValueError(f"{run}: {why}")


def from_system_run(run: Path, folder: Folder, q: Question, system: str = SYSTEM) -> AnswerRecord:
    rd = RunDir(run)
    if rd.state != "complete":
        raise _refuse(run, f"the run is not complete (state {rd.state})")
    record = rd.json(RUN_FILE)
    named = record.get("corpus_id") if isinstance(record, dict) else None
    if named != folder.corpus_id:
        raise _refuse(run, f"the run is of corpus {named!r}, the folder is {folder.corpus_id!r}; "
                           "a run on another corpus is refused")
    plan = load_plan(rd.file(PLAN_FILE))
    if plan.question != q.question or plan.sub_questions != q.sub_questions:
        raise _refuse(run, "the run was planned for another version of the question")
    want, target = answer_by_of(q), target_of(q)
    if plan.answer_by != want or plan.target != target:
        raise _refuse(run, f"the run answers by {plan.answer_by}, the question asks for {want}")
    left_out = None
    if plan.answer_by == "written":
        written = rd.json(WRITTEN_FILE)
        if not isinstance(written, dict):
            raise _refuse(run, "the run has no written answer")
        if "failed" in written:
            raise _refuse(run, f"the written answer's model call failed: {written['failed']}; "
                               "run it again with retry")
        text = written["answer_text"] if written.get("status") in ("ok", "no_facts") else ""
        left_out = sum(written["cut"]["left_out"].values())
    else:
        protocol = parse((rd.file(PROTOCOL_FILE)).read_text(encoding="utf-8"))
        answer = rd.json(ANSWER_FILE)
        text = "\n".join(line.text for line in kind_lines(protocol, answer["synthesis"], plan_names(plan)))
    cut = len(text) > MAX_TEXT
    if cut:
        text = text[:MAX_TEXT] + f"\n[cut at {MAX_TEXT} characters]"
    return AnswerRecord(domain=folder.spec.domain, seed=folder.seed, corpus_id=folder.corpus_id, question_id=q.id,
                        question_sha256=question_sha256(q), system=system, text=text, text_cut=cut,
                        cited=cited_papers(text, PaperIndex.of_corpus(folder.path).ids),
                        facts=pulled_facts(run, folder), passages=[], source=str(run),
                        asked_sha256=asked_sha256(q), plan_confirmed_by=confirmed_by(plan),
                        facts_left_out=left_out)
