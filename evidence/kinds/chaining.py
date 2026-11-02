"""Kind `chaining` (spec section 6.10; plan 2 Task 9): is `chaining.source` better than `chaining.target` on
`chaining.metric`, through things each was tested against?

It reads the run's comparisons (comparisons.json, evidence/comparisons.py), never items: a thing is its key there
(`comparisons.thing_key`: the name group with `names: on`, else the `names.clean` form), so "Drug B" and "drug-B"
are one step apart from nothing. A comparison's `direction` is a over b (preflight P13); a step walked from b to a
reads it the other way round. Copied comparisons (comparisons.json `copied`) are not read: a copied result counts
once, at its origin. Rules, in this order:
1. A comparison of source and target on `metric.canonical` is a direct result: `inferred` false, reason
   `direct_comparison`, never chained. Its verdict is `better`, `worse` or `no_difference` (source over target);
   several direct results that differ give `refused` (still `direct_comparison`).
2. Paths source - via ... - target of 2 to `max_hops` steps over comparisons on `metric.canonical`, no thing twice.
   A step's direction is `rules.effect` of its two values with the block's `min_effect` and the metric's direction.
3, 4. Each path is judged by `rules.chain_verdict` (the rule the truth network uses): steps that both name a
   context must name the same one (`context_differs`); better at every step concludes better, worse at every step
   worse, anything else (a neutral step included) `mixed_directions`.
5. The paths that conclude decide: one verdict among them is the answer (`inferred` true, reason null, `note`
   "inferred through {via}, not tested directly"); different verdicts give `refused`, `paths_disagree`. A path
   refused by rule 3 or 4 does not stand against a concluding one (it is listed under `paths` with its reason).
   When no path concludes, the reason is `mixed_directions` when a path has it, else `context_differs`.
6. No path on the metric: `metric_differs` when a path of 1 to `max_hops` steps links source and target over
   comparisons on any metric (preflight T9), else `no_path`.
7. `studies` lists every document the chosen paths rest on (the concluding paths; else every path listed), in
   manifest order; `via` their middle things, in path order.

Answer: `{kind, system, source, target, metric, verdict, inferred, via, studies, paths, reason, note}`; a path is
`{via, steps: [{comparison, document, from, to, metric, direction, context}], verdict, reason}` (a step's
`direction` is from over to: better, worse, no_difference, or null on a metric of unknown direction).

Per document (`study`, the funnel's completeness check): the document's comparisons on the metric that involve the
source, the target or a `via` thing; none gives reason `no_path`, which escalates the measured-value type.
"""
from __future__ import annotations

from collections.abc import Collection, Sequence
from typing import TYPE_CHECKING, Any

from .. import comparisons as cmp
from .. import rules, synthesis
from ..contract import Item
from ..evidence_types import EvidenceType
from ..protocol import Chaining, Protocol

if TYPE_CHECKING:
    from ..comparisons import Comparison, Comparisons
    from ..names import NameGroups
    from ..pack import RoleMap

KIND = "chaining"
NO_PATH, METRIC_DIFFERS, DIRECT = "no_path", "metric_differs", "direct_comparison"
CONTEXT_DIFFERS, MIXED, DISAGREE = "context_differs", "mixed_directions", "paths_disagree"
assert {NO_PATH, METRIC_DIFFERS, DIRECT, CONTEXT_DIFFERS, MIXED, DISAGREE} == set(rules.CHAIN_REASONS)
GAP_ROLES: dict[str, tuple[str, ...]] = {NO_PATH: ("measured_value",), "screened_out": ()}   # pack.Role values
VERDICT: dict[str | None, str | None] = {"supports": "better", "contradicts": "worse", "neutral": "no_difference",
                                         None: None}
FLIP: dict[str | None, str | None] = {"supports": "contradicts", "contradicts": "supports", "neutral": "neutral",
                                      None: None}
NOTE = "inferred through {via}, not tested directly"

Step = tuple["Comparison", str, str]   # a comparison walked from one thing key to the other


