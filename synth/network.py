"""The truth network of a recipe with `network` (plan 2 Task 4; spec sections 6.9, 6.10): which thing beats which, per
population, so every direct comparison and every allowed chain has a known answer.

- `latent`: a ranking of the network's things (its reference among them) drawn per context, with a true
  rate for each; neighbours in the ranking differ by at least 2 x min_effect + the smallest supporting effect, so the
  rounding of a count to whole units never turns an edge neutral.
- `plan_studies`: which edge and context each study tests, round robin over edges x contexts, then shuffled.
- `draw`: the studies. A study has two arms, the edge's things (the second in the control place, the first in the
  treatment place, so its effect is "first over second"), plus 0-1 distractor arm from the recipe's `others` (role
  other; each used by one study at most, so no chain can pass through it). Every value is a count k of the arm's n
  units, n drawn in `reporting.arm_size`; on the question metric k = round(rate x n) for the latent rate.
- `comparisons` and `chains`: the truth the comparison and chaining kinds are scored against; a chain's verdict comes
  from `evidence.rules.chain_verdict`, the rule the engine applies.

Randomness: the latent ranking from `synth:<seed>:latent`, the plan from `synth:<seed>:network`, the studies from
`random.Random(seed)`. The code holds no topic word: things, contexts and ranges come from the recipe.
"""
from __future__ import annotations

import math
import random
from itertools import combinations
from typing import Any

from evidence import rules
from evidence.protocol import Synthesis
from synth.recipe import MetricSpec, NameForms, Recipe
from synth.truth import (FALSE_CLAIM, Condition, Effect, Measurement, Metric, Study, _decoy, _far, _names_clash,
                         collides, default_spec, metric_spec, true_claim)

Edge = tuple[str, str]
TRIES = 10_000          # draws before a count that fits is given up on (a recipe whose ranges leave no room)


def nodes(recipe: Recipe) -> list[str]:
    """The things of the network and its reference, in recipe order."""
    net = _network(recipe)
    return [*net.things, net.reference]


def edge_of(study: Study) -> Edge:
    """The edge a network study tests: (the thing in the treatment place, the thing in the control place)."""
    return study.treatment_condition.label, study.control_condition.label


def question_metric(recipe: Recipe, spec: Synthesis) -> MetricSpec:
    """The one question metric of a network recipe, which the protocol must ask about."""
    metric = recipe.question_metrics[0]          # the recipe check allows exactly one with a network
    if metric.canonical not in spec.metric_names:
        raise ValueError(f"the network of {recipe.domain} ranks {metric.canonical!r}, which the protocol does not "
                         f"ask about ({sorted(spec.metric_names)})")
    return metric


def latent(seed: int, recipe: Recipe, spec: Synthesis | None = None) -> dict[tuple[str, str], float]:
    """(thing, context) -> true rate of the question metric, for every node and network context. Per context the
    nodes are shuffled (best first) and get rates from the metric's `pair_range`, in thousandths, neighbours apart by
    at least 2 x min_effect + effects.supports[0] (spec: default the recipe's effect protocol)."""
    spec = spec or default_spec(recipe)
    metric = question_metric(recipe, spec)
    low, high = metric.pair_range or metric.range
    gap = math.ceil(round((2 * spec.min_effect + recipe.effects["supports"][0]) * 1000, 6))
    names = nodes(recipe)
    slack = round(high * 1000) - round(low * 1000) - gap * (len(names) - 1)
    if slack < 0:
        raise ValueError(f"the network of {recipe.domain}: {len(names)} things {gap / 1000} apart do not fit in "
                         f"the range {low}-{high} of {metric.canonical}")
    rng = random.Random(f"synth:{seed}:latent")
    rates: dict[tuple[str, str], float] = {}
    for context in _network(recipe).contexts:
        order = list(names)
        rng.shuffle(order)
        offsets = sorted(rng.randint(0, slack) for _ in names)
        rising = [(round(low * 1000) + u + i * gap) / 1000 for i, u in enumerate(offsets)]
        best_first = rising[::-1] if spec.higher_is_better(metric.canonical) else rising
        rates.update({(thing, context): v for thing, v in zip(order, best_first)})
    return rates


def plan_studies(seed: int, n: int, recipe: Recipe, spec: Synthesis) -> list[tuple[Edge, str]]:
    """(edge, context) of each of `n` studies: round robin over edges x contexts (every cell once before any twice),
    then shuffled from `synth:<seed>:network`."""
    question_metric(recipe, spec)
    net = _network(recipe)
    cells = [(tuple(edge), context) for edge in net.edges for context in net.contexts]
    planned = [cells[i % len(cells)] for i in range(n)]
    random.Random(f"synth:{seed}:network").shuffle(planned)
    return planned


