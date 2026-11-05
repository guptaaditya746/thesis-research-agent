"""The experiment map of a paper: which experiments the paper reports, each anchored to a quote.

    map_experiments(doc_text, document) -> list[Experiment]   one DSPy step, `MapExperiments`
    attach(value_item, experiments, items=None) -> exp_id | None
    install()                                                 registers the stages (before_extract, after_document)

A paper often reports one result on several datasets, models or populations. Two values that look the same in
two experiments are two findings, so `rules.duplicates` keys on the experiment id (see evidence/rules.py).
The model proposes each experiment as a label, a short verbatim quote that shows where the paper describes it,
and its setting (field names such as dataset, model, population). Code anchors the quote in the text; an
experiment whose quote is not found is rejected, and so is a second experiment on the same quote. The experiment
id is a hash of the document, the label and the quote's position, so the same map gives the same ids on a rerun.
"""
from __future__ import annotations

import dspy
from pydantic import BaseModel

from agent.anchor import Index, normalize, selector_at
from evidence import stages, steps
from evidence.contract import Item, Span, digest
from evidence.records import EXPERIMENT, Experiment, item

NAME = "experiments"
NAME_STEP = "map_experiments"   # the DSPy step name


class Mapped(BaseModel):
    label: str
    quote: str
    setting: dict[str, str]


class MapExperiments(dspy.Signature):
    """List the separate experiments this paper reports.

    An experiment is one evaluation run under its own setting: a dataset, a model, a population or a configuration.
    Results of the same experiment reported in the abstract, a table and the text are ONE experiment.
    For each experiment return `label` (a short name such as "dataset A"), `quote` (a short passage copied
    word for word from the paper where the experiment is described; no more than 25 words) and `setting` (field
    names such as dataset, model, population mapped to the paper's own words).
    Return an empty list when the paper reports no experiment. Do not invent experiments the text does not describe.

    Example: a paper that tests a method on dataset A and on dataset B returns two experiments:
    {"label": "dataset A", "quote": "On dataset A we compare", "setting": {"dataset": "A"}}
    {"label": "dataset B", "quote": "On dataset B the same comparison", "setting": {"dataset": "B"}}
    """
    paper: str = dspy.InputField(desc="the full text of one paper")
    experiments: list[Mapped] = dspy.OutputField(desc="the experiments, each with label, a verbatim quote and setting")


def _step() -> steps.Step:
    return steps.Step(MapExperiments, NAME_STEP)


def map_experiments(doc_text: str, document: str, file: str | None = None, *, lm=None) -> list[Experiment]:
    """The experiments of one paper, each anchored. `document` is the paper id; `file` (default `document`) names
    the file in the spans. Unanchored experiments (the quote is not in the text) and repeats of one quote are
    dropped. `lm`: the model (default: the thread's, `evidence.steps.using`)."""
    proposed = _step()(lm=lm, paper=doc_text).experiments
    index = Index(doc_text)
    out: list[Experiment] = []
    seen: set[tuple[int, int]] = set()
    for p in proposed:
        found = _anchor(index, p.quote)
        if found is None or found in seen or not p.label.strip():
            continue
        seen.add(found)
        selector = selector_at(doc_text, found[0], found[1], file=file or document, sha256=index.sha256)
        exp_id = "ex-" + digest([document, p.label.strip(), found[0], found[1]])[:12]
        out.append(Experiment(exp_id=exp_id, document=document, label=p.label.strip(),
                              setting={k: v for k, v in p.setting.items() if k.strip() and v.strip()},
                              span=Span.of("experiment", selector)))
    return sorted(out, key=lambda e: e.span.selector["start"])


def _anchor(index: Index, quote: str) -> tuple[int, int] | None:
    """The first place `quote` occurs (normalised like every anchor), None when it does not occur."""
    folded = normalize(quote)
    if not folded:
        return None
    spans = index.spans(folded)
    return min(spans) if spans else None


def _matches(setting: dict[str, str], linked: list[Item]) -> int:
    """How many setting values equal a field value of a linked item (case and spaces ignored)."""
    have = {" ".join(str(v).split()).casefold() for it in linked for v in it.fields.values() if isinstance(v, str)}
    return sum(" ".join(v.split()).casefold() in have for v in setting.values())


def attach(value_item: Item, experiments: list[Experiment], items: dict[str, Item] | None = None) -> str | None:
    """The id of the experiment a value belongs to: the one whose setting matches the items the value links to
    (`items` maps item ids to items; most matches wins, the nearest preceding one breaks ties), else the nearest
    experiment that starts before the value, else None when the value comes before every experiment."""
    if not experiments:
        return None
    start = value_item.first_start()
    before = [e for e in experiments if e.span.selector["start"] <= start]
    nearest = max(before, key=lambda e: e.span.selector["start"], default=None)
    linked = [items[i] for i in value_item.links.values() if items and i in items]
    scored = [(_matches(e.setting, linked), e) for e in experiments if e.setting] if linked else []
    best = max((s for s, _ in scored), default=0)
    if best > 0:
        tied = [e for s, e in scored if s == best]
        near = [e for e in tied if e in before]
        return (max(near, key=lambda e: e.span.selector["start"]) if near else tied[0]).exp_id
    return nearest.exp_id if nearest else None


def _map(doc: object, ctx: stages.StageContext) -> list[Experiment]:
    """The document's map, one recorded call per run (a repeat is answered by the run's call cache). Nothing is kept
    between calls: a second run, or a replay, makes and records its own `map_experiments` call."""
    return map_experiments(doc.text, doc.doc.id, doc.doc.file, lm=ctx.dspy_lm("map_experiments"))   # type: ignore[attr-defined]


def _safe_map(doc: object, ctx: stages.StageContext) -> tuple[list[Experiment], list[str]]:
    """(the map, the notes): a failed map call (evidence.unchecked ITEM_ERRORS) gives no experiments and the note
    "unchecked: experiment map: <reason>"; the paper's other evidence is kept."""
    from evidence.unchecked import ITEM_ERRORS, reason
    try:
        return _map(doc, ctx), []
    except ITEM_ERRORS as exc:
        return [], [f"unchecked: experiment map: {reason(exc)}"]


def before_extract(doc: object, ctx: stages.StageContext) -> None:
    _safe_map(doc, ctx)


def after_document(doc: object, ctx: stages.StageContext) -> list[Item]:
    """The experiments as Items of type `experiment` (the same ones however often it runs); a failed map is noted in
    stage_report.json (evidence.unchecked) and gives none."""
    from evidence.unchecked import note
    found, notes = _safe_map(doc, ctx)
    note(ctx, "experiments", doc.doc.id, notes)   # type: ignore[attr-defined]
    return [item(e) for e in found]


def after_document_kept(doc: object, ctx: stages.StageContext) -> list[Item]:
    """`after_document` for a paper the screen kept; none (and no map call) for one it left out (`doc.skipped`)."""
    return [] if getattr(doc, "skipped", False) else after_document(doc, ctx)


def install() -> None:
    """Register the two stages (a run that registers them records them in run.json `stages`)."""
    stages.register("map-experiments", "before_extract", before_extract)
    stages.register("experiment-items", "after_document", after_document)


__all__ = ["EXPERIMENT", "MapExperiments", "attach", "install", "map_experiments"]