def spec(protocol: Protocol) -> Chaining:
    assert protocol.chaining is not None, "a chaining protocol has a chaining block"
    return protocol.chaining


def _direction(step: Step, chain: Chaining, groups: NameGroups | None) -> rules.Direction | None:
    """The step's direction from over to (rules vocabulary): `rules.effect` on the question metric, else the
    comparison's own direction (None when unknown); turned when the step walks from b to a."""
    c, start, _ = step
    if c.metric == chain.metric.canonical:
        found: rules.Direction | None = rules.effect(c.a_value, c.b_value, chain.metric.higher_is_better,
                                                     chain.min_effect)[0]
    else:
        found = c.direction
    return found if cmp.thing_key(c.a, groups) == start else FLIP[found]   # type: ignore[return-value]


def _paths(edges: dict[str, list[tuple[str, Comparison]]], source: str, target: str, least: int,
           most: int) -> list[list[Step]]:
    """Every path source -> target of `least` to `most` steps visiting no thing twice, depth first in comparison
    order."""
    out: list[list[Step]] = []

    def walk(node: str, seen: frozenset[str], steps: list[Step]) -> None:
        if node == target:
            if len(steps) >= least:
                out.append(steps)
            return
        if len(steps) == most:
            return
        for nxt, c in edges.get(node, []):
            if nxt not in seen:
                walk(nxt, seen | {nxt}, [*steps, (c, node, nxt)])

    walk(source, frozenset({source}), [])
    return out


def _edges(found: Sequence[Comparison], groups: NameGroups | None) -> dict[str, list[tuple[str, Comparison]]]:
    edges: dict[str, list[tuple[str, Comparison]]] = {}
    for c in found:
        ka, kb = cmp.thing_key(c.a, groups), cmp.thing_key(c.b, groups)
        if ka != kb:
            edges.setdefault(ka, []).append((kb, c))
            edges.setdefault(kb, []).append((ka, c))
    return edges


def answer(protocol: Protocol, documents: list[str], items: dict[str, list[Item]],
           reasons: dict[str, dict[str, str]] | None = None,
           funnel: dict[str, dict[str, Any]] | None = None, *,
           roles: RoleMap | None = None, groups: NameGroups | None = None,
           comparisons: Comparisons | None = None, reason: object | None = None) -> tuple[dict[str, Any], list[str]]:
    """The chain answer from the run's comparisons (built here from `items` when `comparisons` is None). `reasons`,
    `funnel` and `reason` (plan 3's inferences) are not read."""
    chain = spec(protocol)
    roles = roles if roles is not None else protocol.roles()
    if comparisons is None:
        comparisons = cmp.of_run(protocol, documents, items, roles, groups)
    canonical = chain.metric.canonical
    every = list(comparisons.comparisons)
    shown: dict[str, str] = {}
    for c in every:
        shown.setdefault(cmp.thing_key(c.a, groups), c.a)
        shown.setdefault(cmp.thing_key(c.b, groups), c.b)
    source, target = cmp.thing_key(chain.source, groups), cmp.thing_key(chain.target, groups)
    on_metric = [c for c in every if c.metric == canonical]

    def step_json(step: Step) -> dict[str, Any]:
        c, start, end = step
        return {"comparison": c.id, "document": c.document, "from": shown[start], "to": shown[end],
                "metric": c.metric, "direction": VERDICT[_direction(step, chain, groups)], "context": c.context}

    def path_json(steps: list[Step], verdict: str, why: str | None) -> dict[str, Any]:
        return {"via": [shown[s[2]] for s in steps[:-1]], "steps": [step_json(s) for s in steps], "verdict": verdict,
                "reason": why}

    out: dict[str, Any] = {"kind": KIND, "system": synthesis.SYSTEM, "source": chain.source, "target": chain.target,
                           "metric": canonical, "verdict": "refused", "inferred": False, "via": [], "studies": [],
                           "paths": [], "reason": None, "note": None}
    edges = _edges(on_metric, groups)
    direct = _paths(edges, source, target, 1, 1)
    if direct:                                                   # rule 1
        listed = [(p, path_json(p, VERDICT[_direction(p[0], chain, groups)] or "refused", DIRECT)) for p in direct]
        verdicts = {p["verdict"] for _, p in listed}
        out.update(verdict=verdicts.pop() if len(verdicts) == 1 else "refused", reason=DIRECT)
        return _finish(out, documents, listed, listed)
    listed = []
    for steps in _paths(edges, source, target, 2, chain.max_hops):   # rules 2-4
        verdict, why = rules.chain_verdict([(_direction(s, chain, groups), s[0].context) for s in steps])
        listed.append((steps, path_json(steps, verdict, why)))
    concluding = [(s, p) for s, p in listed if p["reason"] is None]
    if concluding:                                               # rule 5
        verdicts = {p["verdict"] for _, p in concluding}
        if len(verdicts) == 1:
            out.update(verdict=verdicts.pop(), inferred=True)
        else:
            out.update(reason=DISAGREE)
        return _finish(out, documents, listed, concluding)
    if listed:
        out.update(reason=MIXED if any(p["reason"] == MIXED for _, p in listed) else CONTEXT_DIFFERS)
        return _finish(out, documents, listed, listed)
    other = [(s, path_json(s, "refused", METRIC_DIFFERS))                # rule 6
             for s in _paths(_edges(every, groups), source, target, 1, chain.max_hops)]
    out.update(reason=METRIC_DIFFERS if other else NO_PATH)
    return _finish(out, documents, other, other)


