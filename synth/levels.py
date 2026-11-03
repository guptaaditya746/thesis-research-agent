"""Difficulty levels and the rendering plan shared by the template and the LLM renderer.

A plan fixes, for one study at one level, which facts the paper states and the exact string each one is
written as (names, codes, name variants, value formats, claim sentences, the decoy, the byline, limitation and
dependency sentences). The template renderer lays the plan
out itself; the LLM renderer hands it to a model and then checks the strings are there. So both
renderers write the same facts the same way and differ only in the prose around them.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from synth.recipe import REUSES, Recipe
from synth.text import Decoy, Seg
from synth.truth import Condition, Dependency, Experiment, Limitation, Measurement, Metric, Study

LEVELS = ("explicit", "paraphrased", "distributed", "complex", "contradictory")
# Two harder settings, kept out of LEVELS: the corpus builder, the CLI default and the mixed corpus's round robin
# (synth/corpus.py `level_of`) read LEVELS, so growing it would change every existing corpus. `synth build --levels`
# takes them once corpus.py and cli.py accept ALL_LEVELS; until then they are made with `make_plan` and `render`.
EXTRA_LEVELS = ("multi_experiment", "messy_tables")
ALL_LEVELS = LEVELS + EXTRA_LEVELS
PARAPHRASE_LEVELS = ("paraphrased", "multi_experiment")   # named by synonyms and descriptions, never by labels
# Footnote marks of the messy_tables level, written straight after a table value ("62.4*"); `parse_value` drops them.
FOOTNOTE_MARKS = ("*", "†", "‡")
FOOTNOTES = {"*": "Result as reported by the original authors.", "†": "Result rerun by us with the released code.",
             "‡": "Result on a held-out subset."}
# What a table cell shows for a measurement the paper never states (--missing, our addition): an en dash,
# U+2013, which no number regex reads and which is not a Markdown separator.
MISSING_CELL = "–"

DEFINITIONS = {
    "explicit": "Every value is stated once, in one Results sentence that names the condition and the metric "
                "verbatim (the study's own labels) together with the dataset; values are written as percent "
                "(62.4%), or as counts of the arm (41 of 120 patients) in a recipe that reports counts. No tables. "
                "Facts: all conditions on the question metric on the main dataset.",
    "paraphrased": "Conditions and the metric are never called by their labels but by descriptive synonyms "
                   "(the recipe's `synonym` and metric description); values appear in prose in varied formats: "
                   "percent (62.4%), fraction (0.624) and count (624 out of 1,000, or 41 of 120 patients), the "
                   "ones the recipe reports, at least two formats per paper. Same facts as explicit.",
    "distributed": "Values appear only in one Markdown table whose rows are short codes (B, R, A1, A2) and whose "
                   "value column header is the metric's abbreviation with a percent unit (XY (%)); the codes "
                   "and the abbreviation are defined in the Method section, separated from the table by "
                   "several paragraphs. No sentence states a value. Same facts as explicit.",
    "complex": "Every condition (with the distractor systems), the question metric and one or two distractor "
               "metrics on every dataset of the study (two, or a network study's one population), in one table "
               "with full labels and, over two datasets, a Dataset column "
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
    "multi_experiment": "Like complex, every experiment of the study is shown, at the paraphrased wording (synonyms "
                        "for conditions, the metric's description): one Results subsection per experiment (per dataset "
                        "for a study with one experiment), each with prose that states the question metric of every "
                        "condition (paraphrased formats) and a table of the other metrics. The reader must take the "
                        "values of the main experiment only.",
    "messy_tables": "The main experiment's values are in one Markdown table with a merged group header (the "
                    "dataset's name over the metric columns, the covered cells left empty), the metric names with "
                    "their units in the column header row (Accuracy (%)), and values carrying footnote marks "
                    "(62.4*, 61.0†) explained under the table. No sentence states a value. Full labels, no codes.",
}


# The value formats prose may use, in the order a paraphrased paper draws them from (those the recipe reports).
PROSE_FORMATS = ("pct", "frac", "count", "k_of_n")
# The fixed sentence a dependency of each reuse kind is written in; {phrase} is the recipe's phrase of the kind
# (builds_on.phrases, naming the cited `{label}`), {thing} the name this paper gives the reused thing and {metric} the
# name it gives the copied value's metric.
DEPENDENCY_FRAMES = {"method": "For the {thing}, {phrase}.", "dataset": "This study uses {phrase}.",
                     "result": "For the {thing}, the {metric} is taken {phrase}."}
# The section each planted sentence goes in (fidelity `limitations_placed`, `dependencies_placed`).
LIMITATION_SECTION, DEPENDENCY_SECTION = "Discussion", "Method"


@dataclass(frozen=True)
class Written:
    """A limitation or a dependency as one paper writes it: `template` (slots {thing}, the name this paper gives the
    thing; {label}, the cited study's label; {metric}, the name of a copied value's metric) and the filled `sentence`,
    which the paper holds exactly once."""
    id: str
    thing: str | None
    template: str
    sentence: str
    category: str | None = None    # a limitation's category
    reuses: str | None = None      # a dependency's kind (method, dataset, result)
    cites: str | None = None       # a dependency's cited study id
    label: str | None = None       # a dependency's cited label
    metric: str | None = None      # a copied result's metric id


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
    # plan 2 Task 6 (empty for a recipe that plants none): limitation sentences (Discussion), dependency sentences
    # (Method), the byline under the title (the study's author-year label), and the name variant each thing is written
    # by, condition id -> (kind, form) (not at the paraphrased level, which names things by their synonyms).
    limitations: tuple[Written, ...] = ()
    dependencies: tuple[Written, ...] = ()
    label: str = ""
    variants: dict[str, tuple[str, str]] = field(default_factory=dict)

    @property
    def paper(self) -> str:
        return self.study.study_id

    @property
    def byline(self) -> Seg | None:
        return Seg(f"{self.paper}.b1", "study_label", self.label) if self.label else None

    def facts(self, key: str) -> list[str]:
        """The ids of the plan's facts listed under a study record's `key` (text.TRUTH_TYPES `list`)."""
        return {"conditions": [c.id for c in self.conditions], "metrics": [k.id for k in self.metrics],
                "measurements": [m.id for m in self.measurements],
                "author_claim": [f"{self.paper}.a1"] if self.study.relevant else [],
                "limitations": [x.id for x in self.limitations], "dependencies": [d.id for d in self.dependencies],
                "study_label": [self.byline.fact] if self.byline else []}[key]

    def truth_name(self, cid: str) -> tuple[str, tuple[str, ...]]:
        """(label, aliases) of a condition in its ground-truth record: the name the paper writes it by and its other
        renderings, except that a spelling variant ("QUIN-TAPRIDE") keeps the real label and is an alias of it, so a
        reader of the truth can link the spelling to the thing (a hereafter or code-name variant already lists the
        label among its aliases)."""
        kind, form = self.variants.get(cid, ("", ""))
        if kind == "spelling":
            return self.condition(cid).label, (*self.cond_aliases[cid], form)
        return self.cond_name[cid], self.cond_aliases[cid]

    def first(self, cid: str) -> Seg:
        """The name a condition is first mentioned by (the abstract): its label when the paper then calls it by a
        short form it defines (a hereafter or code-name variant), else its name."""
        kind = self.variants.get(cid, ("", ""))[0]
        if kind in ("hereafter", "code_name"):
            return Seg(cid, "condition_label", self.condition(cid).label)
        return self.cond(cid)

    def introduce(self, cid: str) -> tuple[str, dict[str, Seg]]:
        """How Method introduces a condition: a template (slots {c} and {label}) and its slots. A hereafter variant
        is defined at the start of its own sentence ("Zelvora (hereafter ZV) is taken ..."), the only place
        a definition's long form is read from; a code name follows the label in brackets."""
        c = self.condition(cid)
        kind, form = self.variants.get(cid, ("", ""))
        slots = {"c": self.cond(cid)}
        if kind == "hereafter":
            return " {label} (hereafter {c}) " + c.description, slots | {"label": self.first(cid)}
        if kind == "code_name":
            return " We include the {label} ({c}), which " + c.description, slots | {"label": self.first(cid)}
        return " We include the {c}, which " + c.description, slots

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
                noun: str | None = None, mark: str = "") -> str:
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
    if fmt == "cell_pct_note":      # messy_tables: a table value followed by its footnote mark
        return pct(v) + mark
    if fmt == "cell_raw_note":
        return f"{v:.2f}" + mark
    if fmt == "relative":
        tenths = thousandths(v) - thousandths(base)
        return f"{abs(tenths) // 10}.{abs(tenths) % 10} percentage points {'higher' if tenths > 0 else 'lower'}"
    raise ValueError(fmt)


