import random
import re

import pytest

from synth2.realedit import SURNAME_POOL, unsayable
from synth3.rename import lower_names, names_left, rename_source

SRC = ("# Lisinopril in HOPE-3\n\n## Abstract\n\nPatients in Brightford took lisinopril. "
       "Lisinopril/amlodipine lowered BP and eGFR held. LISINOPRIL-based care was compared, as WHO advises.\n")


def test_drug_names_get_one_invented_name_in_every_form(REAL):
    text, m = rename_source(SRC, REAL, "s1", set())
    new = m["lisinopril"]
    assert new.endswith("pril") and new != "lisinopril"
    for form in (new, new.capitalize(), new.upper()):
        assert form in text
    assert m["amlodipine"].endswith("dipine") and names_left(text, m, REAL) == []


def test_keep_words_stay_and_other_names_go(REAL):
    text, m = rename_source(SRC, REAL, "s1", set())
    assert all(w in text for w in ("BP", "eGFR", "WHO"))
    assert "HOPE-3" not in text and "Brightford" not in text and unsayable(m) == []


def test_same_seed_same_text_and_a_new_seed_a_new_text(REAL):
    assert rename_source(SRC, REAL, "s1", set()) == rename_source(SRC, REAL, "s1", set())
    assert rename_source(SRC, REAL, "s1", set())[0] != rename_source(SRC, REAL, "s2", set())[0]


def test_invented_names_avoid_planted_words(REAL):
    first = rename_source(SRC, REAL, "s1", set())[1]["lisinopril"]
    again = rename_source(SRC, REAL, "s1", {first})[1]["lisinopril"]
    assert again != first and again.endswith("pril")


def test_a_cited_author_never_takes_a_planted_author_surname(REAL):
    src = SRC + "\nAs Smith et al. (2010) showed, doses matter.\n"
    first = rename_source(src, REAL, "s1", set())[1]["Smith"]
    text, m = rename_source(src, REAL, "s1", {first.lower()})
    assert m["Smith"] != first and first not in text and m["Smith"] in text


def test_a_replaced_surname_is_never_a_real_author_of_the_paper(REAL):
    pool = list(SURNAME_POOL)
    random.Random("s1|avoid").shuffle(pool)          # the order replacements are drawn in
    real = pool[:3]
    src = SRC + "\nAs Smith et al. (2010), " + ", ".join(f"{s} et al. (2011)" for s in real) + " showed.\n"
    first = rename_source(src, REAL, "s1", set())[1]["Smith"]
    text, m = rename_source(src, REAL, "s1", {first.lower()})
    assert m["Smith"] not in real and m["Smith"] not in m and not any(s in text for s in real)


def test_a_capitalised_word_after_a_kept_acronym_is_not_a_name(REAL):
    src = "# Title\n\nResults were mixed. WHO Guidelines apply. BP Reduction was large.\n"
    text, m = rename_source(src, REAL, "s1", set())
    assert "WHO Guidelines apply" in text and "BP Reduction was large" in text
    assert not {"Guidelines", "Reduction"} & set(m)


def test_a_name_word_too_short_to_split_is_refused(REAL):
    with pytest.raises(ValueError, match="name_words"):
        lower_names(REAL.model_copy(update={"name_words": ["abc"]}))


def test_heading_words_are_not_names_but_real_names_in_headings_still_go(REAL):
    src = ("# The TRIAX-2 trial in Brightford\n\n## Materials and Methods\n\nAdults were enrolled at two sites.\n\n"
           "## Results and Discussion\n\nIn the TRIAX-2 trial, patients from Brightford did well.\n")
    text, m = rename_source(src, REAL, "s1", set())
    assert "## Results and Discussion" in text and "## Materials and Methods" in text
    assert "TRIAX-2" not in text and "Brightford" not in text and names_left(text, m, REAL) == []


