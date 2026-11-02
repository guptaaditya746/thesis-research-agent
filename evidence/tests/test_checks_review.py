"""Central checks after review (findings 3, 4, 7, 9, 11): number cuts on exact offsets, span roles, optional
spans out of scope, colliding item ids, value bounds of question metrics."""
from __future__ import annotations

import hashlib

from agent.anchor import Index, selector_at
from evidence import checks, merge, protocol
from evidence.contract import (DocumentRef, ExtractionResult, ExtractionTask, Item, ProtocolRef, Scope, Span)

from .conftest import PROTOCOL

PROTO = protocol.load(PROTOCOL)
TEXT = ("## Method\n\nWe compare a closed-book baseline (B) with its retrieval-augmented variant (R).\n\n"
        "## Results\n\nThe retrieval-augmented model reaches 62.0% answer accuracy and a latency of 410 ms.\n")
SHA = hashlib.sha256(TEXT.encode()).hexdigest()
DOC = DocumentRef(id="D", file="papers/D.md", sha256=SHA)


def task(evidence_type: str, scope: Scope = Scope(), context: tuple[str, ...] = ()) -> ExtractionTask:
    return ExtractionTask(protocol=ProtocolRef(id=PROTO.id, sha256=PROTO.sha256), evidence_type=evidence_type,  # type: ignore[arg-type]
                          field_schema_sha256=PROTO.evidence_types[evidence_type].schema_sha256, document=DOC,
                          scope=scope, context=context)


def span(quote: str, role: str, offset: int = 0) -> Span:
    at = TEXT.index(quote) + offset
    return Span.of(role, selector_at(TEXT, at, at + len(quote) - offset, file=DOC.file, sha256=SHA))


RAG = Item.build("condition", {"label": "retrieval-augmented model", "role": "rag"},
                 [span("retrieval-augmented model", "condition_label")])
ACC = Item.build("metric", {"name": "answer accuracy", "canonical": "factual_accuracy", "higher_is_better": True},
                 [span("answer accuracy", "metric_label")])
LAT = Item.build("metric", {"name": "latency", "canonical": "other", "higher_is_better": False},
                 [span("latency", "metric_label")])
CONTEXT = {i.item_id: i for i in (RAG, ACC, LAT)}


def measurement(value: float, spans: list[Span], metric: Item = ACC) -> Item:
    return Item.build("measurement", {"value": value, "dataset": None}, spans,
                      links={"condition": RAG.item_id, "metric": metric.item_id})


def check(items: list[Item], scope: Scope = Scope()) -> ExtractionResult:
    t = task("measurement", scope, tuple(CONTEXT))
    result = ExtractionResult(extractor_id="x@1#0", task_sha256=t.task_sha256, status="ok", items=tuple(items))
    return checks.check(result, t, Index(TEXT), PROTO.evidence_types["measurement"], CONTEXT)


def test_a_span_cutting_a_number_is_rejected_even_at_exact_offsets() -> None:
    at = TEXT.index("62.0") + 1
    cut = Span.of("value", selector_at(TEXT, at, at + 1, file=DOC.file, sha256=SHA))      # "2" of "62.0"
    result = check([measurement(0.02, [cut])])
    assert not result.items and [r.reason for r in result.rejected] == ["partial_number"]


def test_span_roles_are_enforced() -> None:
    no_value = measurement(0.62, [span("retrieval-augmented model", "condition_label")])
    odd_role = measurement(0.62, [span("62.0%", "value"), span("We compare", "whatever")])
    result = check([no_value, odd_role])
    assert not result.items and [r.reason for r in result.rejected] == ["schema", "schema"]


def test_optional_span_out_of_scope_is_dropped_and_noted() -> None:
    results = TEXT.index("## Results")
    scope = Scope(kind="ranges", ranges=((results, len(TEXT)),))
    item = measurement(0.62, [span("62.0%", "value"), span("retrieval-augmented variant (R)", "condition_label")])
    result = check([item], scope)
    assert [[s.role for s in i.spans] for i in result.items] == [["value"]]
    assert [(r.reason, "optional" in r.detail) for r in result.rejected] == [("out_of_scope", True)]
    outside = measurement(0.62, [span("closed-book baseline", "value")])
    assert [r.reason for r in check([outside], scope).rejected] == ["out_of_scope"]


