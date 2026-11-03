"""The defining property of each difficulty level, checked on a rendered paper.

Used by the fidelity check (an LLM may ignore its level instructions) and by the tests (the template
renderer must always satisfy them). Each function returns a list of problems; empty means the paper has
the level's property.
"""
from __future__ import annotations

import re

from synth.levels import Plan
from synth.text import Decoy, Placement
from synth.truth import DECOY_GAP

DISTANCE = 300   # characters between the last code definition and the table (distributed)


def table_lines(text: str) -> list[tuple[int, int]]:
    """(start, end) of every Markdown table line."""
    out, pos = [], 0
    for line in text.split("\n"):
        if line.startswith("|"):
            out.append((pos, pos + len(line)))
        pos += len(line) + 1
    return out


def section_at(text: str, offset: int) -> str:
    """The name of the '## ' section an offset falls in ('title' before the first one)."""
    head = text.rfind("\n## ", 0, offset + 1)
    if head < 0:
        return "title"
    end = text.find("\n", head + 4)
    return text[head + 4:end if end >= 0 else len(text)].strip()


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


def renderings(text: str, plan: Plan) -> list[tuple[str, str, int, int, bool]]:
    """(fact, role, start, end, is_main_name) of every rendering of a condition or metric name.

    A code or abbreviation counts only on a table line or in a sentence that also holds the fact's main
    name (its definition), so a stray 'Appendix B' is not condition B; descriptions count anywhere."""
    tables = table_lines(text)
    items = [(c, "condition_label", plan.cond_name[c], set(plan.cond_aliases[c]), plan.cond_aliases[c])
             for c in plan.cond_name]
    items += [(k, "metric_label", plan.metric_name[k], {plan.metric_of(k).abbr}, plan.metric_aliases[k])
              for k in plan.metric_name]
    out = []
    for fact, role, main, codes, aliases in items:
        mains = occurs(text, main)
        out += [(fact, role, a, b, True) for a, b in mains]
        for alias in aliases:
            for a, b in occurs(text, alias):
                s, e = sentence_of(text, a, b)
                if (alias not in codes or any(x <= a < y for x, y in tables)
                        or any(s <= ma and mb <= e for ma, mb in mains)):
                    out.append((fact, role, a, b, False))
    # A name inside another fact's longer main name (a --hard ablation, '<treatment> without <component>')
    # is part of that rendering, not one of its own.
    return [r for r in out if not any(f != r[0] and is_main and a <= r[2] and r[3] <= b and b - a > r[3] - r[2]
                                      for f, _, a, b, is_main in out)]


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
    bad += [f"metric abbreviation {m.abbr!r} used" for m in plan.metrics if occurs(text, m.abbr)]
    values = [p for p in ps if p.role == "value"]
    fmts = {p.fmt for p in values}
    if len(fmts) < min(2, len(values)):     # a --missing study may leave a single value to write
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
    for k in plan.metrics:
        defs = [p for p in ps if p.fact == k.id and p.exact == k.abbr and not in_table(text, p.start)]
        if not defs:
            bad.append(f"{k.id}: abbreviation {k.abbr!r} never defined outside the table")
        elif max(p.end for p in defs) > first - DISTANCE:
            bad.append(f"{k.id}: abbreviation {k.abbr!r} defined within {DISTANCE} characters of the table")
    for p in ps:
        if p.role == "condition_label" and not in_table(text, p.start):
            a, b = sentence_of(text, p.start, p.end)
            if any(q.role == "value" and a <= q.start < b for q in ps):
                bad.append(f"{p.fact}: a sentence pairs a value with the condition")
    return bad


def _complex(text: str, plan: Plan, ps: list[Placement]) -> list[str]:
    bad = []
    if len(plan.datasets) < min(2, len(plan.study.datasets)):    # a network study has one dataset, its population
        bad.append("fewer than two datasets")
    if not any(m.canonical == "other" for m in plan.metrics):
        bad.append("no distractor metric")
    rel = [p for p in ps if p.role == "value" and p.fmt == "relative"]
    want = [plan.study.effect.treatment] if plan.study.missing is None else []   # no relative value without the pair
    if [p.fact for p in rel] != want:
        bad.append(f"expected relative values for {want}, got {[p.fact for p in rel]}")
    rows = [text[a:b] for a, b in table_lines(text)]
    if plan.experiments:                # --hard: one row per experiment, dataset and condition
        if not rows or not rows[0].startswith("| System | Experiment | Dataset |"):
            bad.append("the table has no Experiment column")
        for e in plan.experiments:
            for dataset in e.datasets:
                if sum(f"| {e.name} | {dataset} |" in r for r in rows) != len(e.conditions):
                    bad.append(f"the table lacks rows for {e.name} on {dataset}")
        return bad
    if len(plan.datasets) == 1:         # no Dataset column: one row per condition under the header and separator
        if len(rows) - 2 != len(plan.conditions):
            bad.append(f"the table has {len(rows) - 2} rows, not one per condition ({len(plan.conditions)})")
        return bad
    for dataset in plan.datasets:
        if sum(f"| {dataset} |" in r for r in rows) != len(plan.conditions):
            bad.append(f"the table lacks rows for {dataset}")
    return bad


