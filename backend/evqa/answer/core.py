"""Answer: rows -> answer table, best-groups and one plain sentence. Code only, no LLM.

    answer = run(spec, rows)

Rows used: quote_ok, not dropped, a readable value, a spec subject, and every fixed slot of the spec matched
(time point and dose compared in canonical form, "24 weeks" = "week 24"; patient group by canon.group of the label).
Settings (plan v2): with links (extract/links.py) a row fits a fixed setting only when its setting set is linked
"same" to the question; "unknown" goes to Answer.cant_tell (shown, never used or silently dropped); rows of sets
linked "same" share one label (the component's first set). Runs made before links: the older canon.group wording key.

lookup  one AnswerRow per distinct combination of the spec's columns (open points answered "all") and value; rows of
        different papers with the same cells and the same value share one AnswerRow, different values stay apart
        (a conflict stays visible). Sorted by subject, time, dose, then the other cells.
best    candidates = the spec's subjects (two or more), else the doses of the one subject. Open points the
        candidates share (time point, patient group) split the rows into groups, one winner per group; an open point
        that is a candidate's own setting (the dose of a drug) is not split: each candidate counts with its best
        value. The winner must beat the runner-up by more than the rounding step of the printed values (one unit of
        the last decimal), else "tie". A candidate with no row in a group makes it "not_reported".
        Direction from spec.higher_is_better (HbA1c lower is better).
effect, trend, list: answer/effect.py, answer/trend.py, answer/papers.py.
conflicts (every type): rows of two or more papers for the same fact (subject, comparator, dose, time point, patient
        group) whose values differ by more than the rounding step are listed in Answer.conflicts, every value kept,
        and the sentence says so. Rows within the step are not a conflict.
No row fits the spec exactly -> not_reported, "Not reported in the papers." A near miss (same drug, another dose or
patient group than the question fixes) does not fit and is never used to answer.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from evqa import norm
from evqa.answer import canon
from evqa.contracts import QUESTION, Answer, AnswerRow, BestGroup, CantTell, Conflict, Link, Row, SettingSet, Spec

NOT_REPORTED = "Not reported in the papers."
OWN = {"dose"}                       # open points that are a setting of the candidate itself
NOT_STATED = "not stated"


# ---------------------------------------------------------------- links (plan v2 step 4)
@dataclass
class LinkView:
    """Accepted links of one question, for fit and grouping. `fit[set id]` = the question link's verdict;
    `rep[set id]` = the representative set of its "same" component (extract/links.components)."""
    fixed: set[str] = field(default_factory=set)        # fixed dimension keys the question links decide
    fit: dict[str, Link] = field(default_factory=dict)
    rep: dict[str, str] = field(default_factory=dict)
    sets: dict[str, SettingSet] = field(default_factory=dict)
    cant: dict[int, str] = field(default_factory=dict)  # row index -> reason (filled while fitting)


_VIEW: ContextVar[LinkView | None] = ContextVar("links", default=None)


def link_view(spec: Spec, rows: list[Row], links: list[Link]) -> LinkView:
    from evqa.extract import links as linking
    view = LinkView(fixed={d.key for d in linking.fixed_dims(spec)})
    view.fit = {lk.b: lk for lk in links if lk.a == QUESTION}
    view.rep = linking.components(links)
    view.sets = {r.setting_set.id: r.setting_set for r in rows if r.setting_set}
    return view


def _fit_by_links(i: int | None, row: Row, view: LinkView) -> bool:
    """A row fits the fixed dimensions the links decide only when its set is linked "same" to the question;
    unknown (or no set) is recorded as can't tell, never used and never silently dropped."""
    if not view.fixed:
        return True
    reason = ""
    if row.setting_set is None:
        reason = "no setting set was assigned to this value"
    else:
        lk = view.fit.get(row.setting_set.id)
        if lk is None:
            reason = "its settings were not compared with the question"
        elif lk.verdict == "same":
            return True
        elif lk.verdict == "different":
            return False
        else:
            reason = lk.note or "the settings could not be linked to the question"
    if i is not None:
        view.cant[i] = reason
    return False


