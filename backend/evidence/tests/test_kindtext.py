"""A fixed kind's answer as short lines in plain words (evidence/kindtext.py)."""
from __future__ import annotations

from typing import Any

import pytest

from evidence.kinds.best import REASONS as BEST_REASONS
from evidence.kinds.best import reason as best_reason
from evidence.kindtext import CANT_TELL_LINE, MAX_KIND_LINES, RULE_TEXT, kind_lines, plan_names
from evidence.plan import with_answer
from evidence.plankinds import kind_protocol
from evidence.planrun import protocol_for
from evidence.protocol import parse
from evidence.tests.test_plan_run import make_plan

NAMES = plan_names(make_plan())


def effect_protocol():
    return parse(protocol_for(make_plan()).decode("utf-8"))


def _kind(by: str, target: str | None = None):
    return parse(kind_protocol(with_answer(make_plan(), by, target)).decode("utf-8"))


def inventory_protocol():
    return _kind("inventory", "condition")


def best_protocol():
    return _kind("best")


def consistency_protocol():
    return _kind("consistency")


def item(n: int, kind: str = "m") -> str:
    return f"{kind}-{n:016x}"


def doc(n: int) -> str:
    return f"S{n:03d}"


def effect_answer(studies: int = 2, label: str = "supported") -> dict[str, Any]:
    """The shape of synthesis.answer: studies with a treatment and a control pair, and the document groups."""
    rows = []
    for n in range(1, studies + 1):
        rows.append({"document": doc(n), "direction": "supports", "delta": 0.1, "metric": "accuracy",
                     "treatment": {"condition": item(n, "c"), "measurement": item(n), "value": 0.8},
                     "control": {"condition": item(n + 1000, "c"), "measurement": item(n + 1000), "value": 0.7},
                     "author_claim": None, "reason": None, "flags": [], "duplicate_of": None,
                     "funnel": {"screened": False, "stopped_after": None}})
    supporting = [r["document"] for r in rows]
    return {"system": "evidence-engine", "question": "Does retrieval help?", "label": label,
            "counts": {"supporting": len(supporting), "contradicting": 0, "neutral": 0, "undetermined": 0,
                       "duplicates": 0},
            "studies": rows, "supporting": supporting, "contradicting": [], "neutral": [], "undetermined": [],
            "duplicates": [], "flags": {}}


def inventory_answer(entries: int = 3) -> dict[str, Any]:
    return {"kind": "inventory", "system": "evidence-engine", "target": "condition",
            "entries": [{"name": f"name {n}", "aliases": [f"alias {n}"] if n % 2 else [],
                         "papers": [doc(n), doc(n + 1)], "items": [item(n, "c")]} for n in range(entries)]}