def _multi_experiment(text: str, plan: Plan, ps: list[Placement]) -> list[str]:
    """Every experiment has its own section (a study with one experiment: every dataset), the question metric's
    values are in prose, the other metrics' in tables, and no condition is called by its label's own table code."""
    bad = []
    sections = [f"### {e.name} experiment\n" for e in plan.experiments] if plan.experiments \
        else [f"### {d}\n" for d in plan.datasets]
    bad += [f"no section {s.strip()!r}" for s in sections if s not in text]
    q = plan.metrics[0].id
    for p in ps:
        if p.role != "value":
            continue
        m = next(x for x in plan.measurements if x.id == p.fact)
        if in_table(text, p.start) != (m.metric != q):
            bad.append(f"{p.fact}: a {'question' if m.metric == q else 'distractor'} metric value "
                       f"{'in a table' if in_table(text, p.start) else 'in prose'}")
    if len({p.fmt for p in ps if p.role == "value" and not in_table(text, p.start)}) < 2 \
            and len(plan.recipe.reporting.formats) > 1 and len(plan.measurements) > 2:
        bad.append("prose values in one format only")
    return bad


def _messy_tables(text: str, plan: Plan, ps: list[Placement]) -> list[str]:
    """One table: units in the header cells, a merged group cell row (the dataset's name, the covered cells empty),
    footnote marks on values (explained under the table), no value in prose."""
    bad = []
    rows = [text[a:b] for a, b in table_lines(text)]
    if not rows or not all(f"({'%' if k.unit == 'fraction' else 's'})" in rows[0] for k in plan.metrics):
        bad.append("the header row lacks the units")
    group = [r for r in rows[2:3]]
    if not group or group[0].split("|")[1].strip() or group[0].split("|")[2].strip() != plan.datasets[0] \
            or any(c.strip() for c in group[0].split("|")[3:-1]):
        bad.append("no merged group cell row under the header")
    values = [p for p in ps if p.role == "value"]
    bad += [f"{p.fact}: value outside the table" for p in values if not in_table(text, p.start)]
    if not any(p.exact[-1] in "*†‡" for p in values):
        bad.append("no value carries a footnote mark")
    return bad


def _contradictory(text: str, plan: Plan, ps: list[Placement], decoys: list[Decoy]) -> list[str]:
    bad = []
    if plan.claim == plan.study.claim:
        bad.append(f"claim {plan.claim!r} agrees with the effect {plan.study.effect.direction!r}")
    bad += [f"{p.fact}: value outside the table" for p in ps if p.role == "value" and not in_table(text, p.start)]
    for d in decoys:
        near = [m.id for m in plan.study.measurements if abs(d.stated_value - m.value) <= DECOY_GAP]
        if near:
            bad.append(f"decoy {d.exact!r} within {DECOY_GAP} of the true values of {near}")
        if in_table(text, d.start):
            bad.append("decoy inside the table")
    return bad


def check_irrelevant(text: str, plan: Plan, placements: list[Placement], decoys: list[Decoy]) -> list[str]:
    """A paper with no experiment (--irrelevant) places nothing: no fact, no decoy, no table."""
    bad = [f"{p.fact}/{p.role}: a placement in a paper with no experiment" for p in placements]
    bad += [f"decoy {d.exact!r} in a paper with no experiment" for d in decoys]
    return bad + [f"table line at {a}" for a, _ in table_lines(text)]


def check_level(text: str, plan: Plan, placements: list[Placement], decoys: list[Decoy]) -> list[str]:
    if not plan.study.relevant:
        return check_irrelevant(text, plan, placements, decoys)
    if plan.level == "contradictory":
        return _contradictory(text, plan, placements, decoys)
    fn = {"explicit": _explicit, "paraphrased": _paraphrased, "distributed": _distributed,
          "complex": _complex, "multi_experiment": _multi_experiment, "messy_tables": _messy_tables}[plan.level]
    bad = fn(text, plan, placements)
    if plan.level != "contradictory" and plan.claim != plan.study.claim:
        bad.append("claim disagrees with the effect outside the contradictory level")
    return bad