# ---------------------------------------------------------------- helpers
def unit_symbol(iri: str) -> str:
    return norm.units().get(iri, {}).get("symbol", iri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]) if iri else ""


def number(row: Row) -> Decimal | None:
    """The row's single value (a range counts by its middle)."""
    s = row.std
    if s is None:
        return None
    if s.value:
        return Decimal(s.value)
    if s.low is not None and s.high is not None:
        return (Decimal(s.low) + Decimal(s.high)) / 2
    return None


def shown(row: Row) -> str:
    s = row.std
    assert s is not None
    return s.value if s.value else f"{s.low} to {s.high}"


def cell(row: Row, slot_key: str) -> str:
    """What the table shows for a slot: canonical time and dose, the paper's wording for a patient group."""
    if slot_key == "subject":
        return row.subject
    if row.setting_set:
        view = _VIEW.get()
        group = row.setting_set
        if view is not None:                       # one wording per "same" component: its representative's
            group = view.sets.get(view.rep.get(group.id, group.id), group)
        setting = next((x for x in group.settings if x.dimension == slot_key), None) or next(
            (x for x in group.settings if canon.slot(x.dimension) == slot_key), None)
        if setting is not None:
            return setting.value
    raw = getattr(row, slot_key, None) if slot_key in Row.model_fields else None
    if not raw:
        return NOT_STATED
    return canon.value(slot_key, raw) if slot_key in ("time_point", "dose") else str(raw).strip()


def fits(row: Row, spec: Spec, *, need_number: bool = True, dose_only_for: str | None = None,
         index: int | None = None) -> bool:
    """The row answers the spec exactly: checked quote, a spec subject (any subject when the spec has none), and
    every slot the question fixes. `dose_only_for`: the fixed dose binds only that subject (effect: the dose of A).
    `need_number` False (list): a row without a readable value still shows the subject was tested."""
    if not row.quote_ok or row.dropped:
        return False
    if need_number and (row.std is None or number(row) is None):
        return False
    if spec.subjects and row.subject.lower() not in {s.label.lower() for s in spec.subjects}:
        return False
    view = _VIEW.get()
    for slot_name, want in spec.fixed.items():
        k = canon.slot(slot_name)
        if k == "dose" and dose_only_for is not None and row.subject.lower() != dose_only_for.lower():
            continue
        if view is not None and view.fixed and k not in ("time_point", "dose"):
            continue                               # decided by the question links below
        if k in ("time_point", "dose", "patient_group"):
            if canon.value(k, getattr(row, k)) != canon.value(k, want):
                return False
    if view is not None:
        return _fit_by_links(index, row, view)
    return True


def _group_cells(rows: list[tuple[int, Row]], slot_key: str) -> dict[int, str]:
    """Cell text per row index; patient groups with the same canonical key get one wording (the first seen)."""
    if slot_key != "patient_group" or _VIEW.get() is not None:
        return {i: cell(r, slot_key) for i, r in rows}
    first: dict[str, str] = {}
    out = {}
    for i, r in rows:
        if not r.patient_group:
            out[i] = NOT_STATED
            continue
        out[i] = first.setdefault(canon.group(r.patient_group), r.patient_group.strip())
    return out


def _sort(cells: dict[str, str], keys: list[tuple[str, str]]) -> tuple:
    order = sorted(keys, key=lambda kv: {"subject": 0, "time_point": 1, "dose": 2}.get(kv[1], 3))
    return tuple(canon.sort_key(k, cells[label]) for label, k in order)


def _common_unit(rows: list[tuple[int, Row]]) -> tuple[str, dict[int, Decimal]]:
    """Values converted to the first row's unit; rows of another kind of unit are left out."""
    unit = rows[0][1].std.unit if rows and rows[0][1].std else ""
    vals: dict[int, Decimal] = {}
    for i, r in rows:
        v, u = number(r), r.std.unit if r.std else ""
        if v is None:
            continue
        if u == unit:
            vals[i] = v
        else:
            try:
                if norm.units()[u]["dimension"] == norm.units()[unit]["dimension"] and {u, unit} != {norm.PP, norm.PERCENT}:
                    vals[i] = v * norm.factor(u, unit)
            except KeyError:
                pass
    return unit, vals


