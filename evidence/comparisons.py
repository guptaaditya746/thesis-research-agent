"""Comparisons are built, not extracted (spec section 6.2; plan 2 Task 8): comparisons.json of every run.

Within one document, every unordered pair of compared things with measured values on the same metric (its
canonical name) and the same context value (a dataset or a population) is one comparison. Rules:
1. Pairing as `synthesis._pair`: the contexts are tried in the order their values first appear; every context both
   things have values in gives one comparison. Only when there is none, a value that names no context joins a
   named one: the first context (document order) where the two things have values once the values naming no
   context are added, at least one of them naming none, gives the one comparison, with that context.
2. `a` is the thing whose name sorts first, `b` the other: the group name with name groups, else the `names.clean`
   form (so "Placebo" and "placebo" sort alike in every paper; plain string order); `a` and `b` show the group name,
   else the name as first written in the paper. `direction` and `delta` are `rules.effect` of a over b (`supports`:
   a is better), the metric's direction from the protocol's question metrics, else from the pack's `words.metrics`;
   a metric of neither has `direction` and `delta` null (no guess). Treatment and control are the kind's to decide.
3. Among several values of one thing there, `prefer` decides (`synthesis.best_value`: a table cell first, then
   the earlier value).
4. A value that links to an item of the dependency type whose `reuses` field is `result` was copied from the study
   that dependency cites (`resolve_cited`): its comparison gets `cited_text` (the cited label as written) and
   `copied_from`, the cited document, or null when no document of the run carries that label. A comparison whose two
   values are both copied is dropped. A comparison equal in (a, b by their thing keys, metric, context, a_value,
   b_value) to one of its cited document is listed under `copied`, not under `comparisons`, so a copied result
   counts once, at its origin (section 6.11).
5. Ids are `cmp-<16 hex>` of `contract.digest`.
6. A compared thing is its name group: `groups.group_of(name)` when the run has name groups (`names: on`), else
   (and for a name in no group) its `names.clean` form, shown as the name it is first written with.

comparisons.json also records the neutral band used (`min_effect`).

Types and fields are found by pack role (pack.RoleMap), links by the type of the item they point to, so no type,
field or link name of a topic is written here; the dependency type's fields are `reuses` (method, dataset or
result) and its name field (the cited label as written), the study-label type's its name field.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import TYPE_CHECKING, Any

from . import names, rules, synthesis
from .contract import Item, digest
from .protocol import Pairing, Protocol

if TYPE_CHECKING:
    from .names import NameGroups
    from .pack import RoleMap

ID_PREFIX = "cmp-"
REUSES_FIELD, COPIED_RESULT = "reuses", "result"   # the dependency type's field, and its value for a copied result
DEFAULT_PREFER: tuple[str, ...] = Pairing().prefer
# The neutral band of a kind that has none (inventory, limitations, builds_on): two values equal at the precision
# values are compared at (rules.VALUE_DECIMALS) are neutral.
NO_BAND = 10.0 ** -rules.VALUE_DECIMALS

# (value, its compared thing, its metric, its copy): the copy of a copied value is (the cited document or None,
# the cited text as written); None for a value the study measured itself.
Value = tuple[Item, Item, Item, "tuple[str | None, str] | None"]


@dataclass(frozen=True)
class Comparison:
    id: str
    document: str
    a: str
    b: str
    metric: str
    context: str | None
    a_value: float
    b_value: float
    direction: rules.Direction | None   # None: the metric's direction is unknown (rule 2)
    delta: float | None
    items: tuple[str, ...]          # the two values, the two compared things and the metric item(s)
    copied_from: str | None         # the cited document of a copied value (rule 4); None when none or unresolved
    cited_text: str | None = None   # the cited label as written, for a copied value

    def json(self) -> dict[str, Any]:
        return {**asdict(self), "items": list(self.items)}

    def key(self, groups: NameGroups | None = None) -> tuple[Any, ...]:
        """What a copied comparison shares with its origin's (rule 4): the things by their keys (rule 6), not by
        how a paper spells them."""
        return (_key(self.a, groups), _key(self.b, groups), self.metric, self.context,
                round(self.a_value, rules.VALUE_DECIMALS), round(self.b_value, rules.VALUE_DECIMALS))


@dataclass(frozen=True)
class Comparisons:
    """A run's comparisons (counted, manifest order) and those listed only as copies of their origin's."""
    comparisons: tuple[Comparison, ...] = ()
    copied: tuple[Comparison, ...] = ()
    min_effect: float | None = None   # the neutral band the directions were computed with

    def json(self) -> dict[str, Any]:
        return {"min_effect": self.min_effect, "comparisons": [c.json() for c in self.comparisons],
                "copied": [c.json() for c in self.copied]}


def _of_role(items: list[Item], roles: RoleMap, role: str) -> list[Item]:
    from .pack import Role
    types = set(roles.types_of(Role(role)))
    return [i for i in items if i.evidence_type in types]


def _name(item: Item, roles: RoleMap) -> str | None:
    field = roles.field_or_none(item.evidence_type, "name")
    value = item.fields.get(field) if field is not None else None
    text = " ".join(str(value).split()) if value is not None else ""
    return text or None


def _sort(key: str) -> tuple[str, str]:
    """A thing key's sort form (rule 2): the group name or the clean form."""
    return key.split(":", 1)[1], key


