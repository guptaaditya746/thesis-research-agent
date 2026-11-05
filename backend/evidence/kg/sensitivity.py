"""Decision reruns (W4 task 4.3): how much does an answer depend on the planner's choices?

Each decision of the plan (must-match fields, counts-as values, threshold, include) has alternatives, strict to loose:
- must-match: add one field (strict) or drop one (loose);
- counts-as: drop one value (strict) or add one (loose);
- threshold: 0 (strict), the main value, twice the main value (loose);
- include: none (a list of papers is the planner's call, not a knob).
`rerun` runs the evidence line again with one decision changed at a time and compares each rerun's verdict with the main
one; `label` turns that into "solid", "same direction", "depends on <field>" or "too few to tell".

A verdict is what the line's answer says, in a word (`Verdict.label`), how many records stand behind it (`n`) and
optionally its size (`size`, e.g. a share or a gap). The default verdict reads the top row's first column (the
winner of a ranking, the first thing listed) and counts the rows; a line that is a count of cases for and against
passes its own `verdict` function.

"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

import pyoxigraph as ox

from evidence.plan import Decision, EvidenceLine

from .build import KG
from .query import Answer, decision_params, run_query, template

Strictness = Literal["strict", "main", "loose"]
TOO_FEW, SOLID, SAME_DIRECTION = "too few to tell", "solid", "same direction"
SIZE_TOLERANCE = 0.1    # a rerun's size within this share of the main size counts as the same size


@dataclass(frozen=True)
class Verdict:
    label: str
    n: int
    size: float | None = None


def default_verdict(answer: Answer) -> Verdict:
    if not answer.rows:
        return Verdict("none", 0)
    first = answer.rows[0]
    return Verdict(str(next(iter(first.values()))), len(answer.rows))


@dataclass(frozen=True)
class Run:
    decision: str
    field: str                 # the must-match field changed, or the decision type for the other decisions
    setting: Strictness
    value: Any
    verdict: Verdict
    flips: bool


@dataclass
class Sensitivity:
    line: str
    main: Verdict
    runs: list[Run] = field(default_factory=list)
    indirect: list[dict[str, Any]] = field(default_factory=list)   # rows only a loose rerun has, `indirect on: <field>`

    @property
    def flipping(self) -> list[Run]:
        """Only the settings that change the verdict."""
        return [r for r in self.runs if r.flips]


def alternatives(decision: Decision, fields: list[Any]) -> list[tuple[Strictness, Any]]:
    """The decision's value under every setting, strict first, then main, then loose. `fields` is the pool a list
    decision draws from (all setting fields for must-match, all values for counts-as)."""
    value = decision.value
    if decision.type == "threshold":
        return [("strict", 0), ("main", value), ("loose", 2 * value)]
    if decision.type in ("must_match", "counts_as"):
        have = list(value)
        more = [[*have, f] for f in sorted(set(fields) - set(have), key=str)]
        less = [[x for x in have if x != f] for f in have]
        if decision.type == "counts_as":
            less = [v for v in less if v]   # counting nothing is not a way of counting
        strict, loose = (more, less) if decision.type == "must_match" else (less, more)
        return [*(("strict", v) for v in strict), ("main", have), *(("loose", v) for v in loose)]
    return [("main", value)]


def _changed(decision: Decision, main: Any, alt: Any) -> str:
    if decision.type == "must_match":
        return str(next(iter(set(main) ^ set(alt))))
    return decision.type


def setting_fields(store: ox.Store) -> list[str]:
    """Every setting field in the graph (the property names ev:setting_<field>, underscores as written there)."""
    rows = store.query("SELECT DISTINCT ?p WHERE { ?s ?p ?o . FILTER(STRSTARTS(STR(?p), "
                       '"https://w3id.org/thesis-ev#setting_")) } ORDER BY ?p')
    return [r["p"].value.rsplit("setting_", 1)[1] for r in rows]


def _same(a: Verdict, b: Verdict) -> bool:
    return a.label == b.label


def winners_verdict(answer: Answer) -> Verdict:
    """For rows `kind, thing, count` (the `best` template): the winner in each counting unit, e.g. "paper: Rossi;
    result: Chen"; `n` is the first unit's top count."""
    top: dict[str, dict[str, Any]] = {}
    for r in answer.rows:
        top.setdefault(r["kind"], r)
    if not top:
        return Verdict("none", 0)
    return Verdict("; ".join(f"{k}: {r['thing']}" for k, r in sorted(top.items())), next(iter(top.values()))["count"])


