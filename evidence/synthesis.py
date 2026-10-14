"""Deterministic synthesis: from the evidence of each document to answer.json (docs/evidence-interfaces.md §4).

Per document: the question metrics are tried in the protocol's order, and within a metric the metric
items in document order; the first metric item with a usable rag/baseline pair gives the study's effect
with `rules.effect` (higher-is-better from `rules.METRICS`, the shared definition, not the extracted field).

Pairing rule (protocol `synthesis.pairing: same_dataset_table_first`):
1. A measurement's place in the document is the start of its first `value` span (where the number is),
   not of its label or alias spans.
2. rag and baseline are paired on the SAME dataset: the datasets are tried in the order they first appear
   (by value position), and the first one with both a rag and a baseline measurement is used. Only when no
   dataset has both, a measurement without a dataset is paired with one that has one (or none).
3. Among several measurements of one condition on one metric and dataset, a value in a Markdown table cell
   beats one in prose (abstracts and discussions may restate or misstate results; the table is the
   result), then the earlier one wins.

The author claim is the document's first author_claim item; it agrees with the data per
`rules.claim_agrees`. A document without a usable pair is `undetermined` with the reason and does not
count; the label is `rules.label` of the counts.
"""
from __future__ import annotations

import re
from typing import Any

from . import rules
from .contract import Item
from .protocol import Protocol

SYSTEM = "evidence-engine"
CELL_BEFORE = re.compile(r"\|[\s*_]*$")
CELL_AFTER = re.compile(r"^[^\n|]*\|")


def value_start(m: Item) -> int:
    starts = [s.selector["start"] for s in m.spans if s.role == "value"]
    return min(starts) if starts else m.first_start()


def in_table(m: Item) -> bool:
    """The measurement's first value span sits in a Markdown table cell (a pipe before and after on its line)."""
    spans = sorted((s for s in m.spans if s.role == "value"), key=lambda s: s.selector["start"])
    return any(CELL_BEFORE.search(s.selector.get("prefix", "")) and CELL_AFTER.match(s.selector.get("suffix", ""))
               for s in spans)


def _best(ms: list[Item]) -> Item:
    return min(ms, key=lambda m: (not in_table(m), value_start(m), m.item_id))


def _pair(rag: list[Item], base: list[Item]) -> tuple[Item, Item] | None:
    order: list[Any] = []
    for m in sorted(rag + base, key=lambda m: (value_start(m), m.item_id)):
        if m.fields.get("dataset") not in order:
            order.append(m.fields.get("dataset"))
    for dataset in order:  # the same dataset on both sides, first dataset in document order
        r = [m for m in rag if m.fields.get("dataset") == dataset]
        b = [m for m in base if m.fields.get("dataset") == dataset]
        if r and b:
            return _best(r), _best(b)
    for dataset in order:  # fallback: one side names no dataset
        r = [m for m in rag if m.fields.get("dataset") in (dataset, None)]
        b = [m for m in base if m.fields.get("dataset") in (dataset, None)]
        if r and b and (dataset is None or any(m.fields.get("dataset") is None for m in r + b)):
            return _best(r), _best(b)
    return None


def study(protocol: Protocol, document: str, items: list[Item]) -> tuple[dict[str, Any], list[str]]:
    """One document's entry and the item ids it rests on."""
    by_id = {i.item_id: i for i in items}
    of = {t: [i for i in items if i.evidence_type == t] for t in ("condition", "metric", "measurement", "author_claim")}
    claim = of["author_claim"][0] if of["author_claim"] else None
    entry: dict[str, Any] = {"document": document, "direction": "undetermined", "delta": None, "metric": None,
                             "rag": None, "baseline": None, "author_claim": None, "reason": None}
    used: list[str] = []
    roles = {c.fields.get("role") for c in of["condition"]}
    question = [m for name in protocol.synthesis.metrics for m in of["metric"] if m.fields.get("canonical") == name]
    pair = None
    for metric in question:
        on = [m for m in of["measurement"] if m.links.get("metric") == metric.item_id]

        def role(m: Item) -> Any:
            cond = by_id.get(m.links.get("condition", ""))
            return cond.fields.get("role") if cond else None

        pair = _pair([m for m in on if role(m) == "rag"], [m for m in on if role(m) == "baseline"])
        if pair:
            break
    if pair is None:
        if "rag" not in roles:
            entry["reason"] = "no rag condition found"
        elif "baseline" not in roles:
            entry["reason"] = "no baseline condition found"
        elif not question:
            entry["reason"] = "no metric of the question found"
        else:
            entry["reason"] = "no rag and baseline measurement on a question metric"
    else:
        r, b = pair
        canonical = by_id[r.links["metric"]].fields["canonical"]
        direction, delta = rules.effect(float(r.fields["value"]), float(b.fields["value"]), rules.METRICS[canonical],
                                        protocol.synthesis.min_effect)
        entry.update(direction=direction, delta=delta, metric=canonical,
                     rag={"condition": r.links["condition"], "measurement": r.item_id, "value": r.fields["value"]},
                     baseline={"condition": b.links["condition"], "measurement": b.item_id, "value": b.fields["value"]})
        used += [r.item_id, b.item_id, r.links["condition"], b.links["condition"], r.links["metric"]]
    if claim is not None:
        determined = entry["direction"] != "undetermined"
        entry["author_claim"] = {"item": claim.item_id, "direction": claim.fields["direction"],
                                 "agrees_with_data": rules.claim_agrees(claim.fields["direction"], entry["direction"])
                                 if determined else None}
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
    label = rules.label(counts["supporting"], counts["contradicting"], counts["neutral"])
    out = {"system": SYSTEM, "question": protocol.question, "label": label, "counts": counts, "studies": studies,
           **groups}
    return out, used