def parse_value(text: str, fmt: str, base: float | None = None) -> float:
    """The normalised value a rendering states (fractions for percent and counts)."""
    if fmt == "k_of_n":
        k, _, n = text.split()[:3]
        return round(int(k.replace(",", "")) / int(n.replace(",", "")), 6)
    number = float(re.sub(r"(\^\w+|[*†‡§¹²³]+)$", "", text.split()[0]).rstrip("%")
                   .replace(",", ""))
    if fmt in ("pct", "cell_pct", "cell_pct_note"):
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
    if level not in ALL_LEVELS:
        raise ValueError(f"unknown level {level!r}")
    if study.relevant:
        raise ValueError(f"{study.study_id} is a relevant study; use make_plan")
    return Plan(study, level, (), (), (), (), {}, {}, {}, {}, {}, "", (), None)


def make_plan(study: Study, level: str, rng: random.Random) -> Plan:
    if level not in ALL_LEVELS:
        raise ValueError(f"unknown level {level!r}")
    if not study.relevant:
        return irrelevant_plan(study, level)
    q, main = study.primary, study.datasets[0]
    # A --hard study shows all its experiments (the ablation among the conditions) only at the complex
    # level, one table with an Experiment column; the other levels show its main experiment alone.
    if level in ("complex", "multi_experiment"):
        conditions, metrics, datasets, ms = study.conditions, study.metrics, study.datasets, study.measurements
        experiments = study.experiments
    elif level == "messy_tables":      # the main experiment on the main dataset, every metric (a merged header needs two)
        conditions, metrics, datasets, experiments = study.main_conditions, study.metrics, (main,), ()
        ms = tuple(m for m in study.measurements if m.dataset == main and m.experiment == study.main_experiment)
    else:
        conditions, metrics, datasets, experiments = study.main_conditions, (q,), (main,), ()
        ms = tuple(m for m in study.measurements
                   if m.metric == q.id and m.dataset == main and m.experiment == study.main_experiment)
    para = level in PARAPHRASE_LEVELS
    recipe = study.recipe
    # A name variant (truth.with_variants) is how this paper writes the thing: a spelling replaces the label; a
    # hereafter short form or a code name is the paper's name for it, the label being said once where it is defined.
    variants = {} if para else {c.id: c.variants[0] for c in conditions if c.variants}
    cond_name = {c.id: c.synonym if para else variants.get(c.id, ("", c.label))[1] for c in conditions}
    cond_aliases = {c.id: ((c.code,) if level == "distributed" else ())
                    + ((c.label,) if variants.get(c.id, ("",))[0] in ("hereafter", "code_name") else ())
                    for c in conditions}
    metric_name = {m.id: m.description if para else m.name for m in metrics}
    metric_aliases = {m.id: () if para else ((m.abbr,) if level == "distributed" else ()) + (m.description,)
                      for m in metrics}
    # A --missing study lacks its control or treatment measurement (None here): the complex level then has
    # no relative value (the treatment value, if present, is a plain cell) and the contradictory level no decoy.
    base = study.find(study.control_condition.id, q.id, main)
    treat = study.find(study.treatment_condition.id, q.id, main)
    base_value = base.value if base is not None else None

    def counted(m: Measurement) -> bool:      # a count k of its arm's n (synth/network.py), writable as "k of n"
        return "k_of_n" in recipe.reporting.formats and m.k is not None and m.condition in study.arm_sizes

    # The prose formats the recipe reports, in PROSE_FORMATS order (the rag recipe's: pct, frac, count, as before).
    prose = [m for m in ms if m.metric == q.id] if level == "multi_experiment" else list(ms)
    fmts = [f for f in PROSE_FORMATS if f in recipe.reporting.formats and (f != "k_of_n" or all(map(counted, prose)))]
    rng.shuffle(fmts)
    values: dict[str, Seg] = {}
    marks = iter(FOOTNOTE_MARKS)       # messy_tables: the first value carries the first mark, then a draw per value
    for i, m in enumerate(ms):
        unit = next(k for k in metrics if k.id == m.metric).unit
        if level == "explicit":
            fmt = "k_of_n" if counted(m) else "pct"
        elif level == "multi_experiment" and m.metric != q.id:
            fmt = "cell_raw" if unit == "seconds" else "cell_pct"
        elif para:
            fmt = fmts[i % len(fmts)] if level == "paraphrased" else fmts[prose.index(m) % len(fmts)]
        elif level == "messy_tables":
            mark = next(marks, None) or rng.choice(("",) + FOOTNOTE_MARKS)
            fmt = "cell_raw_note" if unit == "seconds" else "cell_pct_note"
            values[m.id] = Seg(m.id, "value", write_value(m.value, fmt, mark=mark), fmt)
            continue
        elif level == "complex" and treat is not None and base is not None and m.id == treat.id:
            fmt = "relative"
        else:
            fmt = "cell_raw" if unit == "seconds" else "cell_pct"
        values[m.id] = Seg(m.id, "value", written(study, m, fmt, base_value), fmt)
    claim = study.false_claim if level == "contradictory" else study.claim
    decoy = None
    if level == "contradictory" and study.decoy is not None and treat is not None and base is not None:
        decoy = Decoy(treat.id, study.decoy, write_value(study.decoy, "pct"))
    return Plan(study, level, conditions, metrics, datasets, ms, cond_name, cond_aliases, metric_name,
                metric_aliases, values, claim, recipe.text.claims[claim][q.canonical], decoy, experiments,
                limitations=tuple(_limitation(x, cond_name) for x in study.limitations),
                dependencies=tuple(_dependency(d, study, cond_name, metric_name) for d in study.dependencies),
                label=study.label, variants=variants)


