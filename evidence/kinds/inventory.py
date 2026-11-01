"""Kind `inventory`: every distinct item of one evidence type (`inventory.target`) the papers report.

A name is the item's name field (the pack's `name_field` of the target type: `label` of a rag condition, `name` of
a metric or dataset), compared case-folded with
whitespace collapsed. `inventory.same` maps a canonical name to the other names it goes by: every name that folds
to the canonical name or one of its others is one entry, named by the canonical name. Any other name is an entry
of its own, named by the first form met (documents in manifest order, items in the order given). `aliases` are the
entry's other forms as written, sorted; `papers` (manifest order) and `items` list where it was found. Entries are
sorted by name (case-folded, then as written). A document without a target item has reason `no_target_items`; one
with target items has `target_open`. Both escalate the target type, so in `gaps` mode the funnel runs the target's
whole cascade (recall is not capped at position 0) and the document ends exhausted with that gap on record. Answer: `{kind, system, target, entries: [{name, aliases, papers, items}]}`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import synthesis
from ..contract import Item
from ..evidence_types import EvidenceType
from ..protocol import Inventory, Protocol

if TYPE_CHECKING:
    from ..pack import RoleMap

KIND = "inventory"
NO_TARGET_ITEMS = "no_target_items"
TARGET_OPEN = "target_open"


def spec(protocol: Protocol) -> Inventory:
    assert protocol.inventory is not None, "an inventory protocol has an inventory block"
    return protocol.inventory


def fold(name: str) -> str:
    return " ".join(name.split()).casefold()


def name_field(protocol: Protocol, roles: RoleMap | None = None) -> str:
    """The target type's name field (pack TypeDecl.name_field; Protocol checks the pack declares one)."""
    return (roles if roles is not None else protocol.roles()).field(spec(protocol).target, "name")


def name_of(item: Item, field: str) -> str | None:
    value = item.fields.get(field)
    return " ".join(str(value).split()) if value is not None and str(value).strip() else None


def study(protocol: Protocol, document: str, items: list[Item], preset: dict[str, str] | None = None, *,
          roles: RoleMap | None = None) -> tuple[dict[str, Any], list[str]]:
    target = spec(protocol).target
    field = name_field(protocol, roles)
    entry: dict[str, Any] = {"document": document, "items": [], "reason": None}
    if preset is not None:
        entry["reason"] = dict(preset)
        return entry, []
    found = [i.item_id for i in items if i.evidence_type == target and name_of(i, field) is not None]
    entry["items"] = found
    if not found:
        entry["reason"] = {"code": NO_TARGET_ITEMS, "text": f"no {target} item found"}
    else:   # an inventory is never complete: a later extractor of the target type may find more names
        entry["reason"] = {"code": TARGET_OPEN, "text": f"{len(found)} {target} items found; later extractors may find more"}
    return entry, list(found)


def gap_types(protocol: Protocol, code: str, *, roles: RoleMap | None = None) -> tuple[EvidenceType, ...]:
    return (spec(protocol).target,) if code in (NO_TARGET_ITEMS, TARGET_OPEN) else ()


def answer(protocol: Protocol, documents: list[str], items: dict[str, list[Item]],
           reasons: dict[str, dict[str, str]] | None = None,
           funnel: dict[str, dict[str, Any]] | None = None, *,
           roles: RoleMap | None = None) -> tuple[dict[str, Any], list[str]]:
    inv = spec(protocol)
    roles = roles if roles is not None else protocol.roles()
    field = name_field(protocol, roles)
    canonical = {fold(name): name for name in inv.same}
    canonical |= {fold(other): name for name, others in inv.same.items() for other in others
                  if fold(other) not in canonical}
    groups: dict[str, dict[str, Any]] = {}       # folded group key -> {name, forms, papers, items}
    used: list[str] = []
    for doc in documents:
        entry, ids = study(protocol, doc, items.get(doc, []), (reasons or {}).get(doc), roles=roles)
        by_id = {i.item_id: i for i in items.get(doc, [])}
        for item_id in ids:
            form = name_of(by_id[item_id], field)
            assert form is not None
            name = canonical.get(fold(form), form)
            group = groups.setdefault(fold(name), {"name": name, "forms": [], "papers": [], "items": []})
            if form not in group["forms"]:
                group["forms"].append(form)
            if doc not in group["papers"]:
                group["papers"].append(doc)
            group["items"].append(item_id)
        used += ids
    entries = [{"name": g["name"], "aliases": sorted(f for f in g["forms"] if f != g["name"]),
                "papers": g["papers"], "items": g["items"]}
               for g in sorted(groups.values(), key=lambda g: (fold(g["name"]), g["name"]))]
    return {"kind": KIND, "system": synthesis.SYSTEM, "target": inv.target, "entries": entries}, used


def extractor_config(protocol: Protocol) -> dict[str, Any]:
    inv = spec(protocol)
    return {"target": inv.target, "same": {name: list(others) for name, others in inv.same.items()}}
