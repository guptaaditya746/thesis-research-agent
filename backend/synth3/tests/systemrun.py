"""Helpers that run the evidence plan run on a synth3 folder with fake models (no call leaves the machine): a demo
plan for a question, the plans of a whole question set, fake writer replies, and `make_system_run`."""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from evidence import planrun
from evidence.plan import Decision, Plan, WordList, with_answer, write_plan
from evidence.tests.conftest import provider_of
from evidence.tests.test_plan_run import make_plan
from evidence.tests.test_written_stage import writer_model
from synth3.questions import Question, QuestionSet, answer_by_of, target_of
from synth3.sheetfacts import Folder

WHEN = "2026-11-03T10:00:00+00:00"

OK_REPLY = lambda prompt: {"sentences": [{"text": "The papers cannot tell.", "says": "cannot_tell", "facts": []}]}


def FACT_REPLY(prompt: str) -> dict[str, Any]:
    """One finding that cites fact 1 when the input lists it, else OK_REPLY's reply."""
    if re.search(r"^\[1\] ", prompt, re.M):
        return {"sentences": [{"text": "A paper measured it.", "says": "finding", "facts": [1]}]}
    return OK_REPLY(prompt)


def demo_plan(SPEC, q: Question, answer_by: str = "written", target: str | None = None,
              confirmed: str | None = "aditya") -> Plan:
    """A confirmed plan for `q` over the demo spec's things, the lines of test_plan_run.make_plan (effect, oversell)."""
    base = make_plan(field="medicine", measures=("response_rate",))
    stamp = {"confirmed_by": confirmed, "confirmed_at": WHEN if confirmed else None}
    things = {"targeted": ["Targeted therapy"], "standard": ["Standard care"], "response_rate": ["Response rate"]}
    decisions = [Decision(id="d1", type="threshold", value="0.01", reason="noise", **stamp),
                 Decision(id="direction:response_rate", type="direction", value="higher", reason="its direction",
                          **stamp),
                 Decision(id="main_rule", type="main_rule", value="any_line", reason="any line", **stamp)]
    plan = base.model_copy(update={
        "question": q.question, "sub_questions": list(q.sub_questions),
        "lines": [ln for ln in base.lines if ln.id in ("l1", "oversell")],
        "words": WordList(things=things, cues=base.words.cues, written_by="orch-model", ontology_names={}),
        "decisions": decisions, "measures": ["response_rate"]})
    return with_answer(plan, answer_by, target)


def write_demo_plans(root: Path, qs: QuestionSet, SPEC, confirmed: str | None = "aditya") -> None:
    """`demo_plan` of every question at `root / "demo" / "<id>.json"`."""
    (root / "demo").mkdir(parents=True, exist_ok=True)
    for q in qs.questions:
        write_plan(demo_plan(SPEC, q, answer_by_of(q), target_of(q), confirmed), root / "demo" / f"{q.id}.json")


def system_model(writer_reply: Callable[[str], Any] = OK_REPLY):
    return writer_model([], writer_reply)


def make_system_run(out: Path, folder: Folder, q: Question, plan: Plan, *, writer_reply=OK_REPLY,
                    run_id: str | None = None) -> Path:
    """Write the plan beside `out`, run it on the folder with fake models, return the run folder."""
    out.parent.mkdir(parents=True, exist_ok=True)
    path = out.parent / f"{out.name}-plan.json"
    write_plan(plan, path)
    return planrun.run(path, folder.path, out, cache=out.parent / "cache", run_id=run_id or q.id,
                       selection="regex-only", reason="off", links="off", workers=1,
                       provider=provider_of(system_model(writer_reply)))
