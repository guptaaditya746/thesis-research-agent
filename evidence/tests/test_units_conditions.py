"""regex_measurement_units (values in their own unit unless the metric is a fraction) and regex_condition_kind
(condition labels from configured names, with their method kind), both in new modules so every existing
extractor keeps its id."""
from __future__ import annotations

import json
from pathlib import Path

from agent.anchor import Index, text_sha256
from evidence import engine, protocol
from evidence.contract import DocumentRef, ExtractionTask, Item, ProtocolRef
from evidence.extractors import get

from .conftest import PROTOCOL, make_corpus, regex_run

PROTO = protocol.load(PROTOCOL)
LATENCY = Path(__file__).resolve().parents[1] / "protocols" / "rag-latency.yaml"
# code_sha256 of the extractors that existed before these two modules (main at A3): unchanged
EXISTING = {"regex_condition": "5e6604c2dd98dd7cdc57c102931b5649e6d128f5b93eeb4686e0743ea92fa810",
            "regex_metric": "5e6604c2dd98dd7cdc57c102931b5649e6d128f5b93eeb4686e0743ea92fa810",
            "regex_measurement": "5e6604c2dd98dd7cdc57c102931b5649e6d128f5b93eeb4686e0743ea92fa810",
            "regex_author_claim": "5e6604c2dd98dd7cdc57c102931b5649e6d128f5b93eeb4686e0743ea92fa810",
            "regex_dataset": "5c3a469f71ee2d9c8344c26bace17fcc92d7296af7adcf57c7a9d4d8f1ce7182",
            "llm_condition": "9cc9ce6fd7157a115e25516d4e1814361863741694c8f353cdde22bc55bc4dca",
            "llm_measurement": "9cc9ce6fd7157a115e25516d4e1814361863741694c8f353cdde22bc55bc4dca",
            "regex_screen": "3b0dba02d36f5ce22702a141072ba105a89f2f47136b368d820b8ce885a55dbd",
            "llm_screen": "6879495f24e0398a67ed4c2bfd60b92ffd5b47c159c452df3d54894c174fa6ec"}


class Ctx:
    def __init__(self, text: str, context: list[Item] | None = None) -> None:
        self._text, self._context = text, context or []

    def text(self) -> str:
        return self._text

    def index(self) -> Index:
        return Index(self._text)

    def context_items(self) -> list[Item]:
        return self._context

    def field_schema(self) -> dict:
        return {}


def extract(name: str, text: str, config: dict, evidence_type: str, context: list[Item] | None = None):
    doc = DocumentRef(id="P", file="papers/P.md", sha256=text_sha256(text))
    task = ExtractionTask(protocol=ProtocolRef(id=PROTO.id, sha256=PROTO.sha256), evidence_type=evidence_type,  # type: ignore[arg-type]
                          field_schema_sha256="x", document=doc)
    return get(name, config).extract(task, Ctx(text, context))


def test_existing_extractor_ids_unchanged() -> None:
    assert {n: get(n, {}).spec.code_sha256 for n in EXISTING} == EXISTING


# --- regex_measurement_units -------------------------------------------------------------------------------

LAT_TEXT = ("# Study\nWe compare the retrieval-augmented model with the closed-book model.\n\n"
            "The retrieval-augmented model needs 1.80 s per answer, compared with 1.21 s for the closed-book model.\n\n"
            "| System | latency (s) | factual accuracy (%) |\n|---|---|---|\n"
            "| retrieval-augmented model | 1.8 | 71.0 |\n| closed-book model | 1.21 | 62.0 |\n")


def latency_items(text: str, tmp: Path) -> dict[tuple[str, str], list[float]]:
    _, items = regex_run({"S1": text}, tmp, LATENCY)
    out: dict[tuple[str, str], list[float]] = {}
    for i in items.values():
        if i["evidence_type"] == "measurement":
            key = (items[i["links"]["condition"]]["fields"]["role"], items[i["links"]["metric"]]["fields"]["canonical"])
            out.setdefault(key, []).append(i["fields"]["value"])
    return {k: sorted(v) for k, v in out.items()}


