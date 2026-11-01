"""abbrev_condition and abbrev_metric: names a paper defines for itself ("fact-level accuracy (FLA)")."""
from __future__ import annotations

import json
from pathlib import Path

from agent.anchor import Index, text_sha256
from evidence import engine, protocol
from evidence.contract import DocumentRef, ExtractionTask, Item, ProtocolRef
from evidence.extractors import get
from evidence.extractors.abbrev import definitions
from synth.vocab import QUESTION_METRICS

from .conftest import PROTOCOL, corpus_of, pack_words

PROTO = protocol.load(PROTOCOL)


class Ctx:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def index(self) -> Index:
        return Index(self._text)

    def context_items(self) -> list[Item]:
        return []

    def field_schema(self) -> dict:
        return {}


def extract(name: str, text: str, evidence_type: str, config: dict | None = None):
    doc = DocumentRef(id="P", file="papers/P.md", sha256=text_sha256(text))
    task = ExtractionTask(protocol=ProtocolRef(id=PROTO.id, sha256=PROTO.sha256), evidence_type=evidence_type,  # type: ignore[arg-type]
                          field_schema_sha256="x", document=doc)
    return get(name, {**pack_words(name, evidence_type), **(config or {})}).extract(task, Ctx(text))


def test_definition_found() -> None:
    text = "We report fact-level accuracy (FLA) on every set."
    [d] = definitions(text)
    assert (d.long, d.short) == ("fact-level accuracy", "FLA")
    assert text[d.start:d.end] == "fact-level accuracy (FLA)"


def test_reverse_definition_found() -> None:
    [d] = definitions("We use HR (hallucination rate) throughout.")
    assert (d.long, d.short) == ("hallucination rate", "HR")


def test_not_a_definition() -> None:
    assert definitions("Results are in accuracy (see Table 2). A baseline (B) is used; the model (GPT) too.") == []


def test_every_synthetic_metric_abbreviation_is_found() -> None:
    for metrics in QUESTION_METRICS.values():
        for name, short, _ in metrics:
            assert [(d.long, d.short) for d in definitions(f"We measure the {name} ({short}) here.")] == [(name, short)]


def test_stop_words_may_be_left_out() -> None:
    assert [(d.long, d.short) for d in definitions("the Mean of Errors (ME) is low")] == [("Mean of Errors", "ME")]


TEXT = ("# Study\n\nWe measure fact-level accuracy (FLA) and the unsupported-answer rate (UAR).\n\n"
        "| System | FLA | Latency |\n|---|---|---|\n| X | 0.6 | 1 |\n")


def test_short_form_in_table_becomes_metric_item() -> None:
    result = extract("abbrev_metric", TEXT, "metric")
    by_name = {i.fields["name"]: i for i in result.items}
    item = by_name["fact-level accuracy"]
    assert item.fields == {"name": "fact-level accuracy", "canonical": "factual_accuracy", "higher_is_better": True}
    assert [(s.role, s.selector["exact"]) for s in item.spans] == [("metric_label", "FLA"), ("metric_label", "FLA")]
    assert [s.selector["start"] for s in item.spans][1] == TEXT.index("| FLA |") + 2
    assert by_name["unsupported-answer rate"].fields["canonical"] == "hallucination_rate"
    assert not by_name["unsupported-answer rate"].fields["higher_is_better"]


def test_long_form_without_a_term_gives_no_item() -> None:
    assert extract("abbrev_metric", "A blue green deployment (BGD) is used. BGD works.", "metric").items == ()


def test_condition_item_has_role_and_label() -> None:
    text = "We compare retrieval-augmented generation (RAG) with a closed-book model. RAG wins; RAG is cheap."
    result = extract("abbrev_condition", text, "condition")
    [item] = result.items
    assert item.fields == {"label": "retrieval-augmented generation", "role": "rag"}
    assert [s.role for s in item.spans] == ["condition_label"] * 3


