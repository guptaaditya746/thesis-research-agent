import re
from pathlib import Path

import pytest

from synth3.pmc import jats_paper, tidy, unfit

FIX = Path(__file__).parent / "fixtures" / "jats"


def test_structured_abstract_becomes_one_section_with_run_in_labels():
    p = jats_paper((FIX / "trial.xml").read_bytes())
    head = p.text.split("## Introduction")[0]
    assert head.count("## ") == 1 and "Background: " in head and "Conclusions: " in head


def test_figures_citations_and_back_matter_are_gone(REAL):
    text = tidy(jats_paper((FIX / "trial.xml").read_bytes()).text, REAL)
    assert "Figure 1" not in text and "## Funding" not in text and "References" not in text
    assert not re.search(r"\[\s*[,–-]?\s*\]|\(\s*\)", text)   # no empty brackets left by removed citations
    assert "Treatment lowered the stroke rate in older patients." in text   # the text after a citation stays


def test_a_table_inside_a_paragraph_stays_a_table():
    text = jats_paper((FIX / "trial.xml").read_bytes()).text
    assert len(re.findall(r"(?m)^Table \d+\. ", text)) == 2 and len(re.findall(r"(?m)^\|( --- \|)+$", text)) == 2


def test_tidy_cleans_docling_markdown(REAL):
    text = tidy((FIX / "docling.md").read_text(encoding="utf-8").replace("\n", "\r\n"), REAL)
    assert "## Abstract" in text and "<!--" not in text and "http" not in text
    assert "References" not in text and "\r" not in text


def test_metadata_and_plain_caption():
    p = jats_paper((FIX / "trial.xml").read_bytes())
    assert p.id.startswith("PMC") and p.year and p.article_type == "research-article"
    assert re.search(r"(?m)^Table 1\. ", p.text) and "**" not in p.text


def test_unfit_names_the_reason(REAL):
    assert unfit(jats_paper((FIX / "review.xml").read_bytes()), REAL) == "article type review-article"
    assert unfit(jats_paper((FIX / "trial.xml").read_bytes()), REAL) is None


def test_not_xml_is_a_value_error():
    with pytest.raises(ValueError, match="not XML"):
        jats_paper(b"<html")


def test_a_paper_that_names_too_few_drugs_is_unfit(tmp_path):
    # a salt-meter education trial names no drug, so planted sentences about tablets would not fit it
    from synth3.pmc import PoolPaper
    from synth3.realspec import load_real_spec
    from synth3.tests.conftest import fake_paper, real_good, write_real

    def rs(k):
        d = real_good(); d["min_names"] = k
        return load_real_spec("demo", write_real(tmp_path / f"r{k}", d))

    paper = PoolPaper(id="P1", title="HOPE trial", year=2015, journal="J", license="", article_type="research-article",
                      text=fake_paper(1))   # Lisinopril, lisinopril, amlodipine: 3 drug names
    assert unfit(paper, rs(3)) is None
    assert unfit(paper, rs(4)) == "too few names from name_stems or name_words"
    assert unfit(jats_paper((FIX / "trial.xml").read_bytes()), rs(1)) == "too few names from name_stems or name_words"
    assert unfit(jats_paper((FIX / "trial.xml").read_bytes()), rs(0)) is None


def test_tidy_keeps_a_suspended_hyphen_but_joins_a_broken_word(REAL):
    # "low- to -middle income" became "lowto -middle income" in a built paper
    text = tidy("# T\n\nIn low- to middle-income settings, short- and long-term and pre- or post-dose "
                "values were higher vs. low- vs high-dose groups. The treat- ment worked.\n", REAL)
    assert "low- to middle-income" in text and "short- and long-term" in text and "pre- or post-dose" in text
    assert "low- vs high-dose" in text and "treatment worked" in text


def test_all_caps_headings_labels_and_captions_get_plain_case(REAL):
    # synth2 renames every run of capitals: "## 3. RESULTS" became "## 3. WETARKJ" and "**TABLE 1 ...**" "SOTMU 1"
    from synth3.pmc import calm_caps
    src = ("# T\n\n## Abstract\n\nRESEARCH DESIGN AND METHODS: Adults were enrolled. RESULTS: BP fell.\n\n"
           "## 1. INTRODUCTION\n\nText.\n\n## MATERIALS AND METHODS\n\nText.\n\n## EFFECT ON UACR\n\nUACR fell.\n\n"
           "## RESULTS\n\nAs TABLE 1 shows, BP fell.\n\n**TABLE 1 Baseline characteristics (full set).**\n\n"
           "| a | b |\n| --- | --- |\n| 1 | 2 |\n\n**Table 2 Ocular AEs* related to treatment (safety set)**\n\n"
           "| a | b |\n| --- | --- |\n| 1 | 2 |\n\n## Results of the WISE study\n\nText.\n")
    text = calm_caps(src)
    for want in ("Research design and methods: Adults", "Results: BP fell",
                 "## 1. Introduction", "## Materials and Methods", "## Effect on UACR", "## Results\n",
                 "As Table 1 shows", "Table 1. Baseline characteristics (full set).\n",
                 "Table 2. Ocular AEs* related to treatment (safety set)\n", "## Results of the WISE study"):
        assert want in text, want
    assert calm_caps(text) == text and tidy(src, REAL) == tidy(text, REAL) and "Table 1. Baseline" in tidy(src, REAL)
