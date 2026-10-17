"""Is each value written next to its own condition, metric and dataset?

Locating a value string proves the number is in the paper, not that it is attached to the right fact: a
writer that swaps the rag and baseline numbers passes every presence check while the ground truth then
says the opposite effect. So, where a value is written:

- in a table: its row names its condition (full name or code) and no other; its column header names its
  metric and no other; with a Dataset column, the row's dataset cell is its dataset;
- in prose: its sentence names its condition and no other condition, its metric and no other metric, and
  (with several datasets) its dataset and no other; a relative value ("7.0 percentage points higher than
  the B") names its own condition before the value and the baseline after it, and nothing else.
"""
from __future__ import annotations

from synth.levelcheck import sentence_of
from synth.levels import Plan
from synth.text import Placement


def table_block(text: str, pos: int) -> list[tuple[int, int]]:
    """(start, end) of each line of the Markdown table containing `pos`; empty if `pos` is not in one."""
    lines, start = [], 0
    for line in text.split("\n"):
        lines.append((start, start + len(line), line.startswith("|")))
        start += len(line) + 1
    at = next((i for i, (a, b, _) in enumerate(lines) if a <= pos <= b), None)
    if at is None or not lines[at][2]:
        return []
    lo = hi = at
    while lo > 0 and lines[lo - 1][2]:
        lo -= 1
    while hi + 1 < len(lines) and lines[hi + 1][2]:
        hi += 1
    return [(a, b) for a, b, _ in lines[lo:hi + 1]]


def cells(text: str, a: int, b: int) -> list[tuple[int, int]]:
    """Spans of a table line's cells, index 0 being the empty piece before the first '|'."""
    out, start = [], a
    for piece in text[a:b].split("|"):
        out.append((start, start + len(piece)))
        start += len(piece) + 1
    return out


def facts_in(ps: list[Placement], role: str, a: int, b: int, skip: Placement | None = None) -> list[Placement]:
    return [q for q in ps if q.role == role and a <= q.start and q.end <= b and q is not skip]


def _table(text: str, plan: Plan, ps: list[Placement], p: Placement, block: list[tuple[int, int]]) -> list[str]:
    m = next(x for x in plan.measurements if x.id == p.fact)
    row = next((a, b) for a, b in block if a <= p.start <= b)
    if row == block[0] or len(block) < 3:
        return [f"{p.fact}: value {p.exact!r} in a table header"]
    bad = []
    named = {q.fact for q in facts_in(ps, "condition_label", *row)}
    if named != {m.condition}:
        bad.append(f"{p.fact}: its row names {sorted(named)}, not only {m.condition}")
    row_cells, head_cells = cells(text, *row), cells(text, *block[0])
    col = text[row[0]:p.start].count("|")
    if col >= len(head_cells):
        return bad + [f"{p.fact}: its column has no header"]
    header = {q.fact for q in facts_in(ps, "metric_label", *head_cells[col])}
    if header != {m.metric}:
        bad.append(f"{p.fact}: its column header names {sorted(header)}, not only {m.metric}")
    ds_col = next((i for i, (a, b) in enumerate(head_cells) if text[a:b].strip().lower() == "dataset"), None)
    if ds_col is not None and ds_col < len(row_cells):
        a, b = row_cells[ds_col]
        if text[a:b].strip() != m.dataset:
            bad.append(f"{p.fact}: its row is for dataset {text[a:b].strip()!r}, not {m.dataset!r}")
    elif len(plan.datasets) > 1:
        bad.append(f"{p.fact}: a table over several datasets without a Dataset column")
    return bad


def _prose(text: str, plan: Plan, ps: list[Placement], p: Placement) -> list[str]:
    m = next(x for x in plan.measurements if x.id == p.fact)
    a, b = sentence_of(text, p.start, p.end)
    conds = facts_in(ps, "condition_label", a, b, skip=p)
    bad = []
    if p.fmt == "relative":
        base = plan.study.condition(plan.study.control_role).id
        before = [q.fact for q in conds if q.end <= p.start]
        after = [q.fact for q in conds if q.start >= p.end]
        if not before or before[-1] != m.condition or not after or after[0] != base \
                or {q.fact for q in conds} != {m.condition, base}:
            bad.append(f"{p.fact}: the relative value must name {m.condition} before it and {base} after it")
    elif {q.fact for q in conds} != {m.condition}:
        bad.append(f"{p.fact}: its sentence names {sorted({q.fact for q in conds})}, not only {m.condition}")
    metrics = {q.fact for q in facts_in(ps, "metric_label", a, b, skip=p)}
    if metrics != {m.metric}:
        bad.append(f"{p.fact}: its sentence names metrics {sorted(metrics)}, not only {m.metric}")
    if len(plan.datasets) > 1:
        named = [d for d in plan.datasets if d in text[a:b]]
        if named != [m.dataset]:
            bad.append(f"{p.fact}: its sentence names datasets {named}, not only {m.dataset}")
    return bad


def associations(text: str, plan: Plan, ps: list[Placement]) -> list[str]:
    bad: list[str] = []
    for p in ps:
        if p.role != "value":
            continue
        block = table_block(text, p.start)
        bad += _table(text, plan, ps, p, block) if block else _prose(text, plan, ps, p)
    return bad
