"""Kind `builds_on` (spec section 6.18; plan 2 Task 11): which studies build on which, and how influential each
compared thing is, for one thing (`builds_on.thing`) or for every one.

A dependency item (pack role `dependency`) cites an earlier study by its label as written (its name field) and says
what it reuses (`reuses`: method, dataset or result); it may link the compared thing it reuses (a link to an item of a
compared-thing type; a reused dataset links none). A study-label item (role `study_label`) is the label a paper is
cited by. Rules:
1. A cited label is resolved to a document of the run by `comparisons.resolve_cited` (one rule with comparisons'
   `copied_from`: the name group, else the clean form; the earliest such document in manifest order). A cited text
   that resolves to no document (a study outside the run) goes to `unresolved` (each text once, in the order met),
   never to `links`.
2. `links` are (citing document, cited document, reuses), each with the ids of its dependency items, in manifest
   order of the citing then the cited document, then by `reuses`.
3. A compared thing is its key as comparisons match things (`comparisons.thing_key`), shown by its group name, else by
   the first form met (documents in manifest order). A document mentions a thing when it has an item of a
   compared-thing type of that name.
4. The origin of a thing is the earliest document by its label's year (the last 4-digit run of its first study
   label; a document without one comes after every dated one; ties: manifest order) that mentions the thing and has
   no dependency linking it. A thing every mentioning document took from elsewhere (its origin outside the run) has
   origin null and no followers.
5. The followers of a thing are the documents with a path of links (of any reuse) to its origin, direct or
   indirect, the origin itself excluded; the walk keeps a visited set, so a cycle ends. They are listed in manifest
   order. `influence[x] = len(followers[x])`; `ranking` sorts the things by influence, descending, then by name.
With `thing` set, only that thing is in `origins`, `followers`, `influence` and `ranking`; `links` and `unresolved`
always cover the run.

Answer: `{kind, system, thing, links: [{from, to, reuses, items}], origins: {thing: doc | null},
followers: {thing: [docs]}, influence: {thing: n}, ranking: [thing], unresolved: [cited]}`; the thing maps follow
`ranking`.

Per document (`study`, the funnel's completeness check): reason `no_study_label` (escalates the study-label type)
when the document has no study label, else `no_dependency_items` (escalates the dependency type) when it has no
dependency; an origin study may rightly have none, so the gap only asks for another pass.
"""
from __future__ import annotations

import re
from collections import deque
from typing import TYPE_CHECKING, Any

from .. import comparisons as cmp
from .. import synthesis
from ..contract import Item
from ..evidence_types import EvidenceType
from ..protocol import BuildsOnQ, Protocol

if TYPE_CHECKING:
    from ..comparisons import Comparisons
    from ..names import NameGroups
    from ..pack import RoleMap
    from ..reasoner import Inferences

KIND = "builds_on"
NO_STUDY_LABEL = "no_study_label"
NO_DEPENDENCY_ITEMS = "no_dependency_items"
GAP_ROLES: dict[str, tuple[str, ...]] = {NO_STUDY_LABEL: ("study_label",), NO_DEPENDENCY_ITEMS: ("dependency",),
                                         "screened_out": ()}   # pack.Role values
REUSES = "reuses"   # the dependency type's field: method, dataset or result
YEAR = re.compile(r"(?<!\d)\d{4}(?!\d)")


def spec(protocol: Protocol) -> BuildsOnQ:
    assert protocol.builds_on is not None, "a builds_on protocol has a builds_on block"
    return protocol.builds_on


def _types(roles: RoleMap, role: str) -> set[str]:
    from ..pack import Role
    return set(roles.types_of(Role(role)))


def _labels(items: list[Item], roles: RoleMap) -> list[Item]:
    labels = _types(roles, "study_label")
    return sorted((i for i in items if i.evidence_type in labels), key=lambda i: (i.first_start(), i.item_id))


def year_of(label: str | None) -> int | None:
    """The year of a study label: its last 4-digit run (None: no label, or no year in it)."""
    years = YEAR.findall(label) if label is not None else []
    return int(years[-1]) if years else None


def _year(items: list[Item], roles: RoleMap) -> int | None:
    """The year of the document's first study label (`year_of`)."""
    return year_of(next((n for n in (cmp.name_of(i, roles) for i in _labels(items, roles)) if n is not None), None))


def origin_of(own: list[str], years: dict[str, int | None], position: dict[str, int]) -> str | None:
    """Rule 4: of the documents that mention a thing and have no dependency linking it (`own`), the earliest by
    year (a document without one after every dated one; ties: manifest `position`); None when there is none. The
    truth's expected answer (evaluation/expected.py) uses this and `followers_of` too."""
    return min(own, key=lambda d: (years[d] is None, years[d] or 0, position[d]), default=None)


