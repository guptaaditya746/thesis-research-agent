from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.wholerun import (Answer, RealQuestion, key_status, left_out_line, sample, score, score_set,
                                 tune_split, tune_split_questions)


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


def test_list_dedups_by_name_not_by_string() -> None:
    q = rq("list", {"items": ["SQuAD", "MNLI"]})
    s = score(Answer(names=["SQuAD", "squad", "MNLI"]), q)
    assert s["n_answer"] == 2 and s["precision"] == 1.0


def test_tune_guard_warns_when_id_spaces_differ(tmp_path: Path) -> None:
    (tmp_path / "tune_split.json").write_text(json.dumps({"papers": ["p9"], "rest": ["p8"]}))
    with pytest.warns(UserWarning, match="tune guard"):
        score(Answer(), rq("list", {"items": ["x"], "papers": ["2101.00001v1"]}, tmp_path))


def test_score_set_writes_both_rows_and_the_sample(tmp_path: Path) -> None:
    qs = [RealQuestion(f"q{i}", "?", "cs", tmp_path, {"items": ["a"], "papers": []}, "list") for i in range(12)]
    rows = score_set(qs, {}, {}, tmp_path / "out")
    assert len(rows["auto-confirmed"]) == 10 and len(rows["hand-confirmed"]) == 5
    assert {r["confirmation"] for r in rows["hand-confirmed"]} == {"hand-confirmed"}
    assert (tmp_path / "out" / "sample.json").is_file() and (tmp_path / "out" / "real_set.json").is_file()
    assert key_status(qs[0]) == "key-records run: not available"


def test_tune_split_holds_out_questions_not_papers(tmp_path: Path) -> None:
    """I3: a big board does not drop out with probability 0.8^k; whole questions are picked, and only papers that no
    kept question uses form the tuning slice."""
    big = [f"b{i}" for i in range(20)]
    qs = [RealQuestion("big", "?", "cs", tmp_path, {"papers": big}, "rank")]
    qs += [RealQuestion(f"s{i}", "?", "cs", tmp_path, {"papers": [f"s{i}", "shared"]}, "list") for i in range(9)]
    split = tune_split_questions(qs, 0.2, 0, tmp_path / "tune_split.json")
    assert len(split["questions"]) == 2 and len(split["kept_questions"]) == 8
    kept = {p for q in qs if q.id in split["kept_questions"] for p in q.gold["papers"]}
    assert not set(split["papers"]) & kept and "shared" not in split["papers"]
    assert set(split["papers"]) | set(split["rest"]) == {p for q in qs for p in q.gold["papers"]}
    assert json.loads((tmp_path / "tune_split.json").read_text())["papers"] == split["papers"]
    # every kept question survives the wholerun guard, every held one does not
    from evaluation.wholerun import question_papers, tune_papers
    held = tune_papers(qs[0])
    assert all(not set(question_papers(q)) & held for q in qs if q.id in split["kept_questions"])


def test_tune_split_command_prints_kept_and_held(tmp_path: Path, monkeypatch, capsys) -> None:
    from evaluation import cli
    qs = [RealQuestion(f"q{i}", "?", "cs", tmp_path, {"papers": [f"p{i}"]}, "list") for i in range(10)]
    monkeypatch.setattr(cli, "_real_questions", lambda name, src, corpus: qs)
    assert cli.main(["tune-split", "--set", "sofc", "--src", str(tmp_path), "--corpus", str(tmp_path)]) == 0
    assert "kept 8 questions, held 2" in capsys.readouterr().out
    assert (tmp_path / "tune_split.json").is_file()
    with pytest.raises(SystemExit):     # written once
        cli.main(["tune-split", "--set", "sofc", "--src", str(tmp_path), "--corpus", str(tmp_path)])