def table(rows: list[tuple[int, Row]], keys: list[tuple[str, str]], extra: dict[int, dict[str, str]] | None = None
          ) -> list[AnswerRow]:
    """One AnswerRow per distinct (cells, value); rows giving the same value for the same cells share one."""
    per_slot = {k: _group_cells(rows, k) for _, k in keys}
    out: list[AnswerRow] = []
    for i, r in rows:
        cells = {label: per_slot[k][i] for label, k in keys}
        if extra and i in extra:
            cells = {**extra[i], **cells}
        twin = next((a for a in out if a.cells == cells and a.unit == r.std.unit and a.value == shown(r)), None)
        if twin is None:
            out.append(AnswerRow(cells=cells, value=shown(r), unit=r.std.unit, rows=[i]))
        else:
            twin.rows.append(i)
    out.sort(key=lambda a: _sort(a.cells, [(lbl, canon.slot(lbl)) for lbl in a.cells]))
    return out


def _fmt(value: str | Decimal, unit: str) -> str:
    return f"{value} {unit_symbol(unit)}".strip()


# ---------------------------------------------------------------- lookup
def lookup(spec: Spec, rows: list[Row]) -> Answer:
    used = [(i, r) for i, r in enumerate(rows) if fits(r, spec, index=i)]
    cols = list(spec.columns)
    if len(spec.subjects) > 1 and not any(canon.slot(c) == "subject" for c in cols):
        cols = ["subject", *cols]
    keys = [(c, canon.slot(c)) for c in cols]
    ans = Answer(qid=spec.qid, type="lookup", columns=cols)
    if not used:
        ans.not_reported, ans.sentence = True, NOT_REPORTED
        return ans
    ans.table = table(used, keys)
    head = ", ".join(s.label for s in spec.subjects)
    fixed = "".join(f" {v}" for k, v in spec.fixed.items() if canon.slot(k) == "dose")
    vs = f" vs {spec.comparator.label}" if spec.comparator else ""
    values = "; ".join(f"{', '.join(a.cells.values())}: {_fmt(a.value, a.unit)}".lstrip(": ") for a in ans.table)
    ans.sentence = f"{head}{fixed}{vs}, {spec.measure.label}: {len(ans.table)} value(s) reported - {values}."
    return with_conflicts(ans, used)


# ---------------------------------------------------------------- best
def candidate_slot(spec: Spec) -> str:
    return "subject" if len(spec.subjects) > 1 else "dose"


def step_of(decimals: list[int]) -> Decimal:
    """Rounding step of printed values: one unit of the last decimal of the less precise one."""
    return Decimal(1).scaleb(-min(decimals)) if decimals else Decimal(0)


