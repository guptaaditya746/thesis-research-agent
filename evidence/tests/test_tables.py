"""Two table readers: agreement, disagreement, and a page pdfplumber reads no table on. Readers are fakes: no Docling run."""
from __future__ import annotations

from pathlib import Path

from evidence import tables

PDF = Path(__file__).resolve().parent / "fixtures" / "arxiv" / "tiny.pdf"
DOCLING = [(1, [["System", "EM"], ["Baseline", "61.2"], ["RAG", "74.5"]])]


def read(docling, plumber):
    return tables.read_tables(PDF, docling=lambda _: docling, plumber=lambda _: plumber)


def test_agree_no_unsure() -> None:
    [t] = read(DOCLING, [(1, [["System", "EM"], ["Baseline", "61.2"], ["RAG", " 74.5 "]])])
    assert t.page == 1 and t.unsure == set() and t.cells == DOCLING[0][1]
    assert "table unsure" not in tables.table_markdown(t)


def test_disagree_marked_unsure() -> None:
    [t] = read(DOCLING, [(1, [["System", "EM"], ["Baseline", "61.2"], ["RAG", "74.6"]])])
    assert t.unsure == {(2, 1)} and t.cells[2][1] == "74.5"   # Docling's value kept
    md = tables.table_markdown(t)
    assert md.endswith("<!-- table unsure: 2,1 -->")
    [(a, b)] = tables.unsure_spans(md)
    assert md[a:b].strip() == "74.5"


def test_pdfplumber_empty_keeps_docling_unsure() -> None:
    for plumber in ([], [(2, [["System", "EM"]])]):   # no table at all, and none on that page
        [t] = read(DOCLING, plumber)
        assert t.cells == DOCLING[0][1]
        assert t.unsure == {(r, c) for r in range(3) for c in range(2)}
        assert tables.UNSURE == "table unsure"
        assert tables.table_markdown(t).count("<!-- table unsure:") == 6


def test_default_pdfplumber_reader_reads_a_pdf_without_tables() -> None:
    assert tables.plumber_tables(PDF) == []
