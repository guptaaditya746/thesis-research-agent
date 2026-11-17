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