def test_colliding_item_ids_are_rejected_not_dropped() -> None:
    a = measurement(0.62, [span("62.0%", "value")])
    b = Item.build("measurement", {"value": 0.62, "dataset": None}, [span("62.0%", "value")],
                   links={"condition": RAG.item_id, "metric": LAT.item_id})
    assert a.item_id == b.item_id
    result = check([a, b, a])
    assert not result.items and [r.reason for r in result.rejected] == ["ambiguous", "ambiguous"]
    one = check([a, a])
    assert len(one.items) == 1 and not one.rejected     # an exact duplicate is one item


def test_merge_reports_colliding_ids() -> None:
    a = measurement(0.62, [span("62.0%", "value")])
    b = a.model_copy(update={"links": {"condition": RAG.item_id, "metric": LAT.item_id}})
    r1 = ExtractionResult(extractor_id="x@1#0", task_sha256="t", status="ok", items=(a,))
    r2 = ExtractionResult(extractor_id="y@1#0", task_sha256="t", status="ok", items=(b,))
    items, _, collisions = merge.merge([("t1", r1), ("t2", r2)], PROTO.evidence_types["measurement"])
    assert not items and collisions[0]["item_id"] == a.item_id and collisions[0]["calls"] == ["t1", "t2"]


def test_question_metric_values_must_be_fractions() -> None:
    result = check([measurement(62.0, [span("62.0%", "value")]), measurement(410.0, [span("410", "value")], LAT)])
    assert [i.fields["value"] for i in result.items] == [410.0]
    assert [r.reason for r in result.rejected] == ["schema"] and "[0, 1]" in result.rejected[0].detail


def test_merge_ignores_a_differing_form() -> None:
    # `form` describes how a number was written (D35): "62.0%" read as percent and as plain by two extractors is
    # one value; the first non-null form wins
    pct = Item.build("measurement", {"value": 0.62, "dataset": None, "form": "percent"}, [span("62.0%", "value")],
                     links={"condition": RAG.item_id, "metric": ACC.item_id})
    plain = Item.build("measurement", {"value": 0.62, "dataset": None, "form": "plain"}, [span("62.0", "value")],
                       links={"condition": RAG.item_id, "metric": ACC.item_id})
    r1 = ExtractionResult(extractor_id="x@1#0", task_sha256="t", status="ok", items=(pct,))
    r2 = ExtractionResult(extractor_id="y@1#0", task_sha256="t", status="ok", items=(plain,))
    [item], sources, collisions = merge.merge([("t1", r1), ("t2", r2)], PROTO.evidence_types["measurement"],
                                              descriptive=merge.descriptive("measurement", PROTO.roles()))
    assert item.fields["form"] == "percent" and not collisions and sources[item.item_id] == ["t1", "t2"]
    assert sorted(s.selector["exact"] for s in item.spans) == ["62.0", "62.0%"]


def test_form_is_descriptive_only_on_the_measured_value_type() -> None:
    # a pack field named `form` on another type (here the compared thing) is a real field: two items that differ in
    # it stay two items; only the measured-value type's `form` (how the number was written) is ignored
    roles = PROTO.roles()
    assert merge.descriptive("measurement", roles) == merge.DESCRIPTIVE
    assert merge.descriptive("condition", roles) == frozenset()
    spec = PROTO.evidence_types["condition"].model_copy(update={"merge_key": None})
    a = Item.build("condition", {"label": "RAG", "role": "rag", "form": "tablet"},
                   [span("retrieval-augmented model", "condition_label")])
    b = Item.build("condition", {"label": "RAG", "role": "rag", "form": "injection"},
                   [span("retrieval-augmented model", "condition_label")])
    r1 = ExtractionResult(extractor_id="x@1#0", task_sha256="t", status="ok", items=(a,))
    r2 = ExtractionResult(extractor_id="y@1#0", task_sha256="t", status="ok", items=(b,))
    descriptive = merge.descriptive("condition", roles)
    assert len(merge.merge([("t1", r1), ("t2", r2)], spec, descriptive=descriptive)[0]) == 2
