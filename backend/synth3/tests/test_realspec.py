import pytest

from synth3.realspec import load_real_spec
from synth3.spec import load_spec
from synth3.tests.conftest import real_good, write_real


def test_medicine_real_config_loads():
    rs = load_real_spec("medicine")
    assert rs.source == "pmc" and "open access" in rs.query and rs.n_test == 30
    assert rs.banned(load_spec("medicine")).search("Patients given placebo improved.")
    pat = rs.banned(load_spec("medicine"))
    for real in ("matching placebos", "the usual-care group", "treatment as usual", "the standard arm",
                 "the conventional groups", "aggressive and conventional treatments", "the control treatment"):
        assert pat.search(real), real


@pytest.mark.parametrize("change, words", [
    (lambda d: d.update(control_words="(unclosed"), "control_words"),
    (lambda d: d.update(min_words=9000), "min_words"),
    (lambda d: d.update(n_test=3), "n_test"),
    (lambda d: d.update(source="pmc", query=""), "query"),
    (lambda d: d.update(source="ftp"), "source"),
    (lambda d: d.update(name_stems=["Pril"]), "lower case"),
    (lambda d: d["keep"].remove("SD"), "SD"),
])
def test_refuses_bad_real_configs(tmp_path, change, words):
    d = real_good(); change(d)
    with pytest.raises(ValueError, match=words):
        load_real_spec("demo", write_real(tmp_path, d))


def test_banned_covers_control_words_labels_and_settings(SPEC, REAL):
    pat = REAL.banned(SPEC)
    assert pat.search("on usual care") and pat.search("the standard care arm")
    assert pat.search("at the Northern hospital network") and not pat.search("targeted at kidneys")


def test_numbered_headings_match(REAL):
    assert REAL.heading("results", "## 3. Results") and REAL.heading("conclusion", "## IV. Discussion")


def test_a_space_in_a_control_phrase_also_matches_a_hyphen(SPEC, REAL):
    # "usual-care group" stayed in a built paper next to the planted "Standard care": the config says "usual care"
    pat = REAL.banned(SPEC)
    assert pat.search("compared with the usual-care group") and pat.search("on usual\ncare")
    assert pat.search("the Standard-care arm") and not pat.search("usually cared for")


def test_a_character_class_in_a_control_phrase_keeps_working(SPEC, tmp_path):
    # "as[- ]cast" became "as[-[\s-]+]cast" (a class, then a literal "]"), so no materials or rag control word matched
    d = real_good()
    d["control_words"] = r"as[- ]cast|closed[- ]book|zero[- ]shot (?:llms?|prompting)|no\ retrieval|[^a-z]untreated"
    pat = load_real_spec("demo", write_real(tmp_path, d)).banned(SPEC)
    for real in ("the as-cast samples", "as cast alloy", "a closed-book setting", "zero-shot prompting",
                 "zero shot\nprompting", "zero-shot-prompting", "no retrieval", "an untreated"):
        assert pat.search(real), real
    assert not pat.search("ascast") and not pat.search("no-retrieval")   # an escaped space stays one space
