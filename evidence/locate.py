"""The locate step: which parts of a document the extractors of one evidence type may look at (the task's scope).

- `exhaustive`: the whole document; nothing a ranker decides is left out.
- `bm25`: the document cut into section-aware passages (gold/chunks.py) ranked by rank_bm25 against the
  evidence type's query terms from the protocol; the `top_k` passages with a positive score are the scope.
- `agent`: a pluggable `Locator` (for an agent that reads the document and says where to look); not
  built here, so the engine refuses the strategy unless one is passed in.

What was given as scope is recorded in locate.json, so locate recall (the share of ground-truth placements
inside the scope) can be measured.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from rank_bm25 import BM25Okapi

from gold.chunks import split

from .contract import DocumentRef, Scope
from .protocol import EvidenceTypeSpec, Locate

TOKEN = re.compile(r"\w+|%")


class LocateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Located:
    scope: Scope
    ranked: list[dict[str, Any]] = field(default_factory=list)   # bm25: [{range, score}] in rank order

    def json(self) -> dict[str, Any]:
        return {"scope": self.scope.model_dump(mode="json"), "ranked": self.ranked}


@runtime_checkable
class Locator(Protocol):
    """An `agent` locate strategy: given a document and an evidence type, the parts to search."""
    name: str

    def locate(self, document: DocumentRef, text: str, evidence_type: str, spec: EvidenceTypeSpec,
               params: dict[str, Any]) -> Scope: ...


def tokens(text: str) -> list[str]:
    return [t.casefold() for t in TOKEN.findall(text)]


def bm25(text: str, query: tuple[str, ...], params: dict[str, Any]) -> Located:
    passages = split(text, int(params.get("chunk_chars", 1500)))
    if not passages:
        return Located(Scope(kind="ranges", ranges=()))
    model = BM25Okapi([tokens(text[a:b]) or ["\u0000"] for a, b, _ in passages])
    scores = model.get_scores([t for q in query for t in tokens(q)])
    order = sorted(range(len(passages)), key=lambda n: (-scores[n], passages[n][0]))
    top = [n for n in order[: int(params.get("top_k", 6))] if scores[n] > float(params.get("min_score", 0.0))]
    ranked = [{"range": [passages[n][0], passages[n][1]], "score": round(float(scores[n]), 6)} for n in order]
    ranges = sorted((passages[n][0], passages[n][1]) for n in top)
    merged: list[tuple[int, int]] = []
    for a, b in ranges:  # adjacent passages become one range
        if merged and merged[-1][1] == a:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return Located(Scope(kind="ranges", ranges=tuple(merged)), ranked)


def locate(settings: Locate, document: DocumentRef, text: str, evidence_type: str, spec: EvidenceTypeSpec,
           locator: Locator | None = None) -> Located:
    if settings.strategy == "exhaustive":
        return Located(Scope(kind="document"))
    if settings.strategy == "bm25":
        if not spec.query:
            raise LocateError(f"bm25 locate needs query terms for {evidence_type} in the protocol")
        return bm25(text, spec.query, settings.params)
    if locator is None:
        raise LocateError("locate strategy 'agent' needs a Locator; evidence/ does not build one, "
                          "pass it to engine.run(locator=...)")
    return Located(locator.locate(document, text, evidence_type, spec, settings.params))
