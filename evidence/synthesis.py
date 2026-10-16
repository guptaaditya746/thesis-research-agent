"""Deterministic synthesis: from the evidence of each document to answer.json (docs/evidence-system.md A4,
protocol v2 in Part C). Every parameter comes from the protocol's `synthesis` block; the machinery is
`evidence/rules.py`.

Per document: the question metrics are tried in the protocol's order, and within a metric the metric
items in document order; the first metric item with a usable treatment/control pair (the condition roles
`synthesis.compare` names) gives the study's effect with `rules.effect` (higher-is-better from the
protocol's metric list, not the extracted field).

Pairing rule (`synthesis.pairing`, rule `same_dataset`):
1. A measurement's place in the document is the start of its first `value` span (where the number is),
   not of its label or alias spans.
2. treatment and control are paired on the SAME dataset: the datasets are tried in the order they first
   appear (by value position), and the first one with both a treatment and a control measurement is
   used. Only when no dataset has both, a measurement without a dataset is paired with one that has one
   (or none).
3. Among several measurements of one condition on one metric and dataset, the `prefer` list decides:
   `table_cell` (a value in a Markdown table cell beats one in prose; abstracts and discussions may
   restate or misstate results) and `document_order` (the earlier one wins), applied in the order given.

The author claim is the document's first author_claim item; it agrees with the data per
`rules.claim_agrees` through `synthesis.claim_map`. A document without a usable pair is `undetermined`
with a reason code and text and does not count; the label is `rules.label` of the counts by the
protocol's decision table.
"""
from __future__ import annotations

import re
from typing import Any

from . import rules
from .contract import Item
from .protocol import Protocol, Synthesis

SYSTEM = "evidence-engine"
CELL_BEFORE = re.compile(r"\|[\s*_]*$")
CELL_AFTER = re.compile(r"^[^\n|]*\|")
# Why a document is undetermined: the code names the evidence type the funnel escalates (Part D).
REASONS = {"screened_out": "screened out",
           "no_treatment_condition": "no {treatment} condition found",
           "no_control_condition": "no {control} condition found",
           "no_question_metric": "no metric of the question found",
           "no_pair": "no {treatment} and {control} measurement on a question metric"}
GAP_TYPES = {"no_treatment_condition": ("condition",), "no_control_condition": ("condition",),
             "no_question_metric": ("metric",), "no_pair": ("measurement",), "screened_out": ()}


def reason(code: str, spec: Synthesis) -> dict[str, str]:
    return {"code": code, "text": REASONS[code].format(treatment=spec.compare.treatment, control=spec.compare.control)}


def value_start(m: Item) -> int:
    starts = [s.selector["start"] for s in m.spans if s.role == "value"]
    return min(starts) if starts else m.first_start()


def in_table(m: Item) -> bool:
    """The measurement's first value span sits in a Markdown table cell (a pipe before and after on its line)."""
    spans = sorted((s for s in m.spans if s.role == "value"), key=lambda s: s.selector["start"])
    return any(CELL_BEFORE.search(s.selector.get("prefix", "")) and CELL_AFTER.match(s.selector.get("suffix", ""))
               for s in spans)


def _best(ms: list[Item], spec: Synthesis) -> Item:
    keys = {"table_cell": lambda m: not in_table(m), "document_order": value_start}
    return min(ms, key=lambda m: (*(keys[p](m) for p in spec.pairing.prefer), m.item_id))


