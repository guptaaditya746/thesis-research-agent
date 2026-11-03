"""Deterministic Markdown renderer: a plan becomes a paper with exact placements.

Title (and the byline, a study's author-year label), abstract, introduction, method (with the dependency sentences of
the builds_on preset), results (sentences or tables, by level), discussion (with the planted limitations), conclusion.
Filler comes from the recipe's text (`Plan.recipe`) in random order; facts are written only through `Doc.fill`,
so each one's offsets are recorded as it is written. Same plan and generator state, same bytes.
"""
from __future__ import annotations

import random
from collections.abc import Sequence

from synth.corpus import Rendered
from synth.fidelity import PaperFidelity, check_paper
from synth.levels import FOOTNOTES, LIMITATION_SECTION, MISSING_CELL, PARAPHRASE_LEVELS, Plan, make_plan, plan_rng
from synth.text import Decoy, Doc, Placement, Seg
from synth.truth import Experiment, Study

EXPLICIT = (
    "On {dataset}, the {cond} has {value} {metric}.",
    "The {cond} shows {value} {metric} on {dataset}.",
    "We measure {value} {metric} for the {cond} on {dataset}.",
)
PARAPHRASED = (
    "With the {cond}, the {metric} on {dataset} came to {value}.",
    "For the {cond}, we observe {value} as the {metric} on {dataset}.",
    "On {dataset}, the {metric} of the {cond} was {value}.",
)
CELL = {"fraction": "%", "seconds": "s"}


def claim_seg(plan: Plan, which: int) -> Seg:
    return Seg(f"{plan.paper}.a1", "claim", plan.claim_sentences[which])


def sentences(doc: Doc, rng: random.Random, pool: Sequence[str], k: int) -> None:
    doc.add(" ".join(rng.sample(pool, k)))


def templates(plan: Plan, key: str) -> list[str]:
    """The recipe's sentence templates `key` (`text.templates`); a recipe without them cannot be rendered."""
    found = (plan.recipe.text.templates or {}).get(key)
    if not found:
        raise ValueError(f"the recipe of {plan.recipe.domain} has no text.templates.{key} for the template renderer")
    return found


def dataset_size(plan: Plan, template: str) -> str:
    """The recipe's `reporting.dataset_size`, for a template that states it ({size}); "" for one that does not."""
    size = plan.recipe.reporting.dataset_size
    if size is None and "{size}" in template:
        raise ValueError(f"the recipe of {plan.recipe.domain} has no reporting.dataset_size for the template renderer")
    return size or ""


def abstract(doc: Doc, plan: Plan, rng: random.Random) -> None:
    doc.heading("Abstract")
    doc.add(rng.choice(plan.recipe.text.intro[:3]) + " ")
    control, treatment = plan.study.conditions[0].id, plan.study.conditions[1].id
    main = plan.datasets[0]
    if plan.level == "distributed":
        doc.add(templates(plan, "abstract_without_names")[0].format(dataset=main) + " ")
    else:
        doc.fill("We compare the {b} with the {r} on {d}. ", b=plan.first(control), r=plan.first(treatment), d=main)
    doc.seg(claim_seg(plan, 0))
    if plan.decoy is not None:
        doc.fill(" On {d}, the {r} reaches {v} {k}.", d=main, r=plan.first(treatment),
                 k=plan.metric(plan.metrics[0].id), v=plan.decoy)
    doc.add("\n")


