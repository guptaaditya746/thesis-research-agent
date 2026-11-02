"""Deterministic synthesis: from the evidence of each document to answer.json (docs/evidence-system.md A4,
protocol v2 in Part C). Every parameter comes from the protocol's `synthesis` block; the machinery is
`evidence/rules.py`.

Per document: the question metrics are tried in the protocol's order, and within a metric the metric
items in document order; the first metric item with a usable treatment/control pair (the condition roles
`synthesis.compare` names) gives the study's effect with `rules.effect` (higher-is-better from the
protocol's metric list, not the extracted field).

Pairing rule (`synthesis.pairing`, rule `same_dataset`):
1. A measurement's place in the document is the start of its first `value` span (where the number is),
   not of its label or alias spans.
2. treatment and control are paired on the SAME dataset: the datasets are tried in the order they first
   appear (by value position), and the first one with both a treatment and a control measurement is
   used. Only when no dataset has both, a measurement without a dataset is paired with one that has one
   (or none).
3. Among several measurements of one condition on one metric and dataset, the `prefer` list decides:
   `table_cell` (a value in a Markdown table cell beats one in prose; abstracts and discussions may
   restate or misstate results) and `document_order` (the earlier one wins), applied in the order given.

Every evidence type is found by its pack role (`Types`, from pack.RoleMap): the compared thing (its side field
says treatment or control), the metric (its canonical field), the measured value (its links to the two, named in
the protocol's `links`) and the author claim (its direction field). No type or field name is written here.

The author claim is the document's first item of the claim type; it agrees with the data per
`rules.claim_agrees` through `synthesis.claim_map`. A document without a usable pair is `undetermined`
with a reason code and text and does not count; the label is `rules.label` of the counts by the
protocol's decision table. The reason codes double as the funnel's gaps (Part D, ours): `GAP_ROLES` names the roles of
the evidence types the engine escalates for each code, `study()` is the funnel's completeness check, and a
document the funnel screened out comes in with a pre-set `screened_out` reason and no items. Every study
also carries `funnel: {screened, stopped_after}` (`answer`).

Flags (the supervisor's synthesis step names them; shape ours, docs/evidence-system.md F1; protocol
`synthesis.flags`, definitions in evidence/rules.py), computed after every document's entry, over the
entries in manifest order:
- `duplicate`: `rules.duplicates` over the determined studies as (document, canonical metric, treatment
  value, control value); a later document with the key of an earlier one is a duplicate of that first
  document (`duplicate_of`). It keeps its direction and delta, but is listed under `duplicates` and counted
  in `counts.duplicates`, not under supporting/contradicting/neutral, and `rules.label` gets the counts
  without it. `flags.duplicates: false` switches this off (every study counts, no duplicate flags).
- `large_effect`: `rules.large_effects` over the deltas of the determined, non-duplicate studies with the
  protocol's `flags.large_effect.factor` and `min_studies` (and its `min_effect`, so a study the protocol
  calls neutral is left out of the median as it is left out of the direction). Reported only.
- `claim_disagrees`: `author_claim.agrees_with_data` is false (so never on an undetermined study, whose
  agreement is null). Reported only.
Every study carries `flags` (sorted, from rules.FLAGS) and `duplicate_of`; the answer carries
`duplicates` (the documents, manifest order) and `flags` (every flag name -> sorted documents).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import rules
from .contract import Item
from .pack import DEFAULT_CONTEXT_FIELD
from .protocol import Protocol, Synthesis
from .reasoner import Inferences, counts_as

if TYPE_CHECKING:
    from .pack import RoleMap

SYSTEM = "evidence-engine"
CELL_BEFORE = re.compile(r"\|[\s*_]*$")
CELL_AFTER = re.compile(r"^[^\n|]*\|")
# Why a document is undetermined: the code names the role whose evidence type the funnel escalates (Part D).
REASONS = {"screened_out": "screened out",
           "no_treatment_condition": "no {treatment} condition found",
           "no_control_condition": "no {control} condition found",
           "no_question_metric": "no metric of the question found",
           "no_pair": "no {treatment} and {control} measurement on a question metric"}
GAP_ROLES: dict[str, tuple[str, ...]] = {   # reason code -> pack roles (pack.Role values)
    "no_treatment_condition": ("compared_thing",), "no_control_condition": ("compared_thing",),
    "no_question_metric": ("metric",), "no_pair": ("measured_value",), "screened_out": ()}
SIDE_THING, SIDE_VALUE = rules.SIDE_THING, rules.SIDE_VALUE   # answer.json keys of a study side


@dataclass(frozen=True)
class Types:
    """The protocol's evidence types by role and the fields and links the rules read (pack.RoleMap): `thing` (the
    compared thing; `side` is its treatment/control field), `metric` (`canonical`), `value` (the measured value;
    `to_thing` and `to_metric` its links, `context` its field naming its dataset or population) and `claim`
    (`direction`); None where the protocol or pack has none."""
    thing: str | None
    side: str | None
    metric: str | None
    canonical: str | None
    value: str | None
    to_thing: str | None
    to_metric: str | None
    claim: str | None
    direction: str | None
    context: str = DEFAULT_CONTEXT_FIELD

    @classmethod
    def of(cls, protocol: Protocol, roles: RoleMap | None = None) -> Types:
        from .pack import Role
        roles = roles if roles is not None else protocol.roles()
        declared = protocol.evidence_types
        thing, metric, value, claim = (roles.type_in(r, declared)
                                       for r in (Role.COMPARED_THING, Role.METRIC, Role.VALUE, Role.CLAIM))
        links = dict(declared[value].links) if value is not None else {}

        def link(target: str | None) -> str | None:
            return next((name for name, t in links.items() if t == target), None)

        def field(etype: str | None, which: Any) -> str | None:
            return roles.field_or_none(etype, which) if etype is not None else None

        return cls(thing=thing, side=field(thing, "side"), metric=metric, canonical=field(metric, "canonical"),
                   value=value, to_thing=link(thing), to_metric=link(metric), claim=claim,
                   direction=field(claim, "direction"),
                   context=roles.context_field(value) if value is not None else cls.context)

    @staticmethod
    def of_type(items: list[Item], etype: str | None) -> list[Item]:
        return [i for i in items if etype is not None and i.evidence_type == etype]


def gap_types(protocol: Protocol, code: str, roles: RoleMap | None = None,
              table: dict[str, tuple[str, ...]] = GAP_ROLES) -> tuple[str, ...]:
    """The protocol's evidence types of the roles `table` names for reason code `code` (none for an unknown code)."""
    from .pack import Role
    roles = roles if roles is not None else protocol.roles()
    found = (roles.type_in(Role(r), protocol.evidence_types) for r in table.get(code, ()))
    return tuple(t for t in found if t is not None)


