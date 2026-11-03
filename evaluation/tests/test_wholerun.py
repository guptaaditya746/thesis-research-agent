from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.wholerun import Answer, RealQuestion, left_out_line, sample, score, tune_split


def rq(kind: str, gold: dict, tmp: Path | None = None) -> RealQuestion:
    return RealQuestion("q1", "Which?", "cs", tmp or Path("."), gold, kind)  # type: ignore[arg-type]


def test_rank_top1_and_tau() -> None:
    q = rq("rank", {"ranking": ["a", "b", "c", "d"]})
    perfect = score(Answer(ranking=["A", "b", "c", "d"]), q)
    assert perfect["top1"] == 1 and perfect["kendall_tau"] == pytest.approx(1.0)
    flipped = score(Answer(ranking=["d", "c", "b", "a"]), q)
    assert flipped["top1"] == 0 and flipped["kendall_tau"] == pytest.approx(-1.0)
    partial = score(Answer(ranking=["a", "x", "c"]), q)    # only a and c are in both orders
    assert partial["n_common"] == 2 and partial["kendall_tau"] == pytest.approx(1.0)
    empty = score(Answer(), q)
    assert empty["top1"] == 0 and empty["kendall_tau"] is None


def test_list_prf() -> None:
    q = rq("list", {"items": ["SQuAD", "Natural Questions", "MNLI"]})
    s = score(Answer(names=["squad", "MNLI", "Other"]), q)
    assert s["precision"] == pytest.approx(2 / 3) and s["recall"] == pytest.approx(2 / 3)
    assert s["f1"] == pytest.approx(2 / 3)
    nothing = score(Answer(), q)
    assert nothing["precision"] is None and nothing["recall"] == 0 and nothing["f1"] is None


def test_compare_direction() -> None:
    q = rq("compare", {"directions": {"s1": "improves", "s2": "worsens"}, "conclusion": "improves"})
    s = score(Answer(directions={"s1": "improves", "s2": "improves"}, conclusion="improves"), q)
    assert s["per_study"] == {"s1": 1, "s2": 0} and s["direction_agreement"] == 0.5 and s["conclusion_agrees"] == 1


def test_claims_and_confirmation_rows() -> None:
    q = rq("claims", {"conclusions": [{"id": "c1", "direction": "improves"}]})
    s = score(Answer(claims=[{"about": "c1", "direction": "improves"}, {"about": "c1", "direction": "worsens"}]), q,
              confirmation="hand-confirmed")
    assert s["precision"] == 0.5 and s["recall"] == 1.0 and s["confirmation"] == "hand-confirmed"
    assert score(Answer(), q, confirmation="auto-confirmed")["confirmation"] == "auto-confirmed"
    with pytest.raises(ValueError, match="confirmation"):
        score(Answer(), q, confirmation="maybe")


def test_refuses_tune_papers(tmp_path: Path) -> None:
    (tmp_path / "tune_split.json").write_text(json.dumps({"papers": ["p9"]}))
    q = rq("list", {"items": ["x"], "papers": ["p1", "p9"]}, tmp_path)
    with pytest.raises(ValueError, match="tune_split"):
        score(Answer(), q)
    assert score(Answer(), rq("list", {"items": ["x"], "papers": ["p1"]}, tmp_path))["recall"] == 0


def test_sample_split_and_left_out(tmp_path: Path) -> None:
    qs = [RealQuestion(f"q{i}", "?", "cs", tmp_path, {}, "list") for i in range(30)]
    a, b = sample(qs, 10, 0, tmp_path / "s.json"), sample(qs, 10, 0)
    assert a == b and len(a) == 10 and json.loads((tmp_path / "s.json").read_text())["ids"] == [q.id for q in a]
    split = tune_split([f"p{i}" for i in range(10)], 0.2, 0, tmp_path / "tune_split.json")
    assert len(split["papers"]) == 2 and not set(split["papers"]) & set(split["rest"])
    assert left_out_line(3, 43) == "left out: 3 of 43 (no open full text)"
