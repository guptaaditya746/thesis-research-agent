"""Kind `limitations` (spec section 6.18; plan 2 Task 10): the limitations the papers state, for one compared thing
(`limitations.thing`) or for every one.

A limitation item has a `category` (an enum equal to the pack's `limitation_categories`; Protocol checks) and a quote,
and links the compared thing it is about (`thing`; an optional link). The thing is the name of that linked item, and
two names are one thing as comparisons match things (`comparisons.thing_key`: the name group with `names: on`, else
the clean form); it is shown by its group name, else by the first form met (documents in manifest order). Entries
are (thing, category); `papers` are in manifest order and `items` in the order given. A copied limitation is not a
concept, so every paper that states one counts (nothing is deduplicated across papers). With `thing` set, only that
thing's entries are listed. Entries are sorted by thing (case-folded; the unlinked entry last), then by the pack's
category order.

A limitation without a thing is kept under thing `null` (reason `unlinked`, which escalates nothing: more passes of
the limitation type would not find the link). A document without a limitation item has reason `no_limitation_items`,
which escalates the limitation type. Per document `study` counts any limitation, whichever thing it is about.

Answer: `{kind, system, thing, entries: [{thing, category, papers, items}], counts: {thing: {category: n_papers}},
unlinked: {category: n_papers}}` (`counts` has the linked limitations only; the unlinked ones are `unlinked`).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import comparisons as cmp
from .. import synthesis
from ..contract import Item
from ..evidence_types import EvidenceType
from ..protocol import LimitationsQ, Protocol

if TYPE_CHECKING:
    from ..comparisons import Comparisons
    from ..names import NameGroups
    from ..pack import RoleMap

KIND = "limitations"
NO_LIMITATION_ITEMS = "no_limitation_items"
UNLINKED = "unlinked"
GAP_ROLES: dict[str, tuple[str, ...]] = {NO_LIMITATION_ITEMS: ("limitation",), "screened_out": ()}   # pack.Role values
CATEGORY = "category"   # the limitation type's category field (its enum is the pack's limitation_categories)
THING = "thing"         # the limitation type's link to the compared thing


def spec(protocol: Protocol) -> LimitationsQ:
    assert protocol.limitations is not None, "a limitations protocol has a limitations block"
    return protocol.limitations


def limitation_type(protocol: Protocol, roles: RoleMap) -> EvidenceType:
    from ..pack import Role
    found = roles.type_in(Role.LIMITATION, protocol.evidence_types)
    assert found is not None, "a limitations protocol declares a limitation type"
    return found


def _name(target: Item | None, roles: RoleMap) -> str | None:
    """The name of the compared-thing item a limitation links (None: no link, or a name that is blank)."""
    if target is None:
        return None
    value = target.fields.get(roles.field(target.evidence_type, "name"))
    return " ".join(str(value).split()) or None if value is not None else None


def study(protocol: Protocol, document: str, items: list[Item], preset: dict[str, str] | None = None, *,
          roles: RoleMap | None = None, groups: NameGroups | None = None) -> tuple[dict[str, Any], list[str]]:
    roles = roles if roles is not None else protocol.roles()
    kind = limitation_type(protocol, roles)
    entry: dict[str, Any] = {"document": document, "items": [], "reason": None}
    if preset is not None:
        entry["reason"] = dict(preset)
        return entry, []
    found = [i for i in items if i.evidence_type == kind]
    entry["items"] = [i.item_id for i in found]
    if not found:
        entry["reason"] = {"code": NO_LIMITATION_ITEMS, "text": f"no {kind} item found"}
    elif any(THING not in i.links for i in found):
        entry["reason"] = {"code": UNLINKED, "text": f"a {kind} item names no {THING}"}
    return entry, list(entry["items"])


def gap_types(protocol: Protocol, code: str, *, roles: RoleMap | None = None) -> tuple[EvidenceType, ...]:
    return synthesis.gap_types(protocol, code, roles, GAP_ROLES)


def answer(protocol: Protocol, documents: list[str], items: dict[str, list[Item]],
           reasons: dict[str, dict[str, str]] | None = None,
           funnel: dict[str, dict[str, Any]] | None = None, *,
           roles: RoleMap | None = None, groups: NameGroups | None = None,
           comparisons: Comparisons | None = None, reason: object | None = None) -> tuple[dict[str, Any], list[str]]:
    """The limitations answer. `comparisons` and `reason` (plan 3's inferences) are not read."""
    question = spec(protocol)
    roles = roles if roles is not None else protocol.roles()
    kind = limitation_type(protocol, roles)
    wanted = cmp.thing_key(question.thing, groups) if question.thing is not None else None
    order = {c: n for n, c in enumerate(roles.pack.limitation_categories)}
    found: dict[tuple[str | None, str], dict[str, Any]] = {}   # (thing key, category) -> entry
    shown: dict[str | None, str | None] = {None: None}         # thing key -> the name it is shown by
    used: list[str] = []
    for doc in documents:
        by_id = {i.item_id: i for i in items.get(doc, [])}
        for item in items.get(doc, []):
            if item.evidence_type != kind:
                continue
            name = _name(by_id.get(item.links.get(THING, "")), roles)
            key = None if name is None else cmp.thing_key(name, groups)
            if wanted is not None and key != wanted:
                continue
            if key not in shown:
                shown[key] = (groups.group_of(name) if groups is not None and name is not None else None) or name
            category = str(item.fields[CATEGORY])
            group = found.setdefault((key, category), {"thing": shown[key], "category": category, "papers": [],
                                                       "items": []})
            if doc not in group["papers"]:
                group["papers"].append(doc)
            group["items"].append(item.item_id)
            used.append(item.item_id)
    ranked = sorted(found, key=lambda k: (k[0] is None, (shown[k[0]] or "").casefold(), order.get(k[1], len(order)),
                                          k[1]))
    entries = [found[k] for k in ranked]
    counts: dict[str, dict[str, int]] = {}   # linked limitations only: a JSON key is a string (jsonio sorts keys)
    unlinked: dict[str, int] = {}
    for e in entries:
        target = unlinked if e["thing"] is None else counts.setdefault(e["thing"], {})
        target[e["category"]] = len(e["papers"])
    return {"kind": KIND, "system": synthesis.SYSTEM, "thing": question.thing, "entries": entries,
            "counts": counts, "unlinked": unlinked}, used


def extractor_config(protocol: Protocol) -> dict[str, Any]:
    return {}