def reason(code: str, spec: Synthesis) -> dict[str, str]:
    return {"code": code, "text": REASONS[code].format(treatment=spec.compare.treatment, control=spec.compare.control)}


def value_start(m: Item) -> int:
    starts = [s.selector["start"] for s in m.spans if s.role == "value"]
    return min(starts) if starts else m.first_start()


def in_table(m: Item) -> bool:
    """The measurement's first value span sits in a Markdown table cell (a pipe before and after on its line)."""
    spans = sorted((s for s in m.spans if s.role == "value"), key=lambda s: s.selector["start"])
    return any(CELL_BEFORE.search(s.selector.get("prefix", "")) and CELL_AFTER.match(s.selector.get("suffix", ""))
               for s in spans)


def best_value(ms: list[Item], prefer: tuple[str, ...] | list[str]) -> Item:
    """Among several measurements of one condition (or method kind), the one the `prefer` list picks (Pairing)."""
    keys = {"table_cell": lambda m: not in_table(m), "document_order": value_start}
    return min(ms, key=lambda m: (*(keys[p](m) for p in prefer), m.item_id))


def _best(ms: list[Item], spec: Synthesis) -> Item:
    return best_value(ms, spec.pairing.prefer)


def _pair(treatment: list[Item], control: list[Item], spec: Synthesis,
          context: str = DEFAULT_CONTEXT_FIELD) -> tuple[Item, Item] | None:
    """`context`: the values' field naming their dataset (or population; Types.context)."""
    order: list[Any] = []
    for m in sorted(treatment + control, key=lambda m: (value_start(m), m.item_id)):
        if m.fields.get(context) not in order:
            order.append(m.fields.get(context))
    for dataset in order:  # the same dataset on both sides, first dataset in document order
        t = [m for m in treatment if m.fields.get(context) == dataset]
        c = [m for m in control if m.fields.get(context) == dataset]
        if t and c:
            return _best(t, spec), _best(c, spec)
    for dataset in order:  # fallback: one side names no dataset
        t = [m for m in treatment if m.fields.get(context) in (dataset, None)]
        c = [m for m in control if m.fields.get(context) in (dataset, None)]
        if t and c and (dataset is None or any(m.fields.get(context) is None for m in t + c)):
            return _best(t, spec), _best(c, spec)
    return None