def _key(name: str, groups: NameGroups | None) -> str:
    """The thing a name stands for (rule 6): its group, else its clean form (kept apart from group names)."""
    group = groups.group_of(name) if groups is not None else None
    return f"group:{group}" if group is not None else f"clean:{names.clean(name)}"


def resolve_cited(documents: Sequence[str], items: Mapping[str, list[Item]], roles: RoleMap,
                  groups: NameGroups | None) -> dict[str, str | None]:
    """Each cited text of the run's dependency items -> the document whose study label names the same thing (rule
    6's matching: the name group, else the clean form); the earliest such document in `documents` (manifest order),
    None when no document's label matches."""
    labelled: dict[str, str] = {}
    for doc in documents:
        for label in sorted(_of_role(items.get(doc, []), roles, "study_label"), key=lambda i: (i.first_start(), i.item_id)):
            text = _name(label, roles)
            if text is not None:
                labelled.setdefault(_key(text, groups), doc)
    out: dict[str, str | None] = {}
    for doc in documents:
        for dep in _of_role(items.get(doc, []), roles, "dependency"):
            cited = _name(dep, roles)
            if cited is not None:
                out[cited] = labelled.get(_key(cited, groups))
    return out


def build_comparisons(document: str, items: list[Item], roles: RoleMap, groups: NameGroups | None, *,
                      higher_is_better: Callable[[str], bool | None], min_effect: float, prefer: Sequence[str],
                      cited: Mapping[str, str | None] | None = None) -> list[Comparison]:
    """The comparisons of one document (rules 1-3, 5, 6; and rule 4's `copied_from` and dropping, `cited` being
    `resolve_cited` of the run: None resolves no cited text). Metrics in order of first value, pairs by name."""
    from .pack import Role
    by_id = {i.item_id: i for i in items}
    kinds = {t: role for role in (Role.COMPARED_THING, Role.METRIC, Role.DEPENDENCY) for t in roles.types_of(role)}
    shown: dict[str, str] = {}                                   # thing key -> the name it is first written with
    found: dict[str, dict[str, list[Value]]] = {}                # metric canonical -> thing key -> its values
    values = sorted(_of_role(items, roles, "measured_value"), key=lambda m: (synthesis.value_start(m), m.item_id))
    for value in values:
        linked: dict[Role, Item] = {}
        for target in value.links.values():
            item = by_id.get(target)
            if item is not None and item.evidence_type in kinds:
                linked.setdefault(kinds[item.evidence_type], item)
        thing, metric = linked.get(Role.COMPARED_THING), linked.get(Role.METRIC)
        canonical_field = roles.field_or_none(metric.evidence_type, "canonical") if metric is not None else None
        canonical = metric.fields.get(canonical_field) if metric is not None and canonical_field else None
        name = _name(thing, roles) if thing is not None else None
        if name is None or canonical is None:
            continue
        dep = linked.get(Role.DEPENDENCY)
        copied: tuple[str | None, str] | None = None
        if dep is not None and dep.fields.get(REUSES_FIELD) == COPIED_RESULT:
            text = _name(dep, roles) or ""
            copied = ((cited or {}).get(text), text)
        key = _key(name, groups)
        shown.setdefault(key, key.split(":", 1)[1] if key.startswith("group:") else name)
        found.setdefault(str(canonical), {}).setdefault(key, []).append((value, thing, metric, copied))
    out: list[Comparison] = []
    for canonical, things in found.items():
        for x, y in combinations(sorted(things, key=_sort), 2):
            for context, a, b in _pairs(things[x], things[y], roles, prefer):
                comparison = _comparison(document, shown[x], shown[y], canonical, context, a, b, higher_is_better,
                                         min_effect)
                if comparison is not None:
                    out.append(comparison)
    return out


