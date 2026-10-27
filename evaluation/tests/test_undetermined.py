"""Expected `undetermined` (F4): a study with missing information or an irrelevant paper is not counted in
`direction_accuracy` (the decidable-papers rule: C only on the studies truth can decide, a determined study left
out or called undetermined is wrong); `direction_accuracy_all_papers` keeps the old rule, where such a study is right
when the system says undetermined or leaves it out. completeness and accuracy_answered are over determined
expectations."""
from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.score import GroundTruth, expected_direction, score_answers, score_synthesis

from . import fixtures as fx
from .test_score import row


def _truth() -> GroundTruth:
    data = fx.f_ground_truth()
    return GroundTruth(data["corpus_id"], data["question"], data["studies"], data["placements"], data["answer"])


def test_expected_direction_rules() -> None:
    s1, s2, s3, s4, s5, s6 = fx.f_studies()
    assert [expected_direction(s) for s in (s1, s2, s3, s4, s5, s6)] == [
        "supports", "contradicts", "supports", "undetermined", "undetermined", "supports"]
    assert expected_direction({"study_id": "x", "paper": "x"}) is None          # no effect, not scored
    assert expected_direction({"relevant": False, "effect": {"direction": "supports"}}) == "undetermined"


def test_perfect_answer_is_right_on_every_study_and_answered_over_determined_ones() -> None:
    result = score_synthesis(_truth(), fx.f_answer())
    overall = row(result["rows"], level="all")
    assert (overall["studies"], overall["determined"]) == (6, 4)
    assert (overall["direction_accuracy"], overall["completeness"], overall["accuracy_answered"]) == (1.0, 1.0, 1.0)
    assert {"expected": "undetermined", "given": "undetermined", "n": 2} in result["confusion"]
    assert [s["determined"] for s in result["studies"]] == [True, True, True, False, False, True]
    assert result["label_correct"]


def test_guessing_on_an_undetermined_study_is_wrong_but_not_counted_as_answered() -> None:
    answer = fx.f_answer(directions={**fx.F_DIRECTIONS, "S004": "supports", "S005": "supports"})
    result = score_synthesis(_truth(), answer)
    overall = row(result["rows"], level="all")
    assert overall["direction_accuracy"] == 1.0                                    # over the 4 determined studies only
    assert overall["direction_accuracy_all_papers"] == pytest.approx(4 / 6)
    assert (overall["completeness"], overall["accuracy_answered"]) == (1.0, 1.0)
    complex_ = row(result["rows"], level="complex")                                # S004 only, undetermined
    assert (complex_["direction_accuracy"], complex_["direction_accuracy_all_papers"]) == (None, 0.0)
    assert {"expected": "undetermined", "given": "supports", "n": 2} in result["confusion"]


def test_a_baseline_that_leaves_the_undetermined_studies_out_loses_nothing_and_gains_nothing() -> None:
    answer = fx.baseline_answer("rag-baseline", {"S001": "supports", "S002": "contradicts", "S003": "supports",
                                                 "S006": "supports"}, "mixed")
    result = score_synthesis(_truth(), answer)
    overall = row(result["rows"], level="all")
    assert (overall["direction_accuracy"], overall["completeness"], overall["accuracy_answered"]) == (1.0, 1.0, 1.0)
    assert result["flags"] is None
    partial = fx.baseline_answer("agent-baseline", {"S001": "supports"}, "supported")
    overall = row(score_synthesis(_truth(), partial)["rows"], level="all")
    assert overall["direction_accuracy"] == pytest.approx(1 / 4)   # S001 right; S002, S003, S006 left out: wrong
    assert overall["direction_accuracy_all_papers"] == pytest.approx(3 / 6)   # old: S004 and S005 right by silence
    assert overall["completeness"] == 0.25 and overall["accuracy_answered"] == 1.0


def test_an_undetermined_answer_on_a_determined_study_is_unanswered_and_wrong() -> None:
    answer = fx.f_answer(directions={**fx.F_DIRECTIONS, "S006": "undetermined"})
    overall = row(score_synthesis(_truth(), answer)["rows"], level="all")
    assert overall["direction_accuracy"] == pytest.approx(3 / 4)
    assert overall["direction_accuracy_all_papers"] == pytest.approx(5 / 6)
    assert overall["completeness"] == 0.75 and overall["accuracy_answered"] == 1.0


def test_a_study_without_effect_or_relevance_is_not_scored() -> None:
    data = fx.f_ground_truth()
    data["studies"].append({"study_id": "S007", "paper": "S007", "level": "explicit"})
    truth = GroundTruth(data["corpus_id"], data["question"], data["studies"], data["placements"], data["answer"])
    assert row(score_synthesis(truth, fx.f_answer())["rows"], level="all")["studies"] == 6


def test_through_the_files(tmp_path: Path) -> None:
    corpus = fx.write_f_corpus(tmp_path)
    fx.dump(tmp_path / "engine.json", fx.f_answer())
    result = score_answers(corpus, [tmp_path / "engine.json"])
    assert row(result["synthesis"][0]["rows"], level="all")["direction_accuracy"] == 1.0
    assert result["intervals"]["synthesis"][0]["point"] == 1.0 and result["intervals"]["paired"] == []