def method(doc: Doc, plan: Plan, rng: random.Random) -> None:
    doc.heading("Method")
    if len(plan.datasets) > 1:
        template = templates(plan, "method_two_contexts")[0]
        doc.add(template.format(main=plan.datasets[0], other=plan.datasets[1], size=dataset_size(plan, template)))
    else:
        template = templates(plan, "method_one_context")[0]
        doc.add(template.format(main=plan.datasets[0], size=dataset_size(plan, template)))
    if len(plan.experiments) > 1:          # --hard
        others = " and ".join(f"the {e.name} experiment" for e in plan.experiments[1:])
        doc.add(" " + templates(plan, "hard_more_experiments")[0].format(main=plan.experiments[0].name, others=others,
                                                                         dataset=plan.datasets[0]))
    for c in plan.conditions:
        intro, slots = plan.introduce(c.id)
        if plan.level == "distributed":
            doc.fill(intro + "; we denote it by {code}.", **slots, code=plan.code(c.id))
        else:
            doc.fill(intro + ".", **slots)
    for d in plan.dependencies:            # the builds_on preset: what the study reuses, and whose
        doc.add(" ")
        doc.placed(d.id, "dependency", d.template, label=d.label, **({"thing": plan.cond(d.thing)} if d.thing else {}),
                   **({"metric": plan.metric(d.metric)} if d.metric else {}))
    doc.add("\n\n")
    q = plan.metrics[0]
    if plan.level in PARAPHRASE_LEVELS:
        doc.fill("Our main measure is the {k}.", k=plan.metric(q.id))
    elif plan.level == "distributed":
        doc.fill("Our main measure is the {k}, the {d}; the tables abbreviate it as {a}.",
                 k=plan.metric(q.id), d=plan.metric(q.id, q.description), a=plan.metric(q.id, q.abbr))
    else:
        doc.fill("Our main measure is the {k}, the {d}.", k=plan.metric(q.id), d=plan.metric(q.id, q.description))
    for m in plan.metrics[1:]:
        doc.fill(" We also report {k}, the {d}.", k=plan.metric(m.id), d=plan.metric(m.id, m.description))
    doc.add(" ")
    sentences(doc, rng, plan.recipe.text.method, 3)
    doc.add("\n")
    if plan.level == "distributed":
        doc.heading("Implementation details", 3)
        padding = rng.sample(plan.recipe.text.padding, 7)
        doc.add(" ".join(padding[:4]) + "\n\n" + " ".join(padding[4:]))
        doc.add("\n")


def prose_results(doc: Doc, plan: Plan, rng: random.Random, measurements: Sequence | None = None) -> None:
    out = []
    for m in (plan.measurements if measurements is None else measurements):
        v = plan.values[m.id]
        pool = (templates(plan, "paraphrased_count") if v.fmt == "count" else templates(plan, "prose_k_of_n")
                if v.fmt == "k_of_n" else PARAPHRASED if plan.level in PARAPHRASE_LEVELS else EXPLICIT)
        out.append((rng.choice(pool), m, v))
    for i, (template, m, v) in enumerate(out):
        doc.fill(template, dataset=m.dataset, cond=plan.cond(m.condition), metric=plan.metric(m.metric), value=v)
        doc.add(" " if i + 1 < len(out) else "\n")


def table(doc: Doc, plan: Plan, use_codes: bool) -> None:
    """One table; with several datasets, one row per dataset and condition (a single header, so every
    cell's context is unique); with --hard experiments, an Experiment column and one row per experiment,
    dataset and condition."""
    several = len(plan.datasets) > 1
    doc.add("| System |" + (" Experiment |" if plan.experiments else "") + (" Dataset |" if several else ""))
    for k in plan.metrics:
        doc.fill(" {k} ({u}) |", k=plan.metric(k.id, k.abbr if use_codes else None), u=CELL[k.unit])
    doc.add("\n|---|" + ("---|" if plan.experiments else "") + ("---|" if several else "")
            + "---:|" * len(plan.metrics) + "\n")
    if not plan.experiments:
        for dataset in plan.datasets:
            for c in plan.conditions:
                row(doc, plan, use_codes, c.id, dataset, several)
        return
    for e in plan.experiments:
        for dataset in e.datasets:
            for cid in e.conditions:
                row(doc, plan, use_codes, cid, dataset, several, e)


def row(doc: Doc, plan: Plan, use_codes: bool, cid: str, dataset: str, several: bool,
        experiment: Experiment | None = None) -> None:
    doc.fill("| {c} |", c=plan.code(cid) if use_codes else plan.cond(cid))
    doc.add((f" {experiment.name} |" if experiment else "") + (f" {dataset} |" if several else ""))
    for k in plan.metrics:
        m = plan.study.find(cid, k.id, dataset, experiment.id if experiment else None)
        if m is None:                   # a --missing measurement: the paper never states it
            doc.add(f" {MISSING_CELL} |")
            continue
        v = plan.values[m.id]
        doc.fill(" {v} |", v="see text" if v.fmt == "relative" else v)
    doc.add("\n")


