"""Difficulty levels and the rendering plan shared by the template and the LLM renderer.

A plan fixes, for one study at one level, which facts the paper states and the exact string each one is
written as (names, codes, value formats, claim sentences, the decoy). The template renderer lays the plan
out itself; the LLM renderer hands it to a model and then checks the strings are there. So both
renderers write the same facts the same way and differ only in the prose around them.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from synth.recipe import Recipe
from synth.text import Decoy, Seg
from synth.truth import Condition, Experiment, Measurement, Metric, Study

LEVELS = ("explicit", "paraphrased", "distributed", "complex", "contradictory")
# What a table cell shows for a measurement the paper never states (--missing, our addition): an en dash,
# U+2013, which no number regex reads and which is not a Markdown separator.
MISSING_CELL = "–"

DEFINITIONS = {
    "explicit": "Every value is stated once, in one Results sentence that names the condition and the metric "
                "verbatim (the study's own labels) together with the dataset; values are written as percent "
                "(62.4%). No tables. Facts: all conditions on the question metric on the main dataset.",
    "paraphrased": "Conditions and the metric are never called by their labels but by descriptive synonyms "
                   "(the recipe's `synonym` and metric description); values appear in prose in varied formats: "
                   "percent (62.4%), fraction (0.624) and count (624 out of 1,000), at least two formats per "
                   "paper. Same facts as explicit.",
    "distributed": "Values appear only in one Markdown table whose rows are short codes (B, R, A1, A2) and whose "
                   "value column header is the metric's abbreviation with a percent unit (XY (%)); the codes "
                   "and the abbreviation are defined in the Method section, separated from the table by "
                   "several paragraphs. No sentence states a value. Same facts as explicit.",
    "complex": "Every condition (with the distractor systems), the question metric and one or two distractor "
               "metrics on two datasets, in one table with full labels and a Dataset column "
               "(one row per dataset and condition); the "
               "treatment value on the question metric of the main (first) dataset is not in the table but given "
               "in the text relative to the control ('7.0 percentage points higher than the ...'). The reader "
               "must pick the treatment/control pair of the question metric on the main dataset.",
    "contradictory": "The values are in a table with full labels, but the author claim (abstract and conclusion) "
                     "disagrees with them (it claims an improvement the table does not show, or no effect where "
                     "it does); in odd-index studies the abstract also states a wrong treatment value (a decoy, "
                     "more than 0.0075 from every true value; left out in the rare study where none fits). The "
                     "table is the truth: the effect is computed from it and the claim is recorded as stated. "
                     "Same facts as explicit.",
}


@dataclass(frozen=True)
class Plan:
    study: Study
    level: str
    conditions: tuple[Condition, ...]
    metrics: tuple[Metric, ...]
    datasets: tuple[str, ...]
    measurements: tuple[Measurement, ...]
    cond_name: dict[str, str]                 # the name prose uses (label, or synonym when paraphrased)
    cond_aliases: dict[str, tuple[str, ...]]  # other strings that render the condition (codes)
    metric_name: dict[str, str]               # the name prose uses (name, or description when paraphrased)
    metric_aliases: dict[str, tuple[str, ...]]  # abbreviation, description
    values: dict[str, Seg]                    # measurement id -> its rendering
    claim: str                                # claim direction as stated ("" for an irrelevant paper)
    claim_sentences: tuple[str, ...]          # abstract, conclusion (none for an irrelevant paper)
    decoy: Decoy | None
    experiments: tuple[Experiment, ...] = ()  # --hard, complex level only: every experiment, main first

    @property
    def paper(self) -> str:
        return self.study.study_id

    @property
    def recipe(self) -> Recipe:
        """The recipe the study was drawn from; the renderers write its words."""
        return self.study.recipe

    def cond(self, cid: str) -> Seg:
        return Seg(cid, "condition_label", self.cond_name[cid])

    def code(self, cid: str) -> Seg:
        return Seg(cid, "condition_label", self.cond_aliases[cid][0])

    def metric(self, kid: str, text: str | None = None) -> Seg:
        return Seg(kid, "metric_label", text or self.metric_name[kid])

    def condition(self, cid: str) -> Condition:
        return next(c for c in self.conditions if c.id == cid)

    def metric_of(self, kid: str) -> Metric:
        return next(m for m in self.metrics if m.id == kid)


def thousandths(v: float) -> int:
    return round(v * 1000)


def pct(v: float) -> str:
    k = thousandths(v)
    return f"{k // 10}.{k % 10}"


def write_value(v: float, fmt: str, base: float | None = None, *, k: int | None = None, n: int | None = None,
                noun: str | None = None) -> str:
    """The string a value is written as; `parse_value` inverts it. `k_of_n` writes the count k of the arm's n
    (`Measurement.k`, `Study.arm_sizes`) with the recipe's `text.unit_noun`: "41 of 120 <noun>"."""
    if fmt == "k_of_n":
        if k is None or n is None or not noun:
            raise ValueError("fmt k_of_n needs the count k, the arm size n and the recipe's unit noun")
        return f"{k} of {n} {noun}"
    if fmt == "pct":
        return pct(v) + "%"
    if fmt == "frac":
        return f"0.{thousandths(v):03d}"
    if fmt == "count":
        return f"{thousandths(v)} out of 1,000"
    if fmt == "cell_pct":
        return pct(v)
    if fmt == "cell_raw":
        return f"{v:.2f}"
    if fmt == "relative":
        tenths = thousandths(v) - thousandths(base)
        return f"{abs(tenths) // 10}.{abs(tenths) % 10} percentage points {'higher' if tenths > 0 else 'lower'}"
    raise ValueError(fmt)


