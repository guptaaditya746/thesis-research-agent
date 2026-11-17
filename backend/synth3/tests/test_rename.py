import random

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
