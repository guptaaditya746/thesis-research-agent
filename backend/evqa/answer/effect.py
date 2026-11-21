"""Answer for effect questions ("does A beat B on M?"): one difference A - B per study/group. Code only.

A = spec.subjects[0]. B = spec.subjects[1] when B is a drug (Spec puts it there), else spec.comparator (a control
such as placebo), else the comparator each row names.

B a drug:
  head_to_head      a row of A whose comparator is B: difference = its value; a row of B vs A: minus its value.
                    One entry per row (group: the spec's open columns, the comparator and the paper).
  same_comparator   rows of A and of B against the same other comparator C, same time point and patient group:
                    each side counts with its best value (doses are each drug's own setting, as in best); one entry
                    per (C, time point, patient group) where both sides have a row.
B a control (or none named):
  vs_comparator     every row of A as reported (a mean difference vs placebo is already A - B); one entry per row.
Verdict: |difference| <= the rounding step of the printed values (one unit of the last decimal of the less precise
value) -> "no clear difference"; else "<A> better" or "<B> better" by spec.higher_is_better (None: lower is better,
noted). A fixed dose binds A only. No entry -> not_reported (the sentence names the side with no row).
"""
from __future__ import annotations

import re
from decimal import Decimal

from evqa.answer import canon
from evqa.answer.core import (NOT_REPORTED, NOT_STATED, _common_unit, _fmt, _group_cells, cell, fits, number, step_of,
                              table, with_conflicts)
from evqa.contracts import Answer, EffectEntry, Name, Row, Spec

NO_CLEAR = "no clear difference"


def _words(text: str | None) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower())) - {"mg", "daily", "once", "the", "a", "vs", "versus"}


def names_it(text: str | None, name: Name) -> bool:
    """The row's comparator text names `name` (its label or a synonym: all the name's words are in the text)."""
    got = _words(text)
    return bool(got) and any((w := _words(alias)) and w <= got for alias in (name.label, *name.synonyms))


def verdict(diff: Decimal, step: Decimal, a: str, b: str, hib: bool) -> str:
    if abs(diff) <= step:
        return NO_CLEAR
    return f"{a} better" if (diff > 0) == hib else f"{b} better"


def effect(spec: Spec, rows: list[Row]) -> Answer:
    a_name = spec.subjects[0]
    b_name = spec.subjects[1] if len(spec.subjects) > 1 else None
    a = a_name.label
    used = [(i, r) for i, r in enumerate(rows) if fits(r, spec, dose_only_for=a, index=i)]
    open_cols = [c for c in spec.columns if canon.slot(c) not in ("subject", "comparator")]
    cols = ["subject", "comparator", *open_cols]
    ans = Answer(qid=spec.qid, type="effect", columns=cols)
    hib = bool(spec.higher_is_better)
    note = "" if spec.higher_is_better is not None else " (direction not given; lower taken as better)"
    if used:
        ans.table = table(used, [(c, canon.slot(c)) for c in cols])
    entries: list[EffectEntry] = []
    if b_name is not None:
        entries = _drug_vs_drug(spec, used, a_name, b_name, open_cols, hib)
        b = b_name.label
    else:
        b = spec.comparator.label if spec.comparator else "the comparator"
        for i, r in used:
            if r.subject.lower() != a.lower():
                continue
            v, step = number(r), step_of([r.std.decimals])
            rb = spec.comparator.label if spec.comparator else (r.comparator or "the comparator")
            entries.append(EffectEntry(basis="vs_comparator", group={**_cells(r, open_cols), "paper": r.paper},
                                       a=a, b=rb, difference=str(v), unit=r.std.unit, step=str(step),
                                       verdict=verdict(v, step, a, rb, hib), papers=[r.paper], rows=[i]))
    ans.effects = entries
    if not entries:
        ans.not_reported = True
        sides = {r.subject.lower() for _, r in used}
        missing = [n for n in (a, b) if n.lower() not in sides and (b_name is not None or n == a)]
        if missing:
            ans.sentence = f"{NOT_REPORTED[:-1]} for {' and '.join(missing)}: no difference between {a} and {b}."
        elif used:
            ans.sentence = (f"{NOT_REPORTED[:-1]}: no row compares {a} with {b} head to head or against the same "
                            "comparator at the same time point and patient group.")
        else:
            ans.sentence = NOT_REPORTED
        return with_conflicts(ans, used)
    parts = []
    for e in entries:
        where = ", ".join(v for v in e.group.values() if v and v != NOT_STATED) or "all"
        how = "head to head" if e.basis == "head_to_head" else \
            f"both vs {e.group.get('comparator', 'the same comparator')}" if e.basis == "same_comparator" else ""
        parts.append(f"{where}: {e.verdict} ({e.a} - {e.b} = {_fmt(e.difference, e.unit)}"
                     f"{', ' + how if how else ''})")
    ans.sentence = f"{a} vs {b}, {spec.measure.label}{note}: " + "; ".join(parts) + "."
    return with_conflicts(ans, used)