def written(study: Study, m: Measurement, fmt: str, base: float | None) -> str:
    """The string measurement `m` of `study` is written as in format `fmt` (`write_value`, with the count k, its arm's
    size n and the recipe's unit noun for k_of_n)."""
    if fmt == "k_of_n":
        return write_value(m.value, fmt, k=m.k, n=study.arm_sizes[m.condition], noun=study.recipe.text.unit_noun)
    return write_value(m.value, fmt, base)


def _filled(template: str, **slots: str) -> str:
    for name, value in slots.items():
        template = template.replace("{" + name + "}", value)
    return template


def _limitation(x: Limitation, cond_name: dict[str, str]) -> Written:
    """A planted limitation as this paper writes it: its category's template with the paper's name for the thing."""
    return Written(x.id, x.thing, x.template, _filled(x.template, thing=cond_name[x.thing]), category=x.category)


def _dependency(d: Dependency, study: Study, cond_name: dict[str, str], metric_name: dict[str, str]) -> Written:
    """A dependency as this paper writes it: the frame of its kind around the recipe's phrase of the kind."""
    phrases = study.recipe.builds_on.phrases
    template = DEPENDENCY_FRAMES[d.reuses].replace("{phrase}", phrases[REUSES.index(d.reuses)])
    metric = next(m.metric for m in study.measurements if m.id == d.measurement) if d.measurement else None
    names = {"thing": cond_name[d.thing]} if d.thing else {}
    sentence = _filled(template, label=d.label, **names, **({"metric": metric_name[metric]} if metric else {}))
    return Written(d.id, d.thing, template, sentence, reuses=d.reuses, cites=d.cites, label=d.label, metric=metric)


def plan_rng(seed: int, study_id: str, level: str) -> random.Random:
    """One generator per (seed, study, level): a paper's text does not depend on which other papers or
    levels are built, so the mixed corpus reuses the level corpora's papers byte for byte."""
    return random.Random(f"synth:{seed}:{study_id}:{level}")
