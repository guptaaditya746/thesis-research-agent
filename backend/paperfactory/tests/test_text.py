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
