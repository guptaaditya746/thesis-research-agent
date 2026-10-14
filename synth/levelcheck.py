"""The defining property of each difficulty level, checked on a rendered paper.

Used by the fidelity check (an LLM may ignore its level instructions) and by the tests (the template
renderer must always satisfy them). Each function returns a list of problems; empty means the paper has
the level's property.
"""
from __future__ import annotations

import re

from evidence import rules
from synth.levels import Plan
from synth.text import Decoy, Placement

DISTANCE = 300   # characters between the last code definition and the table (distributed)


def table_lines(text: str) -> list[tuple[int, int]]:
    """(start, end) of every Markdown table line."""
    out, pos = [], 0
    for line in text.split("\n"):
        if line.startswith("|"):
            out.append((pos, pos + len(line)))
        pos += len(line) + 1
    return out


def in_table(text: str, start: int) -> bool:
    return any(a <= start < b for a, b in table_lines(text))


def sentence_of(text: str, start: int, end: int) -> tuple[int, int]:
    """The sentence around [start, end): bounded by '. ' or a line break (decimal points have no space)."""
    a = max(text.rfind(". ", 0, start) + 2, text.rfind("\n", 0, start) + 1, 0)
    ends = [i for i in (text.find(". ", end), text.find("\n", end)) if i >= 0]
    return a, min(ends) if ends else len(text)


def occurs(text: str, name: str) -> list[tuple[int, int]]:
    """Word-bounded occurrences; case-insensitive unless the name is a short code."""
    flags = 0 if len(name) <= 3 else re.IGNORECASE
    return [(m.start(), m.end()) for m in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, flags)]


def _explicit(text: str, plan: Plan, ps: list[Placement]) -> list[str]:
    bad = [f"table line at {a}" for a, _ in table_lines(text)]
    for p in ps:
        if p.role != "value":
            continue
        m = next(x for x in plan.measurements if x.id == p.fact)
        a, b = sentence_of(text, p.start, p.end)
        inside = [q for q in ps if a <= q.start and q.end <= b]
        if not any(q.fact == m.condition and q.exact == plan.cond_name[m.condition] for q in inside):
            bad.append(f"{p.fact}: its sentence does not name the condition verbatim")
        if not any(q.fact == m.metric and q.exact == plan.metric_name[m.metric] for q in inside):
            bad.append(f"{p.fact}: its sentence does not name the metric verbatim")
        if m.dataset not in text[a:b]:
            bad.append(f"{p.fact}: its sentence does not name the dataset")
    return bad


def _paraphrased(text: str, plan: Plan, ps: list[Placement]) -> list[str]:
    bad = [f"label {c.label!r} used verbatim" for c in plan.conditions if occurs(text, c.label)]
    bad += [f"metric name {m.name!r} used verbatim" for m in plan.metrics if occurs(text, m.name)]
    fmts = {p.fmt for p in ps if p.role == "value"}
    if len(fmts) < 2:
        bad.append(f"values in only one format: {sorted(f or '' for f in fmts)}")
    return bad + [f"table line at {a}" for a, _ in table_lines(text)]


def _distributed(text: str, plan: Plan, ps: list[Placement]) -> list[str]:
    tables = table_lines(text)
    if not tables:
        return ["no table"]
    first = tables[0][0]
    bad = [f"{p.fact}: value outside the table" for p in ps if p.role == "value" and not in_table(text, p.start)]
    codes = {c: plan.cond_aliases[c][0] for c in plan.cond_aliases}
    for cid, code in codes.items():
        defs = [p for p in ps if p.fact == cid and p.exact == code and not in_table(text, p.start)]
        if not defs:
            bad.append(f"{cid}: code {code!r} never defined outside the table")
        elif max(p.end for p in defs) > first - DISTANCE:
            bad.append(f"{cid}: code {code!r} defined within {DISTANCE} characters of the table")
        if any(in_table(text, a) for a, _ in occurs(text, plan.cond_name[cid])):
            bad.append(f"{cid}: full label inside the table")
    for p in ps:
        if p.role == "condition_label" and not in_table(text, p.start):
            a, b = sentence_of(text, p.start, p.end)
            if any(q.role == "value" and a <= q.start < b for q in ps):
                bad.append(f"{p.fact}: a sentence pairs a value with the condition")
    return bad


def _complex(text: str, plan: Plan, ps: list[Placement]) -> list[str]:
    bad = []
    if len(plan.datasets) < 2:
        bad.append("fewer than two datasets")
    if not any(m.canonical == "other" for m in plan.metrics):
        bad.append("no distractor metric")
    rel = [p for p in ps if p.role == "value" and p.fmt == "relative"]
    if [p.fact for p in rel] != [plan.study.effect.rag]:
        bad.append(f"expected one relative value for {plan.study.effect.rag}, got {[p.fact for p in rel]}")
    rows = [text[a:b] for a, b in table_lines(text)]
    for dataset in plan.datasets:
        if sum(f"| {dataset} |" in r for r in rows) != len(plan.conditions):
            bad.append(f"the table lacks rows for {dataset}")
    return bad


def _contradictory(text: str, plan: Plan, ps: list[Placement], decoys: list[Decoy]) -> list[str]:
    bad = []
    if rules.claim_agrees(plan.claim, plan.study.effect.direction):
        bad.append(f"claim {plan.claim!r} agrees with the effect {plan.study.effect.direction!r}")
    bad += [f"{p.fact}: value outside the table" for p in ps if p.role == "value" and not in_table(text, p.start)]
    for d in decoys:
        if abs(d.stated_value - plan.study.value_of(d.measurement)) < 0.005:
            bad.append(f"decoy for {d.measurement} equals the true value")
        if in_table(text, d.start):
            bad.append("decoy inside the table")
    return bad


def check_level(text: str, plan: Plan, placements: list[Placement], decoys: list[Decoy]) -> list[str]:
    if plan.level == "contradictory":
        return _contradictory(text, plan, placements, decoys)
    fn = {"explicit": _explicit, "paraphrased": _paraphrased, "distributed": _distributed,
          "complex": _complex}[plan.level]
    bad = fn(text, plan, placements)
    if plan.level != "contradictory" and not rules.claim_agrees(plan.claim, plan.study.effect.direction):
        bad.append("claim disagrees with the effect outside the contradictory level")
    return bad