def parse_value(text: str, fmt: str, base: float | None = None) -> float:
    """The normalised value a rendering states (fractions for percent and counts)."""
    if fmt == "k_of_n":
        k, _, n = text.split()[:3]
        return round(int(k.replace(",", "")) / int(n.replace(",", "")), 6)
    number = float(text.split()[0].rstrip("%").replace(",", ""))
    if fmt in ("pct", "cell_pct"):
        return round(number / 100, 6)
    if fmt == "count":
        return round(number / 1000, 6)
    if fmt == "relative":
        sign = 1 if text.endswith("higher") else -1
        return round(base + sign * number / 100, 6)
    return round(number, 6)


def irrelevant_plan(study: Study, level: str) -> Plan:
    """The (empty) plan of a paper with no experiment: nothing to place, no claim; `level` is the corpus
    level the paper is filed under (its text is the same at every level)."""
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}")
    if study.relevant:
        raise ValueError(f"{study.study_id} is a relevant study; use make_plan")
    return Plan(study, level, (), (), (), (), {}, {}, {}, {}, {}, "", (), None)


def make_plan(study: Study, level: str, rng: random.Random) -> Plan:
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}")
    if not study.relevant:
        return irrelevant_plan(study, level)
    q, main = study.primary, study.datasets[0]
    # A --hard study shows all its experiments (the ablation among the conditions) only at the complex
    # level, one table with an Experiment column; the other levels show its main experiment alone.
    if level == "complex":
        conditions, metrics, datasets, ms = study.conditions, study.metrics, study.datasets, study.measurements
        experiments = study.experiments
    else:
        conditions, metrics, datasets, experiments = study.main_conditions, (q,), (main,), ()
        ms = tuple(m for m in study.measurements
                   if m.metric == q.id and m.dataset == main and m.experiment == study.main_experiment)
    para = level == "paraphrased"
    cond_name = {c.id: c.synonym if para else c.label for c in conditions}
    cond_aliases = {c.id: (c.code,) if level == "distributed" else () for c in conditions}
    metric_name = {m.id: m.description if para else m.name for m in metrics}
    metric_aliases = {m.id: () if para else ((m.abbr,) if level == "distributed" else ()) + (m.description,)
                      for m in metrics}
    # A --missing study lacks its control or treatment measurement (None here): the complex level then has
    # no relative value (the treatment value, if present, is a plain cell) and the contradictory level no decoy.
    base = study.find(study.control_condition.id, q.id, main)
    treat = study.find(study.treatment_condition.id, q.id, main)
    base_value = base.value if base is not None else None
    fmts = ["pct", "frac", "count"]
    rng.shuffle(fmts)
    values: dict[str, Seg] = {}
    for i, m in enumerate(ms):
        unit = next(k for k in metrics if k.id == m.metric).unit
        if level == "explicit":
            fmt = "pct"
        elif para:
            fmt = fmts[i % len(fmts)]
        elif level == "complex" and treat is not None and base is not None and m.id == treat.id:
            fmt = "relative"
        else:
            fmt = "cell_raw" if unit == "seconds" else "cell_pct"
        values[m.id] = Seg(m.id, "value", write_value(m.value, fmt, base_value), fmt)
    claim = study.false_claim if level == "contradictory" else study.claim
    decoy = None
    if level == "contradictory" and study.decoy is not None and treat is not None and base is not None:
        decoy = Decoy(treat.id, study.decoy, write_value(study.decoy, "pct"))
    return Plan(study, level, conditions, metrics, datasets, ms, cond_name, cond_aliases, metric_name,
                metric_aliases, values, claim, study.recipe.text.claims[claim][q.canonical], decoy, experiments)


def plan_rng(seed: int, study_id: str, level: str) -> random.Random:
    """One generator per (seed, study, level): a paper's text does not depend on which other papers or
    levels are built, so the mixed corpus reuses the level corpora's papers byte for byte."""
    return random.Random(f"synth:{seed}:{study_id}:{level}")
