import re

import pytest

from synth3 import realwrite
from synth3.pmc import jats_paper
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
    assert clean_block(table, BANNED) == ""   # a control row anywhere: the whole table goes
    assert clean_block("A first sentence. The placebo was inert. A last one.", BANNED) == "A first sentence. A last one."


@pytest.mark.parametrize("title, want", [
    ("A randomised, placebo-controlled trial of X", "A randomised trial of X"),
    ("X versus usual care in older adults", "X in older adults"),
    ("Placebo-controlled, double-blind trial of X in adults", "Double-blind trial of X in adults"),
    ("Effects of X and placebo on blood pressure", "Effects of X on blood pressure"),
    ("A trial of X", "A trial of X"),
    ("X versus placebo", None),
    ("Drug X plus usual care versus usual care alone in heart failure", "Drug X in heart failure"),
])
def test_clean_title(title, want):
    assert clean_title(title, BANNED) == want


def test_a_caption_naming_the_control_takes_its_table_along(SPEC, REAL):
    src = fake_paper(6).replace("| Outcome | Drug | Placebo |", "| Outcome | Drug | Other |").replace(
        "Table 1. Outcomes by group.", "Table 1. Outcomes in the drug and placebo groups.")
    _, rp = edit(SPEC, REAL, source=src)
    assert rp.problems == () and "| Outcome | Drug | Other |" not in rp.paper.text


_TWO_ROW_XML = b"""<article article-type="research-article"><front><article-meta><title-group>
<article-title>T</article-title></title-group></article-meta></front><body><sec><title>Results</title>
<table-wrap id="T1"><label>Table 1</label><caption><title>Outcomes by group</title></caption>
<table><thead><tr><th rowspan="2">Outcome</th><th colspan="2">Group</th></tr>
<tr><th>Drug A (n=200)</th><th>Placebo (n=200)</th></tr></thead>
<tbody><tr><td>Strokes</td><td>17</td><td>29</td></tr></tbody></table></table-wrap></sec></body></article>"""


def test_a_two_row_header_table_naming_the_control_goes_whole(SPEC, REAL):
    table = next(b for b in jats_paper(_TWO_ROW_XML).text.split("\n\n") if b.startswith("|"))
    assert "| --- |" in table.split("\n")[1] and "Placebo" in table.split("\n")[2]   # the arm row is below
    assert clean_block(table, REAL.banned(SPEC)) == ""
    src = fake_paper(8).replace("| Outcome | Drug | Placebo |\n| --- | --- | --- |\n| Events | 12 | 20 |", table)
    _, rp = edit(SPEC, REAL, source=src)
    assert rp.problems == () and "Strokes" not in rp.paper.text and "Outcomes by group" not in rp.paper.text


def test_our_table_number_follows_the_highest_real_one(SPEC, REAL):
    kept = "Table 2. Visits by month.\n\n| Month | Visits |\n| --- | --- |\n| First | 31 |"
    src = fake_paper(9).replace("## Discussion", f"As Table 1 shows, events were rare.\n\n{kept}\n\n## Discussion")
    _, rp = edit(SPEC, REAL, source=src)
    t = rp.paper.text
    assert rp.problems == () and "Table 3." in rp.inserted[1] and t.count("Table 2.") == 1 and "| First | 31 |" in t
    assert "As Table 1 shows" not in t


def test_results_and_discussion_heading_keeps_the_conclusion_claims_after_the_section(SPEC, REAL):
    src = fake_paper(10).replace("## Results", "## Results and Discussion").replace("## Discussion\n", "## Limits\n")
    _, rp = edit(SPEC, REAL, source=src)
    t = rp.paper.text
    assert rp.problems == () and t.index(rp.inserted[1]) < t.index(rp.inserted[2])


def test_paper_without_results_heading_puts_the_section_before_the_conclusion(SPEC, REAL):
    src = fake_paper(7).replace("## Results", "## Observations")
    s, rp = edit(SPEC, REAL, source=src)
    t = rp.paper.text
    assert rp.problems == () and t.index(rp.inserted[1]) < t.index("## Discussion") < t.index(rp.inserted[2])


def test_a_table_with_a_glued_control_word_goes_whole(SPEC, REAL):
    # PMC cells lose the line break between "Placebo" and "n = 62", and "ΔPlacebo" has no word edge before P
    for head in ("|  | Placebon = 62 | Lisinopriln = 60 |", "|  | ΔPlacebo | ΔARB |"):
        table = f"{head}\n|---|---|---|\n| Age | 61 | 60 |"
        src = fake_paper(1).replace("| Outcome | Drug | Placebo |\n| --- | --- | --- |\n| Events | 12 | 20 |", table)
        assert table in src
        _, rp = edit(SPEC, REAL, source=src)
        assert rp.problems == () and "lacebo" not in rp.paper.text


