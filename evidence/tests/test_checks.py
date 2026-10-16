"""The engine's central checks (contract R1-R3, R7) on results an extractor might return, and the protocol."""
from __future__ import annotations


import pytest
import yaml

from agent.anchor import Index, selector_at, text_sha256
from evidence import checks, protocol
from evidence.contract import (DocumentRef, ExtractionResult, ExtractionTask, Item, ProtocolRef, Rejected, Scope,
                               Span)

from .conftest import PAPERS, PROTOCOL

TEXT = (PAPERS / "S001.md").read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
DOC = DocumentRef(id="S001", file="papers/S001.md", sha256=text_sha256(TEXT))
PROTO = protocol.load(PROTOCOL)


def task(evidence_type: str = "condition", scope: Scope = Scope(), context: tuple[str, ...] = ()) -> ExtractionTask:
    spec = PROTO.evidence_types[evidence_type]
    return ExtractionTask(protocol=ProtocolRef(id=PROTO.id, sha256=PROTO.sha256), evidence_type=evidence_type,  # type: ignore[arg-type]
                          field_schema_sha256=spec.schema_sha256, document=DOC, scope=scope, context=context)


def span_of(quote: str, role: str = "condition_label", start: int | None = None) -> Span:
    at = TEXT.index(quote) if start is None else start
    return Span.of(role, selector_at(TEXT, at, at + len(quote), file=DOC.file, sha256=DOC.sha256))


def condition(spans: list[Span], **fields) -> Item:
    return Item.build("condition", {"label": "closed-book model", "role": "baseline", **fields}, spans)


def run_check(items: list[Item], t: ExtractionTask, context: dict[str, Item] | None = None) -> ExtractionResult:
    result = ExtractionResult(extractor_id="x@1#0", task_sha256=t.task_sha256, status="ok", items=tuple(items))
    return checks.check(result, t, Index(TEXT), PROTO.evidence_types[t.evidence_type], context or {})


def reasons(result: ExtractionResult) -> list[str]:
    return [r.reason for r in result.rejected]


def test_a_checked_span_passes() -> None:
    result = run_check([condition([span_of("closed-book model")])], task())
    assert len(result.items) == 1 and not result.rejected


def test_fabricated_quote_is_rejected_not_found() -> None:
    fake = Span(role="condition_label", selector={**span_of("closed-book model").selector,
                                                  "exact": "a model that never appears in the paper", "start": 5, "end": 9})
    result = run_check([condition([fake])], task())
    assert not result.items and reasons(result) == ["not_found"]
    assert result.rejected[0].quotes == ("a model that never appears in the paper",)


def test_span_of_another_document_is_rejected() -> None:
    other = Span(role="condition_label", selector={**span_of("closed-book model").selector, "sha256": "f" * 64})
    assert reasons(run_check([condition([other])], task())) == ["not_found"]


def test_wrong_offsets_are_re_anchored_by_quote() -> None:
    good = span_of("Retrieval augmentation improves answer accuracy")
    moved = Span(role="condition_label", selector={**good.selector, "start": 0, "end": 10})
    result = run_check([condition([moved])], task())
    assert result.items[0].spans[0].selector["start"] == good.selector["start"]


def test_ambiguous_retyped_quote_is_rejected() -> None:
    first = span_of("retrieval-augmented model")
    retyped = Span(role="condition_label", selector={**first.selector, "start": 0, "end": 3, "prefix": "", "suffix": ""})
    assert reasons(run_check([condition([retyped])], task())) == ["ambiguous"]


def test_span_out_of_scope_is_rejected() -> None:
    at = TEXT.index("## Results")
    result = run_check([condition([span_of("closed-book model")])], task(scope=Scope(kind="ranges", ranges=((at, len(TEXT)),))))
    assert not result.items and reasons(result) == ["out_of_scope"]


def test_fields_failing_the_schema_are_rejected() -> None:
    result = run_check([condition([span_of("closed-book model")], role="oracle")], task())
    assert reasons(result) == ["schema"] and "oracle" in result.rejected[0].detail


def test_links_must_point_to_context_items() -> None:
    cond = condition([span_of("closed-book model")])
    metric = Item.build("metric", {"name": "answer accuracy", "canonical": "factual_accuracy", "higher_is_better": True},
                        [span_of("answer accuracy", "metric_label")])
    value = span_of("62%", "value")
    good = Item.build("measurement", {"value": 0.62, "dataset": None}, [value],
                      links={"condition": cond.item_id, "metric": metric.item_id})
    dangling = Item.build("measurement", {"value": 0.71, "dataset": None}, [span_of("71%", "value")],
                          links={"condition": "c-unknown", "metric": metric.item_id})
    wrong_type = Item.build("measurement", {"value": 0.62, "dataset": None}, [span_of("62.0", "value")],
                            links={"condition": metric.item_id, "metric": metric.item_id})
    context = {cond.item_id: cond, metric.item_id: metric}
    t = task("measurement", context=tuple(context))
    result = run_check([good, dangling, wrong_type], t, context)
    assert [i.item_id for i in result.items] == [good.item_id]
    assert reasons(result) == ["dangling_link", "dangling_link"]


def test_result_is_canonical_whatever_the_order() -> None:
    a, b = condition([span_of("closed-book model")]), condition([span_of("Closed-book model")], label="Closed-book model")
    one, two = run_check([a, b], task()), run_check([b, a], task())
    assert one.output_sha256 == two.output_sha256
    assert [i.first_start() for i in one.items] == sorted(i.first_start() for i in one.items)


def test_protocol_hash_ignores_layout_and_phases_follow_context() -> None:
    data = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    reordered = protocol.parse(yaml.safe_dump(dict(reversed(list(data.items()))), sort_keys=True))
    assert reordered.sha256 == PROTO.sha256
    assert PROTO.phases() == ["condition", "metric", "measurement", "author_claim"]
    data["evidence_types"]["measurement"]["context"] = ["condition"]
    with pytest.raises(ValueError, match="does not list it as context"):
        protocol.Protocol.model_validate(data)
    data = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    data["synthesis"]["metrics"] = [{"canonical": "bleu", "higher_is_better": True}]
    with pytest.raises(ValueError, match="metric.canonical does not allow"):
        protocol.Protocol.model_validate(data)
    data = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    data["synthesis"]["label"] = [{"when": {"supporting": ">0"}, "then": "supported"}]
    with pytest.raises(ValueError, match="last row must have no"):
        protocol.Protocol.model_validate(data)
    data["synthesis"]["label"] = [{"when": {"wins": ">0"}, "then": "supported"}, {"then": "insufficient"}]
    with pytest.raises(ValueError, match="unknown counts"):
        protocol.Protocol.model_validate(data)
    data["synthesis"]["label"] = [{"when": {"supporting": "lots"}, "then": "supported"}, {"then": "insufficient"}]
    with pytest.raises(ValueError, match="<op><int>"):
        protocol.Protocol.model_validate(data)
    data = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    data["synthesis"]["compare"] = {"treatment": "rag", "control": "rag"}
    with pytest.raises(ValueError, match="different roles"):
        protocol.Protocol.model_validate(data)


def test_rejected_reasons_are_the_contract_ones() -> None:
    with pytest.raises(ValueError):
        Rejected(evidence_type="condition", fields={}, reason="made_up")  # type: ignore[arg-type]