def draw(seed: int, n: int, spec: Synthesis, recipe: Recipe) -> list[Study]:
    """The `n` studies of the plan, before the knobs. A study whose pair equals an earlier study's is drawn again
    (as in truth.generate); a distractor arm, once used, is not drawn again."""
    rates = latent(seed, recipe, spec)
    rng = random.Random(seed)
    spare = list(recipe.others)
    studies: list[Study] = []
    for i, (edge, context) in enumerate(plan_studies(seed, n, recipe, spec)):
        study = network_study(rng, i, edge, context, rates, spare, spec, recipe)
        while collides(study, studies):
            study = network_study(rng, i, edge, context, rates, spare, spec, recipe)
        studies.append(study)
        used = {c.label for c in study.conditions[2:]}
        spare = [o for o in spare if o.label not in used]
    return studies


def network_study(rng: random.Random, index: int, edge: Edge, context: str, rates: dict[tuple[str, str], float],
                  spare: list[NameForms], spec: Synthesis, recipe: Recipe) -> Study:
    """One study of `edge` in `context`: its two things (names by label from the recipe's sides) and 0-1 arm of
    `spare`, a form of the question metric and 1-2 other metrics (by their first form), one dataset (the context).
    Each arm has a size n in `reporting.arm_size` and every value is k / n with 1 <= k < n, more than DECOY_GAP from
    the study's other values; the edge's pair is k = round(rate x n), redrawn until rules.effect gives the latent
    direction."""
    sid = f"S{index + 1:03d}"
    first, second = edge
    side_of = {n.label: (role, n) for role, side in recipe.sides.items() for n in side.names}
    qspec = question_metric(recipe, spec)
    hib = spec.higher_is_better(qspec.canonical)
    pool = recipe.other_metrics
    while True:
        distractor = [rng.choice(spare)] if spare and rng.randint(0, 1) else []
        picks = [side_of[second], side_of[first]] + [("other", o) for o in distractor]
        qname = rng.choice(qspec.forms)
        extra = rng.sample(pool, rng.randint(min(1, len(pool)), min(2, len(pool))))
        names = [x for _, c in picks for x in (c.label, c.synonym)] + list(qname[:2])
        names += [x for m in extra for x in m.forms[0][:2]]
        if not _names_clash(names):
            break
    codes = [c.code if role != "other" else (recipe.other_codes or [None])[0] for role, c in picks]
    if None in codes:
        raise ValueError(f"the recipe of {recipe.domain} gives an arm of {sid} no code (its short name at the "
                         "distributed level; `code` of a side's name, `other_codes` of a distractor)")
    conditions = tuple(Condition(f"{sid}.c{i + 1}", role, c.label, c.synonym, c.description, code)
                       for i, ((role, c), code) in enumerate(zip(picks, codes)))
    metrics = (Metric(f"{sid}.k1", qspec.canonical, *qname, hib, qspec.unit),)
    metrics += tuple(Metric(f"{sid}.k{i + 2}", "other", *m.forms[0], m.higher_is_better, m.unit)
                     for i, m in enumerate(extra))
    q, control, treatment = metrics[0], conditions[0], conditions[1]
    want = rules.effect(rates[(first, context)], rates[(second, context)], hib, spec.min_effect)[0]
    low_n, high_n = recipe.reporting.arm_size
    for _ in range(TRIES):
        sizes = {c.id: rng.randint(low_n, high_n) for c in conditions}
        k_c, k_t = (round(rates[(thing, context)] * sizes[c.id]) for thing, c in ((second, control), (first, treatment)))
        v_c, v_t = k_c / sizes[control.id], k_t / sizes[treatment.id]
        if (all(1 <= k < sizes[c.id] and _usable(k / sizes[c.id]) for k, c in ((k_c, control), (k_t, treatment)))
                and rules.effect(v_t, v_c, hib, spec.min_effect)[0] == want):
            break
    else:
        raise ValueError(f"{sid}: no arm sizes in {recipe.reporting.arm_size} give the latent direction")
    counts = {(control.id, q.id): k_c, (treatment.id, q.id): k_t}
    taken = {v_c, v_t, abs(round(v_t - v_c, 3))}     # the complex level writes the difference: no value may read it
    measurements = []
    for metric in metrics:
        for cond in conditions:
            key = (cond.id, metric.id)
            if key not in counts:
                bounds = qspec.range if metric is q else metric_spec(recipe, metric).range
                counts[key] = _count(rng, bounds, sizes[cond.id], taken, sid)
                taken.add(counts[key] / sizes[cond.id])
            measurements.append(Measurement(f"{sid}.m{len(measurements) + 1}", cond.id, metric.id, context,
                                            counts[key] / sizes[cond.id], k=counts[key]))
    m_control = next(m for m in measurements if (m.condition, m.metric) == (control.id, q.id))
    m_treat = next(m for m in measurements if (m.condition, m.metric) == (treatment.id, q.id))
    got, delta = rules.effect(m_treat.value, m_control.value, hib, spec.min_effect)
    assert got == want, (sid, got, want)
    false_claim = FALSE_CLAIM[got]
    decoy = (_decoy(rng, q, m_control.value, false_claim, [m.value for m in measurements], spec, recipe)
             if index % 2 else None)
    return Study(sid, index, conditions, metrics, (context,), tuple(measurements),
                 Effect(got, delta, q.id, m_treat.id, m_control.id), true_claim(spec, got), false_claim, recipe,
                 decoy, population=context, arm_sizes=sizes)