_CONTROL_TABLE = "| Outcome | Drug | Placebo |\n| --- | --- | --- |\n| Events | 12 | 20 |"


def test_an_acronym_defined_for_the_control_goes_with_the_control(SPEC, REAL):
    # built s1/S026: "placebo (PLB)" lost its sentence, but "HOC: -15.7 vs. RHM: -4.3 mmHg" kept the placebo numbers
    src = fake_paper(11).replace("## Results\n\n", "## Results\n\nPatients took lisinopril or placebo (PLB) daily. "
                                 "Systolic BP fell (HOC: -15.7 vs. PLB: -4.3 mmHg). Visits were on time.\n\n")
    src = src.replace(_CONTROL_TABLE, "| Outcome | HOC | PLB |\n| --- | --- | --- |\n| Events | 12 | 20 |")
    _, rp = edit(SPEC, REAL, source=src)
    assert rp.problems == () and "-4.3 mmHg" not in rp.paper.text and "| Events | 12 | 20 |" not in rp.paper.text
    assert "Visits were on time." in rp.paper.text


def test_the_paper_check_names_a_control_acronym_left_in_the_text(SPEC, REAL):
    from synth2.write import Paper
    s, rp = edit(SPEC, REAL)
    paper = Paper(rp.paper.study, rp.paper.text + "\nThe PLB arm fell by four points.\n", rp.paper.placements)
    assert realwrite.check_real_paper(paper, rp.inserted, s, SPEC, REAL, rp.mapping) == []
    problems = realwrite.check_real_paper(paper, rp.inserted, s, SPEC, REAL, rp.mapping, ("PLB",))
    assert any("PLB" in p for p in problems)


def test_medicine_control_phrasings_go(SPEC):
    from synth3.realspec import load_real_spec
    rs = load_real_spec("medicine")
    src = fake_paper(12).replace("## Discussion\n\n", (
        "## Discussion\n\nA sham procedure was done. Patients got lisinopril with standard of care (SoC) or SoC "
        "alone. The SoC arm improved by 4 points. The comparator group did not. Vehicle-treated rats did not. "
        "Visits were on time.\n\n"))
    _, rp = edit(SPEC, rs, source=src)
    t = rp.paper.text
    assert rp.problems == () and "Visits were on time." in t
    assert not re.search(r"sham|SoC|standard of care|comparator|vehicle|by 4 points", t, re.I)


def test_an_all_caps_paper_keeps_its_headings_and_caption_pairs(SPEC, REAL):
    # 49 of 200 built papers had headings like "## 3. WETARKJ", so the section landed at the end of the Discussion,
    # and "**TABLE 1 ...**" became "**SOTMU 1 ...**", a caption that no longer took its table along
    kept = "**TABLE 2 Visits by month.**\n\n| Month | Visits |\n| --- | --- |\n| First | 31 |"
    src = (fake_paper(13).replace("## Introduction", "## 1. INTRODUCTION").replace("## Methods", "## 2. METHODS")
           .replace("## Results", "## 3. RESULTS").replace("## Discussion", f"{kept}\n\n## 4. DISCUSSION")
           .replace("Table 1. Outcomes by group.", "**TABLE 1 Outcomes by group.**"))
    _, rp = edit(SPEC, REAL, source=src)
    t = rp.paper.text
    assert rp.problems == () and "TABLE" not in t and "Outcomes by group" not in t and "| Events |" not in t
    assert "## 1. Introduction" in t and "## 2. Methods" in t
    assert t.index("## 3. Results") < t.index(rp.inserted[1]) < t.index("## 4. Discussion") < t.index(rp.inserted[2])
    assert "Table 2. Visits by month.\n\n| Month | Visits |" in t


def test_a_results_heading_lost_in_renaming_is_a_problem(SPEC, REAL, monkeypatch):
    real_rename = realwrite.rename_source
    monkeypatch.setattr(realwrite, "rename_source",
                        lambda *a: (lambda t, m: (t.replace("## Results", "## Wetarkj"), m))(*real_rename(*a)))
    _, rp = edit(SPEC, REAL)
    assert any("results heading" in p for p in rp.problems)
