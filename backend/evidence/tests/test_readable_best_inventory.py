"""The readable program's rules for best and inventory: copied from the engine, pinned to it, standard library only."""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

import evidence.readable.inputs as inputs_module
import evidence.readable.rules
from evidence.plan import with_answer
from evidence.readable import NotRebuilt, inputs_of, refusal
from evidence.readable.rules import best as rules_best, common, inventory as rules_inventory
from evidence.readable.runview import answer_text, checked_view
from evidence.tests.readable_cases import best_items, case_answer, case_protocol, stdlib_only, study_items
from evidence.tests.test_plan_run import clean_registry, make_plan, plan_run  # noqa: F401  (autouse fixture)

ALLOWED = set(sys.stdlib_module_names) | {"__future__"}
RULES = {"best": rules_best, "inventory": rules_inventory}


def rebuilt(ra):
    i = inputs_of(ra)
    rules = RULES[ra.kind]
    view = rules.rebuild_answer(i.settings, i.facts, i.papers, i.model_text)
    return view, rules.answer_lines(i.settings, view, i.names)


def test_best_rebuilds_wins_ties_and_reasons():
    p = case_protocol("best")
    ra = case_answer(p, {"S001": best_items("S001", {"rag": 0.7, "closed_book": 0.6}),
                         "S002": best_items("S002", {"rag": 0.5, "closed_book": 0.5}),           # a tie
                         "S003": best_items("S003", {"rag": 0.8, "closed_book": 0.4}, kind_field=False),
                         "S004": best_items("S004", {"rag": 0.9})}, "best")                       # one kind only
    view, lines = rebuilt(ra)
    assert view == checked_view(ra) and "\n".join(lines) == answer_text(ra)
    assert view["wins"] == {"rag": 2} and view["studies"][1]["tied"] == ["closed_book", "rag"]
    assert view["studies"][3]["reason"]["code"] == "too_few_kinds"


def test_best_where_lower_is_better_rebuilds_and_prints_as_the_engine():
    """M10: a measure where lower is better: the lower value wins, in the rebuild as in the engine."""
    from evidence.kinds import best as best_kind
    p = case_protocol("best", direction="lower")
    assert best_kind.spec(p).metric.higher_is_better is False
    ra = case_answer(p, {"S001": best_items("S001", {"rag": 0.7, "closed_book": 0.6}),
                         "S002": best_items("S002", {"rag": 0.3, "closed_book": 0.5})}, "best")
    view, lines = rebuilt(ra)
    assert view == checked_view(ra) and "\n".join(lines) == answer_text(ra)
    assert [s["winner"] for s in view["studies"]] == ["closed_book", "rag"]
    assert inputs_of(ra).settings["higher_is_better"] is False


def test_best_whole_number_values_are_compared_as_the_engine_stores_them():
    ra = case_answer(case_protocol("best"), {"S001": best_items("S001", {"rag": 45, "closed_book": 5})}, "best")
    view, lines = rebuilt(ra)
    assert view == checked_view(ra) and view["studies"][0]["values"] == {"rag": 45.0, "closed_book": 5.0}
    assert common.values_sha256(view) == common.values_sha256(checked_view(ra))


def test_a_pair_that_cannot_be_found_again_is_a_refusal(monkeypatch):
    ra = case_answer(case_protocol("consistency"), {"S001": study_items("S001", 0.62, 0.5, claim="improves")},
                     "consistency")
    ra = dataclasses.replace(ra, answer={**ra.answer, "studies": [{**ra.answer["studies"][0],
                                                                    "direction": "contradicts"}]})
    with pytest.raises(NotRebuilt, match="the pair the run used for S001 could not be found again"):
        inputs_of(ra)


def test_best_values_that_cannot_be_found_again_are_a_refusal():
    ra = case_answer(case_protocol("best"), {"S001": best_items("S001", {"rag": 0.7, "closed_book": 0.6})}, "best")
    ra = dataclasses.replace(ra, answer={**ra.answer, "studies": [{**ra.answer["studies"][0], "winner": "closed_book"}]})
    with pytest.raises(NotRebuilt, match="the values the run used for S001 could not be found again"):
        inputs_of(ra)


def test_refusal_also_builds_the_inputs(tmp_path, monkeypatch):
    root = plan_run(tmp_path, with_answer(make_plan(), "best", None))
    assert refusal(root) is None
    monkeypatch.setattr(inputs_module, "best_inputs", lambda ra: (_ for _ in ()).throw(NotRebuilt("not again")))
    assert refusal(root) == "not again"


def test_refusal_never_raises_without_a_corpus_or_with_an_unreadable_answer(tmp_path):
    root = plan_run(tmp_path, with_answer(make_plan(), "best", None))
    assert refusal(tmp_path / "no-such-run")                                  # a text, not an exception
    (root / "answer.json").write_text("{not json", encoding="utf-8")
    text = refusal(root)
    assert isinstance(text, str) and text


def test_refusal_names_a_missing_corpus(tmp_path, monkeypatch):
    root = plan_run(tmp_path, with_answer(make_plan(), "best", None))
    from evidence import rundir
    monkeypatch.setattr(rundir.RunDir, "settings", property(lambda self: None))
    text = refusal(root)
    assert text and "corpus" in text


def test_best_with_no_comparison_says_cant_tell():
    ra = case_answer(case_protocol("best"), {"S001": best_items("S001", {"rag": 0.9})}, "best")
    assert rebuilt(ra)[1][0] == common.CANT_TELL_LINE


@pytest.mark.parametrize("target", ["condition", "metric"])
def test_inventory_rebuilds_names_aliases_and_papers(target):
    p = case_protocol("inventory", target)
    by_paper = {"S001": study_items("S001", 0.6, 0.5, t_label="Method K", c_label="usual  method"),
                "S002": study_items("S002", 0.6, 0.5, t_label="method k", c_label="Usual method")}
    ra = case_answer(p, by_paper, "inventory")
    view, lines = rebuilt(ra)
    assert view == checked_view(ra) and "\n".join(lines) == answer_text(ra)


def test_long_inventories_are_cut_like_the_engine():
    p = case_protocol("inventory", "condition")
    by_paper = {f"S{i:03d}": study_items(f"S{i:03d}", 0.6, 0.5, t_label=f"Method {i}", c_label=f"Usual {i}")
                for i in range(1, 80)}
    ra = case_answer(p, by_paper, "inventory")
    view, lines = rebuilt(ra)
    assert len(lines) == common.MAX_KIND_LINES + 1 and "\n".join(lines) == answer_text(ra)


@pytest.mark.parametrize("name", ["best", "inventory"])
def test_a_rule_file_imports_only_the_standard_library(name):
    assert stdlib_only(Path(evidence.readable.rules.__file__).parent / f"{name}.py") <= ALLOWED
