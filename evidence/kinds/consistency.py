"""Kind `consistency`: does what the authors claim agree with what they measured? (`consistency.by: direction`)

Per document, the effect study of evidence/synthesis.py gives the measured direction and the author claim's
`agrees_with_data`; that is the entry's `agrees`. The reason is synthesis's while the direction is undetermined,
and `no_claim` when the direction is determined but the paper has no author_claim item (the funnel then
escalates author_claim). Answer:
`{kind, system, metric, studies: [{document, claim, direction, agrees, reason}], agreeing, disagreeing,
undetermined}`, documents in manifest order; `undetermined` holds every study whose `agrees` is null.
`metric` is the protocol's first question metric (the consistency protocols name one).
"""
from __future__ import annotations

from typing import Any

from .. import synthesis
from ..contract import EvidenceType, Item
from ..protocol import Protocol
from . import effect

KIND = "consistency"
GAP_TYPES: dict[str, tuple[EvidenceType, ...]] = {**synthesis.GAP_TYPES, "no_claim": ("author_claim",)}  # type: ignore[dict-item]
NO_CLAIM = {"code": "no_claim", "text": "no author claim found"}


def study(protocol: Protocol, document: str, items: list[Item],
          preset: dict[str, str] | None = None) -> tuple[dict[str, Any], list[str]]:
    effect.spec(protocol)
    full, used = synthesis.study(protocol, document, items, preset)
    claim = full["author_claim"]
    reason = full["reason"]
    if reason is None and claim is None:
        reason = dict(NO_CLAIM)
    entry = {"document": document, "claim": claim["direction"] if claim else None, "direction": full["direction"],
             "agrees": claim["agrees_with_data"] if claim else None, "reason": reason}
    return entry, used


def gap_types(protocol: Protocol, code: str) -> tuple[EvidenceType, ...]:
    return GAP_TYPES.get(code, ())


def answer(protocol: Protocol, documents: list[str], items: dict[str, list[Item]],
           reasons: dict[str, dict[str, str]] | None = None,
           funnel: dict[str, dict[str, Any]] | None = None) -> tuple[dict[str, Any], list[str]]:
    studies, used = [], []
    for doc in documents:
        entry, ids = study(protocol, doc, items.get(doc, []), (reasons or {}).get(doc))
        studies.append(entry)
        used += ids
    groups = {name: [s["document"] for s in studies if s["agrees"] is value]
              for name, value in (("agreeing", True), ("disagreeing", False), ("undetermined", None))}
    out = {"kind": KIND, "system": synthesis.SYSTEM, "metric": effect.spec(protocol).metric_names[0],
           "studies": studies, **groups}
    return out, used


def extractor_config(protocol: Protocol) -> dict[str, Any]:
    return effect.extractor_config(protocol)
