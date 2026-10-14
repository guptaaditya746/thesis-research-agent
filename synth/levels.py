"""Difficulty levels and the rendering plan shared by the template and the LLM renderer.

A plan fixes, for one study at one level, which facts the paper states and the exact string each one is
written as (names, codes, value formats, claim sentences, the decoy). The template renderer lays the plan
out itself; the LLM renderer hands it to a model and then checks the strings are there. So both
renderers write the same facts the same way and differ only in the prose around them.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from synth import vocab
from synth.text import Decoy, Seg
from synth.truth import Condition, Measurement, Metric, Study

LEVELS = ("explicit", "paraphrased", "distributed", "complex", "contradictory")

DEFINITIONS = {
    "explicit": "Every value is stated once, in one Results sentence that names the condition and the metric "
                "verbatim (the study's own labels) together with the dataset; values are written as percent "
                "(62.4%). No tables. Facts: all conditions on the question metric on the main dataset.",
    "paraphrased": "Conditions and the metric are never called by their labels but by descriptive synonyms "
                   "('the model that answers from its own parameters', 'share of answers whose facts are all "
                   "correct'); values appear in prose in varied formats: percent (62.4%), fraction (0.624) and "
                   "count (624 out of 1,000), at least two formats per paper. Same facts as explicit.",
    "distributed": "Values appear only in one Markdown table whose rows are short codes (B, R, A1, A2) and whose "
                   "value column header is the metric's abbreviation with a percent unit (FA (%)); the codes "
                   "and the abbreviation are defined in the Method section, separated from the table by "
                   "several paragraphs. No sentence states a value. Same facts as explicit.",
    "complex": "Every condition (with the distractor systems), the question metric and one or two distractor "
               "metrics (BLEU, ROUGE-L, latency) on two datasets, one table per dataset with full labels; the "
               "rag value on the question metric of the main (first) dataset is not in the table but given in "
               "the text relative to the baseline ('7.0 percentage points higher than the ...'). The reader "
               "must pick the rag/baseline pair of the question metric on the main dataset.",
    "contradictory": "The values are in a table with full labels, but the author claim (abstract and conclusion) "
                     "disagrees with them (it claims an improvement the table does not show, or no effect where "
                     "it does); in odd-index studies the abstract also states a wrong rag value (a decoy, more than "
                     "0.0075 from every true value; left out in the rare study where none fits). The "
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
    claim: str                                # claim direction as stated
    claim_sentences: tuple[str, str]          # abstract, conclusion
    decoy: Decoy | None

    @property
    def paper(self) -> str:
        return self.study.study_id

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


def write_value(v: float, fmt: str, base: float | None = None) -> str:
    """The string a value is written as; `parse_value` inverts it."""
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
    number = float(text.split()[0].rstrip("%").replace(",", ""))
    if fmt in ("pct", "cell_pct"):
        return round(number / 100, 6)
    if fmt == "count":
        return round(number / 1000, 6)
    if fmt == "relative":
        sign = 1 if text.endswith("higher") else -1
        return round(base + sign * number / 100, 6)
    return round(number, 6)


def make_plan(study: Study, level: str, rng: random.Random) -> Plan:
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}")
    q, main = study.primary, study.datasets[0]
    if level == "complex":
        metrics, datasets, ms = study.metrics, study.datasets, study.measurements
    else:
        metrics, datasets = (q,), (main,)
        ms = tuple(m for m in study.measurements if m.metric == q.id and m.dataset == main)
    para = level == "paraphrased"
    cond_name = {c.id: c.synonym if para else c.label for c in study.conditions}
    cond_aliases = {c.id: (c.code,) if level == "distributed" else () for c in study.conditions}
    metric_name = {m.id: m.description if para else m.name for m in metrics}
    metric_aliases = {m.id: () if para else ((m.abbr,) if level == "distributed" else ()) + (m.description,)
                      for m in metrics}
    base = study.measurement(study.condition("baseline").id, q.id, main)
    rag = study.measurement(study.condition("rag").id, q.id, main)
    fmts = ["pct", "frac", "count"]
    rng.shuffle(fmts)
    values: dict[str, Seg] = {}
    for i, m in enumerate(ms):
        unit = next(k for k in metrics if k.id == m.metric).unit
        if level == "explicit":
            fmt = "pct"
        elif para:
            fmt = fmts[i % len(fmts)]
        elif level == "complex" and m.id == rag.id:
            fmt = "relative"
        else:
            fmt = "cell_raw" if unit == "seconds" else "cell_pct"
        values[m.id] = Seg(m.id, "value", write_value(m.value, fmt, base.value), fmt)
    claim = study.false_claim if level == "contradictory" else study.claim
    decoy = None
    if level == "contradictory" and study.decoy is not None:
        decoy = Decoy(rag.id, study.decoy, write_value(study.decoy, "pct"))
    return Plan(study, level, study.conditions, metrics, datasets, ms, cond_name, cond_aliases, metric_name,
                metric_aliases, values, claim, vocab.CLAIMS[(claim, q.canonical)], decoy)


def plan_rng(seed: int, study_id: str, level: str) -> random.Random:
    """One generator per (seed, study, level): a paper's text does not depend on which other papers or
    levels are built, so the mixed corpus reuses the level corpora's papers byte for byte."""
    return random.Random(f"synth:{seed}:{study_id}:{level}")
