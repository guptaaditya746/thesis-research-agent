"""R8, the value check: a measured value must be written in its span or table cell; a value from a cell the two PDF
table readers disagreed on is kept and marked."""
from __future__ import annotations

from agent.anchor import Index, selector_at, text_sha256
from evidence import checks, protocol
from evidence.contract import DocumentRef, ExtractionResult, ExtractionTask, Item, ProtocolRef, Scope, Span

from .conftest import PROTOCOL

TEXT = ("The closed-book model reaches answer accuracy of 62% here.\n\n"
        "| System | answer accuracy |\n| --- | --- |\n| closed-book model | 61.2 |\n| other | 74.5 |\n"
        "<!-- table unsure: 2,1 -->\n")
DOC = DocumentRef(id="P", file="papers/P.md", sha256=text_sha256(TEXT))
PROTO = protocol.load(PROTOCOL)


def span_of(quote: str, role: str) -> Span:
    at = TEXT.index(quote)
    return Span.of(role, selector_at(TEXT, at, at + len(quote), file=DOC.file, sha256=DOC.sha256))


COND = Item.build("condition", {"label": "closed-book model", "role": "baseline"}, [span_of("closed-book model", "condition_label")])
METRIC = Item.build("metric", {"name": "answer accuracy", "canonical": "factual_accuracy", "higher_is_better": True},
                    [span_of("answer accuracy", "metric_label")])
LINKS = {"condition": COND.item_id, "metric": METRIC.item_id}


def value(number: float, quote: str) -> Item:
    return Item.build("measurement", {"value": number, "dataset": None}, [span_of(quote, "value")], links=LINKS)


def run(items: list[Item]) -> ExtractionResult:
    context = {COND.item_id: COND, METRIC.item_id: METRIC}
    spec = PROTO.evidence_types["measurement"]
    t = ExtractionTask(protocol=ProtocolRef(id=PROTO.id, sha256=PROTO.sha256), evidence_type="measurement",  # type: ignore[arg-type]
                       field_schema_sha256=spec.schema_sha256, document=DOC, scope=Scope(), context=tuple(context))
    result = ExtractionResult(extractor_id="x@1#0", task_sha256=t.task_sha256, status="ok", items=tuple(items))
    return checks.check(result, t, Index(TEXT), spec, context)


def test_value_not_in_cell_dropped() -> None:
    wrong_number = value(0.99, "61.2")           # 0.99 / 99 is not what the cell says
    wrong_cell = value(0.62, "closed-book model")   # a table cell with no number in it
    good = value(0.612, "61.2")                  # a percentage written as a fraction
    prose = value(0.62, "62%")
    result = run([wrong_number, wrong_cell, good, prose])
    assert sorted(i.fields["value"] for i in result.items) == [0.612, 0.62]
    assert sorted(r.reason for r in result.rejected) == ["not_found", "not_found"]
    assert all("table_unsure" not in i.fields for i in result.items)


def test_unsure_value_kept_and_marked() -> None:
    [kept] = run([value(0.745, "74.5")]).items
    assert kept.fields["table_unsure"] is True and kept.fields["value"] == 0.745
    [plain] = run([value(0.612, "61.2")]).items
    assert "table_unsure" not in plain.fields