def _cells(r: Row, open_cols: list[str]) -> dict[str, str]:
    return {c: cell(r, canon.slot(c)) for c in open_cols}


def _drug_vs_drug(spec: Spec, used: list[tuple[int, Row]], a_name: Name, b_name: Name, open_cols: list[str],
                  hib: bool) -> list[EffectEntry]:
    a, b = a_name.label, b_name.label
    entries: list[EffectEntry] = []
    indirect: list[tuple[int, Row]] = []
    for i, r in used:
        is_a, is_b = r.subject.lower() == a.lower(), r.subject.lower() == b.lower()
        if is_a and names_it(r.comparator, b_name):
            sign = Decimal(1)
        elif is_b and names_it(r.comparator, a_name):
            sign = Decimal(-1)
        else:
            if is_a or is_b:
                indirect.append((i, r))
            continue
        v, step = sign * number(r), step_of([r.std.decimals])
        entries.append(EffectEntry(basis="head_to_head", group={**_cells(r, open_cols), "paper": r.paper}, a=a, b=b,
                                   difference=str(v), unit=r.std.unit, step=str(step),
                                   verdict=verdict(v, step, a, b, hib), papers=[r.paper], rows=[i]))
    shared = [c for c in open_cols if canon.slot(c) in ("time_point", "patient_group")]
    group_cells = {c: _group_cells(indirect, canon.slot(c)) for c in shared}
    groups: dict[tuple[str, ...], list[tuple[int, Row]]] = {}
    for i, r in indirect:
        key = (canon.value("comparator", r.comparator) or NOT_STATED, *(group_cells[c][i] for c in shared))
        groups.setdefault(key, []).append((i, r))
    for key in sorted(groups, key=lambda k: (k[0], *(canon.sort_key(canon.slot(c), v)
                                                     for c, v in zip(shared, k[1:], strict=True)))):
        grp = groups[key]
        unit, vals = _common_unit(grp)
        side: dict[str, int] = {}
        for i, r in grp:
            if i not in vals:
                continue
            s = r.subject.lower()
            if s not in side or (vals[i] > vals[side[s]] if hib else vals[i] < vals[side[s]]):
                side[s] = i
        if a.lower() not in side or b.lower() not in side:
            continue
        ia, ib = side[a.lower()], side[b.lower()]
        by = dict(grp)
        diff = vals[ia] - vals[ib]
        step = step_of([by[ia].std.decimals, by[ib].std.decimals])
        comp = by[ia].comparator or NOT_STATED
        entries.append(EffectEntry(basis="same_comparator",
                                   group={"comparator": comp, **dict(zip(shared, key[1:], strict=True))},
                                   a=a, b=b, a_value=str(vals[ia]), b_value=str(vals[ib]), difference=str(diff),
                                   unit=unit, step=str(step), verdict=verdict(diff, step, a, b, hib),
                                   papers=sorted({by[ia].paper, by[ib].paper}), rows=[ia, ib]))
    return entries