def test_an_acronym_plural_is_its_singular_plus_s_and_counts_as_sayable(REAL):
    # synth2 reads "NCDs" as "NC" + the word "Ds", so NCDs became "GHZatio" in a built paper
    from synth3.rename import hard_to_say
    src = ("# Title\n\n## Abstract\n\nNon-communicable diseases (NCDs) are common. The NCD burden grows and NCDs "
           "kill. In LMICs care is thin. BPs fell and SDs were wide.\n")
    text, m = rename_source(src, REAL, "s1", set())
    assert m["NCDs"] == m["NCD"] + "s" and re.fullmatch(r"[A-Z]{3}s", m["NCDs"])
    assert re.fullmatch(r"[A-Z]{4}s", m["LMICs"])
    assert "BPs fell" in text and "SDs were" in text and not {"BPs", "SDs"} & set(m)
    assert hard_to_say(m) == [] and names_left(text, m, REAL) == []


def test_roman_numerals_are_not_names(REAL):
    # synth2 reads any run of capitals as a name: "angiotensin II" became "angiotensin UI", NYHA "II/III" "AE/OOE"
    src = ("# Title\n\n## Abstract\n\nAngiotensin II type 1 receptors were blocked in NYHA class II/III/IV patients "
           "at the Brightford site in phase III.\n")
    text, m = rename_source(src, REAL, "s1", set())
    assert "Angiotensin II type" in text and "class II/III/IV" in text and "phase III" in text
    assert not {"II", "III", "IV"} & set(m) and "Brightford" not in text


def test_a_long_stem_needs_only_a_two_letter_prefix_and_a_keep_word_is_never_a_drug(REAL):
    # losartan (43 built papers) and prazosin survived: every stem needed 3 letters before it
    rs = REAL.model_copy(update={"name_stems": ["pril", "sartan", "azosin", "statin"], "keep": [*REAL.keep, "cystatin"]})
    src = "# T\n\n## Abstract\n\nLosartan, prazosin and atorvastatin were given; cystatin C was measured.\n"
    text, m = rename_source(src, rs, "s1", set())
    assert {"losartan", "prazosin", "atorvastatin"} <= set(m) and "cystatin" not in m
    assert m["losartan"].endswith("sartan") and m["prazosin"].endswith("azosin") and "cystatin C" in text
    assert names_left(text, m, rs) == []


def test_medicine_names_drugs_outside_the_first_stems():
    from synth3.realspec import load_real_spec
    rs = load_real_spec("medicine")
    real = ["axitinib", "sorafenib", "sunitinib", "bevacizumab", "sildenafil", "tadalafil", "rilmenidine",
            "glibenclamide", "repaglinide", "ritonavir", "tacrolimus", "brinzolamide", "prazosin", "losartan",
            "dorzolamide", "brimonidine", "heparin"]
    src = "# T\n\n## Abstract\n\n" + " ".join(f"Patients took {w}." for w in real) + " Cystatin C was low.\n"
    text, m = rename_source(src, rs, "s1", set())
    assert [w for w in real if re.search(rf"\b{w}\b", text, re.I)] == [] and "Cystatin C" in text


def test_a_control_word_and_the_acronym_defined_for_it_are_never_renamed(REAL):
    # "placebo (PLB)": PLB became "RHM", so "HOC: -15.7 vs. RHM: -4.3 mmHg" kept the real placebo numbers
    src = ("# T\n\n## Abstract\n\nPatients took lisinopril or placebo (PLB). Systolic BP fell (HOC: -15.7 vs. PLB: "
           "-4.3 mmHg). The usual care (UC) arm and the UCs were small.\n")
    text, m = rename_source(src, REAL, "s1", set())
    assert "placebo (PLB)" in text and "PLB: -4.3" in text and "usual care (UC)" in text and "UCs were" in text
    assert not {"PLB", "UC", "UCs"} & set(m) and "HOC" in m
    assert REAL.control_acronyms(src) == ["PLB", "UC"]
