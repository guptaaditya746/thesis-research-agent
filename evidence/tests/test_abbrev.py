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

from .conftest import PROTOCOL, corpus_of

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
    return get(name, config or {}).extract(task, Ctx(text))


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
    assert list(by_name) == ["fact-level accuracy"]   # "unsupported-answer rate" holds no metric term


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
    [item] = get("abbrev_metric", {}).extract(task, Ctx(text)).items
    assert [s.selector["start"] for s in item.spans] == [text.index("FLA is high")]


def test_engine_merges_abbrev_items_with_regex(tmp_path: Path) -> None:
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
    assert len(mine) == 1 and mine[0]["fields"]["canonical"] == "factual_accuracy"
    assert len(mine[0]["found_by"]) == 1   # only the abbrev extractor found it