def multi_experiment_results(doc: Doc, plan: Plan, rng: random.Random) -> None:
    """One subsection per experiment (per dataset when the study has one experiment): prose with the question
    metric of every condition, then a table of the other metrics (none when the study has no other metric)."""
    q, study = plan.metrics[0], plan.study
    groups = ([(f"{e.name} experiment", e.id, e.datasets, e.conditions) for e in plan.experiments] if plan.experiments
              else [(d, None, (d,), tuple(c.id for c in plan.conditions)) for d in plan.datasets])
    others = plan.metrics[1:]
    for heading, exp_id, datasets, conditions in groups:
        doc.heading(heading, 3)
        found = [m for d in datasets for cid in conditions if (m := study.find(cid, q.id, d, exp_id)) is not None]
        prose_results(doc, plan, rng, found)
        if not others:
            continue
        doc.add("\n| System |" + (" Dataset |" if len(datasets) > 1 else ""))
        for k in others:
            doc.fill(" {k} ({u}) |", k=plan.metric(k.id), u=CELL[k.unit])
        doc.add("\n|---|" + ("---|" if len(datasets) > 1 else "") + "---:|" * len(others) + "\n")
        for d in datasets:
            for cid in conditions:
                doc.fill("| {c} |", c=plan.cond(cid))
                doc.add(f" {d} |" if len(datasets) > 1 else "")
                for k in others:
                    m = study.find(cid, k.id, d, exp_id)
                    if m is None:
                        doc.add(f" {MISSING_CELL} |")
                    else:
                        doc.fill(" {v} |", v=plan.values[m.id])
                doc.add("\n")
        doc.add("\n")


def messy_table_results(doc: Doc, plan: Plan) -> None:
    """One table of the main experiment: a group header over the metric columns (the merged cell, the cells it
    covers empty), the metric names with their units as the next row, values with footnote marks, the marks explained
    under the table."""
    doc.add(f"The table below lists the results of all systems on {plan.datasets[0]}.\n\n")
    doc.add("| |" + f" {plan.datasets[0]} |" + " |" * (len(plan.metrics) - 1) + "\n")
    doc.add("|---|" + "---|" * len(plan.metrics) + "\n| System |")
    for k in plan.metrics:
        doc.fill(" {k} ({u}) |", k=plan.metric(k.id), u=CELL[k.unit])
    doc.add("\n")
    used: list[str] = []
    for c in plan.conditions:
        doc.fill("| {c} |", c=plan.cond(c.id))
        for k in plan.metrics:
            m = plan.study.find(c.id, k.id, plan.datasets[0], None)
            if m is None:
                doc.add(f" {MISSING_CELL} |")
                continue
            v = plan.values[m.id]
            used += [x for x in FOOTNOTES if x in v.text and x not in used]
            doc.fill(" {v} |", v=v)
        doc.add("\n")
    doc.add("\n" + "\n".join(f"{x} {FOOTNOTES[x]}" for x in used) + ("\n" if used else ""))


def results(doc: Doc, plan: Plan, rng: random.Random) -> None:
    doc.heading("Results")
    if plan.level == "multi_experiment":
        multi_experiment_results(doc, plan, rng)
        return
    if plan.level == "messy_tables":
        messy_table_results(doc, plan)
        return
    if plan.level in ("explicit", "paraphrased"):
        prose_results(doc, plan, rng)
        return
    if plan.level == "complex":
        where = " and on ".join(plan.datasets)   # two datasets, or a network study's one population
        if plan.experiments:                    # --hard
            doc.add("The table below reports the results of every experiment, the "
                    f"{plan.experiments[0].name} on {where}.\n\n")
        else:
            doc.add(f"The table below reports the results on {where}.\n\n")
        table(doc, plan, use_codes=False)
        doc.add("\n")
        control, treatment = plan.study.conditions[0].id, plan.study.conditions[1].id
        rel = next((v for v in plan.values.values() if v.fmt == "relative"), None)
        if rel is not None:                     # absent when the control or the treatment value is missing
            where = f"In the {plan.experiments[0].name} on {{d}}" if plan.experiments else "On {d}"
            doc.fill(where + ", the {r} scores {v} than the {b} in {k}.\n", d=plan.datasets[0],
                     r=plan.cond(treatment), k=plan.metric(plan.metrics[0].id), v=rel, b=plan.cond(control))
        return
    doc.add(f"The table below lists the results of all systems on {plan.datasets[0]}.\n\n")
    table(doc, plan, use_codes=plan.level == "distributed")
    doc.add("\nAll systems were evaluated under the same conditions.\n")


