"""number_measurement (Part C, number-first search): every number in scope becomes a measurement when a
condition and a metric resolve around it (table cell: row label and column header; sentence: the nearest
labels), with guards against deltas, ranges, years, section numbers, counts and "% of" shares."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.anchor import Index, text_sha256
from evidence import engine, protocol
from evidence.contract import DocumentRef, ExtractionTask, Item, ProtocolRef, Span
from evidence.extractors import base, get, numbers

from .conftest import PROTOCOL, corpus_of, pack_words

PROTO = protocol.load(PROTOCOL)
SPAN = Span(role="label", selector={"file": "papers/X.md", "start": 0, "end": 1, "exact": "X"})
LATENCY = PROTOCOL.parent / "rag-latency.yaml"
WORDS = pack_words("number_measurement", "measurement")
EFFECT = {"question_metrics": ["factual_accuracy"], "compare": {"treatment": "rag", "control": "baseline"}}

RAG = Item.build("condition", {"label": "retrieval-augmented model", "role": "rag"}, [SPAN])
CB = Item.build("condition", {"label": "closed-book model", "role": "baseline"}, [SPAN])
ACC = Item.build("metric", {"name": "accuracy", "canonical": "factual_accuracy", "higher_is_better": True}, [SPAN])
LAT = Item.build("metric", {"name": "latency", "canonical": "latency", "higher_is_better": False}, [SPAN])
TRIVIA = Item.build("dataset", {"name": "TriviaCheck"}, [SPAN])
ROLE = {RAG.item_id: "rag", CB.item_id: "baseline", ACC.item_id: "acc", LAT.item_id: "lat"}


class Ctx:
    def __init__(self, text: str, context: list[Item]) -> None:
        self._text, self._context = text, context

    def text(self) -> str:
        return self._text

    def index(self) -> Index:
        return Index(self._text)

    def context_items(self) -> list[Item]:
        return self._context

    def field_schema(self) -> dict:
        return {}


def run(text: str, context: list[Item] | None = None, config: dict[str, Any] | None = None) -> list[Item]:
    doc = DocumentRef(id="P", file="papers/P.md", sha256=text_sha256(text))
    task = ExtractionTask(protocol=ProtocolRef(id=PROTO.id, sha256=PROTO.sha256), evidence_type="measurement",
                          field_schema_sha256="x", document=doc)
    ctx = Ctx(text, context if context is not None else [RAG, CB, ACC])
    return list(get("number_measurement", {**WORDS, **EFFECT, **(config or {})}).extract(task, ctx).items)


def found(items: list[Item]) -> list[tuple[str, str, float, Any]]:
    """(condition role, metric, value, dataset) by value position."""
    def start(i: Item) -> int:
        return min(s.selector["start"] for s in i.spans if s.role == "value")
    return [(ROLE[i.links["condition"]], ROLE[i.links["metric"]], i.fields["value"], i.fields["dataset"])
            for i in sorted(items, key=start)]


def sentence(body: str) -> str:
    return f"# P\n\nWe compare a closed-book model with a retrieval-augmented model.\n\n{body}\n"


# --- the brief's four ---------------------------------------------------------------------------------------

def test_table_cell_number() -> None:
    text = ("# P\n\nTable 2: Results on TriviaCheck (%).\n\n| Model | Accuracy |\n|---|---|\n"
            "| retrieval-augmented model | 71.0 |\n| closed-book model | 62.0 |\n")
    items = run(text, [RAG, CB, ACC, TRIVIA])
    assert found(items) == [("rag", "acc", 0.71, "TriviaCheck"), ("baseline", "acc", 0.62, "TriviaCheck")]
    for item in items:
        exact = {s.role: s.selector["exact"] for s in item.spans}
        assert set(exact) == {"value", "condition_label", "metric_label"} and exact["metric_label"] == "Accuracy"


def test_sentence_number() -> None:
    # the condition named right after the number, in brackets (regex_measurement wants "for"/"with")
    text = sentence("Accuracy was 71% (retrieval-augmented model) versus 62% (closed-book model).")
    items = run(text)
    assert found(items) == [("rag", "acc", 0.71, None), ("baseline", "acc", 0.62, None)]
    [rag] = [i for i in items if i.links["condition"] == RAG.item_id]
    exact = {s.role: s.selector["exact"] for s in rag.spans}
    assert exact == {"value": "71%", "condition_label": "retrieval-augmented model", "metric_label": "Accuracy"}
    # a comparison target after the number is not its condition: "71% ... over the closed-book model"
    text = sentence("The retrieval-augmented model reaches an accuracy of 71% over the closed-book model.")
    assert found(run(text)) == [("rag", "acc", 0.71, None)]


def test_number_without_condition_skipped() -> None:
    assert run(sentence("Accuracy reached 71% on the test set.")) == []
    assert run(sentence("The closed-book model reached 71% on the test set.")) == []   # no metric either
    table = "# P\n\n| Model | Accuracy |\n|---|---|\n| fine-tuned model | 71.0 |\n"
    assert run(table) == []


def test_seconds_not_normalised() -> None:
    context = [RAG, CB, LAT]
    table = "# P\n\n| System | Latency |\n|---|---|\n| closed-book model | 1.21 |\n"
    assert found(run(table, context)) == [("baseline", "lat", 1.21, None)]
    prose = sentence("The closed-book model has a latency of 1.21 s.")
    assert found(run(prose, context)) == [("baseline", "lat", 1.21, None)]
    ms = sentence("Latency is 655 ms for the retrieval-augmented model.")
    assert found(run(ms, context)) == [("rag", "lat", 0.655, None)]
    header = "# P\n\n| System | Latency (ms) |\n|---|---|\n| closed-book model | 410 |\n"
    assert found(run(header, context)) == [("baseline", "lat", 0.41, None)]
    caption = ("# P\n\nTable 1: Accuracy in percent and latency.\n\n| System | Accuracy | Latency |\n|---|---|---|\n"
               "| closed-book model | 62.0 | 1.21 |\n")   # the % caption is for the accuracy column only
    assert found(run(caption, [RAG, CB, ACC, LAT])) == [("baseline", "acc", 0.62, None),
                                                         ("baseline", "lat", 1.21, None)]


# --- guards -------------------------------------------------------------------------------------------------

def test_deltas_are_not_values() -> None:
    assert run(sentence("The retrieval-augmented model improves accuracy by 4% over the closed-book model.")) == []
    assert run(sentence("The retrieval-augmented model gains +3.2 points of accuracy over the closed-book "
                        "model.")) == []
    assert run(sentence("The retrieval-augmented model is 9% higher in accuracy than the closed-book "
                        "model.")) == []
    assert run(sentence("The retrieval-augmented model is 0.45 s slower in latency than the closed-book model."),
               [RAG, CB, LAT]) == []
    text = sentence("The retrieval-augmented model reaches an accuracy of 71% (+9%) over the closed-book model.")
    assert found(run(text)) == [("rag", "acc", 0.71, None)]
    delta_column = ("# P\n\n| Model | Accuracy | Δ Accuracy |\n|---|---|---|\n"
                    "| retrieval-augmented model | 71.0 | 9.0 |\n")
    assert found(run(delta_column)) == [("rag", "acc", 0.71, None)]


def test_years_are_not_values() -> None:
    text = sentence("In 2023, the retrieval-augmented model reached an accuracy of 0.71.")
    assert found(run(text)) == [("rag", "acc", 0.71, None)]
    assert run(sentence("The closed-book model (2021) was evaluated on accuracy."), [RAG, CB, LAT]) == []


def test_counts_are_not_values() -> None:
    text = sentence("The closed-book model answered 1,000 questions with an accuracy of 62%.")
    assert found(run(text)) == [("baseline", "acc", 0.62, None)]
    assert run(sentence("The closed-book model answered 500 questions; accuracy is reported below.")) == []
    assert run(sentence("We measure the latency of the closed-book model on 120 questions."), [RAG, CB, LAT]) == []


def test_ranges_sections_and_shares_are_not_values() -> None:
    assert run(sentence("Accuracy of the closed-book model lies between 0.6 and 0.7.")) == []
    assert run(sentence("Accuracy of the closed-book model is 0.6-0.7 across seeds.")) == []
    assert run(sentence("Accuracy of the closed-book model drops from 71% to 62%.")) == []
    text = sentence("Section 4.1 reports the latency of the closed-book model.")
    assert run(text, [RAG, CB, LAT]) == []
    # D35: a percentage followed by "of" is no longer turned away as a share ("34% of patients responded")
    [share] = run(sentence("For 40% of the questions, the closed-book model's accuracy is reported."))
    assert (share.fields["value"], share.fields["form"]) == (0.4, "percent")
    assert run(sentence("For 0.4 of the questions, the closed-book model's accuracy is reported.")) == []


def test_percent_only_normalised_for_fraction_metrics() -> None:
    # a bare 1 < x <= 100 is a percentage only for a [0, 1] metric; for latency it stays as written
    text = sentence("The closed-book model reaches an accuracy of 62.5.")
    assert found(run(text)) == [("baseline", "acc", 0.625, None)]
    assert found(run(sentence("The closed-book model has a latency of 2.5."), [RAG, CB, LAT])) == [
        ("baseline", "lat", 2.5, None)]


# --- surface forms: codes and abbreviations of the context items (fix round 1) ---------------------------

def spanned(item: Item, *forms: str) -> Item:
    """The context item with spans whose exact texts are `forms` (as an abbrev or LLM item would carry)."""
    role = "condition_label" if item.evidence_type == "condition" else "metric_label"
    spans = [Span(role=role, selector={"file": "papers/P.md", "start": n, "end": n + len(f), "exact": f})
             for n, f in enumerate(forms)]
    return Item.build(item.evidence_type, dict(item.fields), spans)


def roles(items: list[Item], context: list[Item]) -> list[tuple[str, float]]:
    """(condition role, value) by value position."""
    role = {i.item_id: i.fields.get("role") for i in context}
    def start(i: Item) -> int:
        return min(s.selector["start"] for s in i.spans if s.role == "value")
    return [(role[i.links["condition"]], i.fields["value"]) for i in sorted(items, key=start)]


VERSUS = "Accuracy was 71% (RAG) versus 62% (CB)."


def test_versus_with_codes_defined_in_the_text() -> None:
    text = ("# P\n\nWe compare a closed-book model (CB) with a retrieval-augmented model (RAG).\n\n" + VERSUS + "\n")
    assert roles(run(text), [RAG, CB]) == [("rag", 0.71), ("baseline", 0.62)]


def test_versus_with_codes_from_context_spans() -> None:
    text = "# P\n\nWe compare a closed-book model with a retrieval-augmented model.\n\n" + VERSUS + "\n"
    context = [RAG, spanned(CB, "closed-book model", "CB"), ACC]
    assert roles(run(text, context), context) == [("rag", 0.71), ("baseline", 0.62)]


def test_a_preceding_condition_is_not_taken_across_versus() -> None:
    text = sentence("Accuracy was 71% for the retrieval-augmented model versus 62%.")
    assert found(run(text)) == [("rag", "acc", 0.71, None)]


def test_preceding_condition_beats_a_later_one() -> None:
    text = ("# P\n\nWe compare a closed-book baseline (B) with its retrieval-augmented variant (R).\n\n"
            "On accuracy, R reaches 0.71 and B reaches 0.62.\n")
    assert roles(run(text), [RAG, CB]) == [("rag", 0.71), ("baseline", 0.62)]


def test_abbreviated_metric_resolves_by_its_span_text() -> None:
    hr = spanned(Item.build("metric", {"name": "hallucination rate", "canonical": "hallucination_rate",
                                       "higher_is_better": False}, [SPAN]), "HR")
    context = [RAG, CB, hr]
    table = "# P\n\n| Model | HR (%) |\n|---|---|\n| closed-book model | 20.2 |\n| retrieval-augmented model | 6.3 |\n"
    items = run(table, context)
    assert roles(items, context) == [("baseline", 0.202), ("rag", 0.063)]
    assert {i.links["metric"] for i in items} == {hr.item_id}
    prose = run(sentence("The closed-book model has an HR of 20%."), context)
    assert roles(prose, context) == [("baseline", 0.2)] and prose[0].links["metric"] == hr.item_id


def test_condition_code_in_a_table_row_from_context_spans() -> None:
    context = [spanned(RAG, "R"), spanned(CB, "B"), ACC]
    table = "# P\n\n| System | Accuracy (%) |\n|---|---|\n| B | 60.0 |\n| R | 70.0 |\n"
    assert roles(run(table, context), context) == [("baseline", 0.6), ("rag", 0.7)]


# --- identity ----------------------------------------------------------------------------------------------

def test_registered_as_regex_with_own_hash() -> None:
    ex = get("number_measurement", WORDS)
    assert ex.spec.kind == "regex" and ex.spec.evidence_types == ("measurement",)
    assert ex.spec.code_sha256 == numbers.CODE_SHA256 == base.source_sha256(*numbers.SOURCES)
    names = {p.name for p in numbers.SOURCES}
    assert {"numbers.py", "numreader.py", "measure.py", "terms.py", "units.py", "regex.py", "base.py"} <= names


# --- the engine: [regex_measurement, number_measurement] --------------------------------------------------

def test_engine_cascade_finds_treatment_and_control_by_number(tmp_path: Path) -> None:
    text = PROTOCOL.read_text(encoding="utf-8")
    old = "      - name: regex_measurement\n"
    assert text.count(old) == 1
    variant = tmp_path / "numbers.yaml"
    variant.write_text(text.replace(old, old + "      - name: number_measurement\n"), encoding="utf-8", newline="\n")
    paper = ("# Retrieval for factual QA\n\n## Setup\n\nWe compare a closed-book model with a retrieval-augmented "
             "model and report factual accuracy.\n\n## Results\n\n"
             "Factual accuracy was 71.0 (retrieval-augmented model) versus 62.0 (closed-book model).\n")
    # regex_measurement reads a sentence number only with a % sign or at most 1: it finds neither value
    run_dir = engine.run(variant, corpus_of(tmp_path / "corpus", {"P1": paper}), tmp_path / "runs",
                         selection="regex-only", provider=None, strategy="all")
    answer = json.loads((run_dir / "answer.json").read_text(encoding="utf-8"))
    [study] = answer["studies"]
    assert (study["treatment"]["value"], study["control"]["value"], study["direction"]) == (0.71, 0.62, "supports")
    items = [json.loads(x) for x in (run_dir / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
    values = [i for i in items if i["evidence_type"] == "measurement"]
    assert sorted(i["fields"]["value"] for i in values) == [0.62, 0.71]
    assert all([f.split("@")[0] for f in i["found_by"]] == ["number_measurement"] for i in values)   # regex missed both


def test_one_value_written_in_prose_and_in_a_table_is_one_item() -> None:
    # `form` is not identity: "71%" in prose and "71.0" under a (%) header are one item, form from the earliest span
    text = (sentence("The retrieval-augmented model reaches an accuracy of 71%.")
            + "\n| Model | Accuracy (%) |\n|---|---|\n| retrieval-augmented model | 71.0 |\n")
    [item] = run(text)
    assert (item.fields["value"], item.fields["form"]) == (0.71, "percent")
    assert sorted(s.selector["exact"] for s in item.spans if s.role == "value") == ["71%", "71.0"]
