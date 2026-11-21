"""The writer's brief files (evqa/seed/brief.py): every seed value once in the log, no made-up numbers in the idea."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from evqa.paths import brief_dir
from evqa.seed import brief


@pytest.fixture(scope="module")
def papers() -> dict[str, dict[str, Any]]:
    return brief.paper_facts("medical")


def test_every_paper_gets_both_files(tmp_path: Path, papers: dict[str, dict[str, Any]]) -> None:
    written = brief.write("medical", out=tmp_path)
    assert len(written) == 2 * len(papers) == 80
    assert {p.parent.name for p in written} == set(papers)   # practice and test papers alike
    assert {p.name for p in written} == {"idea_sparse.md", "experimental_log.md"}


def test_log_lists_every_seed_value_exactly_once(papers: dict[str, dict[str, Any]]) -> None:
    for pid, paper in papers.items():
        log = brief.experimental_log(paper)
        for f in paper["facts"]:
            lines = [ln for ln in log.splitlines() if ln.startswith(f"| {f['id']} |")]
            assert len(lines) == 1, f["id"]
            value = f"| {f['value']} {brief.write_as(f['unit'])} |"
            assert value in lines[0], (f["id"], lines[0])   # decimals kept: '-0.90', not '-0.9'
            where = "put in a table" if f["placement"] == "table" else "state in a sentence"
            assert lines[0].endswith(f"| {where} |")
            same = [x for x in paper["facts"] if (x["value"], x["unit"]) == (f["value"], f["unit"])]
            assert log.count(value) == len(same), pid
        tables, text = log.split("### Text")
        assert all(f"| {f['id']} |" in (tables if f["placement"] == "table" else text) for f in paper["facts"])


def test_log_has_no_result_numbers_but_the_seed_values(papers: dict[str, dict[str, Any]]) -> None:
    paper = papers["P-med-01"]
    log = brief.experimental_log(paper)
    rows = re.findall(r"^\| R-[^\n]*$", log, re.M)
    body = "\n".join(ln for ln in log.splitlines() if not ln.startswith(("| R-", "#")))   # headings: '## 1.'
    allowed = {f[k] for f in paper["facts"] for k in ("dose", "week")} | {"2"}   # '2' of 'type 2 diabetes'
    assert set(brief.numbers_in(body)) <= allowed
    assert len(rows) == len(paper["facts"])


def test_idea_has_only_seed_numbers(papers: dict[str, dict[str, Any]]) -> None:
    for paper in papers.values():
        idea = brief.idea_sparse(paper)
        seed_text = " ".join([paper["title"], *(f"{f['context']} {f['dose']} {f['week']}" for f in paper["facts"])])
        assert set(brief.numbers_in(idea)) <= set(brief.numbers_in(seed_text)), paper["id"]
        values = {f["value"].lstrip("-") for f in paper["facts"]}
        assert not values & set(brief.numbers_in(idea)) - set(brief.numbers_in(seed_text))
        heads = re.findall(r"^## (.*)$", idea, re.M)
        assert heads == ["Problem Statement", "Core Hypothesis", "Proposed Methodology (High-Level Technical Approach)",
                         "Expected Contribution"]
        assert idea.startswith(f"# {paper['title']}\n")


def test_checked_in_briefs_are_up_to_date(papers: dict[str, dict[str, Any]]) -> None:
    for pid, paper in papers.items():
        folder = brief_dir("medical", pid)
        assert (folder / "idea_sparse.md").read_text(encoding="utf-8") == brief.idea_sparse(paper)
        assert (folder / "experimental_log.md").read_text(encoding="utf-8") == brief.experimental_log(paper)


def test_code_and_both_papers_name_the_drug_as_planned(papers: dict[str, dict[str, Any]]) -> None:
    code_only = papers["P-med-10"]
    (name, m), = code_only["names"].items()
    assert m["written"] == "code"
    for text in (brief.idea_sparse(code_only), brief.experimental_log(code_only)):
        assert m["code"] in text and name.lower() not in text.lower()
    both = papers["P-med-11"]
    log = brief.experimental_log(both)
    assert len({f["subject"] for f in both["facts"]}) == 3
    assert all(f"{n.capitalize()} ({x['code']})" in log for n, x in both["names"].items())
    assert brief.name_rules(papers["P-med-01"]) == []
