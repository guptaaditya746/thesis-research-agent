"""One rules module per question kind (protocol.Kind): how a document's merged items become its entry, which
evidence types the funnel escalates for a gap, and the answer (answer.json).

Every module has the same four functions:
- `study(protocol, document, items, preset=None) -> (entry, used item ids)`: the per-document entry; it always
  carries `entry["reason"]`, None when the document is complete (the funnel's completeness check) or
  `{code, text}`; `preset` is the pre-set reason of a document the funnel screened out.
- `gap_types(protocol, code) -> evidence types` the funnel escalates for a reason code.
- `answer(protocol, documents, items, reasons, funnel) -> (answer, used item ids)`.
- `extractor_config(protocol) -> dict`: the question's part of every extractor's config (engine.build_extractors).

`effect` is evidence/synthesis.py unchanged, so an effect protocol gives byte-identical runs. Every other kind's
answer carries `kind` and `system`.
"""
from __future__ import annotations

from types import ModuleType
from typing import Any

from ..protocol import Protocol
from . import best, consistency, effect, inventory

MODULES: dict[str, ModuleType] = {"effect": effect, "consistency": consistency, "inventory": inventory, "best": best}
# The reason of a document the funnel screened out, for the kinds other than effect (whose text is synthesis's).
SCREENED_OUT: dict[str, str] = {"code": "screened_out", "text": "screened out"}

__all__ = ["MODULES", "SCREENED_OUT", "best", "consistency", "effect", "inventory", "of", "screened_out"]


def of(protocol: Protocol) -> Any:
    """The rules module of the protocol's kind."""
    return MODULES[protocol.kind]


def screened_out(protocol: Protocol) -> dict[str, str]:
    """The pre-set reason `{code, text}` of a screened-out document: synthesis's for effect, else kind-neutral."""
    if protocol.kind == "effect":
        return effect.screened_out(protocol)
    return dict(SCREENED_OUT)
