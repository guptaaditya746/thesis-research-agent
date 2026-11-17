"""The system under test: the evidence plan run, answering the benchmark questions. This part collects a finished
plan run into the judge's `AnswerRecord` (the text only; no sub-question and no system name reaches a judge)."""
from __future__ import annotations

from pathlib import Path

from evidence.kindtext import kind_lines, plan_names
from evidence.plan import Plan, load_plan
from evidence.protocol import parse
from evidence.rundir import ANSWER_FILE, PLAN_FILE, PROTOCOL_FILE, RUN_FILE, RunDir
from synth3.answers import MAX_TEXT, AnswerRecord, PaperIndex, cited_papers, pulled_facts
from synth3.questions import Question, answer_by_of, asked_sha256, question_sha256, target_of
from synth3.sheetfacts import Folder

SYSTEM = "system"
WRITTEN_FILE = "written-answer.json"


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