def study(protocol: Protocol, document: str, items: list[Item], preset: dict[str, str] | None = None, *,
          roles: RoleMap | None = None, groups: NameGroups | None = None) -> tuple[dict[str, Any], list[str]]:
    roles = roles if roles is not None else protocol.roles()
    entry: dict[str, Any] = {"document": document, "items": [], "reason": None}
    if preset is not None:
        entry["reason"] = dict(preset)
        return entry, []
    labels = _labels(items, roles)
    dependencies = [i for i in items if i.evidence_type in _types(roles, "dependency")]
    entry["items"] = [i.item_id for i in labels + dependencies]
    if not labels:
        entry["reason"] = {"code": NO_STUDY_LABEL, "text": "no study label found"}
    elif not dependencies:
        entry["reason"] = {"code": NO_DEPENDENCY_ITEMS, "text": "no dependency found"}
    return entry, list(entry["items"])


def gap_types(protocol: Protocol, code: str, *, roles: RoleMap | None = None) -> tuple[EvidenceType, ...]:
    return synthesis.gap_types(protocol, code, roles, GAP_ROLES)


def answer(protocol: Protocol, documents: list[str], items: dict[str, list[Item]],
           reasons: dict[str, dict[str, str]] | None = None,
           funnel: dict[str, dict[str, Any]] | None = None, *,
           roles: RoleMap | None = None, groups: NameGroups | None = None,
           comparisons: Comparisons | None = None, reason: Inferences | None = None) -> tuple[dict[str, Any], list[str]]:
    """The builds-on answer. `comparisons` and `reason` (the reasoner's inferences) are not read."""
    question = spec(protocol)
    roles = roles if roles is not None else protocol.roles()
    things, dependencies = _types(roles, "compared_thing"), _types(roles, "dependency")
    cited_doc = cmp.resolve_cited(documents, items, roles, groups)   # rule 1
    wanted = cmp.thing_key(question.thing, groups) if question.thing is not None else None
    position = {doc: n for n, doc in enumerate(documents)}

    found: dict[tuple[str, str, str], list[str]] = {}   # (from, to, reuses) -> dependency item ids
    unresolved: list[str] = []
    shown: dict[str, str] = {}                           # thing key -> the name it is shown by
    mentions: dict[str, list[str]] = {}                  # thing key -> documents that mention it
    taken: set[tuple[str, str]] = set()                  # (document, thing key): a dependency links the thing
    for doc in documents:
        by_id = {i.item_id: i for i in items.get(doc, [])}

        def key_of(name: str) -> str:
            key = cmp.thing_key(name, groups)
            shown.setdefault(key, (groups.group_of(name) if groups is not None else None) or name)
            return key

        for item in items.get(doc, []):
            if item.evidence_type in things and (name := cmp.name_of(item, roles)) is not None:
                key = key_of(name)
                if doc not in mentions.setdefault(key, []):
                    mentions[key].append(doc)
            if item.evidence_type not in dependencies:
                continue
            for target in (by_id.get(t) for t in item.links.values()):
                if target is not None and target.evidence_type in things and (name := cmp.name_of(target, roles)):
                    taken.add((doc, key_of(name)))
            cited = cmp.name_of(item, roles)
            if cited is None:
                continue
            to = cited_doc.get(cited)
            if to is None:
                if cited not in unresolved:
                    unresolved.append(cited)
                continue
            found.setdefault((doc, to, str(item.fields.get(REUSES))), []).append(item.item_id)

    ordered = sorted(found, key=lambda k: (position[k[0]], position[k[1]], k[2]))
    links = [{"from": f, "to": t, "reuses": r, "items": found[(f, t, r)]} for f, t, r in ordered]
    citers: dict[str, list[str]] = {}
    for f, t, _ in ordered:
        citers.setdefault(t, []).append(f)

    years = {doc: _year(items.get(doc, []), roles) for doc in documents}
    origins: dict[str, str | None] = {}
    followers: dict[str, list[str]] = {}
    for key, docs in mentions.items():
        if wanted is not None and key != wanted:
            continue
        own = [d for d in docs if (d, key) not in taken]                       # rule 4
        origin = origin_of(own, years, position)
        origins[key] = origin
        followers[key] = followers_of(origin, citers, position) if origin is not None else []
    if wanted is not None and wanted not in origins:   # the asked thing is mentioned nowhere
        shown.setdefault(wanted, question.thing or "")
        origins[wanted], followers[wanted] = None, []

    ranking = sorted(origins, key=lambda k: (-len(followers[k]), shown[k].casefold(), shown[k]))
    used = [i for link in links for i in link["items"]]
    return {"kind": KIND, "system": synthesis.SYSTEM, "thing": question.thing, "links": links,
            "origins": {shown[k]: origins[k] for k in ranking},
            "followers": {shown[k]: followers[k] for k in ranking},
            "influence": {shown[k]: len(followers[k]) for k in ranking},
            "ranking": [shown[k] for k in ranking], "unresolved": unresolved}, used


def followers_of(origin: str, citers: dict[str, list[str]], position: dict[str, int]) -> list[str]:
    """Every document with a path of links to `origin` (rule 5), in manifest order; the visited set ends a cycle."""
    seen = {origin}
    queue = deque([origin])
    while queue:
        for doc in citers.get(queue.popleft(), []):
            if doc not in seen:
                seen.add(doc)
                queue.append(doc)
    return sorted(seen - {origin}, key=position.__getitem__)


def extractor_config(protocol: Protocol) -> dict[str, Any]:
    return {}
