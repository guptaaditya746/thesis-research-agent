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
LETTER = {"relies_on": "relies_on", "distinguishes": "distinguishes", "rejects": "rejects", "none": "none"}
PAPER = ("Rusk v. Oberline Health distinguished Marrin v. Tolst Media on its facts in this case.\n\n"
         "The Supreme Court took section 14 as the basis of its ruling in Rusk.\n")


def run_qa(tmp_path: Path, item: dict, judge: str = "distinguishes", gold=("K5-distinguishes-K1",)) -> dict:
    (tmp_path / "work" / "L-01").mkdir(parents=True)
    (tmp_path / "work" / "L-01" / "paper.md").write_text(PAPER)
    s = config.Settings("law", "argument", out=str(tmp_path))
    _, g = seed.make(PILOT, LAW, per_question=3, seed=1)
    judged: list[str] = []

    def fake(role, step, system, user, schema, check=None):
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


# ------------------------------------------------------------------ #1 alias tables per paper
from paperfactory import text  # noqa: E402

ORD_PAPER = ("Ostra Bank v. Kelvig relied on section 9 of the Veldra Personal Data Act 2016 in this case.\n\n"
             "The clerk's consent was taken as the basis, and the decision also drew on the Ordinance.\n")


def test_head_noun_alias_from_the_pack() -> None:
    tab = text.alias_table(PILOT, LAW)
    assert [m.eid for m in text.find_mentions("the decision also drew on the Ordinance.", tab)] == ["WMO"]
    assert "the Act" in tab.ambiguous            # section 9, 14 and 21 all end in "... Act 2016": never used


def test_first_party_alias_and_shared_first_party_is_ambiguous() -> None:
    import copy
    w = copy.deepcopy(PILOT)
    w["entities"]["K4"]["alt"] = []
    assert [m.eid for m in text.find_mentions("Pell rejected it.", text.alias_table(w, LAW))] == ["K4"]
    w["entities"]["K7"] = {"kind": "decision", "label": "Pell v. Arnot Freight", "alt": [],
                           "attrs": {"court": "CT3", "year": 2024, "facts": "x"}}
    tab = text.alias_table(w, LAW)
    assert text.find_mentions("Pell rejected it.", tab) == [] and tab.ambiguous["pell"] == ["K4", "K7"]


def test_terms_defined_in_the_paper() -> None:
    import copy
    w = copy.deepcopy(PILOT)
    w["entities"]["WMO"]["alt"] = []
    md = ('The Workplace Monitoring Ordinance 2018 (the "Monitoring Rules") applies. '
          "Section 21 of the Veldra Personal Data Act 2016 (VPDA-21) is also relevant to it.\n")
    extra = text.defined_terms(text.normalize_paper(md).text, text.alias_table(w, LAW), LAW)
    assert extra == {"Monitoring Rules": "WMO", "VPDA-21": "S21"}


def test_ordinance_tag_is_kept_and_the_answer_scores_correct(tmp_path: Path) -> None:
    (tmp_path / "work" / "L-03").mkdir(parents=True)
    (tmp_path / "work" / "L-03" / "paper.md").write_text(ORD_PAPER)
    s = config.Settings("law", "argument", out=str(tmp_path))
    _, g = seed.make(PILOT, LAW, per_question=3, seed=1)
    sents = split_sents(ORD_PAPER, split_rules(LAW, PILOT))

    def fake(role, step, system, user, schema, check=None):
        if role == "tagger":
            return {"tags": [{"id": "K3-relies_on-WMO", "sentences": [1]}]}
        if role == "verifier":
            return {"answers": [{"id": x["id"], "verdict": "yes"} for x in json.loads(user)]}
        if role == "qa":
            return {"items": [{"paper": "L-03", "subject": "Ostra Bank v. Kelvig", "relation": "relied on",
                               "object": "Workplace Monitoring Ordinance 2018", "quote": sents[1][2],
                               "answer_sentence": "Ostra Bank relied on the Ordinance."}]}
        return {"choice": LETTER["relies_on"]}
    e = Eval(s, PILOT, LAW, g, fake)
    t = e.tag_paper("L-03")
    assert t["spans"]["K3-relies_on-WMO"] == [list(sents[1][:2])]
    assert (tmp_path / "work" / "L-03" / "paper.aliases.json").is_file()
    q = {"id": "L-03:relied", "text": "?", "papers": ["L-03"], "gold": ["K3-relies_on-WMO"]}
    it = e.qa_one(q, {"L-03": t})["items"][0]
    assert it["provenance"] == "gold_span" and it["correct"]


def test_a_tag_with_an_unknown_name_goes_to_the_verifier_not_the_bin(tmp_path: Path) -> None:
    md = "Ostra Bank v. Kelvig was decided in this way.\n\nThe bank's rulebook was its basis for the ruling.\n"
    (tmp_path / "work" / "L-03").mkdir(parents=True)
    (tmp_path / "work" / "L-03" / "paper.md").write_text(md)
    sent_to_verifier: list[str] = []

    def fake(role, step, system, user, schema, check=None):
        if role == "tagger":
            return {"tags": [{"id": "K3-relies_on-WMO", "sentences": [1]}]}
        sent_to_verifier.extend(x["sentence"] for x in json.loads(user))
        return {"answers": [{"id": x["id"], "verdict": "yes"} for x in json.loads(user)]}
    _, g = seed.make(PILOT, LAW, per_question=3, seed=1)
    t = Eval(config.Settings("law", "argument", out=str(tmp_path)), PILOT, LAW, g, fake).tag_paper("L-03")
    assert "The bank's rulebook was its basis for the ruling." in sent_to_verifier
    assert any("unknown_name" in n for n in t["code_notes"])
