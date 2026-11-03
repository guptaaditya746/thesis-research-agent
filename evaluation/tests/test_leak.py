"""The on-the-list / unseen split."""
from __future__ import annotations

import pytest

from evaluation.leak import mark, split_scores
from evaluation.truth import Fact, GroundTruth
from evidence.plan import WordList

WORDS = WordList(things={"t": ["Retrieval-Augmented Model", "closed book"]}, cues=[], written_by="orch-model",
                 ontology_names={"t": ["Fine tuned model"]})


def truth(corpus_id: str = "rag-claude-k1-abc") -> GroundTruth:
    t = GroundTruth(corpus_id, "q", [], [], {})
    for i, label in enumerate(["retrieval augmented models", "Closed-Book", "fine-tuned model", "brand new thing"]):
        t.facts[f"S.c{i}"] = Fact(f"S.c{i}", "condition", "S", "explicit", {"label": label})
    t.facts["S.k1"] = Fact("S.k1", "metric", "S", "explicit", {"name": "accuracy"})
    t.facts["S.m1"] = Fact("S.m1", "measurement", "S", "explicit", {"value": 1.0})   # no name: not marked
    return t


def test_mark_uses_clean_names():
    marks = mark(truth(), WORDS)
    assert marks == {"S.c0": "on the list", "S.c1": "on the list", "S.c2": "on the list",
                     "S.c3": "unseen", "S.k1": "unseen"}


def test_split_counts_sum_to_total():
    marks = mark(truth(), WORDS)
    split = split_scores({"missed": ["S.c1", "S.c3"]}, marks)
    assert split["on the list"]["facts"] + split["unseen"]["facts"] == len(marks)
    assert (split["on the list"]["matched"], split["on the list"]["facts"]) == (2, 3)
    assert (split["unseen"]["matched"], split["unseen"]["facts"]) == (1, 2)
    assert split["unseen"]["recall"] == 0.5 and split["unseen"]["precision"] is None
    assert split_scores({"extraction": {"missed": []}}, marks)["on the list"]["recall"] == 1.0


def test_types_limit_what_is_marked():
    assert set(mark(truth(), WORDS, types=["metric"])) == {"S.k1"}


def test_refuses_non_claude_corpus():
    with pytest.raises(ValueError, match="rag-claude-"):
        mark(truth("rag-qwen-k1-abc"), WORDS)