def best_answer(winner: str | None = "rag", comparisons: int = 3) -> dict[str, Any]:
    """winner=None with comparisons: the papers split their wins, so no kind is best (tied lists both kinds)."""
    values = {"rag": 0.8, "closed_book": 0.7}
    base = {"kind": "best", "system": "evidence-engine", "metric": "accuracy"}
    if comparisons == 0:
        studies = [{"document": doc(1), "winner": None, "tied": [], "values": {},
                    "reason": best_reason("no_comparison", best_protocol().best)}]
        return {**base, "studies": studies, "wins": {}, "winner": None, "tied": []}
    if winner is None:
        studies = [{"document": doc(n), "winner": ("rag", "closed_book")[n % 2], "tied": [], "values": values,
                    "reason": None} for n in range(1, comparisons + 1)]
        return {**base, "studies": studies, "wins": {"rag": comparisons // 2, "closed_book": comparisons - comparisons // 2},
                "winner": None, "tied": ["closed_book", "rag"]}
    studies = [{"document": doc(n), "winner": winner, "tied": [], "values": values, "reason": None}
               for n in range(1, comparisons + 1)]
    return {**base, "studies": studies, "wins": {winner: comparisons}, "winner": winner, "tied": []}


def consistency_answer(checkable: bool = True) -> dict[str, Any]:
    if not checkable:
        studies = [{"document": doc(1), "claim": None, "direction": "undetermined", "agrees": None,
                    "reason": {"code": "no_pair", "text": "no pair of values"}}]
        return {"kind": "consistency", "system": "evidence-engine", "metric": "accuracy", "studies": studies,
                "agreeing": [], "disagreeing": [], "undetermined": [doc(1)]}
    studies = [{"document": doc(1), "claim": "supports", "direction": "supports", "agrees": True, "reason": None},
               {"document": doc(2), "claim": None, "direction": "undetermined", "agrees": None,
                "reason": {"code": "no_pair", "text": "no pair of values"}},
               {"document": doc(3), "claim": "supports", "direction": "contradicts", "agrees": False, "reason": None}]
    return {"kind": "consistency", "system": "evidence-engine", "metric": "accuracy", "studies": studies,
            "agreeing": [doc(1)], "disagreeing": [doc(3)], "undetermined": [doc(2)]}


def test_effect_lines_use_names_and_each_study():
    lines = kind_lines(effect_protocol(), effect_answer(studies=3), NAMES)
    assert lines[0].text == ("retrieval-augmented model against closed-book model on answer accuracy: "
                             "retrieval-augmented model does better.")
    studies = [l for l in lines if l.study]
    assert len(studies) == 3 and all(l.items for l in studies)
    assert studies[0].text == "S001: better on answer accuracy (0.8 against 0.7)."
    assert "Papers that show it better: S001, S002, S003." in [l.text for l in lines]
    assert not any(w in l.text for l in lines for w in ("rag ", "closed_book", "Answer by"))


def test_forty_studies_stay_under_the_judge_cut():
    text = "\n".join(l.text for l in kind_lines(effect_protocol(), effect_answer(studies=40), NAMES))
    assert len(text) < 12_000 and "evidence-engine" not in text and "plan-" not in text
    assert effect_answer()["question"] not in text and "Does retrieval" not in text


def test_long_inventories_are_cut_with_a_count():
    lines = kind_lines(inventory_protocol(), inventory_answer(entries=200), NAMES)
    assert len(lines) == MAX_KIND_LINES + 1 and lines[-1].text == f"... and {200 - (MAX_KIND_LINES - 1)} more."


@pytest.mark.parametrize("protocol, answer", [
    (effect_protocol, lambda: effect_answer(studies=2, label="insufficient")),
    (inventory_protocol, lambda: inventory_answer(entries=0)),
    (best_protocol, lambda: best_answer(winner=None, comparisons=0)),
    (consistency_protocol, lambda: consistency_answer(checkable=False)),
])
def test_every_kind_says_cant_tell_in_plain_words(protocol, answer):
    assert CANT_TELL_LINE in [l.text for l in kind_lines(protocol(), answer(), NAMES)]


def test_best_and_consistency_summaries():
    assert kind_lines(best_protocol(), best_answer(winner="rag"), NAMES)[0].text.startswith(
        "On answer accuracy, retrieval-augmented model is best in the most papers (")
    lines = kind_lines(consistency_protocol(), consistency_answer(checkable=True), NAMES)
    assert lines[0].text == ("On answer accuracy, the authors' claims agree with their numbers in S001; "
                             "disagree in S003; cannot be checked in S002.")
    assert [l.text for l in lines[1:]] == [
        "S001: the authors say better, the numbers say better.",
        "S002: cannot be checked (no retrieval-augmented model and closed-book model measurement on a question metric).",
        "S003: the authors say better, the numbers say worse."]


def test_inventory_lines_list_names_aliases_and_item_ids():
    lines = kind_lines(inventory_protocol(), inventory_answer(entries=2), NAMES)
    assert [l.text for l in lines] == ["2 distinct names of compared things.", "name 0: S000, S001.",
                                       "name 1 (also alias 1): S001, S002."]
    assert lines[1].items == [item(0, "c")] and not lines[0].study


def test_rule_text_has_the_six_rules():
    assert set(RULE_TEXT) == {"effect", "consistency", "inventory", "best", "written", "lines"}
    assert RULE_TEXT["lines"].format(rule="x") == "The plan's main rule: x."


def effect_with(label: str, **groups: list[str]) -> dict[str, Any]:
    answer = effect_answer(studies=0, label=label)
    answer.update(groups)
    return answer


@pytest.mark.parametrize("label, said", [
    ("refuted", "retrieval-augmented model does worse."), ("no_effect", "no real difference."),
    ("mixed", "the papers disagree.")])
def test_effect_labels_in_plain_words(label, said):
    head = "retrieval-augmented model against closed-book model on answer accuracy: "
    assert kind_lines(effect_protocol(), effect_with(label), NAMES)[0].text == head + said


def test_effect_groups_and_unreadable_study_lines():
    answer = effect_with("mixed", contradicting=["S002"], neutral=["S003"], undetermined=["S004"],
                         duplicates=["S005"])
    answer["studies"] = [{"document": "S004", "direction": "undetermined", "metric": None, "treatment": None,
                          "control": None, "reason": {"code": "no_pair", "text": "no pair of values"}},
                         {"document": "S002", "direction": "contradicts", "metric": "accuracy",
                          "treatment": {"value": 0.5}, "control": {"value": 0.6}}]
    texts = [l.text for l in kind_lines(effect_protocol(), answer, NAMES)]
    assert texts[1:] == ["Papers that show it worse: S002.", "Papers that show no real difference: S003.",
                         "Papers that could not be read: S004.", "Papers that repeat an earlier paper: S005.",
                         "S004: could not be read (no retrieval-augmented model and closed-book model measurement on a question metric).",
                         "S002: worse on answer accuracy (0.5 against 0.6)."]


def test_best_tie_and_no_comparison_lines():
    lines = kind_lines(best_protocol(), best_answer(winner=None, comparisons=2), NAMES)
    assert lines[0].text == ("On answer accuracy, no single kind is best: closed-book model, "
                             "retrieval-augmented model tie.")
    texts = [l.text for l in kind_lines(best_protocol(), best_answer(winner=None, comparisons=0), NAMES)]
    assert texts == [CANT_TELL_LINE, "S001: no comparison (no dataset with values of two method kinds on answer accuracy)."]
    tied = best_answer()
    tied["studies"][0].update(winner=None, tied=["rag", "closed_book"])
    assert kind_lines(best_protocol(), tied, NAMES)[1].text == (
        "S001: retrieval-augmented model, closed-book model tie.")


def test_inventory_of_measures():
    answer = inventory_answer(entries=1)
    answer["target"] = "metric"
    assert kind_lines(inventory_protocol(), answer, NAMES)[0].text == "1 distinct names of measures."


def test_a_reason_without_text_never_prints_its_code():
    answer = consistency_answer(checkable=False)
    answer["studies"][0]["reason"] = {"code": "no_pair"}
    texts = [l.text for l in kind_lines(consistency_protocol(), answer, NAMES)]
    assert "S001: cannot be checked (no reason given)." in texts and not any("no_pair" in t for t in texts)


def test_an_effect_reason_of_a_known_code_names_the_thing_not_its_id():
    answer = effect_with("mixed")
    answer["studies"] = [{"document": "S004", "direction": "undetermined", "metric": None, "treatment": None,
                          "control": None,
                          "reason": {"code": "no_treatment_condition", "text": "no rag condition found"}}]
    texts = [l.text for l in kind_lines(effect_protocol(), answer, NAMES)]
    assert "S004: could not be read (no retrieval-augmented model condition found)." in texts


@pytest.mark.parametrize("code", sorted(BEST_REASONS))
def test_a_best_reason_names_the_measure_not_its_id(code):
    protocol = best_protocol()
    answer = best_answer(winner=None, comparisons=0)
    answer["studies"][0]["reason"] = best_reason(code, protocol.best)   # the kind's own reason, as a run writes it
    line = kind_lines(protocol, answer, NAMES)[1].text
    want = BEST_REASONS[code].format(metric="answer accuracy")
    assert line == f"S001: no comparison ({want})."
    assert "accuracy" not in line.replace("answer accuracy", "")   # the id "accuracy" never stands alone