def is_question_metric(canonical: Any, wanted: str, inferred: Inferences | None) -> bool:
    """Does a metric item's canonical name answer for question metric `wanted`: without the reasoner's inferences
    (`reason: off`, runs before it) only the same name; with them, also a narrower one (reasoner.counts_as)."""
    if inferred is None:
        return canonical == wanted
    return canonical is not None and counts_as(str(canonical), wanted, inferred)


def study(protocol: Protocol, document: str, items: list[Item], preset: dict[str, str] | None = None, *,
          roles: RoleMap | None = None, inferred: Inferences | None = None) -> tuple[dict[str, Any], list[str]]:
    """One document's entry and the item ids it rests on; `roles` is the protocol's pack by role (None: the
    protocol's own, `Protocol.roles`); `inferred` the run's reasoner inferences (a narrower metric answers a broader
    question metric, which the entry then names).

    `preset` is a pre-set reason `{code, text}` for a document the funnel did not extract from (screened out,
    Part D): the entry is undetermined with that reason, whatever `items` holds (the engine passes none)."""
    spec = protocol.synthesis
    assert spec is not None, "an effect or consistency protocol has a synthesis block"
    ty = Types.of(protocol, roles)
    by_id = {i.item_id: i for i in items}
    things, metrics, values, claims = (ty.of_type(items, t) for t in (ty.thing, ty.metric, ty.value, ty.claim))
    claim = claims[0] if claims else None
    entry: dict[str, Any] = {"document": document, "direction": "undetermined", "delta": None, "metric": None,
                             "treatment": None, "control": None, "author_claim": None, "reason": None,
                             "flags": [], "duplicate_of": None}
    used: list[str] = []
    if preset is not None:
        entry["reason"] = dict(preset)
        return entry, used
    side, canonical, to_thing, to_metric = ty.side or "", ty.canonical or "", ty.to_thing or "", ty.to_metric or ""
    sides = {c.fields.get(side) for c in things}
    question = [(name, m) for name in spec.metric_names for m in metrics
                if is_question_metric(m.fields.get(canonical), name, inferred)]
    pair, wanted = None, None
    for wanted, metric in question:
        on = [m for m in values if m.links.get(to_metric) == metric.item_id]

        def side_of(m: Item) -> Any:
            thing = by_id.get(m.links.get(to_thing, ""))
            return thing.fields.get(side) if thing else None

        pair = _pair([m for m in on if side_of(m) == spec.compare.treatment],
                     [m for m in on if side_of(m) == spec.compare.control], spec, ty.context)
        if pair:
            break
    if pair is None:
        if spec.compare.treatment not in sides:
            entry["reason"] = reason("no_treatment_condition", spec)
        elif spec.compare.control not in sides:
            entry["reason"] = reason("no_control_condition", spec)
        elif not question:
            entry["reason"] = reason("no_question_metric", spec)
        else:
            entry["reason"] = reason("no_pair", spec)
    else:
        t, c = pair
        name = wanted   # the question metric the pair's metric answers for (its own canonical name without inferences)
        direction, delta = rules.effect(float(t.fields["value"]), float(c.fields["value"]),
                                        spec.higher_is_better(name), spec.min_effect)
        entry.update(direction=direction, delta=delta, metric=name,
                     treatment={SIDE_THING: t.links[to_thing], SIDE_VALUE: t.item_id, "value": t.fields["value"]},
                     control={SIDE_THING: c.links[to_thing], SIDE_VALUE: c.item_id, "value": c.fields["value"]})
        used += [t.item_id, c.item_id, t.links[to_thing], c.links[to_thing], t.links[to_metric]]
    if claim is not None:
        determined = entry["direction"] != "undetermined"
        said = claim.fields[ty.direction or ""]
        entry["author_claim"] = {"item": claim.item_id, "direction": said,
                                 "agrees_with_data": rules.claim_agrees(said, entry["direction"], spec.claim_map)
                                 if determined else None}
        used.append(claim.item_id)
    return entry, used