def _pair(treatment: list[Item], control: list[Item], spec: Synthesis) -> tuple[Item, Item] | None:
    order: list[Any] = []
    for m in sorted(treatment + control, key=lambda m: (value_start(m), m.item_id)):
        if m.fields.get("dataset") not in order:
            order.append(m.fields.get("dataset"))
    for dataset in order:  # the same dataset on both sides, first dataset in document order
        t = [m for m in treatment if m.fields.get("dataset") == dataset]
        c = [m for m in control if m.fields.get("dataset") == dataset]
        if t and c:
            return _best(t, spec), _best(c, spec)
    for dataset in order:  # fallback: one side names no dataset
        t = [m for m in treatment if m.fields.get("dataset") in (dataset, None)]
        c = [m for m in control if m.fields.get("dataset") in (dataset, None)]
        if t and c and (dataset is None or any(m.fields.get("dataset") is None for m in t + c)):
            return _best(t, spec), _best(c, spec)
    return None


def study(protocol: Protocol, document: str, items: list[Item]) -> tuple[dict[str, Any], list[str]]:
    """One document's entry and the item ids it rests on."""
    spec = protocol.synthesis
    by_id = {i.item_id: i for i in items}
    of = {t: [i for i in items if i.evidence_type == t] for t in ("condition", "metric", "measurement", "author_claim")}
    claim = of["author_claim"][0] if of["author_claim"] else None
    entry: dict[str, Any] = {"document": document, "direction": "undetermined", "delta": None, "metric": None,
                             "treatment": None, "control": None, "author_claim": None, "reason": None}
    used: list[str] = []
    roles = {c.fields.get("role") for c in of["condition"]}
    question = [m for name in spec.metric_names for m in of["metric"] if m.fields.get("canonical") == name]
    pair = None
    for metric in question:
        on = [m for m in of["measurement"] if m.links.get("metric") == metric.item_id]

        def role(m: Item) -> Any:
            cond = by_id.get(m.links.get("condition", ""))
            return cond.fields.get("role") if cond else None

        pair = _pair([m for m in on if role(m) == spec.compare.treatment],
                     [m for m in on if role(m) == spec.compare.control], spec)
        if pair:
            break
    if pair is None:
        if spec.compare.treatment not in roles:
            entry["reason"] = reason("no_treatment_condition", spec)
        elif spec.compare.control not in roles:
            entry["reason"] = reason("no_control_condition", spec)
        elif not question:
            entry["reason"] = reason("no_question_metric", spec)
        else:
            entry["reason"] = reason("no_pair", spec)
    else:
        t, c = pair
        canonical = by_id[t.links["metric"]].fields["canonical"]
        direction, delta = rules.effect(float(t.fields["value"]), float(c.fields["value"]),
                                        spec.higher_is_better(canonical), spec.min_effect)
        entry.update(direction=direction, delta=delta, metric=canonical,
                     treatment={"condition": t.links["condition"], "measurement": t.item_id, "value": t.fields["value"]},
                     control={"condition": c.links["condition"], "measurement": c.item_id, "value": c.fields["value"]})
        used += [t.item_id, c.item_id, t.links["condition"], c.links["condition"], t.links["metric"]]
    if claim is not None:
        determined = entry["direction"] != "undetermined"
        entry["author_claim"] = {"item": claim.item_id, "direction": claim.fields["direction"],
                                 "agrees_with_data": rules.claim_agrees(claim.fields["direction"], entry["direction"],
                                                                        spec.claim_map) if determined else None}
        used.append(claim.item_id)
    return entry, used


def answer(protocol: Protocol, documents: list[str], items: dict[str, list[Item]]) -> tuple[dict[str, Any], list[str]]:
    """answer.json and the ids of every item it counted."""
    studies, used = [], []
    for doc in documents:
        entry, ids = study(protocol, doc, items.get(doc, []))
        studies.append(entry)
        used += ids
    groups = {k: [s["document"] for s in studies if s["direction"] == d]
              for k, d in (("supporting", "supports"), ("contradicting", "contradicts"), ("neutral", "neutral"),
                           ("undetermined", "undetermined"))}
    counts = {k: len(v) for k, v in groups.items()}
    label = rules.label(counts, protocol.synthesis.table)
    out = {"system": SYSTEM, "question": protocol.question, "label": label, "counts": counts, "studies": studies,
           **groups}
    return out, used
