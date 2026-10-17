"""Flag scores (F4): per flag precision and recall against the ground truth's flags, counts_correct,
duplicates_correct; null for a system without flags."""
from __future__ import annotations

from pathlib import Path

from evaluation import report as rep
from evaluation.score import GroundTruth, expected_flags, score_answers, score_flags, score_synthesis

from . import fixtures as fx


def truth() -> GroundTruth:
    data = fx.f_ground_truth()
    return GroundTruth(data["corpus_id"], data["question"], data["studies"], data["placements"], data["answer"])


def flag_rows(result: dict) -> dict[str, dict]:
    return {r["flag"]: r for r in result["rows"]}


def test_expected_flags_come_from_the_studies() -> None:
    t = truth()
    assert expected_flags(t, "duplicate") == {"S003"} and expected_flags(t, "large_effect") == {"S006"}
    assert expected_flags(t, "claim_disagrees") == {"S002"}
    for s in t.studies:
        s["flags"] = []
    assert expected_flags(t, "duplicate") == {"S003"}   # duplicate_of alone flags a duplicate


def test_perfect_flags_score_one() -> None:
    result = score_flags(truth(), fx.f_answer())
    assert result is not None
    for flag, r in flag_rows(result).items():
        assert (r["tp"], r["fp"], r["fn"], r["precision"], r["recall"]) == (1, 0, 0, 1.0, 1.0), flag
    assert result["counts_correct"] is True
    assert result["counts"]["expected"] == {"supporting": 2, "contradicting": 1, "neutral": 0, "undetermined": 2,
                                            "duplicates": 1}
    assert result["counts"]["given"] == result["counts"]["expected"]
    assert result["duplicates_correct"] is True and result["duplicates"]["given"] == {"S003": "S001"}


def test_a_missed_duplicate_fails_recall_counts_and_duplicates() -> None:
    answer = fx.f_answer(flags={**fx.F_FLAGS, "duplicate": []}, duplicate_of={})
    result = score_flags(truth(), answer)
    dup = flag_rows(result)["duplicate"]
    assert (dup["tp"], dup["fp"], dup["fn"], dup["precision"], dup["recall"]) == (0, 0, 1, None, 0.0)
    assert flag_rows(result)["large_effect"]["recall"] == 1.0
    assert result["counts_correct"] is False       # supporting 3 vs 2, duplicates 0 vs 1
    assert result["counts"]["given"]["supporting"] == 3
    assert result["duplicates_correct"] is False and result["duplicates"]["given"] == {}


def test_a_false_flag_lowers_precision_only() -> None:
    answer = fx.f_answer(flags={**fx.F_FLAGS, "large_effect": ["S001", "S006"]})
    r = flag_rows(score_flags(truth(), answer))["large_effect"]
    assert (r["tp"], r["fp"], r["fn"], r["precision"], r["recall"]) == (1, 1, 0, 0.5, 1.0)
    assert r["given"] == ["S001", "S006"] and r["expected"] == ["S006"]


def test_the_wrong_original_fails_duplicates_correct_but_not_the_flag() -> None:
    answer = fx.f_answer(duplicate_of={"S003": "S002"})
    result = score_flags(truth(), answer)
    assert flag_rows(result)["duplicate"]["recall"] == 1.0 and flag_rows(result)["duplicate"]["precision"] == 1.0
    assert result["duplicates_correct"] is False
    assert result["duplicates"] == {"expected": {"S003": "S001"}, "given": {"S003": "S002"}}


def test_flags_fall_back_to_the_study_entries() -> None:
    answer = fx.f_answer()
    del answer["flags"]["large_effect"]       # the top-level list is missing: the study entries decide
    del answer["duplicates"]
    result = score_flags(truth(), answer)
    assert flag_rows(result)["large_effect"]["given"] == ["S006"]
    assert result["duplicates_correct"] is True


def test_counts_without_the_optional_lists_compare_the_counted_groups_only() -> None:
    data = fx.ground_truth()               # the pre-F ground truth: no undetermined/duplicates lists, no flags
    t = GroundTruth(data["corpus_id"], data["question"], data["studies"], data["placements"], data["answer"])
    answer = fx.f_answer(directions={"S001": "supports", "S002": "contradicts"}, flags={}, duplicate_of={})
    result = score_flags(t, answer)
    assert result["counts"]["expected"] == {"supporting": 1, "contradicting": 1, "neutral": 0}
    assert result["counts_correct"] is True
    assert all(r["expected"] == [] and r["recall"] is None for r in result["rows"])
    answer["counts"] = None
    assert score_flags(t, answer)["counts_correct"] is None


def test_a_system_without_flags_gets_null_and_is_not_listed(tmp_path: Path) -> None:
    corpus = fx.write_f_corpus(tmp_path)
    fx.dump(tmp_path / "engine.json", fx.f_answer())
    fx.dump(tmp_path / "rag.json", fx.baseline_answer("rag-baseline", {"S001": "supports"}, "supported"))
    result = score_answers(corpus, [tmp_path / "engine.json", tmp_path / "rag.json"])
    engine, rag = result["synthesis"]
    assert engine["flags"]["counts_correct"] is True and rag["flags"] is None
    assert score_synthesis(truth(), {"system": "x", "studies": []})["flags"] is None
    text = rep.render(result)
    flag_lines = [line for line in text.splitlines() if "| duplicate " in line]
    assert len(flag_lines) == 1 and flag_lines[0].startswith("| evidence-engine")   # the baseline has no flag rows
    assert "counts_correct" in text
    js, md = rep.write_report(result, tmp_path / "out")
    assert '"duplicates_correct": true' in js.read_text(encoding="utf-8")
