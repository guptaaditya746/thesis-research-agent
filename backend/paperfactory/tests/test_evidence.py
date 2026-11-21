"""#2: strict evidence rule next to the old (legacy) one. Fake models only."""
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
FILLER = " ".join(f"The parties argued about point number {i} of the dispute at some length." for i in range(14))
GOLD1 = "Pell v. Vantor Systems refused to treat section 9 as a ground for the monitoring."
GOLD2 = "In Pell the court again declined to rest the ruling on section 9."
P1 = f"{FILLER} {GOLD1} {FILLER}\n\nLater, {GOLD2[0].lower() + GOLD2[1:]}\n"
P2 = ("Rusk v. Oberline Health relied on section 14 of the Act.\n\n"
      "The parties argued about point number 3 of the dispute at some length.\n")


def run(tmp_path: Path, quote: str, paper: str = "L-03", answer: str = "rejects") -> dict:
    for pid, md in (("L-03", P1), ("L-01", P2)):
        (tmp_path / "work" / pid).mkdir(parents=True, exist_ok=True)
        (tmp_path / "work" / pid / "paper.md").write_text(md)
    s = config.Settings("law", "argument", out=str(tmp_path))
    _, g = seed.make(PILOT, LAW, per_question=3, seed=1)

    def fake(role, step, system, user, out, check=None):
        if role == "qa":
            return {"items": [{"paper": paper, "subject": "Pell v. Vantor Systems", "relation": "x",
                               "object": "section 9", "quote": quote, "answer_sentence": "Pell rejected s. 9."}]}
        return {"choice": answer}
    e = Eval(s, PILOT, LAW, g, fake)
    tagged = {}
    for pid, md in (("L-03", P1), ("L-01", P2)):
        S = [list(x) for x in split_sents(md, split_rules(LAW, PILOT))]
        spans = {"K4-rejects-S9": [x[:2] for x in S if x[2] in (GOLD1, "Later, " + GOLD2[0].lower() + GOLD2[1:])]}
        tagged[pid] = {"sentences": S, "spans": spans if pid == "L-03" else {}}
    assert len(tagged["L-03"]["spans"]["K4-rejects-S9"]) == 2
    q = {"id": "t", "text": "?", "papers": ["L-03", "L-01"], "gold": ["K4-rejects-S9"]}
    return e.qa_one(q, tagged)["items"][0]


def test_a_whole_paragraph_passes_legacy_but_fails_strict(tmp_path: Path) -> None:
    para = f"{FILLER} {GOLD1} {FILLER}"
    assert len(para.split()) > 169
    it = run(tmp_path, para)
    assert it["evidence_ok_legacy"] and not it["evidence_ok"] and it["evidence_reason"] == "too_long"
    assert it["correct_legacy"] and not it["correct"]


@pytest.mark.parametrize("quote", [GOLD1, "the court again declined to rest the ruling on section 9",
                                   "Pell v. Vantor Systems refused to treat section 9"])
def test_gold_sentence_other_mention_and_clause_pass(tmp_path: Path, quote: str) -> None:
    it = run(tmp_path, quote)
    assert it["evidence_ok"] and it["correct"], it["evidence_reason"]


def test_a_three_word_fragment_fails(tmp_path: Path) -> None:
    it = run(tmp_path, "as a ground")
    assert not it["evidence_ok"] and it["evidence_reason"] == "too_short"


def test_quote_outside_gold_and_not_found(tmp_path: Path) -> None:
    assert run(tmp_path, "Rusk v. Oberline Health relied on section 14 of the Act.", "L-01")["evidence_reason"] == \
        "outside_gold"
    assert run(tmp_path, "Pell v. Vantor Systems relied on nothing at all.")["evidence_reason"] == "not_found"


def test_a_quote_found_in_two_papers_is_ambiguous(tmp_path: Path) -> None:
    it = run(tmp_path, "The parties argued about point number 3 of the dispute at some length.")
    assert it["evidence_reason"] == "ambiguous_quote" and not it["evidence_ok"]


def test_thresholds_come_from_the_settings(tmp_path: Path) -> None:
    s = config.Settings("law", "argument")
    assert s.evidence == {"min_inside": 0.9, "min_sentence_cover": 0.5}
