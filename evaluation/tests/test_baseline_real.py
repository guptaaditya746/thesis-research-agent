"""The RAG baseline on real whole-run questions: scored like an engine answer, same papers, empty answer valid."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from evaluation.baselines.real import rag_real
from evaluation.wholerun import Answer, RealQuestion, score

from . import fixtures as fx
from .helpers import Scripted

PASSAGES = "\n\nPassages:\n\n"


def script(answer_text: str, mapped: dict[str, Any]) -> Scripted:
    return Scripted(lambda prompt: {"answer_text": answer_text, "citations": []} if PASSAGES in prompt else mapped)


def question(tmp: Path, kind: str, gold: dict[str, Any]) -> RealQuestion:
    return RealQuestion("r1", "Which system is most accurate?", "cs", fx.write_corpus(tmp), gold, kind)  # type: ignore[arg-type]


def test_rank_answer_scored_like_engine(tmp_path: Path) -> None:
    q = question(tmp_path, "rank", {"ranking": ["R", "B"]})
    fake = script("R is best, then B.", {"ranking": ["R", "B"]})
    base = rag_real(q, model=fake.model())
    assert base == Answer(ranking=["R", "B"])
    engine = Answer(ranking=["R", "B"])
    assert score(base, q).keys() == score(engine, q).keys() and score(base, q)["top1"] == 1
    assert len(fake.prompts) == 2 and q.question in fake.prompts[0]


def test_compare_maps_paper_ids(tmp_path: Path) -> None:
    q = question(tmp_path, "compare", {"directions": {"S001": "improves", "S002": "worsens"}})
    fake = script("S001 helps; S002 does not.",
                  {"studies": [{"document": "S001.md", "direction": "improves"},
                               {"document": "S002", "direction": "worsens"}, {"document": "S999", "direction": "improves"}],
                   "conclusion": None})
    answer = rag_real(q, model=fake.model(), mode="per_paper")
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
        rag_real(q, model=fake.model(), engine_corpus=other)
    assert fake.prompts == []                                   # refused before any call
    rag_real(q, model=fake.model(), engine_corpus=q.corpus_dir)  # the same corpus passes


def test_empty_answer_valid(tmp_path: Path) -> None:
    q = question(tmp_path, "list", {"items": ["R"]})
    fake = script("   ", {"names": ["R"]})
    answer = rag_real(q, model=fake.model())
    assert answer == Answer() and len(fake.prompts) == 1       # no mapping call
    assert score(answer, q)["recall"] == 0
