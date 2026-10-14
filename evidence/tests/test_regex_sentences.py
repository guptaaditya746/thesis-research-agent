"""Regex measurements in sentences (review finding 2): a value is not attached to a condition across another
system or another number, signed deltas and "from X to Y" changes are no values, and "RAG with/without ..."
names another system."""
from __future__ import annotations

from pathlib import Path

from .conftest import measurements, regex_run

ABSTRACT = "# P\n\n## Abstract\n\nWe compare a closed-book model with a retrieval-augmented model. {}\n"


def test_no_reach_back_across_another_system(tmp_path: Path) -> None:
    text = ABSTRACT.format("The retrieval-augmented model reaches an accuracy of 71%, while a fine-tuned model "
                           "reaches 57%, compared with 62% for the closed-book model.")
    _, items = regex_run({"S": text}, tmp_path)
    assert measurements(items, "S") == [("rag", 0.71), ("baseline", 0.62)]


def test_signed_delta_is_not_a_value(tmp_path: Path) -> None:
    text = ABSTRACT.format("The retrieval-augmented model reaches an accuracy of 71% (+9%) over the closed-book "
                           "model at 62%.")
    _, items = regex_run({"S": text}, tmp_path)
    assert measurements(items, "S") == [("rag", 0.71), ("baseline", 0.62)]


def test_from_to_change_is_skipped(tmp_path: Path) -> None:
    text = ABSTRACT.format("The RAG model raises accuracy from 62% to 71% over the closed-book model.")
    _, items = regex_run({"S": text}, tmp_path)
    assert measurements(items, "S") == []


def test_rag_without_reranking_is_another_system(tmp_path: Path) -> None:
    text = ("# D\n\n## Method\n\nWe compare the closed-book model, the retrieval-augmented generator and the RAG "
            "without reranking.\n\n## Results\n\nThe closed-book model shows 36.1% hallucination rate on TriviaCheck. "
            "The RAG without reranking shows 19.5% hallucination rate on TriviaCheck. The retrieval-augmented "
            "generator shows 30.5% hallucination rate on TriviaCheck.\n")
    answer, items = regex_run({"D": text}, tmp_path)
    assert measurements(items, "D") == [("baseline", 0.361), ("rag", 0.305)]
    assert answer["studies"][0]["direction"] == "supports"
