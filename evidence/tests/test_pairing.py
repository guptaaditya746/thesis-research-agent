"""Synthesis pairing (review finding 1): rag and baseline on the same dataset, by value position, a table
cell before prose."""
from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import regex_run

HEAD = "# T\n\n## Setup\n\nWe compare a closed-book baseline (B) with its retrieval-augmented variant (R).\n\n## Results\n\n"


@pytest.mark.parametrize("rag_nq, rag_tqa", [(70, 50), (71, 49), (72, 48), (73, 47), (74, 46), (75, 45)])
def test_pairs_on_the_first_dataset_with_both(tmp_path: Path, rag_nq: int, rag_tqa: int) -> None:
    table = ("| System | Dataset | Accuracy (%) |\n|---|---|---|\n| B | NQ | 60.0 |\n"
             f"| R | NQ | {rag_nq}.0 |\n| B | TQA | 60.0 |\n| R | TQA | {rag_tqa}.0 |\n")
    answer, items = regex_run({"T": HEAD + table}, tmp_path)
    study = answer["studies"][0]
    assert study["direction"] == "supports"
    assert study["rag"]["value"] == rag_nq / 100 and study["baseline"]["value"] == 0.6
    assert items[study["rag"]["measurement"]]["fields"]["dataset"] == "NQ"


def test_dataset_order_follows_the_values_not_the_labels(tmp_path: Path) -> None:
    """TQA rows come first in the table, so TQA is the first dataset with both conditions."""
    table = ("| System | Dataset | Accuracy (%) |\n|---|---|---|\n| R | TQA | 40.0 |\n| B | TQA | 60.0 |\n"
             "| R | NQ | 80.0 |\n| B | NQ | 60.0 |\n")
    answer, _ = regex_run({"T": HEAD + table}, tmp_path)
    assert answer["studies"][0]["direction"] == "contradicts" and answer["studies"][0]["rag"]["value"] == 0.4


def test_a_table_cell_beats_a_decoy_in_the_abstract(tmp_path: Path) -> None:
    text = ("# D\n\n## Abstract\n\nThe retrieval-augmented model reaches an accuracy of 80%, compared with 50% for the "
            "closed-book model.\n\n## Results\n\n| Condition | Accuracy (%) |\n|---|---|\n| Closed-book model | 64.0 |\n"
            "| Retrieval-augmented model | 60.0 |\n")
    answer, _ = regex_run({"D": text}, tmp_path)
    study = answer["studies"][0]
    assert (study["rag"]["value"], study["baseline"]["value"], study["direction"]) == (0.6, 0.64, "contradicts")