def title(rng: random.Random, titles: Sequence[str], avoid: str | None = None) -> str:
    """The title template a paper draws from `titles` (the renderer's first draw); a duplicate paper (`avoid`:
    its original's) takes the next one, so a second report never carries the same title."""
    pick = rng.choice(titles)
    if pick == avoid:
        pick = titles[(titles.index(pick) + 1) % len(titles)]
    return pick


def render_irrelevant(plan: Plan, rng: random.Random) -> str:
    """A paper with no experiment (--irrelevant): title, abstract, introduction, two topic sections,
    discussion and conclusion from the recipe's text.irrelevant[topic]; nothing is placed."""
    words = plan.recipe.text.irrelevant[plan.study.topic]
    doc = Doc(plan.paper)
    doc.add("# " + rng.choice(words.titles) + "\n")
    doc.heading("Abstract")
    doc.add(" ".join(words.abstract) + "\n")
    body = rng.sample(words.body, 11)
    doc.heading("Introduction")
    doc.add(" ".join(body[:3]) + "\n")
    for i, section in enumerate(rng.sample(words.sections, 2)):
        doc.heading(section)
        doc.add(" ".join(body[3 + 3 * i:6 + 3 * i]) + "\n")
    doc.heading("Discussion")
    doc.add(" ".join(body[9:11]) + "\n")
    doc.heading("Conclusion")
    doc.add(" ".join(words.conclusion) + "\n")
    return doc.text


def render(plan: Plan, rng: random.Random, avoid_title: str | None = None) -> tuple[str, list[Placement], list[Decoy]]:
    """The paper's text, its placements and decoys (offsets into the text)."""
    if not plan.study.relevant:
        return render_irrelevant(plan, rng), [], []
    text = plan.recipe.text
    doc = Doc(plan.paper)
    doc.add("# " + title(rng, text.titles, avoid_title).format(dataset=plan.datasets[0]) + "\n")
    if plan.byline is not None:            # the author-year label the paper is cited by, under the title
        doc.line("\n", plan.byline)
    abstract(doc, plan, rng)
    doc.heading("Introduction")
    sentences(doc, rng, text.intro, 5)
    doc.add("\n")
    method(doc, plan, rng)
    results(doc, plan, rng)
    doc.heading(LIMITATION_SECTION)
    sentences(doc, rng, text.discussion, 3)
    for x in plan.limitations:             # the limitations the authors state
        doc.add(" ")
        doc.placed(x.id, "limitation", x.template, thing=plan.cond(x.thing))
    doc.add("\n")
    doc.heading("Conclusion")
    doc.seg(claim_seg(plan, 1))
    doc.add(" ")
    sentences(doc, rng, text.conclusion, 2)
    doc.add("\n")
    return doc.text, doc.placements, doc.decoys


def text_rng(seed: int, study: Study, level: str) -> random.Random:
    """The generator the paper's prose is drawn from: per (seed, study, level); an irrelevant paper's text
    does not depend on the level it is filed under."""
    return plan_rng(seed, study.study_id, level + ":text" if study.relevant else "irrelevant")


def render_study(study: Study, level: str, seed: int) -> Rendered:
    plan = make_plan(study, level, plan_rng(seed, study.study_id, level))
    avoid = (title(plan_rng(seed, study.duplicate_of, level + ":text"), study.recipe.text.titles)
             if study.duplicate_of else None)
    text, placements, decoys = render(plan, text_rng(seed, study, level), avoid)
    checks = check_paper(text, plan, placements, decoys)
    return Rendered(study, plan, text, placements, decoys,
                    PaperFidelity(study.study_id, all(c.ok for c in checks), checks))


class TemplateRenderer:
    """The deterministic renderer behind `synth build --renderer template`."""
    name = "template"

    def render_all(self, jobs: Sequence[tuple[Study, str]], seed: int) -> dict[tuple[str, str], Rendered]:
        return {(s.study_id, level): render_study(s, level, seed) for s, level in jobs}

    def models(self) -> None:
        return None