def _pairs(xs: list[Value], ys: list[Value], roles: RoleMap,
           prefer: Sequence[str]) -> list[tuple[str | None, Value, Value]]:
    """(context, x's value, y's value) per rule 1, each value chosen by `prefer` (rule 3)."""
    def context(v: Value) -> Any:
        return v[0].fields.get(roles.context_field(v[0].evidence_type))

    def best(vs: list[Value]) -> Value:
        chosen = synthesis.best_value([v[0] for v in vs], tuple(prefer))
        return next(v for v in vs if v[0] is chosen)

    order: list[Any] = []
    for v in sorted(xs + ys, key=lambda v: (synthesis.value_start(v[0]), v[0].item_id)):
        if context(v) not in order:
            order.append(context(v))
    same = [(c, [v for v in xs if context(v) == c], [v for v in ys if context(v) == c]) for c in order]
    out = [(c, best(a), best(b)) for c, a, b in same if a and b]
    if out:
        return out
    for c in order:   # fallback: values that name no context join a named one
        a = [v for v in xs if context(v) in (c, None)]
        b = [v for v in ys if context(v) in (c, None)]
        if a and b and (c is None or any(context(v) is None for v in a + b)):
            return [(c, best(a), best(b))]
    return []


def _comparison(document: str, a_name: str, b_name: str, metric: str, context: str | None, a: Value, b: Value,
                higher_is_better: Callable[[str], bool | None], min_effect: float) -> Comparison | None:
    if a[3] is not None and b[3] is not None:   # both values copied: nothing of this study is compared (rule 4)
        return None
    a_value, b_value = float(a[0].fields["value"]), float(b[0].fields["value"])
    better = higher_is_better(metric)
    direction, delta = (None, None) if better is None else rules.effect(a_value, b_value, better, min_effect)
    copy = a[3] if a[3] is not None else b[3]
    items = tuple(dict.fromkeys((a[0].item_id, b[0].item_id, a[1].item_id, b[1].item_id, a[2].item_id, b[2].item_id)))
    ident = digest([document, a_name, b_name, metric, context, a[0].item_id, b[0].item_id])
    return Comparison(id=f"{ID_PREFIX}{ident[:16]}", document=document, a=a_name, b=b_name, metric=metric,
                      context=None if context is None else str(context), a_value=a_value, b_value=b_value,
                      direction=direction, delta=delta, items=items, copied_from=copy[0] if copy else None,
                      cited_text=copy[1] if copy else None)


def settings(protocol: Protocol) -> dict[str, Any]:
    """The keyword arguments of `build_comparisons` a protocol's kind gives: the direction of its question metrics,
    else the pack's (`words.metrics`, the first entry of a canonical), else None (unknown: rule 2); its neutral band
    (NO_BAND for a kind without one) and its `prefer` order."""
    metrics: dict[str, bool] = {}
    for _, canonical, better in protocol.pack().words.metrics:
        metrics.setdefault(canonical, better)
    min_effect, prefer = NO_BAND, DEFAULT_PREFER
    if protocol.synthesis is not None:
        s = protocol.synthesis
        metrics |= {m.canonical: m.higher_is_better for m in s.metrics}
        min_effect, prefer = s.min_effect, s.pairing.prefer
    elif protocol.best is not None:
        metrics |= {protocol.best.metric.canonical: protocol.best.metric.higher_is_better}
        prefer = protocol.best.pairing.prefer
    elif protocol.chaining is not None:
        metrics |= {protocol.chaining.metric.canonical: protocol.chaining.metric.higher_is_better}
        min_effect = protocol.chaining.min_effect
    return {"higher_is_better": lambda canonical: metrics.get(canonical), "min_effect": min_effect,
            "prefer": tuple(prefer)}


def of_run(protocol: Protocol, documents: Sequence[str], items: Mapping[str, list[Item]], roles: RoleMap,
           groups: NameGroups | None) -> Comparisons:
    """Every document's comparisons (manifest order), a copy of its cited document's comparison moved to `copied`
    (rule 4)."""
    cited = resolve_cited(documents, items, roles, groups)
    knobs = settings(protocol)
    per_doc = {doc: build_comparisons(doc, items.get(doc, []), roles, groups, cited=cited, **knobs)
               for doc in documents}
    counted: list[Comparison] = []
    copied: list[Comparison] = []
    for doc in documents:
        for c in per_doc[doc]:
            origin = per_doc.get(c.copied_from) if c.copied_from is not None and c.copied_from != doc else None
            (copied if origin and any(o.key(groups) == c.key(groups) for o in origin) else counted).append(c)
    return Comparisons(comparisons=tuple(counted), copied=tuple(copied), min_effect=knobs["min_effect"])
