import re

import pytest

from synth3 import realwrite
from synth3.realwrite import MAX_SEEDS, clean_block, clean_title, edit_study
from synth3.tests.conftest import fake_paper, supported
from synth3.write import TEXT_LEVELS, _claim_sentence, missing_facts


def edit(SPEC, REAL, i=1, source=None, level="table"):
    s = supported(SPEC, 1)[0]
    return s, edit_study(source or fake_paper(i), s, SPEC, REAL, level, f"synth3:1:real:{s.id}")


@pytest.mark.parametrize("level", TEXT_LEVELS)
def test_real_paper_keeps_every_planted_fact(SPEC, REAL, level):
    s, rp = edit(SPEC, REAL, level=level)
    assert rp.problems == () and missing_facts(rp.paper, s, SPEC) == []


def test_control_tables_go_whole(SPEC, REAL):
    _, rp = edit(SPEC, REAL)
    rest = rp.paper.text
    for t in rp.inserted:
        rest = rest.replace(t, " ")
    assert not REAL.banned(SPEC).search(rest) and "| Placebo" not in rp.paper.text


def test_inserts_land_in_abstract_results_and_discussion(SPEC, REAL):
    s, rp = edit(SPEC, REAL)
    t = rp.paper.text
    abstract = t[t.index("## Abstract"):t.index("## Introduction")]
    assert _claim_sentence(SPEC, *next(iter(s.claims.items()))) in abstract
    assert t.index(rp.inserted[1]) < t.index("## Discussion") < t.index(rp.inserted[2])
    assert t.split("\n")[2] == s.label


def test_paper_with_only_abstract_and_introduction(SPEC, REAL):
    bare = fake_paper(2).split("## Methods")[0]
    s, rp = edit(SPEC, REAL, source=bare)
    assert rp.problems == () and rp.paper.text.rstrip().endswith(rp.inserted[2].rstrip())


def test_a_planted_name_in_the_real_text_is_cut_with_its_sentence(SPEC, REAL):
    src = fake_paper(3).replace("## Discussion\n\n", "## Discussion\n\nTargeted therapy was popular. ")
    _, rp = edit(SPEC, REAL, source=src)
    assert rp.problems == () and "Targeted therapy was popular" not in rp.paper.text


def test_a_title_naming_the_control_is_cleaned_not_rejected(SPEC, REAL):
    src = "# A randomised, placebo-controlled trial of lisinopril in older adults\n" + fake_paper(4).split("\n", 1)[1]
    _, rp = edit(SPEC, REAL, source=src)
    line1 = rp.paper.text.split("\n")[0]
    assert rp.problems == () and not REAL.banned(SPEC).search(line1) and line1.startswith("# A randomised trial of")


def test_numbered_headings_and_template_words_do_not_sink_a_source(SPEC, REAL):
    src = (fake_paper(5).replace("## Results", "## 3. Results").replace("## Discussion", "## 4. Discussion")
           + "\nValues are given as mean and SD throughout.\n")
    bare_keep = REAL.model_copy(update={"keep": ["BP", "eGFR", "WHO"]})   # no SD: the real "SD" gets renamed
    _, rp = edit(SPEC, bare_keep, source=src, level="prose")              # yet our "(SD ...)" must not count
    t = rp.paper.text
    assert rp.problems == () and t.index(rp.inserted[1]) < t.index("## 4. Discussion")


def test_every_try_failing_returns_the_problems(SPEC, REAL, monkeypatch):
    monkeypatch.setattr(realwrite, "check_real_paper", lambda *a: ["always"])
    _, rp = edit(SPEC, REAL)
    assert rp.problems == ("always",) and rp.seed.endswith(f":{MAX_SEEDS - 1}")


# ---- the cleaning rules on their own --------------------------------------------------------------------------

BANNED = re.compile(r"\b(?:placebo|usual care|Targeted therapy)\b", re.I)


def test_clean_block_rules():
    assert clean_block("Nothing to see here.", BANNED) is None
    assert clean_block("## Placebo arm", BANNED) == ""
    assert clean_block("Table 2. Events in the placebo group.", BANNED) == ""
    assert clean_block("| Outcome | Drug | Placebo |\n| --- | --- | --- |\n| Events | 1 | 2 |", BANNED) == ""
    table = "| Group | Events |\n| --- | --- |\n| Drug | 1 |\n| Placebo | 2 |"
    assert clean_block(table, BANNED) == "| Group | Events |\n| --- | --- |\n| Drug | 1 |"
    assert clean_block("A first sentence. The placebo was inert. A last one.", BANNED) == "A first sentence. A last one."


@pytest.mark.parametrize("title, want", [
    ("A randomised, placebo-controlled trial of X", "A randomised trial of X"),
    ("X versus usual care in older adults", "X in older adults"),
    ("Placebo-controlled, double-blind trial of X in adults", "Double-blind trial of X in adults"),
    ("Effects of X and placebo on blood pressure", "Effects of X on blood pressure"),
    ("A trial of X", "A trial of X"),
    ("X versus placebo", None),
])
def test_clean_title(title, want):
    assert clean_title(title, BANNED) == want


def test_a_caption_naming_the_control_takes_its_table_along(SPEC, REAL):
    src = fake_paper(6).replace("| Outcome | Drug | Placebo |", "| Outcome | Drug | Other |").replace(
        "Table 1. Outcomes by group.", "Table 1. Outcomes in the drug and placebo groups.")
    _, rp = edit(SPEC, REAL, source=src)
    assert rp.problems == () and "| Outcome | Drug | Other |" not in rp.paper.text


def test_paper_without_results_heading_puts_the_section_before_the_conclusion(SPEC, REAL):
    src = fake_paper(7).replace("## Results", "## Observations")
    s, rp = edit(SPEC, REAL, source=src)
    t = rp.paper.text
    assert rp.problems == () and t.index(rp.inserted[1]) < t.index("## Discussion") < t.index(rp.inserted[2])
