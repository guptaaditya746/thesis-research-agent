"""Oracle checks (Tim M2 §5C): synthesis on perfect evidence, the RAG baseline on perfect passages, and the
per-study attribution of a system's errors to upstream (extraction, retrieval) or downstream (synthesis)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation import cli, oracle
from evaluation.baselines import rag
from evaluation.baselines.common import DEFAULT_PROTOCOL
from evaluation.score import attribute, score, score_synthesis
from evaluation.truth import MAIN_ROLE, GroundTruth

from . import fixtures as fx
from .helpers import Scripted
from .test_rag import scripted

EXAMPLES = Path(__file__).resolve().parents[2] / "synth" / "examples"
MIXED = EXAMPLES / "rag-demo-mixed"


@pytest.mark.parametrize("corpus", [MIXED, None])
def test_every_fact_gets_an_item_at_its_main_placements(tmp_path: Path, corpus: Path | None) -> None:
    corpus = corpus or fx.write_corpus(tmp_path)
    truth = GroundTruth.load(corpus / "ground_truth.json")
    items, item_of = oracle.items_from_truth(truth, corpus)
    by_id = {i.item_id: i for doc in items.values() for i in doc}
    assert set(item_of) == set(truth.facts)
    for fact in truth.facts.values():
        item = by_id[item_of[fact.id]]
        assert item in items[fact.paper] and item.evidence_type == fact.type and item.found_by == ("oracle",)
        main = truth.placements_of(fact.id, MAIN_ROLE[fact.type])
        assert sorted((s.selector["start"], s.selector["end"], s.selector["exact"]) for s in item.spans) == \
            sorted((p["start"], p["end"], p["exact"]) for p in main)
        assert {s.role for s in item.spans} == {MAIN_ROLE[fact.type]}
        assert all(s.selector["file"] == f"papers/{fact.paper}.md" for s in item.spans)
        if fact.type == "measurement":
            assert item.links == {"condition": item_of[fact.data["condition"]], "metric": item_of[fact.data["metric"]]}
            assert item.fields == {"value": fact.data["value"], "dataset": fact.data["dataset"]}


def test_oracle_synthesis_on_the_mixed_example_gets_the_label(tmp_path: Path) -> None:
    run = oracle.run(DEFAULT_PROTOCOL, MIXED, tmp_path / "oracle")
    answer = json.loads((run / "answer.json").read_text(encoding="utf-8"))
    truth = GroundTruth.load(MIXED / "ground_truth.json")
    assert answer["system"] == "oracle-synthesis"
    result = score_synthesis(truth, answer)
    assert result["label_correct"] is True and all(s["correct"] for s in result["studies"])
    report = score(run, MIXED)   # the run dir is a scoreable engine-shaped run: every fact matched, at its span
    assert all(r["f1"] == 1.0 and r["span_accuracy"] == 1.0 for r in report["extraction"]["rows"] if r["facts"])


def test_attribute_splits_upstream_from_downstream(tmp_path: Path) -> None:
    truth = GroundTruth.load(fx.write_corpus(tmp_path) / "ground_truth.json")
    system = fx.baseline_answer("evidence-engine", {"S001": "neutral", "S002": "supports"}, "supported")
    oracle_answer = fx.baseline_answer("oracle-synthesis", {"S001": "supports", "S002": "neutral"}, "supported")
    assert attribute(truth, system, oracle_answer) == [
        {"study": "S001", "system_correct": False, "oracle_correct": True, "error": "upstream"},
        {"study": "S002", "system_correct": False, "oracle_correct": False, "error": "downstream"}]
    right = fx.baseline_answer("evidence-engine", {"S001": "supports", "S002": "contradicts"}, "mixed")
    assert [a["error"] for a in attribute(truth, right, oracle_answer)] == [None, None]


def test_score_with_oracle_adds_attribution_and_its_table(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    fx.dump(tmp_path / "rag.json", fx.baseline_answer("rag-baseline", {"S001": "neutral", "S002": "supports"}, "supported"))
    fx.dump(tmp_path / "oracle.json", fx.baseline_answer("oracle-synthesis", {"S001": "supports"}, "supported"))
    assert cli.main(["score", "--corpus", str(corpus), "--baseline", str(tmp_path / "rag.json"),
                     "--oracle", str(tmp_path / "oracle.json"), "--out", str(tmp_path / "out")]) == 0
    report = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    (entry,) = report["attribution"]["systems"]
    assert report["attribution"]["oracle"] == "oracle-synthesis" and entry["system"] == "rag-baseline"
    assert [s["error"] for s in entry["studies"]] == ["upstream", "downstream"]
    assert {"level": "all", "studies": 2, "system_correct": 0, "oracle_correct": 1, "upstream": 1,
            "downstream": 1} in entry["rows"]
    assert "## Attribution" in (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    run = fx.write_run(tmp_path / "runs", list(fx.perfect_items().values()), fx.engine_answer(fx.perfect_items()))
    assert score(run, corpus)["attribution"] is None


def test_oracle_command_writes_a_run(tmp_path: Path) -> None:
    assert cli.main(["oracle", "--protocol", str(DEFAULT_PROTOCOL), "--corpus", str(MIXED),
                     "--out", str(tmp_path / "o")]) == 0
    assert json.loads((tmp_path / "o" / "answer.json").read_text(encoding="utf-8"))["system"] == "oracle-synthesis"
    assert (tmp_path / "o" / "evidence.jsonl").is_file() and (tmp_path / "o" / "run.json").is_file()


@pytest.mark.parametrize("corpus", [MIXED, None])
def test_oracle_passages_are_the_paragraphs_holding_the_values(tmp_path: Path, corpus: Path | None) -> None:
    corpus = corpus or fx.write_corpus(tmp_path)
    truth = GroundTruth.load(corpus / "ground_truth.json")
    found = rag.oracle_passages(truth, corpus)
    texts = {p: (corpus / "papers" / f"{p}.md").read_text(encoding="utf-8") for p in {s["paper"] for s in truth.studies}}
    assert found == sorted(found, key=lambda p: (p.document, p.start)) and len(set(found)) == len(found)
    for p in found:
        text = texts[p.document]
        assert p.text == text[p.start:p.end] and "\n\n" not in p.text.strip()
        assert p.start == 0 or text[:p.start].endswith("\n\n")
        assert p.end == len(text) or text[p.end:].startswith("\n\n")
    for place in (p for p in truth.placements if p["role"] == "value"):
        assert any(p.document == place["paper"] and p.start <= place["start"] < place["end"] <= p.end for p in found)
    assert all(any(p.start <= v["start"] and v["end"] <= p.end for v in truth.placements
                   if v["role"] == "value" and v["paper"] == p.document) for p in found)   # nothing else


def test_rag_baseline_on_oracle_passages(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    model = scripted()
    answer = rag.rag_baseline(corpus, model=model.model(), oracle=True)
    shown = rag.oracle_passages(GroundTruth.load(corpus / "ground_truth.json"), corpus)
    assert answer["system"] == "rag-oracle-passages" and answer["label"] == "mixed"
    assert answer["retrieved"] == [{"document": p.document, "start": p.start, "end": p.end} for p in shown]
    assert answer["settings"]["retrieval"] == "oracle_passages"
    answering, mapping = model.prompts   # the same two calls as the BM25 baseline
    assert answering == rag.user_prompt(fx.QUESTION, [(p, 0.0) for p in shown])
    assert "Corpus paper ids: S001, S002" in mapping


def test_rag_baseline_command_with_oracle_passages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model = Scripted(lambda prompt: {"answer_text": "x", "citations": []} if "\n\nPassages:\n\n" in prompt
                     else {"label": "supported", "answer_text": "y", "studies": [{"document": "S001", "stance": "supports"}]})
    monkeypatch.setattr(cli, "_model", lambda alias: (model.model(alias), alias))
    corpus = fx.write_corpus(tmp_path)
    assert cli.main(["rag-baseline", "--corpus", str(corpus), "--out", str(tmp_path / "rag"), "--oracle-passages"]) == 0
    answer = json.loads((tmp_path / "rag" / "answer.json").read_text(encoding="utf-8"))
    assert answer["system"] == "rag-oracle-passages" and answer["label"] == "supported"
    assert (tmp_path / "rag" / "rag-oracle-passages-calls.jsonl").is_file()