def test_seconds_stay_seconds_and_percent_stays_a_fraction(tmp_path: Path) -> None:
    found = latency_items(LAT_TEXT, tmp_path)
    assert found[("rag", "latency")] == [1.8]          # prose "1.80 s" and the cell 1.8: one value
    assert found[("baseline", "latency")] == [1.21]
    assert found[("rag", "other")] == [0.71] and found[("baseline", "other")] == [0.62]


def test_milliseconds_become_seconds(tmp_path: Path) -> None:
    text = ("# Study\nWe compare the retrieval-augmented model with the closed-book model.\n\n"
            "| Condition | Answer accuracy (%) | Latency (ms) |\n|---|---|---|\n"
            "| Closed-book model | 62.0 | 410 |\n| Retrieval-augmented model | 71.0 | 655 |\n")
    found = latency_items(text, tmp_path)
    assert found[("rag", "latency")] == [0.655] and found[("baseline", "latency")] == [0.41]


def test_fraction_metrics_config_keeps_the_old_normalisation() -> None:
    ex = get("regex_measurement_units", {"fraction_metrics": ["latency"]})
    assert ex.spec.config["fraction_metrics"] == ["latency"]
    assert get("regex_measurement_units", {}).spec.config["fraction_metrics"] == ["factual_accuracy", "hallucination_rate"]


def test_latency_smoke_direction_on_the_fixture_corpus(tmp_path: Path) -> None:
    run = engine.run(LATENCY, make_corpus(tmp_path / "corpus"), tmp_path / "runs", selection="regex-only", provider=None)
    answer = json.loads((run / "answer.json").read_text(encoding="utf-8"))
    by_doc = {s["document"]: s for s in answer["studies"]}
    s1 = by_doc["S001"]   # Latency (ms): closed-book 410, retrieval-augmented 655 -> RAG is slower
    assert (s1["treatment"]["value"], s1["control"]["value"], s1["direction"]) == (0.655, 0.41, "contradicts")
    assert answer["counts"]["contradicting"] >= 1 and answer["counts"]["supporting"] == 0


# --- regex_condition_kind ----------------------------------------------------------------------------------

KINDS = {"rag": ["retrieval-augmented model", "RAG pipeline"], "no-retrieval": ["closed-book model"],
         "rag-no-rerank": ["RAG without reranking"]}
BEST_SCHEMA = {"type": "object", "properties": {"label": {"type": "string"}, "kind": {"type": "string"}}}


def test_condition_kind_writes_label_and_kind() -> None:
    text = ("We compare the Closed-book model, the retrieval-augmented model and RAG without reranking. "
            "The closed-book model is weaker than the retrieval-augmented model.")
    result = extract("regex_condition_kind", text, {"kinds": KINDS, "field_schema": BEST_SCHEMA}, "condition")
    got = [(i.fields, [s.role for s in i.spans], i.spans[0].selector["exact"]) for i in result.items]
    assert sorted(got, key=lambda g: g[0]["label"]) == [
        ({"label": "Closed-book model", "kind": "no-retrieval"}, ["condition_label"], "Closed-book model"),
        ({"label": "RAG without reranking", "kind": "rag-no-rerank"}, ["condition_label"], "RAG without reranking"),
        ({"label": "retrieval-augmented model", "kind": "rag"}, ["condition_label"], "retrieval-augmented model")]


def test_condition_kind_with_names_writes_label_only() -> None:
    schema = {"type": "object", "properties": {"label": {"type": "string"}}}
    text = "The vanilla LLM and the fine-tuned model are compared; the vanilla LLM is weaker."
    result = extract("regex_condition_kind", text, {"names": ["vanilla LLM", "fine-tuned model"], "field_schema": schema},
                     "condition")
    assert sorted(i.fields["label"] for i in result.items) == ["fine-tuned model", "vanilla LLM"]
    assert all(set(i.fields) == {"label"} and len(i.spans) == 1 for i in result.items)


def test_condition_kind_longest_name_wins() -> None:
    text = "RAG without reranking is an ablation."
    names = {"rag": ["RAG"], "rag-no-rerank": ["RAG without reranking"]}
    result = extract("regex_condition_kind", text, {"kinds": names, "field_schema": BEST_SCHEMA}, "condition")
    assert [i.fields for i in result.items] == [{"label": "RAG without reranking", "kind": "rag-no-rerank"}]
