"""Text handling: Markdown normalization and sentence splitting (#10). No model calls."""
from __future__ import annotations

import json
from pathlib import Path

from paperfactory import packs, text

HERE = Path(__file__).resolve().parents[1]
PILOT = json.loads((HERE / "worlds" / "law-pilot.json").read_text())
LAW, MED = packs.field("law"), packs.field("medicine")
MED_WORLD = {"entities": {
    "T1": {"kind": "trial", "label": "the CORVA-2 trial", "alt": ["CORVA-2"], "attrs": {}},
    "D1": {"kind": "treatment", "label": "zorvimab", "alt": [], "attrs": {}}}}


def sents(md: str, f=LAW, w=PILOT) -> list[str]:
    return [s[2] for s in text.split_sents(md, text.split_rules(f, w))]


def test_lowercase_drug_name_starts_a_sentence() -> None:
    md = "The trial enrolled 300 patients. zorvimab reduced events by a third in the CORVA-2 trial.\n"
    assert sents(md, MED, MED_WORLD) == ["The trial enrolled 300 patients.",
                                         "zorvimab reduced events by a third in the CORVA-2 trial."]


def test_section_abbreviation_starts_a_sentence() -> None:
    md = "The court relied on the Act in 2019. s. 9 was rejected later by the Court of Appeal in Pell.\n"
    assert sents(md) == ["The court relied on the Act in 2019.",
                         "s. 9 was rejected later by the Court of Appeal in Pell."]


def test_abbreviations_from_the_pack_do_not_split() -> None:
    assert sents("Acme Co. Ltd was the claimant in this long dispute here.\n") == [
        "Acme Co. Ltd was the claimant in this long dispute here."]
    assert sents("In Marrin v. Tolst Media the court relied on s. 9 of the Act, cf. para. 4 there.\n") == [
        "In Marrin v. Tolst Media the court relied on s. 9 of the Act, cf. para. 4 there."]


def test_hard_wrapped_lines_are_one_sentence() -> None:
    md = "The Supreme Court relied on section 14 of the\nVeldra Personal Data Act 2016 as the basis of its ruling.\n"
    assert sents(md) == ["The Supreme Court relied on section 14 of the Veldra Personal Data Act 2016 as the basis "
                         "of its ruling."]


def test_heading_list_and_table_are_never_merged_into_the_next_paragraph() -> None:
    md = ("## 2. Legal Framework of the Veldra Act\nThe court relied on it in that case.\n\n"
          "| Rusk relied on section 14 | of the Act here |\n|---|---|\n"
          "- Pell rejected section 9 as a basis\n"
          "Next the court turned to the facts.\n")
    p = text.normalize_paper(md)
    kinds = [u.kind for u in p.units]
    assert kinds == ["heading", "paragraph", "cell", "cell", "item"], kinds
    got = sents(md)
    assert "The court relied on it in that case." in got
    assert "Rusk relied on section 14" in got
    assert not any("Legal Framework" in s for s in got)            # headings are not sentences
    assert not any("of the Act here" in s and "Rusk" in s for s in got)
    # a list item without a blank line before the next line: the next line continues the item (Markdown rule)
    assert "Pell rejected section 9 as a basis Next the court turned to the facts." in got


def test_one_normalization_for_paper_quote_and_span() -> None:
    md = "In “Rusk” the **court** relied on\n_section 14_ — firmly.\n"
    p = text.normalize_paper(md)
    assert p.text == 'In "Rusk" the court relied on section 14 - firmly.'
    assert text.norm_text("In “Rusk” the *court* relied   on section 14 – firmly.") == p.text
    i = p.text.index("court")
    assert md[p.back[i]:p.back[i] + 5] == "court"                  # offsets map back to the original
    s = text.split_sents(md, text.split_rules(LAW, PILOT))[0]
    assert p.text[s[0]:s[1]] == s[2]


def test_missing_text_rules_in_a_pack_is_a_clear_error() -> None:
    import pytest
    f = packs.Field({k: v for k, v in LAW.raw.items() if k != "text"})
    with pytest.raises(KeyError, match="text"):
        text.split_rules(f, PILOT)


# ------------------------------------------------------------------ #5 whole-name matching
def _with_s91(w: dict) -> dict:
    import copy
    w = copy.deepcopy(w)
    w["entities"]["S91"] = {"kind": "provision", "label": "section 91 of the Veldra Personal Data Act 2016",
                            "alt": ["section 91"], "attrs": {"topic": "x"}}
    return w


def ids(t: str, f=LAW, w=PILOT) -> list[str]:
    return [m.eid for m in text.find_mentions(t, text.alias_table(w, f))]


def test_a_name_inside_a_longer_number_does_not_match() -> None:
    w = _with_s91(PILOT)
    assert ids("The court relied on section 91.", w=w) == ["S91"]
    assert ids("The court relied on s. 91 and on section 9-1 or section 9.1.", w=w) == ["S91"]
    med = {"entities": {"T1": {"kind": "trial", "label": "the CORVA-2 trial", "alt": ["CORVA-2"], "attrs": {}},
                        "T2": {"kind": "trial", "label": "the CORVA-21 trial", "alt": ["CORVA-21"], "attrs": {}}}}
    assert ids("CORVA-21 found no effect, unlike CORVA-2.", MED, med) == ["T2", "T1"]


def test_subsection_counts_as_the_section_and_is_logged() -> None:
    ms = text.find_mentions("Pell rejected section 9(1) of the Act.", text.alias_table(PILOT, LAW))
    assert [(m.eid, m.subsection) for m in ms] == [("K4", None), ("S9", "(1)")]


def test_pack_variants_and_leftmost_longest() -> None:
    assert ids("Under Section 14 and s 21 and § 9 the Supreme Court of Veldra ruled.") == [
        "S14", "S21", "S9", "CT1"]
    assert ids("the supreme court ruled") == []              # case is exact after the first character
    assert ids("Rusk v. Oberline Health relied on it") == ["K5"]


def test_world_check_rejects_a_name_nested_in_another_entity_name() -> None:
    import copy
    from paperfactory import world
    w = copy.deepcopy(PILOT)
    w["entities"]["CT2"]["alt"].append("Veldra Court")
    w["entities"]["CT4"] = {"kind": "court", "label": "Veldra Court", "alt": [], "attrs": {"level": 1}}
    w["entities"]["CT2"]["alt"].remove("Veldra Court")
    errs = world.check(w, LAW, packs.genre("argument"))
    assert any("'Veldra Court' (CT4) inside" in e and "CT2" in e for e in errs), errs
    assert world.check(_with_s91(PILOT), LAW, packs.genre("argument")) == []   # section 9 / 91: told apart