def best(spec: Spec, rows: list[Row]) -> Answer:
    cand = candidate_slot(spec)
    cand_label = "subject" if cand == "subject" else "dose"
    used = [(i, r) for i, r in enumerate(rows) if fits(r, spec, index=i)]
    open_keys = [(c, canon.slot(c)) for c in spec.columns if canon.slot(c) != cand]
    split = [(c, k) for c, k in open_keys if k not in OWN and k != "subject"]
    own = [(c, k) for c, k in open_keys if k in OWN]
    ans = Answer(qid=spec.qid, type="best", columns=[cand_label, *[c for c, _ in open_keys]])
    if not used:
        ans.not_reported, ans.sentence = True, NOT_REPORTED
        return ans
    hib = spec.higher_is_better
    direction_note = "" if hib is not None else "direction not given; lower taken as better"
    hib = bool(hib)
    cand_of = {i: cell(r, cand) for i, r in used}
    candidates = [s.label for s in spec.subjects] if cand == "subject" else \
        sorted({c for c in cand_of.values() if c != NOT_STATED}, key=lambda c: canon.sort_key("dose", c))
    ans.table = table(used, open_keys, extra={i: {cand_label: cand_of[i]} for i, _ in used})
    unit, vals = _common_unit(used)
    split_cells = {k: _group_cells(used, k) for _, k in split}
    own_cells = {k: _group_cells(used, k) for _, k in own}
    groups: dict[tuple[str, ...], list[int]] = {}
    for i, _ in used:
        if i in vals:
            groups.setdefault(tuple(split_cells[k][i] for _, k in split), []).append(i)
    order = sorted(groups, key=lambda g: tuple(canon.sort_key(k, v) for (_, k), v in zip(split, g, strict=True)))
    by_idx = dict(used)
    for g in order:
        bestrow: dict[str, int] = {}
        for i in groups[g]:
            c = cand_of[i]
            if c not in bestrow or (vals[i] > vals[bestrow[c]] if hib else vals[i] < vals[bestrow[c]]):
                bestrow[c] = i
        ranked = sorted(bestrow.items(), key=lambda kv: vals[kv[1]], reverse=hib)
        bg = BestGroup(group={c: v for (c, _), v in zip(split, g, strict=True)},
                       ranking=[{"candidate": c, "value": str(vals[i]), "unit": unit,
                                 "cells": {lbl: own_cells[k][i] for lbl, k in own},
                                 "rows": [j for j in groups[g] if cand_of[j] == c and vals[j] == vals[i]]}
                                for c, i in ranked],
                       missing=[c for c in candidates if c not in bestrow])
        notes = [direction_note] if direction_note else []
        if bg.missing:
            bg.status, bg.winner = "not_reported", None
            notes.append("not reported for " + ", ".join(bg.missing))
        elif len(ranked) < 2:
            bg.status, bg.winner = "winner", ranked[0][0]
            notes.append("only one candidate reported")
        else:
            (w, wi), (_, ri) = ranked[0], ranked[1]
            margin = abs(vals[wi] - vals[ri])
            step = step_of([by_idx[wi].std.decimals, by_idx[ri].std.decimals])
            bg.margin = str(margin)
            if margin > step:
                bg.status, bg.winner = "winner", w
            else:
                bg.status, bg.winner = "tie", None
                notes.append(f"{ranked[0][0]} and {ranked[1][0]} differ by {margin}, not more than the rounding {step}")
        bg.note = "; ".join(notes)
        ans.groups.append(bg)
    ans.sentence = _best_sentence(spec, ans, cand_label)
    return with_conflicts(ans, used)


def _best_sentence(spec: Spec, ans: Answer, cand_label: str) -> str:
    parts = []
    for g in ans.groups:
        where = ", ".join(g.group.values()) or "all"
        top = g.ranking[0] if g.ranking else None

        def how(entry: dict[str, Any]) -> str:
            own = ", ".join(entry["cells"].values())
            return f"{_fmt(entry['value'], entry['unit'])}{' at ' + own if own else ''}"
        if g.status == "not_reported":
            parts.append(f"{where}: not reported for {', '.join(g.missing)}")
        elif g.status == "tie":
            parts.append(f"{where}: tie between {g.ranking[0]['candidate']} ({how(g.ranking[0])}) and "
                         f"{g.ranking[1]['candidate']} ({how(g.ranking[1])})")
        elif top and len(g.ranking) > 1:
            parts.append(f"{where}: {g.winner} ({how(top)}), ahead of {g.ranking[1]['candidate']} by "
                         f"{_fmt(g.margin or '', top['unit'])}")
        elif top:
            parts.append(f"{where}: {g.winner} ({how(top)}), the only {cand_label} reported")
    return f"Best {cand_label} for {spec.measure.label}: " + "; ".join(parts) + "."


# ---------------------------------------------------------------- conflicts (every type)
CONFLICT_SLOTS = ("subject", "comparator", "dose", "time_point", "patient_group")
CONFLICT_LABEL = {"time_point": "time point", "patient_group": "patient group"}


def _fact_key(row: Row) -> tuple[str, ...]:
    return (row.subject.lower(), canon.value("comparator", row.comparator), canon.value("dose", row.dose),
            canon.value("time_point", row.time_point), canon.value("patient_group", row.patient_group))


