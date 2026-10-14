"""Deterministic Markdown renderer: a plan becomes a paper with exact placements.

Title, abstract, introduction, method, results (sentences or tables, by level), discussion, conclusion.
Filler comes from the fixed vocabularies in random order; facts are written only through `Doc.fill`, so
each one's offsets are recorded as it is written. Same plan and generator state, same bytes.
"""
from __future__ import annotations

import random

from synth import vocab
from synth.levels import Plan
from synth.text import Decoy, Doc, Placement, Seg

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
PARAPHRASED_COUNT = (
    "In terms of the {metric}, the {cond} corresponds to {value} {dataset} questions.",
    "On {dataset}, the {cond} reaches {value} questions in terms of the {metric}.",
)
CELL = {"fraction": "%", "seconds": "s"}


def claim_seg(plan: Plan, which: int) -> Seg:
    return Seg(f"{plan.paper}.a1", "claim", plan.claim_sentences[which])


def sentences(doc: Doc, rng: random.Random, pool: tuple[str, ...], k: int) -> None:
    doc.add(" ".join(rng.sample(pool, k)))


def abstract(doc: Doc, plan: Plan, rng: random.Random) -> None:
    doc.heading("Abstract")
    doc.add(rng.choice(vocab.INTRO[:3]) + " ")
    base, rag = plan.study.condition("baseline").id, plan.study.condition("rag").id
    main = plan.datasets[0]
    if plan.level == "distributed":
        doc.add(f"We study whether access to retrieved documents changes the correctness of generated answers "
                f"on {main}. ")
    else:
        doc.fill("We compare the {b} with the {r} on {d}. ", b=plan.cond(base), r=plan.cond(rag), d=main)
    doc.seg(claim_seg(plan, 0))
    if plan.decoy is not None:
        doc.fill(" On {d}, the {r} reaches {v} {k}.", d=main, r=plan.cond(rag),
                 k=plan.metric(plan.metrics[0].id), v=plan.decoy)
    doc.add("\n")


def method(doc: Doc, plan: Plan, rng: random.Random) -> None:
    doc.heading("Method")
    if len(plan.datasets) > 1:
        doc.add(f"We evaluate on two benchmarks: {plan.datasets[0]}, our main benchmark, and "
                f"{plan.datasets[1]}; each has 1,000 questions with reference answers.")
    else:
        doc.add(f"We evaluate on {plan.datasets[0]}, a benchmark of 1,000 questions with reference answers.")
    for c in plan.conditions:
        if plan.level == "distributed":
            doc.fill(" We include the {c}, which {d}; we denote it by {code}.", c=plan.cond(c.id),
                     d=c.description, code=plan.code(c.id))
        else:
            doc.fill(" We include the {c}, which {d}.", c=plan.cond(c.id), d=c.description)
    doc.add("\n\n")
    q = plan.metrics[0]
    if plan.level == "paraphrased":
        doc.fill("Our main measure is the {k}.", k=plan.metric(q.id))
    elif plan.level == "distributed":
        doc.fill("Our main measure is the {k}, the {d}; the tables abbreviate it as {a}.",
                 k=plan.metric(q.id), d=plan.metric(q.id, q.description), a=plan.metric(q.id, q.abbr))
    else:
        doc.fill("Our main measure is the {k}, the {d}.", k=plan.metric(q.id), d=plan.metric(q.id, q.description))
    for m in plan.metrics[1:]:
        doc.fill(" We also report {k}, the {d}.", k=plan.metric(m.id), d=plan.metric(m.id, m.description))
    doc.add(" ")
    sentences(doc, rng, vocab.METHOD, 3)
    doc.add("\n")
    if plan.level == "distributed":
        doc.heading("Implementation details", 3)
        padding = rng.sample(vocab.PADDING, 7)
        doc.add(" ".join(padding[:4]) + "\n\n" + " ".join(padding[4:]))
        doc.add("\n")


def prose_results(doc: Doc, plan: Plan, rng: random.Random) -> None:
    out = []
    for m in plan.measurements:
        v = plan.values[m.id]
        pool = PARAPHRASED_COUNT if v.fmt == "count" else PARAPHRASED if plan.level == "paraphrased" else EXPLICIT
        out.append((rng.choice(pool), m, v))
    for i, (template, m, v) in enumerate(out):
        doc.fill(template, dataset=m.dataset, cond=plan.cond(m.condition), metric=plan.metric(m.metric), value=v)
        doc.add(" " if i + 1 < len(out) else "\n")


def table(doc: Doc, plan: Plan, dataset: str, use_codes: bool) -> None:
    doc.add("| System |")
    for k in plan.metrics:
        doc.fill(" {k} ({u}) |", k=plan.metric(k.id, k.abbr if use_codes else None), u=CELL[k.unit])
    doc.add("\n|---|" + "---:|" * len(plan.metrics) + "\n")
    for c in plan.conditions:
        doc.fill("| {c} |", c=plan.code(c.id) if use_codes else plan.cond(c.id))
        for k in plan.metrics:
            m = plan.study.measurement(c.id, k.id, dataset)
            v = plan.values[m.id]
            doc.fill(" {v} |", v="see text" if v.fmt == "relative" else v)
        doc.add("\n")


def results(doc: Doc, plan: Plan, rng: random.Random) -> None:
    doc.heading("Results")
    if plan.level in ("explicit", "paraphrased"):
        prose_results(doc, plan, rng)
        return
    if plan.level == "complex":
        doc.add(f"The first table reports the results on {plan.datasets[0]}, the second those on "
                f"{plan.datasets[1]}.\n\n")
        for dataset in plan.datasets:
            table(doc, plan, dataset, use_codes=False)
            doc.add("\n")
        base, rag = plan.study.condition("baseline").id, plan.study.condition("rag").id
        rel = plan.values[plan.study.effect.rag]
        doc.fill("On {d}, the {r} scores {v} than the {b} in {k}.\n", d=plan.datasets[0], r=plan.cond(rag),
                 k=plan.metric(plan.metrics[0].id), v=rel, b=plan.cond(base))
        return
    doc.add(f"The table below lists the results of all systems on {plan.datasets[0]}.\n\n")
    table(doc, plan, plan.datasets[0], use_codes=plan.level == "distributed")
    doc.add("\nAll systems were evaluated under the same conditions.\n")


def render(plan: Plan, rng: random.Random) -> tuple[str, list[Placement], list[Decoy]]:
    """The paper's text, its placements and decoys (offsets into the text)."""
    doc = Doc(plan.paper)
    doc.add("# " + rng.choice(vocab.TITLES).format(dataset=plan.datasets[0]) + "\n")
    abstract(doc, plan, rng)
    doc.heading("Introduction")
    sentences(doc, rng, vocab.INTRO, 5)
    doc.add("\n")
    method(doc, plan, rng)
    results(doc, plan, rng)
    doc.heading("Discussion")
    sentences(doc, rng, vocab.DISCUSSION, 3)
    doc.add("\n")
    doc.heading("Conclusion")
    doc.seg(claim_seg(plan, 1))
    doc.add(" ")
    sentences(doc, rng, vocab.CONCLUSION, 2)
    doc.add("\n")
    return doc.text, doc.placements, doc.decoys
