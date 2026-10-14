"""Cascade merge (contract section 10): items of one evidence type in one document with equal normalised
fields and equal links are one item that keeps every span and lists every extractor that found it.

Fields compared are the type's `merge_key` (all fields when the protocol gives none); strings compare case
folded with dashes and runs of spaces as one space. The other fields must not conflict: a null matches
anything, but two different non-null values (the same value on two datasets) keep the items apart. The
merged item takes the fields of the first extractor in cascade order that found it, with null fields
filled from later ones, so the cascade order decides between equivalent wordings. Its id is recomputed
from the merged fields and spans.

Two different merged items can end up with the same id (`Item.make_id` covers type, fields and span
positions, not links: one passage read as two associations). Neither is kept; both are returned as
collisions, which the engine records in the merge event, so nothing disappears silently.
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


def _compatible(fields: dict[str, Any], other: dict[str, Any]) -> bool:
    return all(a is None or b is None or _normal(a) == _normal(b)
               for name in set(fields) | set(other) for a, b in [(fields.get(name), other.get(name))])


def merge(results: list[tuple[str, ExtractionResult]], spec: EvidenceTypeSpec
          ) -> tuple[list[Item], dict[str, list[str]], list[dict[str, Any]]]:
    """(merged items in canonical order, merged item id -> the call ids that found it, collisions).

    `results` are (call_id, checked result) in cascade order."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for call_id, result in results:
        for item in result.items:
            candidates = groups.setdefault(key(item, spec), [])
            g = next((c for c in candidates if _compatible(c["fields"], item.fields)), None)
            if g is None:
                g = {"type": item.evidence_type, "fields": dict(item.fields), "links": item.links, "spans": {},
                     "found_by": [], "calls": []}
                candidates.append(g)
            for name, value in item.fields.items():
                if g["fields"].get(name) is None and value is not None:
                    g["fields"][name] = value
            for s in item.spans:
                g["spans"].setdefault((s.selector["start"], s.selector["end"], s.role), s)
            if result.extractor_id not in g["found_by"]:
                g["found_by"].append(result.extractor_id)
            if call_id not in g["calls"]:
                g["calls"].append(call_id)
    built: dict[str, list[tuple[Item, list[str]]]] = {}
    for g in (g for candidates in groups.values() for g in candidates):
        spans: list[Span] = [g["spans"][k] for k in sorted(g["spans"])]
        item = Item.build(g["type"], g["fields"], spans, links=dict(g["links"]))
        built.setdefault(item.item_id, []).append((item.model_copy(update={"found_by": tuple(g["found_by"])}), g["calls"]))
    items: list[Item] = []
    sources: dict[str, list[str]] = {}
    collisions: list[dict[str, Any]] = []
    for item_id, same in built.items():
        if len(same) == 1:
            items.append(same[0][0])
            sources[item_id] = same[0][1]
        else:
            collisions.append({"item_id": item_id, "reason": "ambiguous",
                               "detail": "items with the same fields and spans but different links; none kept",
                               "links": [i.links for i, _ in same], "calls": sorted({c for _, cs in same for c in cs})})
    items.sort(key=lambda i: (i.first_start(), i.evidence_type, i.item_id))
    return items, sources, collisions