def conflicts(used: list[tuple[int, Row]]) -> list[Conflict]:
    """Facts that two or more papers report with values further apart than the rounding step (module doc)."""
    by: dict[tuple[str, ...], list[tuple[int, Row]]] = {}
    for i, r in used:
        if r.std is not None and number(r) is not None:
            by.setdefault(_fact_key(r), []).append((i, r))
    out: list[Conflict] = []
    for group in by.values():
        if len({r.paper for _, r in group}) < 2:
            continue
        unit, vals = _common_unit(group)
        kept = [(i, r) for i, r in group if i in vals]
        if len({r.paper for _, r in kept}) < 2:
            continue
        hi, lo = max(vals[i] for i, _ in kept), min(vals[i] for i, _ in kept)
        step = step_of([r.std.decimals for _, r in kept])
        if hi - lo <= step:
            continue
        first = kept[0][1]
        cells = {CONFLICT_LABEL.get(k, k): cell(first, k) for k in CONFLICT_SLOTS}
        cells = {k: v for k, v in cells.items() if v and v != NOT_STATED}
        out.append(Conflict(cells=cells, spread=str(hi - lo), step=str(step), unit=unit,
                            values=[{"paper": r.paper, "value": str(vals[i]), "unit": unit, "rows": [i]}
                                    for i, r in sorted(kept, key=lambda x: (x[1].paper, vals[x[0]]))]))
    out.sort(key=lambda c: tuple(sorted(c.cells.items())))
    return out


def with_conflicts(ans: Answer, used: list[tuple[int, Row]]) -> Answer:
    """Adds Answer.conflicts and one clause per conflict to the sentence (nothing when there is none)."""
    ans.conflicts = conflicts(used)
    if ans.conflicts:
        said = "; ".join(", ".join(c.cells.values()) + ": " + " vs ".join(
            f"{v['paper']} {_fmt(v['value'], v['unit'])}" for v in c.values) for c in ans.conflicts)
        ans.sentence = f"{ans.sentence} Conflict, the papers disagree - {said}."
    return ans


def run(spec: Spec, rows: list[Row], links: list[Link] | None = None) -> Answer:
    """The answer to `spec` from Extract's rows (indexes in AnswerRow.rows / ranking rows refer to `rows`).
    `links` (extract/links.py): fit to the question's fixed settings and grouping by accepted links; values whose
    fit is unknown go to Answer.cant_tell. None (runs made before links): the older word-based grouping."""
    if links is None:
        return _run(spec, rows)
    view = link_view(spec, rows, links)
    token = _VIEW.set(view)
    try:
        ans = _run(spec, rows)
    finally:
        _VIEW.reset(token)
    ans.cant_tell = [CantTell(row=i, paper=rows[i].paper, value=shown(rows[i]) if rows[i].std else rows[i].raw,
                              reason=why) for i, why in sorted(view.cant.items())]
    if ans.cant_tell:
        said = "; ".join(f"{c.paper} {c.value}" for c in ans.cant_tell)
        ans.sentence = (f"{ans.sentence} Can't tell if these values fit the question's settings: {said}.").strip()
    return ans


def _run(spec: Spec, rows: list[Row]) -> Answer:
    extras = sorted({x.dimension for row in rows if row.setting_set for x in row.setting_set.settings if x.extra})
    spec = spec.model_copy(update={"columns": list(dict.fromkeys([*spec.columns, *extras]))})
    if spec.type == "lookup":
        answer = lookup(spec, rows)
        for key in extras:
            marked = key + " (found in the papers, not asked)"
            answer.columns = [marked if col == key else col for col in answer.columns]
            for item in answer.table:
                if key in item.cells:
                    item.cells[marked] = item.cells.pop(key)
        return answer
    if spec.type == "best":
        return best(spec, rows)
    if spec.type == "effect":
        from evqa.answer.effect import effect
        return effect(spec, rows)
    if spec.type == "trend":
        from evqa.answer.trend import trend
        return trend(spec, rows)
    if spec.type == "list":
        from evqa.answer.papers import papers
        return papers(spec, rows)
    return lookup(spec, rows)
