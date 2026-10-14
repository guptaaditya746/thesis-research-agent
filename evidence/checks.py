"""The engine's checks of every result, whatever the extractor returned (contract rules R1-R3, R7).

R1: every span is re-anchored against the document text: the selector's file and sha256 must be the
task's document, and its offsets must hold its exact text; failing that the exact text is searched again
(agent/anchor.find, ties broken by prefix and suffix) and the span moves to where it is found. An item
with at least one span that cannot be anchored is rejected with the anchor's reason.
R2: fields validate against the evidence type's JSON schema (jsonschema), links name exactly the declared
links and point to context items or items of this result, of the declared type.
R3: every span lies inside the task's scope.
Item ids are recomputed from the checked fields and spans, and the result is put in canonical order (R7).
Rejected items keep their reason; nothing is dropped silently.
"""
from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from agent.anchor import AnchorError, Index, find, selector_at

from .contract import ExtractionResult, ExtractionTask, Item, Rejected, Span
from .protocol import EvidenceTypeSpec


def _reject(item: Item, reason: str, detail: str) -> Rejected:
    return Rejected(evidence_type=item.evidence_type, fields=item.fields,
                    quotes=tuple(str(s.selector.get("exact", "")) for s in item.spans),
                    reason=reason, detail=detail[:300])  # type: ignore[arg-type]


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
        found = selector_at(text, start, end, file=task.document.file, sha256=index.sha256)
    else:
        found = find(index, exact, file=task.document.file, prefix=str(sel.get("prefix", "")),
                     suffix=str(sel.get("suffix", "")))
    return Span.of(span.role, found)


def check(result: ExtractionResult, task: ExtractionTask, index: Index, spec: EvidenceTypeSpec,
          context: dict[str, Item]) -> ExtractionResult:
    """The result with every item checked; failing items moved to `rejected` with their reason."""
    validator = Draft202012Validator(spec.fields)
    kept: list[Item] = []
    rejected = list(result.rejected)
    for item in result.items:
        if item.evidence_type != task.evidence_type:
            rejected.append(_reject(item, "schema", f"evidence type {item.evidence_type}, task asks for {task.evidence_type}"))
            continue
        errors = sorted(e.message for e in validator.iter_errors(item.fields))
        if errors:
            rejected.append(_reject(item, "schema", "; ".join(errors)))
            continue
        try:
            spans = [anchor_span(s, task, index) for s in item.spans]
        except AnchorError as exc:
            rejected.append(_reject(item, exc.reason, str(exc)))
            continue
        outside = [s for s in spans if not task.scope.contains(s.selector["start"], s.selector["end"])]
        if outside:
            where = ", ".join(f"[{s.selector['start']}, {s.selector['end']})" for s in outside)
            rejected.append(_reject(item, "out_of_scope", f"span {where} outside the task's scope"))
            continue
        kept.append(Item.build(item.evidence_type, dict(item.fields), spans, links=dict(item.links),
                               confidence=item.confidence))
    known = {**{i.item_id: i.evidence_type for i in context.values()}, **{i.item_id: i.evidence_type for i in kept}}
    linked: list[Item] = []
    for item in kept:
        problem = _link_problem(item, spec, known)
        if problem:
            rejected.append(_reject(item, "dangling_link", problem))
        else:
            linked.append(item)
    unique = {i.item_id: i for i in linked}
    return result.model_copy(update={"items": tuple(unique.values()), "rejected": tuple(rejected)}).canonical()


def _link_problem(item: Item, spec: EvidenceTypeSpec, known: dict[str, Any]) -> str:
    if set(item.links) != set(spec.links):
        return f"links {sorted(item.links)}, the evidence type declares {sorted(spec.links)}"
    for name, target in item.links.items():
        if known.get(target) != spec.links[name]:
            return f"{name} -> {target} is not a {spec.links[name]} of the context or of this result"
    return ""
