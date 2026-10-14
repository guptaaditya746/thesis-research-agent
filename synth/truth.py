"""Structured ground truth: a seeded set of fictional studies on the RAG factuality question.

A study has a baseline and a rag condition plus 0-2 distractor conditions, one question metric
(factual_accuracy or hallucination_rate) plus 1-2 distractor metrics, two datasets (the first is the
main one), a measurement for every condition x metric x dataset, and an author claim that agrees with
the data. The effect is always `evidence.rules.effect` on the main dataset's rag/baseline pair of the
question metric, so the generator and the engine use one definition. Randomness comes only from one
`random.Random(seed)`; there is no clock.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from evidence import rules
from synth import vocab

DIRECTIONS = ("supports", "contradicts", "neutral")
TRUE_CLAIM = {"supports": "improves", "contradicts": "worsens", "neutral": "no_effect"}
# The claim a contradictory paper states instead: the usual spin (an improvement where there is none),
# or "no effect" where the data do show one.
FALSE_CLAIM = {"supports": "no_effect", "contradicts": "improves", "neutral": "improves"}


@dataclass(frozen=True)
class Condition:
    id: str
    role: str                      # baseline | rag | other
    label: str
    synonym: str
    description: str
    code: str


@dataclass(frozen=True)
class Metric:
    id: str
    canonical: str                 # factual_accuracy | hallucination_rate | other
    name: str
    abbr: str
    description: str
    higher_is_better: bool
    unit: str                      # fraction | seconds


@dataclass(frozen=True)
class Measurement:
    id: str
    condition: str
    metric: str
    dataset: str
    value: float


@dataclass(frozen=True)
class Effect:
    direction: str
    delta: float
    metric: str
    rag: str
    baseline: str


@dataclass(frozen=True)
class Study:
    study_id: str
    index: int
    conditions: tuple[Condition, ...]
    metrics: tuple[Metric, ...]
    datasets: tuple[str, ...]
    measurements: tuple[Measurement, ...]
    effect: Effect
    claim: str                     # agrees with the effect
    false_claim: str               # what a contradictory paper states
    decoy: float | None = None     # a wrong rag value a contradictory abstract states (odd studies)

    def condition(self, role: str) -> Condition:
        return next(c for c in self.conditions if c.role == role)

    @property
    def primary(self) -> Metric:
        return self.metrics[0]

    def measurement(self, condition: str, metric: str, dataset: str) -> Measurement:
        return next(m for m in self.measurements
                    if (m.condition, m.metric, m.dataset) == (condition, metric, dataset))

    def value_of(self, measurement_id: str) -> float:
        return next(m.value for m in self.measurements if m.id == measurement_id)


def effect_counts(n: int, mix: dict[str, float]) -> dict[str, int]:
    """Studies per effect direction: largest remainder, ties in DIRECTIONS order."""
    total = sum(mix.get(d, 0.0) for d in DIRECTIONS)
    if total <= 0:
        raise ValueError("the effect mix must give a positive share to at least one direction")
    exact = {d: n * mix.get(d, 0.0) / total for d in DIRECTIONS}
    counts = {d: int(exact[d]) for d in DIRECTIONS}
    rest = sorted(DIRECTIONS, key=lambda d: (-(exact[d] - counts[d]), DIRECTIONS.index(d)))
    for d in rest[:n - sum(counts.values())]:
        counts[d] += 1
    return counts


def _thousandths(rng: random.Random, low: float, high: float) -> float:
    """A fraction with three decimals whose last digit is not 0, so its percent form always has a
    decimal (62.4) and can never be read off an integer elsewhere in the paper."""
    while True:
        k = rng.randint(round(low * 1000), round(high * 1000))
        if k % 10:
            return k / 1000


def _improvement(rng: random.Random, direction: str) -> float:
    if direction == "supports":
        return _thousandths(rng, 0.03, 0.15)
    if direction == "contradicts":
        return -_thousandths(rng, 0.03, 0.10)
    return rng.choice((1, -1)) * rng.randint(2, 6) / 1000


def _pair(rng: random.Random, metric: Metric, direction: str, taken: set[float]) -> tuple[float, float]:
    """(baseline, rag) on a question metric with the given effect direction under rules.effect."""
    low, high = (0.35, 0.80) if metric.higher_is_better else (0.10, 0.45)
    while True:
        base = _thousandths(rng, low, high)
        delta = _improvement(rng, direction)
        rag = round(base + delta if metric.higher_is_better else base - delta, 3)
        if (round(rag * 1000) % 10 and 0.05 <= rag <= 0.95 and base not in taken and rag not in taken
                and rules.effect(rag, base, metric.higher_is_better)[0] == direction):
            return base, rag


def _value(rng: random.Random, metric: Metric, taken: set[float]) -> float:
    while True:
        if metric.unit == "seconds":
            k = rng.randint(40, 350)
            if not k % 10:          # 1.00 or 2.50 would equal a count denominator or a round filler number
                continue
            v = k / 100
        elif metric.canonical == "other":
            v = _thousandths(rng, 0.10, 0.55)
        else:
            v = _thousandths(rng, 0.30, 0.80) if metric.higher_is_better else _thousandths(rng, 0.08, 0.50)
        if v not in taken:
            return v


def _names_clash(names: list[str]) -> bool:
    """One name inside another would make a rendering of one fact look like a rendering of another."""
    low = [n.lower() for n in names]
    return any(a != b and a in b for a in low for b in low)


def make_study(rng: random.Random, index: int, direction: str) -> Study:
    sid = f"S{index + 1:03d}"
    while True:
        others = rng.sample(vocab.OTHERS, rng.randint(0, 2))
        picks = [("baseline", rng.choice(vocab.BASELINES)), ("rag", rng.choice(vocab.RAGS))]
        picks += [("other", o) for o in others]
        canonical = rng.choice(sorted(rules.METRICS))
        qname = rng.choice(vocab.QUESTION_METRICS[canonical])
        extra = rng.sample(vocab.OTHER_METRICS, rng.randint(1, 2))
        names = [n for _, c in picks for n in c[:2]] + list(qname[:2]) + [n for m in extra for n in m[1:3]]
        if not _names_clash(names):
            break
    conditions = tuple(
        Condition(f"{sid}.c{i + 1}", role, label, syn, desc,
                  vocab.CODES.get(role) or vocab.OTHER_CODES[i - 2])
        for i, (role, (label, syn, desc)) in enumerate(picks))
    metrics = (Metric(f"{sid}.k1", canonical, *qname, rules.METRICS[canonical], "fraction"),) + tuple(
        Metric(f"{sid}.k{i + 2}", "other", name, abbr, desc, hib, unit)
        for i, (_, name, abbr, desc, hib, unit) in enumerate(extra))
    datasets = tuple(rng.sample(vocab.DATASETS, 2))
    base, rag = conditions[0], conditions[1]
    q = metrics[0]
    values: dict[tuple[str, str, str], float] = {}
    taken: set[float] = set()
    for dataset in datasets:            # both datasets show the same direction, so either pair answers alike
        b, r = _pair(rng, q, direction, taken)
        values[(base.id, q.id, dataset)], values[(rag.id, q.id, dataset)] = b, r
        taken |= {b, r}
        if dataset == datasets[0]:      # the complex level writes this difference ("7.0 percentage points"):
            taken.add(abs(round(r - b, 3)))   # no other value may read the same
    measurements = []
    for dataset in datasets:
        for metric in metrics:
            for cond in conditions:
                key = (cond.id, metric.id, dataset)
                if key not in values:
                    values[key] = _value(rng, metric, taken)
                    taken.add(values[key])
                measurements.append(Measurement(f"{sid}.m{len(measurements) + 1}", cond.id, metric.id,
                                                dataset, values[key]))
    m_base = next(m for m in measurements if (m.condition, m.metric, m.dataset) == (base.id, q.id, datasets[0]))
    m_rag = next(m for m in measurements if (m.condition, m.metric, m.dataset) == (rag.id, q.id, datasets[0]))
    got, delta = rules.effect(m_rag.value, m_base.value, q.higher_is_better)
    assert got == direction, (sid, got, direction)
    false_claim = FALSE_CLAIM[direction]
    decoy = _decoy(rng, q, m_base.value, false_claim, taken) if index % 2 else None
    return Study(sid, index, conditions, metrics, datasets, tuple(measurements),
                 Effect(got, delta, q.id, m_rag.id, m_base.id), TRUE_CLAIM[direction], false_claim, decoy)


def _decoy(rng: random.Random, metric: Metric, base: float, claim: str, taken: set[float]) -> float:
    """A rag value that fits the false claim, distinct from every true value of the study."""
    direction = "supports" if claim == "improves" else "neutral" if claim == "no_effect" else "contradicts"
    while True:
        d = _improvement(rng, direction)
        v = round(base + d if metric.higher_is_better else base - d, 3)
        if round(v * 1000) % 10 and 0.05 <= v <= 0.95 and v not in taken:
            return v


def generate(seed: int, n: int, mix: dict[str, float] | None = None) -> list[Study]:
    """`n` studies; the share of each true effect direction follows `mix` (default 0.6/0.2/0.2)."""
    rng = random.Random(seed)
    counts = effect_counts(n, mix or {"supports": 0.6, "contradicts": 0.2, "neutral": 0.2})
    directions = [d for d in DIRECTIONS for _ in range(counts[d])]
    rng.shuffle(directions)
    return [make_study(rng, i, d) for i, d in enumerate(directions)]


def answer(studies: list[Study]) -> dict:
    """The answer to the question from the studies' true effects, via rules.label."""
    by = {d: [s.study_id for s in studies if s.effect.direction == d] for d in DIRECTIONS}
    return {"label": rules.label(len(by["supports"]), len(by["contradicts"]), len(by["neutral"])),
            "supporting": by["supports"], "contradicting": by["contradicts"], "neutral": by["neutral"]}
