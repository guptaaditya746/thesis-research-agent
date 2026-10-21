"""Atomic Results statements: every value a level writes in prose is first written as one checked sentence.

EV1 Step 10 failed three whole-paper attempts on one sentence ("... yields 662 out of 1,000 answers judged
factually correct" never names the metric as planned). So the LLM renderer asks the model, in one call per
paper, for one sentence per prose value; code checks each sentence alone with the paper checks that apply
to a single sentence (the value and, where the level names it verbatim, the metric; the association of
`assoc`; no other number; the level's wording for explicit and paraphrased); failed sentences go back in a
repair call that carries only them, their rejected text and their failed checks. The paper is then
composed around the accepted sentences, which it must hold verbatim. Table values get no statement.
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from pydantic import BaseModel

from agent import anchor
import modelcall
from synth import assoc, fidelity, levelcheck
from synth.fidelity import Check
from synth.levels import Plan
from synth.text import Placement

PROSE_FORMATS = ("pct", "frac", "count", "relative")     # cell_pct and cell_raw are table cells
HEADER = "Statement tasks:"
REPAIR_HEADER = "Statement tasks (repair; rewrite only these sentences):"
# The level checks that hold for one sentence; the others are about tables and the whole paper.
LEVEL_CHECKS = {"explicit": levelcheck._explicit, "paraphrased": levelcheck._paraphrased}


@dataclass(frozen=True)
class StatementTask:
    id: str                 # the measurement id
    condition_name: str
    metric_phrase: str
    dataset: str
    value_text: str
    level: str
    fmt: str
    compared_with: str | None = None    # the control's name, for a relative value
    plan: Plan = field(repr=False, compare=False, default=None)  # type: ignore[assignment]

    @property
    def metric_required(self) -> bool:
        """Explicit names the metric verbatim; paraphrased has only its description; complex accepts an alias."""
        return self.level in ("explicit", "paraphrased")

    def json(self) -> dict:
        out = {"id": self.id, "level": self.level, "condition": self.condition_name, "metric": self.metric_phrase,
               "dataset": self.dataset, "value": self.value_text}
        return out | ({"compared_with": self.compared_with} if self.compared_with else {})


class StatementText(BaseModel):
    id: str
    text: str


class StatementReply(BaseModel):
    statements: list[StatementText]


def plan_statements(plan: Plan) -> list[StatementTask]:
    """One task per measurement the level writes in prose, in plan order."""
    control = plan.study.condition(plan.study.control_role).id if plan.study.relevant else None
    out = []
    for m in plan.measurements:
        seg = plan.values[m.id]
        if seg.fmt not in PROSE_FORMATS:
            continue
        out.append(StatementTask(m.id, plan.cond_name[m.condition], plan.metric_name[m.metric], m.dataset, seg.text,
                                 plan.level, seg.fmt, plan.cond_name[control] if seg.fmt == "relative" else None,
                                 plan))
    return out


def check(task: StatementTask, text: str) -> list[Check]:
    """The paper checks that apply to one sentence, run on the sentence alone."""
    plan, index, problems = task.plan, anchor.Index(text), []
    ps: list[Placement] = []
    try:
        sel = anchor.find(index, task.value_text)
        ps.append(Placement(task.id, "value", plan.paper, sel.start, sel.end, sel.exact, task.fmt))
    except anchor.AnchorError as exc:
        problems.append(f"{task.id}/value: required string {task.value_text!r} is {exc.reason}")
    if task.metric_required and not levelcheck.occurs(text, task.metric_phrase):
        problems.append(f"{task.id}/metric_label: required string {task.metric_phrase!r} is not_found; "
                        "write the metric exactly as given in the sentence")
    body = text.strip()
    several = "\n" in body or ". " in body or not body.endswith(".")
    checks = [Check("one_sentence", not several, "write one sentence, on one line, ending with a full stop"
                    if several else ""),
              Check("required_strings", not problems, "; ".join(problems))]
    if not ps:
        return checks
    ps += [Placement(f, role, plan.paper, a, b, text[a:b]) for f, role, a, b, _ in levelcheck.renderings(text, plan)]
    checks += [fidelity._check("values_associated", assoc.associations(text, plan, ps)),
               fidelity._check("added_numbers", fidelity.added_numbers(text, plan, ps, []))]
    if task.level in LEVEL_CHECKS:
        checks.append(fidelity._check(f"level_{task.level}", LEVEL_CHECKS[task.level](text, plan, ps)))
    return checks


def prompt(plan: Plan, tasks: list[StatementTask], rejected: dict[str, tuple[str, list[Check]]] | None = None) -> str:
    """The user prompt: the tasks, and for a repair each one's rejected sentence and failed checks."""
    items = []
    for t in tasks:
        item = t.json()
        if rejected and t.id in rejected:
            text, failed = rejected[t.id]
            item |= {"rejected": text, "failed_checks": [f"{c.name}: {c.detail}" for c in failed]}
        items.append(item)
    head = REPAIR_HEADER if rejected else HEADER
    return head + "\n" + json.dumps({"paper": plan.paper, "tasks": items}, indent=2, ensure_ascii=False)


Call = Callable[[str, int], Awaitable[dict]]


async def write(plan: Plan, call: Call, rounds: int, seed: int) -> tuple[dict[str, str], dict]:
    """Accepted sentences by task id, and the record {"rounds": calls made, "failed": ids never accepted}.
    `call(prompt, seed)` returns a StatementReply as a dict and may raise; a failed call fails every task
    of its round. Round r uses seed + r - 1, so an identical repair prompt cannot replay a cached reply."""
    tasks = plan_statements(plan)
    accepted: dict[str, str] = {}
    rejected: dict[str, tuple[str, list[Check]]] = {}
    done = 0
    for r in range(1, rounds + 1):
        todo = [t for t in tasks if t.id not in accepted]
        if not todo:
            break
        done = r
        try:
            reply = StatementReply.model_validate(await call(prompt(plan, todo, rejected or None), seed + r - 1))
            got = {s.id: s.text.strip() for s in reply.statements}
        except modelcall.ModelCallError as exc:  # a dead server or a malformed reply fails the round
            failure = Check("model_call", False, exc.reason)
            rejected = {t.id: ("", [failure]) for t in todo}
            continue
        except Exception as exc:  # a cached reply that no longer decodes, too
            failure = Check("model_call", False, modelcall.redact(f"{type(exc).__name__}: {exc}"))
            rejected = {t.id: ("", [failure]) for t in todo}
            continue
        rejected = {}
        for t in todo:
            if t.id not in got:
                rejected[t.id] = ("", [Check("missing", False, f"no sentence with id {t.id!r} in the reply")])
                continue
            failed = [c for c in check(t, got[t.id]) if not c.ok]
            if failed:
                rejected[t.id] = (got[t.id], failed)
            else:
                accepted[t.id] = got[t.id]
    ordered = {t.id: accepted[t.id] for t in tasks if t.id in accepted}
    return ordered, {"rounds": done, "failed": [t.id for t in tasks if t.id not in accepted]}


def missing(text: str, accepted: dict[str, str]) -> list[str]:
    """Problems for every accepted statement the paper does not hold exactly once, verbatim."""
    index, bad = anchor.Index(text), []
    for sid, sentence in accepted.items():
        try:
            anchor.find(index, sentence)
        except anchor.AnchorError as exc:
            bad.append(f"{sid}/statement: required sentence {sentence!r} is {exc.reason}")
    return bad
