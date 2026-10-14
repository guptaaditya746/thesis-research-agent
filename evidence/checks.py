"""The engine's checks of every result, whatever the extractor returned (contract rules R1-R3, R7).

R1: every span is re-anchored against the document text: the selector's file and sha256 must be the
task's document, and its offsets must hold its exact text without cutting a number (as agent/anchor.py
demands of a found quote: "2" inside "62.0" is partial_number); failing the offsets, the exact text is
searched again (agent/anchor.find, ties broken by prefix and suffix) and the span moves to where it is
found. An item with a span that cannot be anchored is rejected with the anchor's reason.
R2: fields validate against the evidence type's JSON schema (jsonschema) and its `bounds` (a question
metric's value is a fraction in [0, 1]); span roles are the type's declared roles and the first (required)
role is present; links name exactly the declared links and point to context items or items of this
result, of the declared type. Failures are rejected with reason schema or dangling_link.
R3: spans lie inside the task's scope. A span of an optional role outside the scope is dropped and noted
in `rejected` (reason out_of_scope, the item kept) as long as a span of the required role is inside;
otherwise the item is rejected.
Item ids are recomputed from the checked fields and spans. Two different items with one id (same fields
and spans, different links) are both rejected as ambiguous; an exact duplicate is kept once. The result is
put in canonical order (R7). Nothing is dropped silently.
"""
from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from agent.anchor import DASHES, AnchorError, Index, find, selector_at

from .contract import ExtractionResult, ExtractionTask, Item, Rejected, Span
from .protocol import Bound, EvidenceTypeSpec


def _reject(item: Item, reason: str, detail: str, spans: tuple[Span, ...] | None = None) -> Rejected:
    return Rejected(evidence_type=item.evidence_type, fields=item.fields,
                    quotes=tuple(str(s.selector.get("exact", "")) for s in (item.spans if spans is None else spans)),
                    reason=reason, detail=detail[:300])  # type: ignore[arg-type]


def cuts_number(text: str, start: int, end: int) -> bool:
    """text[start:end] starts or ends inside a number, or leaves out the minus sign touching it."""
    first, last = text[start], text[end - 1]
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    if first.isdigit() and (before.isdigit() or before in DASHES
                            or (before == "." and start > 1 and text[start - 2].isdigit())):
        return True
    if first == "." and before.isdigit():
        return True
    return last.isdigit() and (after.isdigit() or (after == "." and end + 1 < len(text) and text[end + 1].isdigit()))


def anchor_span(span: Span, task: ExtractionTask, index: Index) -> Span:
    """The span re-anchored in the document; raises AnchorError(reason) when it cannot be."""
    sel = span.selector
    if sel.get("file") != task.document.file or sel.get("sha256") != task.document.sha256:
        raise AnchorError("not_found", f"the selector names {sel.get('file')}@{str(sel.get('sha256'))[:12]}, "
                                       f"not the task's document {task.document.file}@{task.document.sha256[:12]}")
    exact = sel.get("exact")
    if not isinstance(exact, str) or not exact.strip():
        raise AnchorError("empty_quote", "the span has no exact text")
    start, end = sel.get("start"), sel.get("end")
    text = index.text
    if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text) and text[start:end] == exact:
        if cuts_number(text, start, end):
            raise AnchorError("partial_number", f"[{start}, {end}) {exact!r} cuts a number or drops its sign")
        found = selector_at(text, start, end, file=task.document.file, sha256=index.sha256)
    else:
        found = find(index, exact, file=task.document.file, prefix=str(sel.get("prefix", "")),
                     suffix=str(sel.get("suffix", "")))
    return Span.of(span.role, found)


def _bound_problem(item: Item, bound: Bound, known: dict[str, Item]) -> str:
    if bound.when is not None:
        linked = known.get(item.links.get(bound.when.link, ""))
        if linked is None or linked.fields.get(bound.when.field) not in bound.when.values:
            return ""
    value = item.fields.get(bound.field)
    if not isinstance(value, (int, float)):
        return ""
    low = bound.min if bound.min is not None else float("-inf")
    high = bound.max if bound.max is not None else float("inf")
    if low <= value <= high:
        return ""
    when = f" for {bound.when.field} in {list(bound.when.values)}" if bound.when else ""
    return f"{bound.field}={value:g} outside [{low:g}, {high:g}]{when}"