def comparisons(studies: list[Study], spec: Synthesis) -> list[dict[str, Any]]:
    """Every pair of arms of a counted network study (relevant, not a duplicate) with values on the question metric,
    as the comparisons step builds them (plan 2 Task 8): `a` the name that sorts first, `direction` and `delta` of a
    over b by rules.effect. A --missing study lacks the pair whose value it never states."""
    out = []
    for s in studies:
        if not s.relevant or s.duplicate_of or s.population is None:
            continue
        q = s.primary
        arms = [(c.label, m.value) for c in s.conditions if (m := s.find(c.id, q.id, s.datasets[0])) is not None]
        for (a, a_value), (b, b_value) in (sorted(pair) for pair in combinations(arms, 2)):
            direction, delta = rules.effect(a_value, b_value, q.higher_is_better, spec.min_effect)
            out.append({"document": s.study_id, "a": a, "b": b, "metric": q.canonical, "context": s.population,
                        "a_value": a_value, "b_value": b_value, "direction": direction, "delta": delta})
    return out


def chains(studies: list[Study], recipe: Recipe, spec: Synthesis) -> list[dict[str, Any]]:
    """For every ordered pair (source, target) of network things that no study compares directly, every path
    source - via - target over two comparisons of `comparisons`, one record per pair of comparisons:
    {source, target, via: [via], studies (in study order), metric, context (the steps' context when they share it,
    else None), verdict, reason} with verdict and reason from rules.chain_verdict."""
    names = nodes(recipe)
    found = [c for c in comparisons(studies, spec) if c["a"] in names and c["b"] in names]
    direct = {frozenset((c["a"], c["b"])) for c in found}
    order = {s.study_id: i for i, s in enumerate(studies)}

    def steps(x: str, y: str) -> list[tuple[dict[str, Any], str]]:
        """The comparisons of x and y, each with the direction of x over y."""
        return [(c, c["direction"] if c["a"] == x else _flipped(c["direction"]))
                for c in found if {c["a"], c["b"]} == {x, y}]

    out = []
    for source in names:
        for target in names:
            if source == target or frozenset((source, target)) in direct:
                continue
            for via in names:
                if via in (source, target):
                    continue
                for c1, d1 in steps(source, via):
                    for c2, d2 in steps(via, target):
                        verdict, reason = rules.chain_verdict([(d1, c1["context"]), (d2, c2["context"])])
                        out.append({"source": source, "target": target, "via": [via],
                                    "studies": sorted({c1["document"], c2["document"]}, key=order.__getitem__),
                                    "metric": c1["metric"],
                                    "context": c1["context"] if c1["context"] == c2["context"] else None,
                                    "verdict": verdict, "reason": reason})
    return out


def _network(recipe: Recipe):
    if recipe.network is None:
        raise ValueError(f"the recipe of {recipe.domain} has no network")
    return recipe.network


def _flipped(direction: str) -> str:
    return {"supports": "contradicts", "contradicts": "supports"}.get(direction, direction)


def _usable(v: float) -> bool:
    """As truth._thousandths: the value's thousandths do not end in 0, so its percent form always has a non-zero
    decimal and is never read off a round number elsewhere in the paper."""
    return bool(round(v * 1000) % 10)


def _count(rng: random.Random, bounds: tuple[float, float], n: int, taken: set[float], sid: str) -> int:
    """A count k of n, 1 <= k < n, whose rate k / n lies in `bounds` and is far from every value taken."""
    low, high = max(1, math.ceil(bounds[0] * n)), min(n - 1, math.floor(bounds[1] * n))
    for _ in range(TRIES):
        k = rng.randint(low, high)
        if _usable(k / n) and _far(k / n, taken):
            return k
    raise ValueError(f"{sid}: no count of {n} in {bounds} lies apart from the study's other values")
