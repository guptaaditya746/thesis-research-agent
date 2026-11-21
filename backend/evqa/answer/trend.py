"""Answer for trend questions (the measure over time, or over dose): ordered rows and a direction per group. Code only.

Axis = spec.trend_by (time_point or dose; Spec keeps it an open column). The other open columns (and the subject
when there are several) split the rows into groups; in each group the points are ordered by the axis (canon.sort_key:
'12 wk' < '24 wk' < '12 mo', '5 mg' < '10 mg'). Values at one axis point within the rounding step merge into one
point (all their rows kept); values further apart make the group's direction "unclear" (they are also listed in
Answer.conflicts when they come from different papers). Rows with no stated axis value are left out of the series.

Direction from consecutive points: a step above the rounding step (one unit of the last printed decimal of the
less precise value) goes up, below minus the step goes down, else flat.
  all flat -> "flat"; only down (and flat) -> "decreasing"; only up (and flat) -> "increasing"; both -> "mixed";
  one point -> "one point".
"""
from __future__ import annotations

from decimal import Decimal

from evqa.answer import canon
from evqa.answer.core import (NOT_REPORTED, NOT_STATED, _common_unit, _fmt, _group_cells, fits, step_of, table,
                              with_conflicts)
from evqa.contracts import Answer, Row, Spec, TrendSeries


def direction(values: list[Decimal], steps: list[Decimal]) -> str:
    """Direction of an ordered series; steps[k] is the rounding step between values k and k+1."""
    if len(values) < 2:
        return "one point"
    moves = {"down" if y - x < -s else "up" if y - x > s else "flat"
             for x, y, s in zip(values, values[1:], steps, strict=False)}
    moves.discard("flat")
    if not moves:
        return "flat"
    return "mixed" if len(moves) > 1 else {"down": "decreasing", "up": "increasing"}[moves.pop()]


def trend(spec: Spec, rows: list[Row]) -> Answer:
    axis = spec.trend_by or "time_point"
    cols = list(spec.columns)
    if not any(canon.slot(c) == axis for c in cols):
        cols.append(axis)
    if len(spec.subjects) > 1 and not any(canon.slot(c) == "subject" for c in cols):
        cols = ["subject", *cols]
    axis_col = next(c for c in cols if canon.slot(c) == axis)
    by_cols = [c for c in cols if c != axis_col]
    used = [(i, r) for i, r in enumerate(rows) if fits(r, spec, index=i)]
    ans = Answer(qid=spec.qid, type="trend", columns=cols)
    if not used:
        ans.not_reported, ans.sentence = True, NOT_REPORTED
        return ans
    ans.table = table(used, [(c, canon.slot(c)) for c in cols])
    cells = {c: _group_cells(used, canon.slot(c)) for c in cols}
    groups: dict[tuple[str, ...], list[tuple[int, Row]]] = {}
    for i, r in used:
        if cells[axis_col][i] != NOT_STATED:
            groups.setdefault(tuple(cells[c][i] for c in by_cols), []).append((i, r))
    order = sorted(groups, key=lambda g: tuple(canon.sort_key(canon.slot(c), v)
                                               for c, v in zip(by_cols, g, strict=True)))
    for g in order:
        grp = groups[g]
        unit, vals = _common_unit(grp)
        at: dict[str, list[tuple[int, Row]]] = {}
        for i, r in grp:
            if i in vals:
                at.setdefault(cells[axis_col][i], []).append((i, r))
        points, values, decimals, unclear = [], [], [], []
        for x in sorted(at, key=lambda v: canon.sort_key(axis, v)):
            here = at[x]
            hv = [vals[i] for i, _ in here]
            step = step_of([r.std.decimals for _, r in here])
            if max(hv) - min(hv) > step:
                unclear.append(x)
            i0, r0 = here[0]
            points.append({"at": x, "value": str(vals[i0]), "unit": unit,
                           "papers": sorted({r.paper for _, r in here}), "rows": [i for i, _ in here]})
            values.append(vals[i0])
            decimals.append(min(r.std.decimals for _, r in here))
        steps = [step_of([d1, d2]) for d1, d2 in zip(decimals, decimals[1:], strict=False)]
        s = TrendSeries(group=dict(zip(by_cols, g, strict=True)), axis=axis_col, points=points,
                        direction=direction(values, steps))
        if unclear:
            s.direction = "unclear"
            s.note = "the papers give different values at " + ", ".join(unclear)
        ans.trend.append(s)
    parts = []
    for s in ans.trend:
        where = ", ".join(s.group.values()) or "all"
        pts = ", ".join(f"{p['at']} {_fmt(p['value'], p['unit'])}" for p in s.points)
        parts.append(f"{where}: {s.direction} ({pts})")
    ans.sentence = (f"{', '.join(n.label for n in spec.subjects)}, {spec.measure.label} by {axis_col.replace('_', ' ')}"
                    f": " + "; ".join(parts) + ".")
    return with_conflicts(ans, used)