def _one(item: Item, task: ExtractionTask, index: Index, spec: EvidenceTypeSpec, validator: Draft202012Validator,
         notes: list[Rejected]) -> Item | Rejected:
    """The checked item (notes get dropped optional spans), or its rejection."""
    if item.evidence_type != task.evidence_type:
        return _reject(item, "schema", f"evidence type {item.evidence_type}, task asks for {task.evidence_type}")
    errors = sorted(e.message for e in validator.iter_errors(item.fields))
    if errors:
        return _reject(item, "schema", "; ".join(errors))
    roles = [s.role for s in item.spans]
    undeclared = sorted(set(roles) - set(spec.roles))
    if undeclared or spec.roles[0] not in roles:
        return _reject(item, "schema", f"span roles {sorted(set(roles))}: undeclared {undeclared}"
                                       if undeclared else f"no span of the required role {spec.roles[0]}")
    try:
        spans = [anchor_span(s, task, index) for s in item.spans]
    except AnchorError as exc:
        return _reject(item, exc.reason, str(exc))
    inside = [s for s in spans if task.scope.contains(s.selector["start"], s.selector["end"])]
    outside = tuple(s for s in spans if s not in inside)
    if outside:
        where = ", ".join(f"{s.role} [{s.selector['start']}, {s.selector['end']})" for s in outside)
        if not any(s.role == spec.roles[0] for s in inside):
            return _reject(item, "out_of_scope", f"span {where} outside the task's scope")
        notes.append(_reject(item, "out_of_scope", f"optional span {where} outside the scope dropped; item kept",
                             outside))
    return Item.build(item.evidence_type, dict(item.fields), inside, links=dict(item.links), confidence=item.confidence)


def check(result: ExtractionResult, task: ExtractionTask, index: Index, spec: EvidenceTypeSpec,
          context: dict[str, Item]) -> ExtractionResult:
    """The result with every item checked; failing items moved to `rejected` with their reason."""
    validator = Draft202012Validator(spec.fields)
    kept: list[Item] = []
    rejected = list(result.rejected)
    for item in result.items:
        notes: list[Rejected] = []
        checked = _one(item, task, index, spec, validator, notes)
        if isinstance(checked, Rejected):
            rejected.append(checked)
        else:
            kept.append(checked)
            rejected.extend(notes)
    by_id: dict[str, list[Item]] = {}
    for item in kept:
        if all(item != other for other in by_id.get(item.item_id, [])):
            by_id.setdefault(item.item_id, []).append(item)
    unique: list[Item] = []
    for same in by_id.values():
        if len(same) == 1:
            unique.append(same[0])
        else:
            rejected += [_reject(i, "ambiguous", f"item id {i.item_id} also names an item with other links "
                                                 f"({len(same)} items, same fields and spans)") for i in same]
    known = {**context, **{i.item_id: i for i in unique}}
    final: list[Item] = []
    for item in unique:
        problem = _link_problem(item, spec, known)
        bound = next((p for b in spec.bounds if (p := _bound_problem(item, b, known))), "")
        if problem:
            rejected.append(_reject(item, "dangling_link", problem))
        elif bound:
            rejected.append(_reject(item, "schema", bound))
        else:
            final.append(item)
    return result.model_copy(update={"items": tuple(final), "rejected": tuple(rejected)}).canonical()


def _link_problem(item: Item, spec: EvidenceTypeSpec, known: dict[str, Any]) -> str:
    if set(item.links) != set(spec.links):
        return f"links {sorted(item.links)}, the evidence type declares {sorted(spec.links)}"
    for name, target in item.links.items():
        linked = known.get(target)
        if linked is None or linked.evidence_type != spec.links[name]:
            return f"{name} -> {target} is not a {spec.links[name]} of the context or of this result"
    return ""
