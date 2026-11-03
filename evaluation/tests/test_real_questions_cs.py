"""Whole-run questions of the cs sets: SciLead boards (rank) and SciREX tasks (list). Fixtures are hand-made."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from evaluation.realpapers import scilead, scirex

DATA = Path(__file__).resolve().parent / "data"


def test_scilead_27_boards() -> None:
    qs = scilead.questions(DATA / "scilead_tiny")
    assert len(qs) == 1 and qs[0].kind == "rank" and qs[0].field == "cs"
    assert qs[0].question == "Which method is best on SQuAD by F1?"
    assert qs[0].gold["ranking"] == ["p1", "p2", "2103.00003.pdf"]
    real = os.environ.get("SCILEAD_DATA")
    if not real or not (Path(real) / scilead.BOARDS_FILE).is_file():
        pytest.skip("the real SciLead release is not present (set SCILEAD_DATA)")
    assert len(scilead.questions(Path(real))) == 27


def test_scilead_lower_is_better(tmp_path: Path) -> None:
    import json
    import shutil
    shutil.copytree(DATA / "scilead_tiny", tmp_path / "d")
    path = tmp_path / "d" / scilead.BOARDS_FILE
    boards = json.loads(path.read_text())
    boards[0]["Metric"] = "Perplexity"
    path.write_text(json.dumps(boards))
    assert scilead.questions(tmp_path / "d")[0].gold["ranking"] == ["2103.00003.pdf", "p2", "p1"]


def test_scirex_task_list() -> None:
    qs = scirex.questions(DATA / "scirex_tasks.jsonl")
    assert [q.question for q in qs] == ["Which datasets are used for Question Answering?"]   # Cora's task has 1
    assert qs[0].kind == "list" and qs[0].field == "cs"
    assert qs[0].gold["items"] == ["NaturalQuestions", "SQuAD"] and qs[0].gold["papers"] == ["t1", "t2"]
    assert scirex.questions(DATA / "scirex_tiny.jsonl") == []