def flag(protocol: Protocol, studies: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Fills `flags` and `duplicate_of` of the entries (manifest order) in place; returns flag -> documents."""
    spec = protocol.synthesis
    settings = spec.flags
    determined = [s for s in studies if s["direction"] != "undetermined"]
    duplicate_of = (rules.duplicates((s["document"], s["metric"], s["treatment"]["value"], s["control"]["value"])
                                     for s in determined) if settings.duplicates else {})
    large = rules.large_effects({s["document"]: s["delta"] for s in determined if s["document"] not in duplicate_of},
                                settings.large_effect.factor, settings.large_effect.min_studies, spec.min_effect)
    found: dict[str, list[str]] = {name: [] for name in rules.FLAGS}
    for s in studies:
        doc = s["document"]
        s["duplicate_of"] = duplicate_of.get(doc)
        flags = set()
        if doc in duplicate_of:
            flags.add("duplicate")
        if doc in large:
            flags.add("large_effect")
        if s["author_claim"] is not None and s["author_claim"]["agrees_with_data"] is False:
            flags.add("claim_disagrees")
        s["flags"] = sorted(flags)
        for name in s["flags"]:
            found[name].append(doc)
    return found                      # documents in manifest order, like `duplicates` and the groups


NO_FUNNEL = {"screened": False, "stopped_after": None}   # a study's `funnel` when the funnel made no decision


def answer(protocol: Protocol, documents: list[str], items: dict[str, list[Item]],
           reasons: dict[str, dict[str, str]] | None = None,
           funnel: dict[str, dict[str, Any]] | None = None, *,
           roles: RoleMap | None = None, inferred: Inferences | None = None) -> tuple[dict[str, Any], list[str]]:
    """answer.json and the ids of every item it rests on (a duplicate's items included: they are evidence
    the answer reports, even though the duplicate is not counted).

    `reasons`: document -> a pre-set reason (`study`); `funnel`: document -> `{screened, stopped_after}`
    (Part D): `screened` is true when the screen decided the paper is not relevant, `stopped_after` the
    cascade position after which the funnel stopped because the study was complete (null in `all` mode,
    for a screened-out document, and when the gap types' cascades were exhausted). Every study carries
    the key (`NO_FUNNEL` when the engine gives nothing), so the shape does not depend on the strategy."""
    studies, used = [], []
    roles = roles if roles is not None else protocol.roles()
    for doc in documents:
        entry, ids = study(protocol, doc, items.get(doc, []), (reasons or {}).get(doc), roles=roles, inferred=inferred)
        entry["funnel"] = dict((funnel or {}).get(doc) or NO_FUNNEL)
        studies.append(entry)
        used += ids
    flags = flag(protocol, studies)
    groups = {k: [s["document"] for s in studies if s["direction"] == d and s["duplicate_of"] is None]
              for k, d in (("supporting", "supports"), ("contradicting", "contradicts"), ("neutral", "neutral"),
                           ("undetermined", "undetermined"))}
    groups["duplicates"] = [s["document"] for s in studies if s["duplicate_of"] is not None]
    counts = {k: len(v) for k, v in groups.items()}
    label = rules.label(counts, protocol.synthesis.table)   # the table reads supporting/contradicting/neutral only
    out = {"system": SYSTEM, "question": protocol.question, "label": label, "counts": counts, "studies": studies,
           **groups, "flags": flags}
    return out, used
