"""The RAG baseline with a scripted model: retrieval, the answer, the cache, and the hard rule."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.baselines import rag
from evaluation.baselines.common import SystemCorpus
from evaluation.score import score_answers
from gold.llm import JsonlCache

from . import fixtures as fx
from .helpers import Scripted, guard_forbidden

REPLY = {"label": "mixed", "answer_text": "S001 improves accuracy; S002 hallucinates more with retrieval.",
         "studies": [{"document": "S001", "stance": "supports"}, {"document": "S002", "stance": "contradicts"},
                     {"document": "S999", "stance": "supports"}, {"document": "S001", "stance": "neutral"}]}


def test_rag_baseline_answers_from_retrieved_passages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = fx.write_corpus(tmp_path)
    attempts = guard_forbidden(monkeypatch)
    scripted = Scripted(REPLY)
    answer = rag.rag_baseline(corpus, model=scripted.model(), k=3, max_chars=200)
    assert attempts == []
    assert answer["system"] == "rag-baseline" and answer["label"] == "mixed"
    assert answer["studies"] == [{"document": "S001", "direction": "supports"},
                                 {"document": "S002", "direction": "contradicts"}]  # S999 dropped, S001 once
    assert answer["dropped"] == ["S999"] and answer["supporting"] == ["S001"] and answer["contradicting"] == ["S002"]
    assert answer["counts"] == {"supporting": 1, "contradicting": 1, "neutral": 0, "undetermined": 0}
    assert len(answer["retrieved"]) == 3 and answer["label_by_rule"] == "mixed"
    texts = {"S001": fx.S001, "S002": fx.S002}
    for hit in answer["retrieved"]:  # offsets are raw offsets into the paper, and the prompt quotes them
        passage = texts[hit["document"]][hit["start"]:hit["end"]].strip()
        assert passage and passage in scripted.prompts[0]
    assert "Question: " + fx.QUESTION in scripted.prompts[0]
    monkeypatch.undo()
    result = score_answers(corpus, [_dump(tmp_path / "a.json", answer)])
    assert result["synthesis"][0]["label_correct"]


def test_retrieval_is_bm25_and_deterministic(tmp_path: Path) -> None:
    corpus = SystemCorpus(fx.write_corpus(tmp_path))
    chunks = rag.passages(corpus, max_chars=200)
    assert all(c.end - c.start <= 200 for c in chunks)
    hits = rag.retrieve(chunks, "hallucinated fetched passages", k=2)
    assert hits[0][0].document == "S002" and hits[0][1] > 0
    assert rag.retrieve(list(reversed(chunks)), "hallucinated fetched passages", k=2) == hits


def test_cache_makes_a_rerun_free_and_identical(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    cache = JsonlCache(tmp_path / "cache" / "rag.jsonl")
    first = Scripted(REPLY)
    a = rag.rag_baseline(corpus, model=first.model(), cache=cache)
    second = Scripted({"label": "supported", "studies": [], "answer_text": "other"})
    b = rag.rag_baseline(corpus, model=second.model(), cache=JsonlCache(tmp_path / "cache" / "rag.jsonl"))
    assert second.prompts == [] and a == b
    c = rag.rag_baseline(corpus, model=second.model(), cache=cache, k=1)  # other passages: a new call
    assert len(second.prompts) == 1 and c["label"] == "supported"


def test_manifest_cannot_point_a_baseline_at_the_ground_truth(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    manifest["papers"].append({"id": "GT", "file": "ground_truth.json", "sha256": ""})
    fx.dump(corpus / "manifest.json", manifest)
    with pytest.raises(ValueError, match="may not read"):
        SystemCorpus(corpus)


def _dump(path: Path, obj: dict) -> Path:
    fx.dump(path, obj)
    return path
