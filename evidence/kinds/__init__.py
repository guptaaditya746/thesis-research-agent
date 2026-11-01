"""One rules module per question kind (protocol.Kind): how a document's merged items become its entry, which
evidence types the funnel escalates for a gap, and the answer (answer.json).

Every module has the same four functions. Each reads evidence types and fields by their pack role, never by name:
`roles` (keyword, a pack.RoleMap; the engine passes the protocol's, None reads `protocol.roles()`).
- `study(protocol, document, items, preset=None, *, roles=None) -> (entry, used item ids)`: the per-document entry; it always
  carries `entry["reason"]`, None when the document is complete (the funnel's completeness check) or
  `{code, text}`; `preset` is the pre-set reason of a document the funnel screened out.
- `gap_types(protocol, code, *, roles=None) -> evidence types` the funnel escalates for a reason code (the
  protocol's types of the roles the module's `GAP_ROLES` names).
- `answer(protocol, documents, items, reasons, funnel, *, roles=None, groups=None, reason=None) -> (answer, used item
  ids)`: `groups` the names step's NameGroups, `reason` the reasoner's Inferences (a narrower metric answers a
  broader question metric, reasoner.counts_as); a kind that reads neither still takes both.
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
