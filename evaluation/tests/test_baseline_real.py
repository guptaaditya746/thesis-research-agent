"""The RAG baseline on real whole-run questions: scored like an engine answer, same papers, empty answer valid."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from evaluation.baselines.real import rag_real, rag_real_full
from evaluation.realpapers import cochraneforest as cf
from evaluation.wholerun import Answer, RealQuestion, score

from . import fixtures as fx
from .helpers import Scripted

PASSAGES = "\n\nPassages:\n\n"


def script(answer_text: str, mapped: dict[str, Any]) -> Scripted:
    return Scripted(lambda prompt: {"answer_text": answer_text, "citations": []} if PASSAGES in prompt else mapped)


def same(q: RealQuestion) -> dict[str, Any]:
    return {"engine_corpus": q.corpus_dir, "engine_model_id": "scripted"}


def question(tmp: Path, kind: str, gold: dict[str, Any]) -> RealQuestion:
    return RealQuestion("r1", "Which system is most accurate?", "cs", fx.write_corpus(tmp), gold, kind)  # type: ignore[arg-type]


def test_rank_answer_scored_like_engine(tmp_path: Path) -> None:
    q = question(tmp_path, "rank", {"ranking": ["S002", "S001"]})
    fake = script("S002 is best, then S001.", {"ranking": ["S002.md", "S001", "S999"]})   # ids resolve; unknown dropped
    base = rag_real(q, model=fake.model(), **same(q))
    assert base == Answer(ranking=["S002", "S001"])
    engine = Answer(ranking=["S002", "S001"])
    assert score(base, q).keys() == score(engine, q).keys() and score(base, q)["top1"] == 1
    assert len(fake.prompts) == 2 and q.question in fake.prompts[0]


def test_compare_maps_paper_ids(tmp_path: Path) -> None:
    q = question(tmp_path, "compare", {"directions": {"S001": "improves", "S002": "worsens"}})
    fake = script("S001 helps; S002 does not.",
                  {"studies": [{"document": "S001.md", "direction": "improves"},
                               {"document": "S002", "direction": "worsens"}, {"document": "S999", "direction": "improves"}],
                   "conclusion": None})
    answer = rag_real(q, model=fake.model(), mode="per_paper", **same(q))
    assert answer.directions == {"S001": "improves", "S002": "worsens"}
    assert score(answer, q)["direction_agreement"] == 1.0


def test_same_papers_as_engine(tmp_path: Path) -> None:
    q = question(tmp_path, "list", {"items": []})
    other = tmp_path / "other"
    shutil.copytree(q.corpus_dir, other)
    manifest = json.loads((other / "manifest.json").read_text())
    manifest["papers"] = manifest["papers"][:1]
    (other / "manifest.json").write_text(json.dumps(manifest))
    fake = script("x", {"names": []})
    with pytest.raises(ValueError, match="same papers"):
        rag_real(q, model=fake.model(), engine_corpus=other, engine_model_id="scripted")
    assert fake.prompts == []                                   # refused before any call
    rag_real(q, model=fake.model(), **same(q))  # the same corpus passes


def test_empty_answer_valid(tmp_path: Path) -> None:
    q = question(tmp_path, "list", {"items": ["R"]})
    fake = script("   ", {"names": ["R"]})
    answer = rag_real(q, model=fake.model(), **same(q))
    assert answer == Answer() and len(fake.prompts) == 1       # no mapping call
    assert score(answer, q)["recall"] == 0


def test_record_is_like_rag_baseline_and_a_model_mismatch_is_refused(tmp_path: Path) -> None:
    q = question(tmp_path, "list", {"items": ["R"]})
    fake = script("It uses R.", {"names": ["R"]})
    answer, record = rag_real_full(q, model=fake.model(), **same(q))
    assert answer == Answer(names=["R"])
    for key in ("model_call", "mapping_call", "retrieved", "citations", "dropped_citations", "settings", "answer_text",
                "corpus_id"):
        assert key in record
    assert "cached" not in record["model_call"] and record["settings"]["retrieval"] == "global"
    with pytest.raises(ValueError, match="pinned model"):
        rag_real_full(q, model=fake.model(), engine_corpus=q.corpus_dir, engine_model_id="other-model")


def test_correct_claim_scores_one_of_one(tmp_path: Path) -> None:
    claims = [q for q in cf.questions(Path(__file__).resolve().parent / "data" / "cochrane_tiny", tmp_path)
              if q.kind == "claims"][0]
    out = cf.to_corpus(Path(__file__).resolve().parent / "data" / "cochrane_tiny", tmp_path / "c")
    q = RealQuestion(claims.id, claims.question, claims.field, out / "r1", claims.gold, "claims")
    fake = script("Drug X reduces mortality.", {"claims": [{"about": "r1", "direction": "improves"},
                                                          {"about": "free label", "direction": "worsens"}]})
    answer = rag_real(q, model=fake.model(), **same(q))
    assert answer.claims == [{"about": "r1", "direction": "improves"}]
    s = score(answer, q)
    assert s["precision"] == 1.0 and s["recall"] == 1.0
    assert "- r1:" in fake.prompts[1]       # the mapping call is given the conclusion ids
