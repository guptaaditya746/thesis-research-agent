"""Structured ground truth: a seeded set of fictional studies for a protocol's question.

A study has a control and a treatment condition (the roles `synthesis.compare` of the protocol names)
plus 0-2 distractor conditions, one question metric (one of the protocol's `synthesis.metrics`) plus 1-2
distractor metrics, two datasets (the first is the main one), a measurement for every condition x metric x
dataset, and an author claim that agrees with the data. The effect is always `evidence.rules.effect` with the
protocol's parameters on the main dataset's treatment/control pair of the question metric, so the generator
and the engine use one definition: the protocol (`spec`, its `synthesis` block; the default is the recipe's
`effect_protocol`). Every name, context and value range comes from the recipe (`domains/<name>/generator.yaml`,
synth/recipe.py; default the default pack's); the code holds no topic word. Randomness comes only from one
`random.Random(seed)`; there is no clock.

The benchmark knobs (the supervisor's variants of 14 Oct, section 6: duplicated studies, missing
information, methodological limitations, unusually large effects; the irrelevant papers and the
mechanics are ours; contract docs/evidence-system.md F2) change the set after it is drawn, each from its
own `random.Random(f"synth:{seed}:{knob}")` stream, so the plain set (every knob 0) stays byte for byte
what it was:

- outliers: supporting studies whose treatment/control pair is drawn again with an improvement in the
  recipe's `effects.large` (the usual one is in `effects.supports`);
- duplicates: extra studies, ids continuing the sequence, that report an existing study's values again;
- missing: studies whose control (or, alternately, treatment) measurement on the question metric is
  dropped from both datasets, so the paper never states it and the effect is undetermined;
- irrelevant: extra studies with no experiment at all (a survey, or a paper on another topic), which a
  screening step should leave out (`relevant: false`, expected reason `screened_out`).

`hard` (ours; Tim M2 section 6-7, `synth build --hard`, template renderer only) is drawn before the knobs,
from `random.Random(f"synth:{seed}:hard")`: every study's measurements become its main experiment (`e1`, the
only one the effect, the claims and the answer are computed from), and about a third of the studies
(HARD_SHARE) report one or two more experiments on the main dataset: a question subset (control and
treatment again, any direction) and/or an ablation (the treatment against `<treatment> without
<component>`, role other; at most one per study). Their values are distractors: ground-truth facts that
extraction is scored on, never the synthesis pair. Without `hard` the set is byte for byte what it was.

The flags of every study come from `evidence.rules` applied to the set (`flagged`), as the engine applies
them to what it extracts; the generator then asserts the rules find exactly what it planted. The
counterfactual variant (F3, `redrawn`) draws one study's pair again with another direction.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

from evidence import protocol, rules
from evidence.pack import DOMAINS
from evidence.protocol import Synthesis
from synth.recipe import MetricSpec, Recipe, default_recipe, effect_protocol_path

DIRECTIONS = rules.DIRECTIONS
DEFAULT_PROTOCOL = effect_protocol_path(default_recipe())
# The claim a contradictory paper states instead: the usual spin (an improvement where there is none),
# or "no effect" where the data do show one.
FALSE_CLAIM = {"supports": "no_effect", "contradicts": "improves", "neutral": "improves"}
# A decoy lies more than this from every true value: the evaluation tolerance (0.005) plus a margin.
DECOY_GAP = 0.0075
DEFAULT_MIX = {"supports": 0.6, "contradicts": 0.2, "neutral": 0.2}
MISSING_SIDES = ("control", "treatment")   # --missing drops these in turn (the protocol's compare roles)
IRRELEVANT_TOPICS = ("survey", "other")    # --irrelevant alternates these templates (recipe text.irrelevant)
KNOBS = ("duplicates", "missing", "outliers", "irrelevant")
HARD_SHARE = 1 / 3                     # --hard: the share of studies that report more than one experiment
HARD_EXTRAS = (("subset",), ("ablation",), ("subset", "ablation"))   # the further experiments, drawn per study


def default_spec(recipe: Recipe | None = None) -> Synthesis:
    """The synthesis block of the recipe's effect protocol (default: the default pack's)."""
    recipe = recipe or default_recipe()
    return protocol.load(effect_protocol_path(recipe), None if recipe.root == DOMAINS else recipe.root).synthesis


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
    # --hard only (None otherwise): the experiment id. Left out of repr, so a plain set's repr is unchanged.
    experiment: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class Experiment:
    """One experiment of a --hard study: `e1` is the main comparison, the only one the effect is computed
    from; the others are distractors on the main dataset."""
    id: str                        # <study id>.e<n>
    name: str                      # the complex table's Experiment column
    conditions: tuple[str, ...]    # condition ids, in table order
    datasets: tuple[str, ...]


@dataclass(frozen=True)
class Effect:
    direction: str                 # supports | contradicts | neutral | undetermined
    delta: float | None            # None when undetermined
    metric: str | None             # question metric id; None for an irrelevant study
    treatment: str | None          # measurement id of the treatment condition on the main dataset
    control: str | None            # measurement id of the control condition; one is None when missing
    reason: str | None = None      # undetermined only: missing_control | missing_treatment | screened_out

    @property
    def determined(self) -> bool:
        return self.direction in DIRECTIONS


@dataclass(frozen=True)
class Study:
    study_id: str
    index: int
    conditions: tuple[Condition, ...]
    metrics: tuple[Metric, ...]
    datasets: tuple[str, ...]
    measurements: tuple[Measurement, ...]
    effect: Effect
    claim: str                     # agrees with the effect (with the data's direction when undetermined)
    false_claim: str               # what a contradictory paper states
    recipe: Recipe = field(repr=False, compare=False)   # the words the study was drawn from (and is written with)
    decoy: float | None = None     # a wrong treatment value a contradictory abstract states (odd studies)
    relevant: bool = True          # False: no experiment at all (--irrelevant); nothing below applies
    topic: str | None = None       # irrelevant only: the template, one of IRRELEVANT_TOPICS
    flags: tuple[str, ...] = ()    # from rules.FLAGS as the rules find them over the set (`flagged`)
    duplicate_of: str | None = None   # the study this one reports again (--duplicates)
    missing: str | None = None     # control | treatment: the measurement the paper never states (--missing)
    # --hard only (empty otherwise; left out of repr, so a plain set's repr is unchanged): main first
    experiments: tuple[Experiment, ...] = field(default=(), repr=False)

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

    @property
    def main_experiment(self) -> str | None:
        """The id of the experiment the effect is computed from (None without --hard)."""
        return self.experiments[0].id if self.experiments else None

    @property
    def main_conditions(self) -> tuple[Condition, ...]:
        """The conditions of the main experiment: all but a --hard ablation."""
        if not self.experiments:
            return self.conditions
        return tuple(c for c in self.conditions if c.id in self.experiments[0].conditions)

    def find(self, condition: str, metric: str, dataset: str, experiment: str | None = None) -> Measurement | None:
        """The measurement in `experiment` (default the main one)."""
        e = experiment or self.main_experiment
        return next((m for m in self.measurements
                     if (m.condition, m.metric, m.dataset, m.experiment) == (condition, metric, dataset, e)), None)

    def measurement(self, condition: str, metric: str, dataset: str) -> Measurement:
        found = self.find(condition, metric, dataset)
        if found is None:
            raise KeyError((self.study_id, condition, metric, dataset))
        return found

    def value_of(self, measurement_id: str) -> float:
        return next(m.value for m in self.measurements if m.id == measurement_id)

    def pair(self, dataset: str) -> tuple[Measurement, Measurement] | None:
        """(control, treatment) measurements on the question metric and `dataset`; None when one is
        missing or the study has no experiment."""
        if not self.relevant:
            return None
        q = self.primary
        c = self.find(self.condition(self.control_role).id, q.id, dataset)
        t = self.find(self.condition(self.treatment_role).id, q.id, dataset)
        return None if c is None or t is None else (c, t)

    @property
    def counted(self) -> bool:
        """Whether the answer counts this study: relevant, determined and not a duplicate."""
        return self.relevant and self.effect.determined and not self.duplicate_of


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


def _improvement(rng: random.Random, direction: str, min_effect: float, recipe: Recipe, large: bool = False) -> float:
    """A difference of `direction` in the recipe's `effects` ranges (`large`: an outlier's, supports only)."""
    if direction == "supports":
        return _thousandths(rng, *recipe.effects["large" if large else "supports"])
    if direction == "contradicts":
        return -_thousandths(rng, *recipe.effects["contradicts"])
    return rng.choice((1, -1)) * rng.choice(_neutral_band(min_effect)) / 1000


def metric_spec(recipe: Recipe, metric: Metric) -> MetricSpec:
    """The recipe's entry of a study's metric: a question metric by its canonical name, another by its name."""
    if metric.canonical != "other":
        return next(m for m in recipe.question_metrics if m.canonical == metric.canonical)
    return next(m for m in recipe.other_metrics if metric.name in (f[0] for f in m.forms))


def _far(v: float, taken: set[float]) -> bool:
    """`v` lies more than DECOY_GAP from every value already in the study, so a value read from the wrong
    cell can never match another fact by value alone (the evaluation's tolerance is 0.005)."""
    return all(abs(v - x) > DECOY_GAP for x in taken)


def _pair(rng: random.Random, metric: Metric, direction: str, taken: set[float], spec: Synthesis, recipe: Recipe,
          large: bool = False) -> tuple[float, float]:
    """(control, treatment) on a question metric with the given effect direction under rules.effect
    (`large`: an outlier-sized improvement, supports only); the control value from the metric's `pair_range`."""
    ms = metric_spec(recipe, metric)
    low, high = ms.pair_range or ms.range
    while True:
        base = _thousandths(rng, low, high)
        delta = _improvement(rng, direction, spec.min_effect, recipe, large)
        treat = round(base + delta if metric.higher_is_better else base - delta, 3)
        if (round(treat * 1000) % 10 and 0.05 <= treat <= 0.95 and _far(base, taken) and _far(treat, taken)
                and rules.effect(treat, base, metric.higher_is_better, spec.min_effect)[0] == direction):
            return base, treat


def _value(rng: random.Random, metric: Metric, taken: set[float], recipe: Recipe) -> float:
    """A value not under test, in the metric's `range` (seconds in hundredths, fractions in thousandths)."""
    low, high = metric_spec(recipe, metric).range
    while True:
        if metric.unit == "seconds":
            k = rng.randint(round(low * 100), round(high * 100))
            if not k % 10:          # 1.00 or 2.50 would equal a count denominator or a round filler number
                continue
            v = k / 100
        else:
            v = _thousandths(rng, low, high)
        if _far(v, taken):
            return v


def _names_clash(names: list[str]) -> bool:
    """One name inside another would make a rendering of one fact look like a rendering of another."""
    low = [n.lower() for n in names]
    return any(a != b and a in b for a in low for b in low)


def make_study(rng: random.Random, index: int, direction: str, spec: Synthesis, recipe: Recipe) -> Study:
    """One study of `direction`, its names drawn from the recipe: a name of each compared side (`recipe.sides`, by
    the protocol's roles), 0-2 other conditions, a form of the question metric, 1-2 other metrics (each written by
    its first form) and two contexts."""
    sid = f"S{index + 1:03d}"
    control_role, treatment_role = spec.compare.control, spec.compare.treatment
    missing = [r for r in (control_role, treatment_role) if r not in recipe.sides]
    if missing:
        raise ValueError(f"the recipe of {recipe.domain} has no side for the compared roles {missing}")
    names_of = {role: recipe.sides[role].names for role in (control_role, treatment_role)}
    question = {m.canonical: m for m in recipe.question_metrics}
    unknown = [m for m in spec.metric_names if m not in question]
    if unknown:
        raise ValueError(f"metric not in recipe: the recipe of {recipe.domain} has no question metric {unknown}")
    while True:
        others = rng.sample(recipe.others, rng.randint(0, 2))
        picks = [(control_role, rng.choice(names_of[control_role])), (treatment_role, rng.choice(names_of[treatment_role]))]
        picks += [("other", o) for o in others]
        canonical = rng.choice(sorted(spec.metric_names))
        qname = rng.choice(question[canonical].forms)
        extra = rng.sample(recipe.other_metrics, rng.randint(1, 2))
        names = [n for _, c in picks for n in (c.label, c.synonym)] + list(qname[:2])
        names += [n for m in extra for n in m.forms[0][:2]]
        if not _names_clash(names):
            break
    codes = [c.code if role != "other" else recipe.other_codes[i - 2] for i, (role, c) in enumerate(picks)]
    if None in codes:
        raise ValueError(f"the recipe of {recipe.domain} gives a compared name no code (its short name at the "
                         "distributed level)")
    conditions = tuple(Condition(f"{sid}.c{i + 1}", role, c.label, c.synonym, c.description, code)
                       for i, ((role, c), code) in enumerate(zip(picks, codes)))
    metrics = (Metric(f"{sid}.k1", canonical, *qname, spec.higher_is_better(canonical), question[canonical].unit),)
    metrics += tuple(Metric(f"{sid}.k{i + 2}", "other", *m.forms[0], m.higher_is_better, m.unit)
                     for i, m in enumerate(extra))
    datasets = tuple(rng.sample(recipe.contexts, 2))
    control, treatment = conditions[0], conditions[1]
    q = metrics[0]
    values: dict[tuple[str, str, str], float] = {}
    taken: set[float] = set()
    for dataset in datasets:            # both datasets show the same direction, so either pair answers alike
        b, t = _pair(rng, q, direction, taken, spec, recipe)
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
                    values[key] = _value(rng, metric, taken, recipe)
                    taken.add(values[key])
                measurements.append(Measurement(f"{sid}.m{len(measurements) + 1}", cond.id, metric.id,
                                                dataset, values[key]))
    m_control = next(m for m in measurements if (m.condition, m.metric, m.dataset) == (control.id, q.id, datasets[0]))
    m_treat = next(m for m in measurements if (m.condition, m.metric, m.dataset) == (treatment.id, q.id, datasets[0]))
    got, delta = rules.effect(m_treat.value, m_control.value, q.higher_is_better, spec.min_effect)
    assert got == direction, (sid, got, direction)
    false_claim = FALSE_CLAIM[direction]
    decoy = (_decoy(rng, q, m_control.value, false_claim, [m.value for m in measurements], spec, recipe)
             if index % 2 else None)
    return Study(sid, index, conditions, metrics, datasets, tuple(measurements),
                 Effect(got, delta, q.id, m_treat.id, m_control.id), true_claim(spec, direction), false_claim, recipe,
                 decoy)


def _decoy(rng: random.Random, metric: Metric, base: float, claim: str, values: list[float],
           spec: Synthesis, recipe: Recipe) -> float | None:
    """A treatment value that fits the false claim under rules.effect and lies more than DECOY_GAP from
    every true value of the study, so an extractor that takes it can never score it as a correct
    measurement. "No effect" leaves a narrow band between DECOY_GAP and min_effect; when other values
    block it, the study gets no decoy (None) rather than a misleading one."""
    direction = spec.claim_map[claim]
    for _ in range(200):
        d = _improvement(rng, direction, spec.min_effect, recipe)
        v = round(base + d if metric.higher_is_better else base - d, 3)
        if (round(v * 1000) % 10 and 0.05 <= v <= 0.95 and all(abs(v - x) > DECOY_GAP for x in values)
                and rules.effect(v, base, metric.higher_is_better, spec.min_effect)[0] == direction):
            return v
    return None


# --- the knobs and the counterfactual (our additions; docs/evidence-system.md F2, F3) ------------------

def redrawn(rng: random.Random, study: Study, direction: str, spec: Synthesis, *, large: bool = False) -> Study:
    """`study` with the treatment/control pair of the question metric drawn again on both datasets with
    the given direction (`large`: an outlier's improvement), from `rng`. Every other value is kept; as in
    make_study, the new values lie more than DECOY_GAP from them and from each other, and the main
    dataset's difference from every value. The effect, the claims and the decoy (odd studies) follow."""
    if not study.relevant or study.missing is not None:
        raise ValueError(f"{study.study_id} has no complete treatment/control pair to draw again")
    q, main = study.primary, study.datasets[0]
    control, treatment = study.conditions[0], study.conditions[1]
    pair_ids = {study.measurement(c.id, q.id, d).id for c in (control, treatment) for d in study.datasets}
    others = {m.value for m in study.measurements if m.id not in pair_ids}
    while True:
        taken, new = set(others), {}
        for dataset in study.datasets:
            b, t = _pair(rng, q, direction, taken, spec, study.recipe, large)
            new[(control.id, dataset)], new[(treatment.id, dataset)] = b, t
            taken |= {b, t}
            if dataset == main:
                taken.add(abs(round(t - b, 3)))
        if _far(abs(round(new[(treatment.id, main)] - new[(control.id, main)], 3)), others):
            break
    measurements = tuple(replace(m, value=new[(m.condition, m.dataset)]) if m.id in pair_ids else m
                         for m in study.measurements)
    m_control, m_treat = (next(m for m in measurements if m.id == study.measurement(c.id, q.id, main).id)
                          for c in (control, treatment))
    got, delta = rules.effect(m_treat.value, m_control.value, q.higher_is_better, spec.min_effect)
    assert got == direction, (study.study_id, got, direction)
    false_claim = FALSE_CLAIM[direction]
    decoy = (_decoy(rng, q, m_control.value, false_claim, [m.value for m in measurements], spec, study.recipe)
             if study.index % 2 else None)
    return replace(study, measurements=measurements, effect=Effect(got, delta, q.id, m_treat.id, m_control.id),
                   claim=true_claim(spec, direction), false_claim=false_claim, decoy=decoy)


def duplicate(original: Study, index: int) -> Study:
    """A second report of `original` as study number `index`: the same conditions, metrics, datasets and
    values, every fact id under the new study id, the same claims and decoy."""
    sid = f"S{index + 1:03d}"

    def renamed(fact_id: str | None) -> str | None:
        return None if fact_id is None else sid + fact_id[len(original.study_id):]

    e = original.effect
    return replace(
        original, study_id=sid, index=index,
        conditions=tuple(replace(c, id=renamed(c.id)) for c in original.conditions),
        metrics=tuple(replace(k, id=renamed(k.id)) for k in original.metrics),
        measurements=tuple(replace(m, id=renamed(m.id), condition=renamed(m.condition), metric=renamed(m.metric),
                                   experiment=renamed(m.experiment)) for m in original.measurements),
        experiments=tuple(replace(e, id=renamed(e.id), conditions=tuple(renamed(c) for c in e.conditions))
                          for e in original.experiments),
        effect=replace(e, metric=renamed(e.metric), treatment=renamed(e.treatment), control=renamed(e.control)),
        flags=(), duplicate_of=original.study_id)


def without(study: Study, side: str) -> Study:
    """`study` without its `side` (control | treatment) measurement on the question metric on both
    datasets: the paper never states it, so the effect is undetermined (`reason` missing_<side>) and the
    contradictory level states no decoy (a decoy is a treatment value, and a stated one would be a stray
    fact or, without a control, mean nothing)."""
    if side not in MISSING_SIDES:
        raise ValueError(f"missing side must be one of {MISSING_SIDES}, not {side!r}")
    q, e = study.primary, study.effect
    role = study.control_role if side == "control" else study.treatment_role
    dropped = {study.measurement(study.condition(role).id, q.id, d).id for d in study.datasets}
    effect = Effect("undetermined", None, q.id, treatment=e.treatment if side == "control" else None,
                    control=e.control if side == "treatment" else None, reason=f"missing_{side}")
    return replace(study, measurements=tuple(m for m in study.measurements if m.id not in dropped),
                   effect=effect, missing=side, decoy=None)


def irrelevant_study(index: int, topic: str, recipe: Recipe) -> Study:
    """A paper with no treatment/control experiment (a survey, or a paper on another topic; its text from the
    recipe's `text.irrelevant`): nothing to extract, expected to be screened out."""
    if topic not in IRRELEVANT_TOPICS:
        raise ValueError(f"irrelevant topic must be one of {IRRELEVANT_TOPICS}, not {topic!r}")
    return Study(f"S{index + 1:03d}", index, (), (), (), (), Effect("undetermined", None, None, None, None,
                                                                   "screened_out"), "", "", recipe,
                 relevant=False, topic=topic)


def with_experiments(rng: random.Random | None, study: Study, spec: Synthesis) -> Study:
    """`study` (complete, before the knobs) as a --hard study: its measurements become the main experiment;
    with `rng`, one or two further experiments on the main dataset (HARD_EXTRAS) are drawn: a question subset
    (control and treatment, a pair of any direction) and/or an ablation (the treatment, which beats it, and
    `<treatment> without <component>`, role other), every metric for each. As in make_study, every new
    value lies more than DECOY_GAP from every value of the study, the decoy and the main difference."""
    sid, q, dataset = study.study_id, study.primary, study.datasets[0]
    recipe = study.recipe
    words = recipe.text.hard
    main = Experiment(f"{sid}.e1", words.main_experiment, tuple(c.id for c in study.conditions), study.datasets)
    ms = [replace(m, experiment=main.id) for m in study.measurements]
    if rng is None:
        return replace(study, measurements=tuple(ms), experiments=(main,))
    control, treatment = study.conditions[0], study.conditions[1]
    kinds = rng.choice(HARD_EXTRAS)
    others = [n for c in study.conditions if c is not treatment for n in (c.label, c.synonym)]
    others += [n for k in study.metrics for n in (k.name, k.abbr)]
    while True:                         # the ablation contains the treatment's label, by design; nothing else may
        subset, component = rng.choice(words.subset_experiments), rng.choice(words.ablated)
        label = f"{treatment.label} without {component}"
        new = [words.main_experiment] + [{"subset": subset, "ablation": label}[k] for k in kinds]
        if not _names_clash(others + new):
            break
    taken = {m.value for m in ms} | {abs(round(study.value_of(study.effect.treatment)
                                               - study.value_of(study.effect.control), 3))}
    taken |= {study.decoy} if study.decoy is not None else set()
    conditions, experiments = list(study.conditions), [main]
    for kind in kinds:
        eid = f"{sid}.e{len(experiments) + 1}"
        if kind == "subset":
            b, t = _pair(rng, q, rng.choice(DIRECTIONS), taken, spec, recipe)
            e, pair = Experiment(eid, subset, (control.id, treatment.id), (dataset,)), {control.id: b, treatment.id: t}
        else:
            ablation = Condition(f"{sid}.c{len(conditions) + 1}", "other", label, label,
                                 words.ablation_description.format(component=component), "")
            conditions.append(ablation)
            b, t = _pair(rng, q, "supports", taken, spec, recipe)
            e, pair = (Experiment(eid, words.ablation_experiment, (treatment.id, ablation.id), (dataset,)),
                       {ablation.id: b, treatment.id: t})
        taken |= {b, t}
        experiments.append(e)
        for metric in study.metrics:
            for cid in e.conditions:
                v = pair[cid] if metric.id == q.id else _value(rng, metric, taken, recipe)
                taken.add(v)
                ms.append(Measurement(f"{sid}.m{len(ms) + 1}", cid, metric.id, dataset, v, eid))
    return replace(study, conditions=tuple(conditions), measurements=tuple(ms), experiments=tuple(experiments))


def hardened(seed: int, studies: list[Study], spec: Synthesis) -> list[Study]:
    """--hard over a plain set: HARD_SHARE of the studies (from `synth:<seed>:hard`) get further experiments,
    the rest only their main one (`with_experiments`)."""
    rng = random.Random(f"synth:{seed}:hard")
    chosen = set(rng.sample(range(len(studies)), round(len(studies) * HARD_SHARE)))
    return [with_experiments(rng if i in chosen else None, s, spec) for i, s in enumerate(studies)]


def pair_keys(study: Study) -> set[tuple[str, float, float]]:
    """rules.duplicate_key of the study's treatment/control pair on each dataset (none when undetermined)."""
    keys = set()
    for dataset in study.datasets:
        pair = study.pair(dataset)
        if pair is not None:
            keys.add(rules.duplicate_key(study.primary.canonical, pair[1].value, pair[0].value))
    return keys


def collides(study: Study, others: list[Study]) -> bool:
    """One of the study's pairs equals a pair of another study (on either dataset): the engine would take
    the two for one study, so the generator never lets it happen between distinct studies."""
    taken = set().union(*(pair_keys(o) for o in others if o.study_id != study.study_id))
    return bool(pair_keys(study) & taken)


def flagged(studies: list[Study], spec: Synthesis) -> list[Study]:
    """`flags` and `duplicate_of` of every study as evidence.rules finds them over the set with the
    protocol's `synthesis.flags`, in document order: `duplicate` (a later study with the same canonical
    metric, treatment and control value on the main dataset; off when the protocol says so),
    `large_effect` over the determined, non-duplicate studies' deltas. `claim_disagrees` depends on the
    level a paper is rendered at and is added by the corpus writer."""
    determined = [s for s in studies if s.effect.determined]
    dups = rules.duplicates([(s.study_id, s.primary.canonical, s.value_of(s.effect.treatment), s.value_of(s.effect.control))
                             for s in determined]) if spec.flags.duplicates else {}
    le = spec.flags.large_effect
    large = set(rules.large_effects({s.study_id: s.effect.delta for s in determined if s.study_id not in dups},
                                    le.factor, le.min_studies, spec.min_effect))
    out = []
    for s in studies:
        flags = (("duplicate",) if s.study_id in dups else ()) + (("large_effect",) if s.study_id in large else ())
        out.append(replace(s, flags=flags, duplicate_of=dups.get(s.study_id)))
    return out


def with_knobs(seed: int, base: list[Study], spec: Synthesis, recipe: Recipe, *, duplicates: int = 0,
               missing: int = 0, outliers: int = 0, irrelevant: int = 0) -> list[Study]:
    """The benchmark knobs applied to a plain study set, each from its own stream (`synth:<seed>:<knob>`):
    outliers among the supporting studies, duplicates of any study (ids after the set), missing among the
    studies that are neither outliers nor duplicated nor --hard studies with further experiments (control,
    treatment, control, ... in turn), then
    irrelevant papers (ids after the duplicates; survey, other, survey, ...). The result is `flagged`,
    and the planted outliers and duplicates must be exactly what the rules find; otherwise (too few
    studies, a natural large effect next to a planted one, a protocol with duplicate detection off) the
    build stops with the knob named."""
    for knob, value in (("duplicates", duplicates), ("missing", missing), ("outliers", outliers), ("irrelevant", irrelevant)):
        if value < 0:
            raise SystemExit(f"--{knob} {value}: a knob is a count, not negative")
    n, studies = len(base), list(base)
    o_rng = random.Random(f"synth:{seed}:outliers")
    supporting = [s.study_id for s in studies if s.effect.direction == "supports"]
    if outliers > len(supporting):
        raise SystemExit(f"--outliers {outliers}: only {len(supporting)} supporting studies to choose from")
    planted_outliers = sorted(o_rng.sample(supporting, outliers))
    for sid in planted_outliers:
        i = next(i for i, s in enumerate(studies) if s.study_id == sid)
        studies[i] = redrawn(o_rng, studies[i], "supports", spec, large=True)
        while collides(studies[i], studies):
            studies[i] = redrawn(o_rng, studies[i], "supports", spec, large=True)
    d_rng = random.Random(f"synth:{seed}:duplicates")
    if duplicates > n:
        raise SystemExit(f"--duplicates {duplicates}: only {n} studies to duplicate")
    if duplicates and not spec.flags.duplicates:
        raise SystemExit(f"--duplicates {duplicates}: the protocol turns duplicate detection off "
                         "(synthesis.flags.duplicates: false), so the planted duplicates would be counted")
    originals = [studies[i] for i in sorted(d_rng.sample(range(n), duplicates))]
    planted_duplicates = {}
    for k, original in enumerate(originals):
        studies.append(duplicate(original, n + k))
        planted_duplicates[studies[-1].study_id] = original.study_id
    m_rng = random.Random(f"synth:{seed}:missing")
    protected = set(planted_outliers) | set(planted_duplicates.values())
    # a --hard study with further experiments keeps a complete subset or ablation comparison when its main side
    # is dropped (`without` drops the main experiment's), so its undetermined gold would be arguable: not eligible
    eligible = [s.study_id for s in studies[:n] if s.study_id not in protected and len(s.experiments) <= 1]
    if missing > len(eligible):
        raise SystemExit(f"--missing {missing}: only {len(eligible)} studies are neither outliers nor duplicated "
                         "nor --hard studies with further experiments")
    for k, sid in enumerate(sorted(m_rng.sample(eligible, missing))):
        i = next(i for i, s in enumerate(studies) if s.study_id == sid)
        studies[i] = without(studies[i], MISSING_SIDES[k % len(MISSING_SIDES)])
    for k in range(irrelevant):
        studies.append(irrelevant_study(n + duplicates + k, IRRELEVANT_TOPICS[k % len(IRRELEVANT_TOPICS)], recipe))
    studies = flagged(studies, spec)
    found_duplicates = {s.study_id: s.duplicate_of for s in studies if s.duplicate_of}
    if found_duplicates != planted_duplicates:
        raise SystemExit(f"--duplicates {duplicates}: rules.duplicates finds {found_duplicates}, "
                         f"planted {planted_duplicates}")
    found_large = [s.study_id for s in studies if "large_effect" in s.flags]
    if outliers and found_large != planted_outliers:
        raise SystemExit(f"--outliers {outliers}: rules.large_effects flags {found_large}, planted "
                         f"{planted_outliers} (fewer than {spec.flags.large_effect.min_studies} non-neutral studies, "
                         "the median effect too close to them, or a study of the set is a large effect on its own); "
                         "choose another seed or count")
    return studies


def generate(seed: int, n: int, mix: dict[str, float] | None = None, spec: Synthesis | None = None, *,
             recipe: Recipe | None = None, duplicates: int = 0, missing: int = 0, outliers: int = 0,
             irrelevant: int = 0, hard: bool = False) -> list[Study]:
    """`n` studies drawn from `recipe` (default: the default pack's) for the protocol's synthesis block `spec`
    (default: the recipe's effect protocol's); the share of each true effect direction follows `mix` (default
    0.6/0.2/0.2); then `hard` (`hardened`), then the knobs. A study whose treatment/control pair equals an earlier
    study's (on either dataset) is drawn again, so equal pairs always mean one study; this never happens for the
    seeds in use, and the plain set is byte for byte what it was."""
    recipe = recipe or default_recipe()
    spec = spec or default_spec(recipe)
    rng = random.Random(seed)
    counts = effect_counts(n, mix or DEFAULT_MIX)
    directions = [d for d in DIRECTIONS for _ in range(counts[d])]
    rng.shuffle(directions)
    studies: list[Study] = []
    for i, d in enumerate(directions):
        study = make_study(rng, i, d, spec, recipe)
        while collides(study, studies):
            study = make_study(rng, i, d, spec, recipe)
        studies.append(study)
    if hard:
        studies = hardened(seed, studies, spec)
    return with_knobs(seed, studies, spec, recipe, duplicates=duplicates, missing=missing, outliers=outliers,
                      irrelevant=irrelevant)


def counted(studies: list[Study]) -> list[Study]:
    """The studies the answer counts: relevant, determined, not duplicates."""
    return [s for s in studies if s.counted]


def answer(studies: list[Study], spec: Synthesis | None = None, flags: dict[str, list[str]] | None = None) -> dict:
    """The answer to the question from the studies' true effects, via the protocol's label table over the
    counted studies; `flags` per study id (default: the studies' own, which lack the level-dependent
    claim_disagrees)."""
    spec = spec or default_spec()
    flags = flags if flags is not None else {s.study_id: list(s.flags) for s in studies}
    by = {d: [s.study_id for s in counted(studies) if s.effect.direction == d] for d in DIRECTIONS}
    counts = {rules.GROUP_OF[d]: len(v) for d, v in by.items()}
    return {"label": rules.label(counts, spec.table),
            "supporting": by["supports"], "contradicting": by["contradicts"], "neutral": by["neutral"],
            "undetermined": [s.study_id for s in studies if not s.duplicate_of and not s.effect.determined],
            "duplicates": [s.study_id for s in studies if s.duplicate_of],
            "flags": {f: [s.study_id for s in studies if f in flags.get(s.study_id, [])] for f in rules.FLAGS}}


def answer_counts(ans: dict) -> dict[str, int]:
    """The counts behind an answer (as the engine's answer.json reports them)."""
    return {k: len(ans[k]) for k in ("supporting", "contradicting", "neutral", "undetermined", "duplicates")}
