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
    assert qs[0].question == "Which paper reports the best result on SQuAD by F1?"
    assert qs[0].gold["ranking"] == ["2101.00001", "2102.00002", "2103.00003"]   # no manifest yet: arXiv ids
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
    assert scilead.questions(tmp_path / "d")[0].gold["ranking"] == ["2103.00003", "2102.00002", "2101.00001"]


def test_scirex_task_list() -> None:
    qs = scirex.questions(DATA / "scirex_tasks.jsonl")
    assert [q.question for q in qs] == ["Which datasets are used for Question Answering?"]   # Cora's task has 1
    assert qs[0].kind == "list" and qs[0].field == "cs"
    assert qs[0].gold["items"] == ["NaturalQuestions", "SQuAD"] and qs[0].gold["papers"] == ["t1", "t2"]
    assert scirex.questions(DATA / "scirex_tiny.jsonl") == []


def test_scilead_ranking_in_manifest_ids_scores_top1(tmp_path: Path) -> None:
    import json
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    ids = ["2101.00001v1", "2102.00002v2", "2103.00003v1"]          # as `evidence fetch` names them
    (corpus / "manifest.json").write_text(json.dumps({"papers": [{"id": i, "file": f"papers/{i}.md"} for i in ids[1:]]}))
    q = scilead.questions(DATA / "scilead_tiny", corpus)[0]
    assert q.gold["ranking"] == ["2102.00002v2", "2103.00003v1"] and q.gold["left_out"] == 1   # p1 is not in the corpus
    from evaluation.wholerun import Answer, score
    assert score(Answer(ranking=["2102.00002v2", "2103.00003v1"]), q)["top1"] == 1
    assert {r["paper"] for r in q.records} == {"2102.00002v2", "2103.00003v1"}


def test_truth_items_make_a_queryable_key_store() -> None:
    pytest.importorskip("evidence.kg.query")
    from evaluation.wholerun import key_status, key_store
    from evidence.kg.query import run_query
    q = scirex.questions(DATA / "scirex_tasks.jsonl")[0]
    assert key_status(q) == "available" and q.records
    rows = run_query(key_store(q), "PREFIX ev: <https://w3id.org/thesis-ev#> "
                                   "SELECT ?paper WHERE { ?p a ev:Paper ; ev:name ?paper } ORDER BY ?paper", {}).rows
    assert [r["paper"] for r in rows] == ["t1", "t2"]
