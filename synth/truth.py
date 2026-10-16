"""Structured ground truth: a seeded set of fictional studies for a protocol's question.

A study has a control and a treatment condition (the roles `synthesis.compare` of the protocol names;
for the RAG question `baseline` and `rag`) plus 0-2 distractor conditions, one question metric (one of
the protocol's `synthesis.metrics`) plus 1-2 distractor metrics, two datasets (the first is the main
one), a measurement for every condition x metric x dataset, and an author claim that agrees with the
data. The effect is always `evidence.rules.effect` with the protocol's parameters on the main dataset's
treatment/control pair of the question metric, so the generator and the engine use one definition: the
protocol (`spec`, its `synthesis` block; the default is `evidence/protocols/rag-factuality.yaml`).
Randomness comes only from one `random.Random(seed)`; there is no clock.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from evidence import protocol, rules
from evidence.protocol import Synthesis
from synth import vocab

DIRECTIONS = rules.DIRECTIONS
DEFAULT_PROTOCOL = Path(__file__).resolve().parents[1] / "evidence" / "protocols" / "rag-factuality.yaml"
# The claim a contradictory paper states instead: the usual spin (an improvement where there is none),
# or "no effect" where the data do show one.
FALSE_CLAIM = {"supports": "no_effect", "contradicts": "improves", "neutral": "improves"}
# A decoy lies more than this from every true value: the evaluation tolerance (0.005) plus a margin.
DECOY_GAP = 0.0075


def default_spec() -> Synthesis:
    return protocol.load(DEFAULT_PROTOCOL).synthesis


def true_claim(spec: Synthesis, direction: str) -> str:
    """The author-claim value that asserts `direction` (the inverse of the protocol's claim_map)."""
    return next(c for c, d in spec.claim_map.items() if d == direction)


@dataclass(frozen=True)
class Condition:
    id: str
    role: str                      # control role | treatment role | other
    label: str
    synonym: str
    description: str
    code: str


@dataclass(frozen=True)
class Metric:
    id: str
    canonical: str                 # a question metric's canonical name | other
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
    treatment: str                 # measurement id of the treatment condition on the main dataset
    control: str                   # measurement id of the control condition on the main dataset


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
    decoy: float | None = None     # a wrong treatment value a contradictory abstract states (odd studies)

    def condition(self, role: str) -> Condition:
        return next(c for c in self.conditions if c.role == role)

    @property
    def primary(self) -> Metric:
        return self.metrics[0]

    @property
    def treatment_role(self) -> str:
        return self.conditions[1].role

    @property
    def control_role(self) -> str:
        return self.conditions[0].role

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


def _neutral_band(min_effect: float) -> tuple[int, ...]:
    """Thousandths a neutral difference may take: more than DECOY_GAP (so the pair stays apart) and
    below the protocol's min_effect. Empty when the protocol leaves no room."""
    band = tuple(range(int(DECOY_GAP * 1000) + 1, round(min_effect * 1000)))
    if not band:
        raise ValueError(f"min_effect {min_effect} leaves no neutral band above DECOY_GAP {DECOY_GAP}")
    return band


def _improvement(rng: random.Random, direction: str, min_effect: float) -> float:
    if direction == "supports":
        return _thousandths(rng, 0.03, 0.15)
    if direction == "contradicts":
        return -_thousandths(rng, 0.03, 0.10)
    return rng.choice((1, -1)) * rng.choice(_neutral_band(min_effect)) / 1000


def _far(v: float, taken: set[float]) -> bool:
    """`v` lies more than DECOY_GAP from every value already in the study, so a value read from the wrong
    cell can never match another fact by value alone (the evaluation's tolerance is 0.005)."""
    return all(abs(v - x) > DECOY_GAP for x in taken)


def _pair(rng: random.Random, metric: Metric, direction: str, taken: set[float], spec: Synthesis) -> tuple[float, float]:
    """(control, treatment) on a question metric with the given effect direction under rules.effect."""
    low, high = (0.35, 0.80) if metric.higher_is_better else (0.10, 0.45)
    while True:
        base = _thousandths(rng, low, high)
        delta = _improvement(rng, direction, spec.min_effect)
        treat = round(base + delta if metric.higher_is_better else base - delta, 3)
        if (round(treat * 1000) % 10 and 0.05 <= treat <= 0.95 and _far(base, taken) and _far(treat, taken)
                and rules.effect(treat, base, metric.higher_is_better, spec.min_effect)[0] == direction):
            return base, treat


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
        if _far(v, taken):
            return v


def _names_clash(names: list[str]) -> bool:
    """One name inside another would make a rendering of one fact look like a rendering of another."""
    low = [n.lower() for n in names]
    return any(a != b and a in b for a in low for b in low)


def make_study(rng: random.Random, index: int, direction: str, spec: Synthesis) -> Study:
    sid = f"S{index + 1:03d}"
    control_role, treatment_role = spec.compare.control, spec.compare.treatment
    names_of = {control_role: vocab.BASELINES, treatment_role: vocab.RAGS}
    unknown = [m for m in spec.metric_names if m not in vocab.QUESTION_METRICS]
    if unknown:
        raise ValueError(f"synth has no vocabulary for the question metrics {unknown}")
    while True:
        others = rng.sample(vocab.OTHERS, rng.randint(0, 2))
        picks = [(control_role, rng.choice(names_of[control_role])), (treatment_role, rng.choice(names_of[treatment_role]))]
        picks += [("other", o) for o in others]
        canonical = rng.choice(sorted(spec.metric_names))
        qname = rng.choice(vocab.QUESTION_METRICS[canonical])
        extra = rng.sample(vocab.OTHER_METRICS, rng.randint(1, 2))
        names = [n for _, c in picks for n in c[:2]] + list(qname[:2]) + [n for m in extra for n in m[1:3]]
        if not _names_clash(names):
            break
    conditions = tuple(
        Condition(f"{sid}.c{i + 1}", role, label, syn, desc,
                  vocab.CODES.get(role) or vocab.OTHER_CODES[i - 2])
        for i, (role, (label, syn, desc)) in enumerate(picks))
    metrics = (Metric(f"{sid}.k1", canonical, *qname, spec.higher_is_better(canonical), "fraction"),) + tuple(
        Metric(f"{sid}.k{i + 2}", "other", name, abbr, desc, hib, unit)
        for i, (_, name, abbr, desc, hib, unit) in enumerate(extra))
    datasets = tuple(rng.sample(vocab.DATASETS, 2))
    control, treatment = conditions[0], conditions[1]
    q = metrics[0]
    values: dict[tuple[str, str, str], float] = {}
    taken: set[float] = set()
    for dataset in datasets:            # both datasets show the same direction, so either pair answers alike
        b, t = _pair(rng, q, direction, taken, spec)
        values[(control.id, q.id, dataset)], values[(treatment.id, q.id, dataset)] = b, t
        taken |= {b, t}
        if dataset == datasets[0]:      # the complex level writes this difference ("7.0 percentage points"):
            taken.add(abs(round(t - b, 3)))   # no other value may read the same
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
    m_control = next(m for m in measurements if (m.condition, m.metric, m.dataset) == (control.id, q.id, datasets[0]))
    m_treat = next(m for m in measurements if (m.condition, m.metric, m.dataset) == (treatment.id, q.id, datasets[0]))
    got, delta = rules.effect(m_treat.value, m_control.value, q.higher_is_better, spec.min_effect)
    assert got == direction, (sid, got, direction)
    false_claim = FALSE_CLAIM[direction]
    decoy = (_decoy(rng, q, m_control.value, false_claim, [m.value for m in measurements], spec)
             if index % 2 else None)
    return Study(sid, index, conditions, metrics, datasets, tuple(measurements),
                 Effect(got, delta, q.id, m_treat.id, m_control.id), true_claim(spec, direction), false_claim, decoy)


def _decoy(rng: random.Random, metric: Metric, base: float, claim: str, values: list[float],
           spec: Synthesis) -> float | None:
    """A treatment value that fits the false claim under rules.effect and lies more than DECOY_GAP from
    every true value of the study, so an extractor that takes it can never score it as a correct
    measurement. "No effect" leaves a narrow band between DECOY_GAP and min_effect; when other values
    block it, the study gets no decoy (None) rather than a misleading one."""
    direction = spec.claim_map[claim]
    for _ in range(200):
        d = _improvement(rng, direction, spec.min_effect)
        v = round(base + d if metric.higher_is_better else base - d, 3)
        if (round(v * 1000) % 10 and 0.05 <= v <= 0.95 and all(abs(v - x) > DECOY_GAP for x in values)
                and rules.effect(v, base, metric.higher_is_better, spec.min_effect)[0] == direction):
            return v
    return None


def generate(seed: int, n: int, mix: dict[str, float] | None = None, spec: Synthesis | None = None) -> list[Study]:
    """`n` studies for the protocol's synthesis block `spec` (default: the RAG protocol); the share of each
    true effect direction follows `mix` (default 0.6/0.2/0.2)."""
    spec = spec or default_spec()
    rng = random.Random(seed)
    counts = effect_counts(n, mix or {"supports": 0.6, "contradicts": 0.2, "neutral": 0.2})
    directions = [d for d in DIRECTIONS for _ in range(counts[d])]
    rng.shuffle(directions)
    return [make_study(rng, i, d, spec) for i, d in enumerate(directions)]


def answer(studies: list[Study], spec: Synthesis | None = None) -> dict:
    """The answer to the question from the studies' true effects, via the protocol's label table."""
    spec = spec or default_spec()
    by = {d: [s.study_id for s in studies if s.effect.direction == d] for d in DIRECTIONS}
    counts = {rules.GROUP_OF[d]: len(v) for d, v in by.items()}
    return {"label": rules.label(counts, spec.table),
            "supporting": by["supports"], "contradicting": by["contradicts"], "neutral": by["neutral"]}