def param_names(sparql: str, decisions: list[Decision], param_of: dict[str, str] | None) -> dict[str, str]:
    """Decision id -> the query parameter it fills: `param_of` first, else the template's `# decisions:` header, else
    the decision's type. Two decisions filling one parameter would overwrite each other: ValueError."""
    header = decision_params(sparql)
    names = {d.id: (param_of or {}).get(d.id) or header.get(d.type, d.type) for d in decisions}
    seen: dict[str, str] = {}
    for ident, name in names.items():
        if name in seen:
            raise ValueError(f"decisions {seen[name]!r} and {ident!r} both fill parameter {name!r}; "
                             "name a parameter for each with param_of")
        seen[name] = ident
    return names


def rerun(store: ox.Store, line: EvidenceLine, decisions: list[Decision], *, params: dict[str, Any] | None = None,
          verdict: Callable[[Answer], Verdict] = default_verdict,
          candidates: dict[str, list[Any]] | None = None, param_of: dict[str, str] | None = None,
          match: Any = None) -> Sensitivity:
    """Run `line` with the decisions as they are, then once per alternative of each decision (the others unchanged).
    `params` are the line's own params (a metric, a thing), `candidates` the pool per decision type; `match` the
    line's name matcher (`query.render`)."""
    sparql = template(line.template) if line.template else line.query
    names = param_names(sparql, decisions, param_of)
    base = {**(params or {}), **{names[d.id]: d.value for d in decisions}}
    pool = {"must_match": setting_fields(store), **(candidates or {})}
    main_answer = run_query(store, sparql, base, match)
    main = verdict(main_answer)
    out = Sensitivity(line=line.id, main=main)
    main_rows = {json.dumps(r, sort_keys=True, default=str) for r in main_answer.rows}
    for d in decisions:
        for setting, value in alternatives(d, pool.get(d.id, pool.get(d.type, []))):
            if setting == "main":
                continue
            answer = run_query(store, sparql, {**base, names[d.id]: value}, match)
            v = verdict(answer)
            changed = _changed(d, d.value, value) if d.type == "must_match" else d.type
            out.runs.append(Run(d.id, changed, setting, value, v, flips=not _same(main, v)))
            if setting == "loose" and d.type == "must_match":
                out.indirect += [{**r, "note": f"indirect on: {changed}"} for r in answer.rows
                                 if json.dumps(r, sort_keys=True, default=str) not in main_rows]
    return out


def _stable_size(main: Verdict, v: Verdict) -> bool:
    if main.size is None or v.size is None:
        return True
    return abs(v.size - main.size) <= SIZE_TOLERANCE * abs(main.size)


def label(results: Sensitivity, min_count: int = 3) -> str:
    """"too few to tell" when fewer than `min_count` records stand behind the main verdict (3 is our call: the spec
    says "a minimum count"); "depends on <field>" for the settings that flip the verdict (several: joined with
    " and "); "solid" when no setting changes the verdict, its size or leaves too few records, else "same direction"."""
    if results.main.n < min_count:
        return TOO_FEW
    flipping = list(dict.fromkeys(r.field for r in results.flipping))
    if flipping:
        return "depends on " + " and ".join(flipping)
    steady = all(r.verdict.n >= min_count and _stable_size(results.main, r.verdict) for r in results.runs)
    return SOLID if steady else SAME_DIRECTION