def test_scope_limits_uses_not_definitions() -> None:
    text = "fact-level accuracy (FLA) is used.\n\nLater FLA is high."
    doc = DocumentRef(id="P", file="papers/P.md", sha256=text_sha256(text))
    from evidence.contract import Scope
    task = ExtractionTask(protocol=ProtocolRef(id=PROTO.id, sha256=PROTO.sha256), evidence_type="metric",
                          field_schema_sha256="x", document=doc, scope=Scope(kind="ranges", ranges=((text.index("Later"), len(text)),)))
    [item] = get("abbrev_metric", pack_words("abbrev_metric", "metric")).extract(task, Ctx(text)).items
    assert [s.selector["start"] for s in item.spans] == [text.index("FLA is high")]


def test_engine_keeps_abbrev_and_regex_metric_items_with_one_canonical(tmp_path: Path) -> None:
    text = PROTOCOL.read_text(encoding="utf-8")
    text = text.replace("      - name: regex_metric\n", "      - name: regex_metric\n      - name: abbrev_metric\n", 1)
    variant = tmp_path / "abbrev.yaml"
    variant.write_text(text, encoding="utf-8", newline="\n")
    paper = ("# T\n\n## Setup\n\nWe compare a closed-book baseline (B) with its retrieval-augmented variant (R). "
             "We report fact-level accuracy (FLA).\n\n## Results\n\n| System | Dataset | FLA |\n|---|---|---|\n"
             "| B | NQ | 60.0 |\n| R | NQ | 70.0 |\n")
    run = engine.run(variant, corpus_of(tmp_path / "corpus", {"P1": paper}), tmp_path / "runs", selection="regex-only",
                     provider=None, strategy="all")
    items = [json.loads(x) for x in (run / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
    metrics = [i for i in items if i["evidence_type"] == "metric"]
    mine = [m for m in metrics if m["fields"]["name"] == "fact-level accuracy"]   # next to the regex "accuracy" item
    assert len(mine) == 1 and mine[0]["spans"] and {s["role"] for s in mine[0]["spans"]} == {"metric_label"}
    plain = [m for m in metrics if m["fields"]["name"] == "accuracy"]   # both passed the engine checks (schema, roles)
    assert len(plain) == 1 and plain[0]["fields"]["canonical"] == mine[0]["fields"]["canonical"] == "factual_accuracy"
    assert len(mine[0]["found_by"]) == 1   # only the abbrev extractor found it


def test_every_synthetic_metric_abbreviation_yields_an_item_with_its_canonical() -> None:
    for canonical, metrics in QUESTION_METRICS.items():
        for name, short, _ in metrics:
            [item] = extract("abbrev_metric", f"We measure the {name} ({short}) here. Table: {short} is high.",
                             "metric").items
            assert (item.fields["name"], item.fields["canonical"]) == (name, canonical), name


def test_measure_noun_falls_back_to_other_only_when_the_enum_allows() -> None:
    text = "We report the throughput rate (TR) of the system. TR is stable."
    assert [i.fields["canonical"] for i in extract("abbrev_metric", text, "metric").items] == ["other"]
    schema = {"properties": {"canonical": {"enum": ["factual_accuracy", "hallucination_rate"]}}}
    assert extract("abbrev_metric", text, "metric", {"field_schema": schema}).items == ()


# --- phrase definitions ("abbreviated HR", "denoted by the code B"; synth/render_llm.py "distributed") -----

PHRASED = [
    ("The outcome is the hallucination rate, abbreviated HR, which is the share of answers.",
     "hallucination rate", "HR"),
    ("The metric, fact-level accuracy, is abbreviated FLA, and it is the fraction of answers.",
     "fact-level accuracy", "FLA"),
    ("Performance is measured with the unsupported-answer rate, abbreviated UAR, which is defined below.",
     "unsupported-answer rate", "UAR"),
    ("The measure answer accuracy, abbreviated AA, is the proportion of questions.", "answer accuracy", "AA"),
    ("We report answer accuracy (abbreviated AA) throughout.", "answer accuracy", "AA"),
    ("The vanilla LLM, which is denoted by the code B, is prompted with the question.", "vanilla LLM", "B"),
    ("The fine-tuned model, denoted by its code A2, was trained further.", "fine-tuned model", "A2"),
    ("The retrieval-augmented generator is denoted by its code R and is given passages.",
     "retrieval-augmented generator", "R"),
    ("The no-retrieval baseline, denoted NRB, receives only the question.", "no-retrieval baseline", "NRB"),
    ("We run the closed-book model, hereafter CB, on every question.", "closed-book model", "CB"),
    ("We report fact-level accuracy, or FLA for short, on every set.", "fact-level accuracy", "FLA"),
    ("We report fact-level accuracy (FLA for short) on every set.", "fact-level accuracy", "FLA"),
]


def test_phrase_definitions_found() -> None:
    for sentence, long, short in PHRASED:
        assert [(d.long, d.short) for d in definitions(sentence)] == [(long, short)], sentence


SUBJECT = [   # "..., and it is denoted by the code R": the sentence's subject; the item is named by its term
    ("The second condition is the retrieval-augmented generator, which is given the top passages of a dense "
     "retriever together with the question and is denoted by its code R.", "retrieval-augmented", "R"),
    ("The vanilla LLM is prompted with the question and nothing else, and it is denoted by the code B.",
     "vanilla LLM", "B"),
    ("The RAG pipeline first searches the reference collection and then writes an answer, and it is denoted by "
     "the code R.", "RAG pipeline", "R"),
    ("The first condition, the closed-book model, relies on its parametric knowledge alone, and it is denoted "
     "by its code B.", "closed-book model", "B"),
]


def test_subject_definitions_name_the_term_of_the_sentence_subject() -> None:
    for sentence, label, short in SUBJECT:
        [d] = definitions(sentence)
        assert d.subject and d.code and d.short == short and label in d.long, sentence
        [item] = extract("abbrev_condition", sentence, "condition").items
        assert item.fields["label"] == label and [s.selector["exact"] for s in item.spans] == [short], sentence


def test_code_definition_never_makes_a_metric() -> None:
    text = "The retrieval-augmented generator, which improves accuracy, is denoted by the code R. R is good."
    assert extract("abbrev_metric", text, "metric").items == ()


def test_one_letter_short_form_needs_the_code_phrasing() -> None:
    assert definitions("The no-retrieval baseline, denoted B, receives only the question.") == []
    assert definitions("The baseline is abbreviated B in the tables.") == []
    assert definitions("The vanilla LLM is denoted by x in the equations.") == []


def test_phrase_definition_span_covers_long_and_short_form() -> None:
    text = "The outcome is the hallucination rate, abbreviated HR, which is the share of answers."
    [d] = definitions(text)
    assert text[d.start:d.end] == "hallucination rate, abbreviated HR"


DISTRIBUTED = ("# Grounded Generation\n\n## Method\n\nThe first condition is the vanilla LLM, which is prompted with "
               "the question and nothing else and is denoted by its code B. The second condition is the "
               "retrieval-augmented generator, which is given the top passages of a dense retriever together with "
               "the question and is denoted by its code R. The outcome measure is the hallucination rate, abbreviated "
               "HR, which is the share of answers with an unsupported statement.\n\n## Results\n\n"
               "| System | HR (%) |\n| --- | --- |\n| B | 20.2 |\n| R | 6.3 |\n")


def test_coded_conditions_and_abbreviated_metric_become_items() -> None:
    conditions = {i.fields["label"]: i for i in extract("abbrev_condition", DISTRIBUTED, "condition").items}
    assert {k: v.fields["role"] for k, v in conditions.items()} == {"vanilla LLM": "baseline",
                                                                     "retrieval-augmented": "rag"}
    assert [s.selector["exact"] for s in conditions["vanilla LLM"].spans] == ["B", "B"]
    [metric] = extract("abbrev_metric", DISTRIBUTED, "metric").items
    assert metric.fields["canonical"] == "hallucination_rate"
    assert [s.selector["exact"] for s in metric.spans] == ["HR", "HR"]