Listed = list[tuple[list[Step], dict[str, Any]]]   # a path's steps and its answer.json form


def _finish(out: dict[str, Any], documents: list[str], listed: Listed,
            chosen: Listed) -> tuple[dict[str, Any], list[str]]:
    """`paths` (every path listed), and `via`, `studies` (manifest order) and `note` of the chosen paths (rule 7);
    the item ids the chosen paths rest on."""
    order = {d: n for n, d in enumerate(documents)}
    via: list[str] = []
    for _, p in chosen:
        via += [v for v in p["via"] if v not in via]
    docs = {s[0].document for steps, _ in chosen for s in steps}
    out.update(paths=[p for _, p in listed], via=via,
               studies=sorted(docs, key=lambda d: (order.get(d, len(order)), d)))
    if out["inferred"]:
        out["note"] = NOTE.format(via=", ".join(via))
    used = dict.fromkeys(i for steps, _ in chosen for s in steps for i in s[0].items)
    return out, list(used)


def study(protocol: Protocol, document: str, items: list[Item], preset: dict[str, str] | None = None, *,
          roles: RoleMap | None = None, groups: NameGroups | None = None,
          via: Collection[str] = ()) -> tuple[dict[str, Any], list[str]]:
    """The document's comparisons (ids) on the metric that involve the source, the target or a thing of `via`;
    reason `no_path` when there is none (or the funnel's `preset`)."""
    chain = spec(protocol)
    roles = roles if roles is not None else protocol.roles()
    entry: dict[str, Any] = {"document": document, "comparisons": [], "reason": None}
    if preset is not None:
        entry["reason"] = dict(preset)
        return entry, []
    wanted = {cmp.thing_key(n, groups) for n in (chain.source, chain.target, *via)}
    found = [c for c in cmp.build_comparisons(document, items, roles, groups, **cmp.settings(protocol))
             if c.metric == chain.metric.canonical
             and wanted & {cmp.thing_key(c.a, groups), cmp.thing_key(c.b, groups)}]
    entry["comparisons"] = [c.id for c in found]
    if not found:
        entry["reason"] = {"code": NO_PATH, "text": f"no comparison on {chain.metric.canonical} of {chain.source} "
                                                    f"or {chain.target}"}
    return entry, list(dict.fromkeys(i for c in found for i in c.items))


def gap_types(protocol: Protocol, code: str, *, roles: RoleMap | None = None) -> tuple[EvidenceType, ...]:
    return synthesis.gap_types(protocol, code, roles, GAP_ROLES)


def extractor_config(protocol: Protocol) -> dict[str, Any]:
    return {"question_metrics": [spec(protocol).metric.canonical]}
