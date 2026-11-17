"""A fixed kind's answer as short lines in plain words (evidence/kindtext.py)."""
from __future__ import annotations

from typing import Any

import pytest

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
    studies = [{"document": doc(n), "winner": winner or "closed_book", "tied": [], "values": {"rag": 0.8,
               "closed_book": 0.7}, "reason": None} for n in range(1, comparisons + 1)]
    if comparisons == 0:
        studies = [{"document": doc(1), "winner": None, "tied": [], "values": {},
                    "reason": {"code": "no_comparison", "text": "no dataset has values of two kinds"}}]
    wins = {winner: comparisons} if winner and comparisons else {}
    return {"kind": "best", "system": "evidence-engine", "metric": "accuracy", "studies": studies, "wins": wins,
            "winner": winner if comparisons else None, "tied": []}


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
        "S002: cannot be checked (no pair of values).",
        "S003: the authors say better, the numbers say worse."]


def test_inventory_lines_list_names_aliases_and_item_ids():
    lines = kind_lines(inventory_protocol(), inventory_answer(entries=2), NAMES)
    assert [l.text for l in lines] == ["2 distinct names of compared things.", "name 0: S000, S001.",
                                       "name 1 (also alias 1): S001, S002."]
    assert lines[1].items == [item(0, "c")] and not lines[0].study


def test_rule_text_has_the_six_rules():
    assert set(RULE_TEXT) == {"effect", "consistency", "inventory", "best", "written", "lines"}
    assert RULE_TEXT["lines"].format(rule="x") == "The plan's main rule: x."
