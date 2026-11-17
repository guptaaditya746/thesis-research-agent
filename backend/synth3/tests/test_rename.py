from synth2.realedit import unsayable
from synth3.rename import names_left, rename_source

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
