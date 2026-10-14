"""Cascade merge (contract section 10): items of one evidence type in one document with equal normalised
fields and equal links are one item that keeps every span and lists every extractor that found it.

Fields compared are the type's `merge_key` (all fields when the protocol gives none); strings compare case
folded with dashes and runs of spaces as one space. The merged item takes the fields of the first
extractor in cascade order that found it, with null fields filled from later ones, so the cascade order
decides between equivalent wordings. Its id is recomputed from the merged fields and spans.
"""
from __future__ import annotations

from typing import Any

from .contract import ExtractionResult, Item, Span, digest
from .extractors.terms import norm
from .protocol import EvidenceTypeSpec


def _normal(value: Any) -> Any:
    if isinstance(value, str):
        return norm(value)
    if isinstance(value, float):
        return round(value, 6)
    return value


def key(item: Item, spec: EvidenceTypeSpec) -> str:
    names = spec.merge_key or tuple(sorted(item.fields))
    return digest([item.evidence_type, {n: _normal(item.fields.get(n)) for n in names}, item.links])


def merge(results: list[tuple[str, ExtractionResult]], spec: EvidenceTypeSpec) -> tuple[list[Item], dict[str, list[str]]]:
    """(merged items in canonical order, merged item id -> the call ids that found it).

    `results` are (call_id, checked result) in cascade order."""
    groups: dict[str, dict[str, Any]] = {}
    for call_id, result in results:
        for item in result.items:
            k = key(item, spec)
            g = groups.setdefault(k, {"type": item.evidence_type, "fields": dict(item.fields), "links": item.links,
                                      "spans": {}, "found_by": [], "calls": []})
            for name, value in item.fields.items():
                if g["fields"].get(name) is None and value is not None:
                    g["fields"][name] = value
            for s in item.spans:
                g["spans"].setdefault((s.selector["start"], s.selector["end"], s.role), s)
            if result.extractor_id not in g["found_by"]:
                g["found_by"].append(result.extractor_id)
            if call_id not in g["calls"]:
                g["calls"].append(call_id)
    items: list[Item] = []
    sources: dict[str, list[str]] = {}
    for g in groups.values():
        spans: list[Span] = [g["spans"][k] for k in sorted(g["spans"])]
        item = Item.build(g["type"], g["fields"], spans, links=dict(g["links"]))
        item = item.model_copy(update={"found_by": tuple(g["found_by"])})
        items.append(item)
        sources[item.item_id] = g["calls"]
    items.sort(key=lambda i: (i.first_start(), i.evidence_type, i.item_id))
    return items, sources
