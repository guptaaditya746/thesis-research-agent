"""QA scoring with fake models (no model calls)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperfactory import config, packs, seed
from paperfactory.evaluate import Eval
from paperfactory.text import split_rules, split_sents

HERE = Path(__file__).resolve().parents[1]
PILOT = json.loads((HERE / "worlds" / "law-pilot.json").read_text())
LAW = packs.field("law")
LETTER = {"relies_on": "A", "distinguishes": "B", "rejects": "C", "none": "D"}
PAPER = ("Rusk v. Oberline Health distinguished Marrin v. Tolst Media on its facts in this case.\n\n"
         "The Supreme Court took section 14 as the basis of its ruling in Rusk.\n")


def run_qa(tmp_path: Path, item: dict, judge: str = "distinguishes", gold=("K5-distinguishes-K1",)) -> dict:
    (tmp_path / "work" / "L-01").mkdir(parents=True)
    (tmp_path / "work" / "L-01" / "paper.md").write_text(PAPER)
    s = config.Settings("law", "argument", out=str(tmp_path))
    _, g = seed.make(PILOT, LAW, per_question=3, seed=1)
    judged: list[str] = []

    def fake(role, step, system, user, schema):
        if role == "qa":
            return {"items": [{"paper": "L-01", "relation": "x", "answer_sentence": "Rusk distinguished it.",
                               "quote": "Rusk v. Oberline Health distinguished Marrin v. Tolst Media", **item}]}
        judged.append(json.loads(user)["source"])
        return {"choice": LETTER[judge]}
    e = Eval(s, PILOT, LAW, g, fake)
    tagged = {"L-01": {"sentences": [list(x) for x in split_sents(PAPER, split_rules(LAW, PILOT))], "spans": {}}}
    q = {"id": "t", "text": "?", "papers": ["L-01"], "gold": list(gold)}
    out = e.qa_one(q, tagged)["items"][0]
    out["judged_sources"] = judged
    return out


def test_citation_in_brackets_resolves_to_the_decision_not_the_court(tmp_path: Path) -> None:
    it = run_qa(tmp_path, {"subject": "Rusk v. Oberline Health (Supreme Court of Veldra, 2023)",
                           "object": "Marrin v. Tolst Media (Veldra Court of Appeal, 2019)"})
    assert it["as_fact"] == "K5-distinguishes-K1" and it["answer_right"]
    assert it["resolution"] == "resolved"


@pytest.mark.parametrize("obj", ["Veldra Court of Appeal", "the Supreme Court of Veldra", "the Court of Appeal"])
def test_a_court_is_never_an_object(tmp_path: Path, obj: str) -> None:
    it = run_qa(tmp_path, {"subject": "Rusk v. Oberline Health", "object": obj, "quote": "section 14 as the basis"},
                judge="relies_on")
    assert it["as_fact"] != "K5-relies_on-CT1" and "CT" not in str(it["as_fact"])
    assert it["as_fact"] == "K5-relies_on-S14"          # falls back to the quote, which names a valid object


def test_a_newer_decision_is_never_an_object(tmp_path: Path) -> None:
    # Marrin (2019) cannot treat Rusk (2023)
    it = run_qa(tmp_path, {"subject": "Marrin v. Tolst Media", "object": "Rusk v. Oberline Health",
                           "quote": "distinguished Marrin v. Tolst Media on its facts"})
    assert it["as_fact"] is None and it["resolution"] == "no_valid_object"
    assert it["judged_sources"] == []


def test_judge_none_gives_no_fact(tmp_path: Path) -> None:
    it = run_qa(tmp_path, {"subject": "Rusk", "object": "Marrin"}, judge="none")
    assert it["as_fact"] is None and it["resolution"] == "relation_none"


def test_relation_not_allowed_for_the_object_kind(tmp_path: Path) -> None:
    it = run_qa(tmp_path, {"subject": "Rusk", "object": "section 14"}, judge="distinguishes")
    assert it["as_fact"] is None and it["resolution"] == "invalid_fact"


def test_several_objects_go_to_the_judge_one_by_one(tmp_path: Path) -> None:
    it = run_qa(tmp_path, {"subject": "Rusk", "object": "Marrin and section 14"}, judge="distinguishes")
    # distinguishes fits Marrin (a decision) but not section 14 (a provision): one candidate survives
    assert it["resolution"] == "resolved_by_judge" and it["as_fact"] == "K5-distinguishes-K1"
    assert sorted(it["object_candidates"]) == ["K1", "S14"]
