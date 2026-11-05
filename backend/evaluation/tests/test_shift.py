"""`evaluate shift` (F3, F4): the changed study's direction and the label before and after a counterfactual
variant, per system, against variant.json's prediction."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from evaluation import shift as sh
from evaluation.score import score_answers

from . import fixtures as fx

VARIANT = {"base_corpus_id": "base", "corpus_id": "base-cf-S002-supports", "study": "S002", "paper": "S002",
           "from": "contradicts", "to": "supports",
           "changed": [{"measurement": "S002.m2", "from": 0.25, "to": 0.15}],
           "expected": {"before": {"label": "mixed", "counts": {"supporting": 1, "contradicting": 1, "neutral": 0}},
                        "after": {"label": "supported", "counts": {"supporting": 2, "contradicting": 0, "neutral": 0}},
                        "label_changes": True}}


def corpora(tmp_path: Path) -> tuple[Path, Path]:
    base = fx.write_corpus(tmp_path / "a", corpus_id="base")
    variant = fx.write_corpus(tmp_path / "b", corpus_id="base-cf-S002-supports")
    truth = fx.ground_truth("base-cf-S002-supports")
    truth["studies"][1]["effect"].update(direction="supports", delta=0.05)
    truth["answer"] = {"label": "supported", "supporting": ["S001", "S002"], "contradicting": [], "neutral": []}
    fx.dump(variant / "ground_truth.json", truth)
    return base, variant


def reports(tmp_path: Path, before: dict[str, dict[str, str]], after: dict[str, dict[str, str]],
            labels: dict[str, tuple[str, str]]) -> tuple[dict[str, Any], dict[str, Any]]:
    base, variant = corpora(tmp_path)
    out = []
    for corpus, directions, idx in ((base, before, 0), (variant, after, 1)):
        paths = []
        for system, dirs in directions.items():
            path = tmp_path / f"{system}-{idx}.json"
            fx.dump(path, fx.baseline_answer(system, dirs, labels[system][idx]))
            paths.append(path)
        out.append(score_answers(corpus, paths))
    return out[0], out[1]


def test_shift_as_expected_and_not(tmp_path: Path) -> None:
    before = {"evidence-engine": {"S001": "supports", "S002": "contradicts"},
              "rag-baseline": {"S001": "supports", "S002": "contradicts"}}
    after = {"evidence-engine": {"S001": "supports", "S002": "supports"},
             "rag-baseline": {"S001": "supports", "S002": "contradicts"}}      # the baseline does not move
    base, variant = reports(tmp_path, before, after, {"evidence-engine": ("mixed", "supported"),
                                                      "rag-baseline": ("mixed", "mixed")})
    result = sh.shift(base, variant, VARIANT)
    engine, rag = result["systems"]
    assert engine["system"] == "evidence-engine" and engine["shifted_as_expected"] is True
    assert engine["direction"] == {"from": "contradicts", "to": "supports", "before": "contradicts", "after": "supports",
                                   "before_correct": True, "after_correct": True}
    assert engine["label"]["changed"] is True and engine["label"]["expected_change"] is True
    assert rag["shifted_as_expected"] is False
    assert (rag["direction"]["before_correct"], rag["direction"]["after_correct"]) == (True, False)
    assert (rag["label"]["before_correct"], rag["label"]["after_correct"], rag["label"]["changed"]) == (True, False, False)
    assert (result["study"], result["paper"], result["from"], result["to"]) == ("S002", "S002", "contradicts", "supports")
    assert result["label_changes"] is True and result["unmatched_systems"] == []
    text = sh.render(result)
    assert "## The changed study's direction" in text and "| evidence-engine" in text and "S002.m2: 0.25 -> 0.15" in text
    js, md = sh.write_shift(result, tmp_path / "out")
    assert js.name == "shift.json" and md.read_text(encoding="utf-8") == text


def test_a_paper_the_system_never_answers_is_undetermined_before_and_after(tmp_path: Path) -> None:
    base, variant = reports(tmp_path, {"agent-baseline": {"S001": "supports"}}, {"agent-baseline": {"S001": "supports"}},
                            {"agent-baseline": ("supported", "supported")})
    (agent,) = sh.shift(base, variant, VARIANT)["systems"]
    assert agent["direction"]["before"] == "undetermined" and agent["direction"]["after"] == "undetermined"
    assert agent["label"]["after_correct"] is True and agent["shifted_as_expected"] is False


def test_systems_in_only_one_report_are_listed_not_compared(tmp_path: Path) -> None:
    base, variant = reports(tmp_path, {"evidence-engine": {"S001": "supports", "S002": "contradicts"}},
                            {"rag-baseline": {"S001": "supports", "S002": "supports"}},
                            {"evidence-engine": ("mixed", "mixed"), "rag-baseline": ("supported", "supported")})
    result = sh.shift(base, variant, VARIANT)
    assert result["systems"] == [] and result["unmatched_systems"] == ["evidence-engine", "rag-baseline"]


def test_the_wrong_corpus_is_refused(tmp_path: Path) -> None:
    base, variant = reports(tmp_path, {"evidence-engine": {"S001": "supports", "S002": "contradicts"}},
                            {"evidence-engine": {"S001": "supports", "S002": "supports"}},
                            {"evidence-engine": ("mixed", "supported")})
    with pytest.raises(ValueError, match="base corpus id is base"):
        sh.shift(variant, base, VARIANT)
    spec = {**VARIANT, "expected": {"before": {"label": "mixed"}, "after": {"label": "supported"}}}
    assert sh.shift(base, variant, spec)["label_changes"] is True   # derived when variant.json leaves it out
