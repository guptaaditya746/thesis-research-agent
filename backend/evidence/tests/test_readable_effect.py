"""The readable program's rules for effect and consistency: copied from the engine, pinned to it, standard library
only."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import evidence.readable.rules
from evidence import kindtext, rules, synthesis
from evidence.kinds import best, consistency
from evidence.readable.inputs import effect_inputs
from evidence.readable.rules import common, effect as rules_effect
from evidence.readable.runview import answer_text, checked_view
from evidence.tests.readable_cases import case_answer, case_protocol, stdlib_only, study_items

ALLOWED = set(sys.stdlib_module_names) | {"__future__"}


def rebuilt(ra):
    i = effect_inputs(ra)
    view = rules_effect.rebuild_answer(i.settings, i.facts, i.papers, i.model_text)
    return view, rules_effect.answer_lines(i.settings, view, i.names)


def test_effect_rebuilds_label_counts_flags_and_lines():
    p = case_protocol()
    by_paper = {"S001": study_items("S001", 0.62, 0.50, claim="improves"),
                "S002": study_items("S002", 0.40, 0.55, claim="improves"),    # the claim disagrees
                "S003": study_items("S003", 0.62, 0.50),                      # repeats S001
                "S004": study_items("S004", 0.505, 0.50),                     # inside the neutral band
                "S005": study_items("S005", 0.70, None),                      # no control
                "S006": study_items("S006", 1.40, 0.50)}                      # a large effect
    ra = case_answer(p, by_paper, "effect")
    view, lines = rebuilt(ra)
    assert view == checked_view(ra) and "\n".join(lines) == answer_text(ra)
    assert view["duplicates"] == ["S003"] and view["undetermined"] == ["S005"]
    assert view["flags"]["claim_disagrees"] == ["S002"] and view["flags"]["large_effect"] == ["S006"]


def test_the_condition_pattern_and_flag_names_are_the_engines():
    """M4: the copied condition pattern and flag names are pinned to the engine's, and both read a condition alike."""
    assert rules_effect.CONDITION_PATTERN.pattern == rules.CONDITION.pattern
    assert rules_effect.FLAG_NAMES == rules.FLAGS
    for condition, value in ((">=2", 2), (" < 3 ", 3), ("==0", 1)):
        assert rules_effect.condition_holds(condition, value) == rules.condition_holds(condition, value)
    with pytest.raises(ValueError):
        rules_effect.condition_holds("2+", 1)


def test_numbers_keep_their_form():
    p = case_protocol(direction="lower")
    ra = case_answer(p, {"S001": study_items("S001", 10, 12), "S002": study_items("S002", 1e-05, 2e-05),
                         "S003": study_items("S003", 0.1234564, 0.1234561)}, "effect")
    view, lines = rebuilt(ra)
    assert view == checked_view(ra) and "\n".join(lines) == answer_text(ra)
    assert common.values_sha256(view) == common.values_sha256(checked_view(ra))   # 10 stays 10, never 10.0


def test_no_readable_paper_says_cant_tell():
    ra = case_answer(case_protocol(), {"S001": study_items("S001", None, 0.5)}, "effect")
    view, lines = rebuilt(ra)
    assert view["label"] == "insufficient" and lines[0] == common.CANT_TELL_LINE and view == checked_view(ra)


def test_consistency_rebuilds_agreement_and_no_claim():
    p = case_protocol("consistency")
    ra = case_answer(p, {"S001": study_items("S001", 0.62, 0.5, claim="improves"),
                         "S002": study_items("S002", 0.40, 0.55, claim="improves"),
                         "S003": study_items("S003", 0.62, 0.4),
                         "S004": study_items("S004", None, 0.5, claim="worsens")}, "consistency")
    view, lines = rebuilt(ra)
    assert view == checked_view(ra) and "\n".join(lines) == answer_text(ra)
    assert view["agreeing"] == ["S001"] and view["disagreeing"] == ["S002"]
    # review round 1, engine-C1: the claim is in the claim words (improves), not a direction
    assert lines[1:3] == ["S001: the authors say better, the numbers say better.",
                          "S002: the authors say better, the numbers say worse."]
    assert view["studies"][2]["reason"] == {"code": "no_claim", "text": "no author claim found"}


def test_repeats_use_the_experiment_setting():
    rows = [("S1", "a", 1.0, 2.0, "x"), ("S2", "a", 1.0, 2.0, "y"), ("S3", "a", 1.0004, 2.0, "x"),
            ("S4", "a", 1, 2, None)]
    assert rules_effect.repeated_studies(rows) == rules.duplicates(rows) == {"S3": "S1"}


def test_the_copies_match_the_engine():
    assert common.REASON_TEMPLATES == synthesis.REASONS and common.BEST_REASON_TEMPLATES == best.REASONS
    assert (common.CANT_TELL_LINE, common.MAX_KIND_LINES) == (kindtext.CANT_TELL_LINE, kindtext.MAX_KIND_LINES)
    assert (common.SAYS, common.LABEL_TEXT, common.GROUPS, common.INVENTORY_TARGETS) == (
        kindtext.SAYS, kindtext.LABEL_TEXT, kindtext.GROUPS, kindtext.INVENTORY_TARGETS)
    assert rules_effect.NO_CLAIM == consistency.NO_CLAIM and rules_effect.VALUE_DECIMALS == rules.VALUE_DECIMALS


@pytest.mark.parametrize("name", ["common", "effect"])
def test_a_rule_file_imports_only_the_standard_library(name):
    assert stdlib_only(Path(evidence.readable.rules.__file__).parent / f"{name}.py") <= ALLOWED
