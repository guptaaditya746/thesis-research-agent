"""gold/chunks.py: chunks cut at headings, raw offsets that give the file back, the corpus wrapper."""
from __future__ import annotations

import pytest

from agent.broker import Rejected
from agent.tests.conftest import papers
from gold.chunks import MAX_CHARS, MIN_PIECE_CHARS, Chunk, GoldCorpus, halve, paper_chunks, sections, split

from .scripted import corpus


@pytest.mark.parametrize("max_chars", [MAX_CHARS, 8000, 1500])
def test_chunks_cover_every_d1_paper_exactly(max_chars):
    for name, text in papers().items():
        chunks = paper_chunks(name, text, max_chars)
        assert chunks[0].start == 0 and chunks[-1].end == len(text), name
        assert all(a.end == b.start for a, b in zip(chunks, chunks[1:], strict=False)), name
        assert "".join(text[c.start:c.end] for c in chunks) == text
        assert all(0 < c.chars <= max_chars for c in chunks)
        assert [c.chunk for c in chunks] == list(range(len(chunks)))


@pytest.mark.parametrize("name", list(papers()))
def test_chunks_start_at_headings_unless_a_section_is_too_long(name):
    text = papers()[name]
    found = sections(text)
    heading_starts = {start for start, _, heading in found if heading}
    too_long = [(start, end) for start, end, _ in found if end - start > 8000]
    chunks = paper_chunks(name, text, 8000)
    for c in chunks[1:]:
        assert c.start in heading_starts or any(s < c.start < e for s, e in too_long)
        if c.start in heading_starts:
            assert text[c.start:].startswith("## " + c.heading)
    if name == "2025-emnlp-main-1032":
        assert chunks[0].heading == ("How Do Large Vision-Language Models See Text in Image? Unveiling the "
                                     "Distinctive Role of OCR Heads")


def test_a_paper_under_the_limit_is_one_chunk():
    text = papers()["2025-emnlp-main-1032"]  # 45,584 characters: two chunks at the default limit
    assert len(paper_chunks("p6", text)) == 2
    assert [(c.start, c.end) for c in paper_chunks("p6", text, len(text))] == [(0, len(text))]


def test_long_sections_are_cut_at_paragraphs_then_lines_then_spaces():
    para = "word " * 50  # 250 characters, no line break
    text = "# A\n\n" + "\n\n".join([para.strip()] * 6) + "\n## B\nshort\n"
    chunks = split(text, 600)
    assert "".join(text[a:b] for a, b, _ in chunks) == text
    assert all(b - a <= 600 for a, b, _ in chunks)
    first_cut = chunks[0][1]
    assert text[first_cut - 2:first_cut] == "\n\n"  # at a blank line
    assert [h for _, _, h in chunks][:2] == ["A", "A"]  # a continued section repeats its heading
    hard = split("x" * 25, 10)
    assert [(a, b) for a, b, _ in hard] == [(0, 10), (10, 20), (20, 25)]
    assert ["aaaa bbbb cccc"[a:b] for a, b, _ in split("aaaa bbbb cccc", 7)] == ["aaaa ", "bbbb ", "cccc"]


def test_text_before_the_first_heading_and_empty_files():
    chunks = split("preamble\n# One\nbody\n# Two\nmore\n", 12)
    assert chunks[0] == (0, 9, None)
    assert split("", 100) == [] and split(" \n\n ", 100) == []


def test_hashes_in_code_are_not_headings_and_setext_headings_are():
    text = ("# Paper\nintro\n\n```\n# not a heading\n### Background You are\n```\n\n"
            "    # indented code\n\nSetext Title\n============\nbody\n\n> # quoted\n\nSub\n---\nend\n")
    assert [(text[start:start + 12], heading) for start, _, heading in sections(text)] == [
        ("# Paper\nintr", "Paper"), ("Setext Title", "Setext Title"), ("Sub\n---\nend\n", "Sub")]
    crlf = text.replace("\n", "\r\n")
    assert [h for _, _, h in sections(crlf)] == ["Paper", "Setext Title", "Sub"]
    assert [crlf[s:s + 3] for s, _, _ in sections(crlf)] == ["# P", "Set", "Sub"]


def test_no_section_of_a_d1_paper_starts_inside_a_code_fence():
    text = papers()["2025-acl-long-625"]  # its appendix prints prompt templates with '### ...' lines in fences
    fenced = [n for n, line in enumerate(text.split("\n")) if line.startswith("```")]
    assert fenced, "the fixture paper has fenced blocks"
    for start, _, heading in sections(text):
        inside = sum(1 for n in fenced if n < text.count("\n", 0, start)) % 2 == 1
        assert not inside, heading
        assert not (heading or "").startswith("Reference Answer")


def test_halve_cuts_a_chunk_at_the_paragraph_nearest_its_middle():
    para = "word " * 100  # 500 characters
    text = "# A\n\n" + "\n\n".join([para.strip()] * 10) + "\n"
    whole = paper_chunks("p1", text, len(text))[0]
    first, second = halve(text, whole)
    assert (first.start, second.end, first.end) == (whole.start, whole.end, second.start)
    assert text[first.end - 2:first.end] == "\n\n" and abs(first.end - len(text) // 2) < 300
    assert (first.piece, second.piece, first.chunk, second.chunk) == ("1", "2", 0, 0)
    assert halve(text, first)[1].piece == "12"
    assert halve(text, Chunk("p1", 0, 0, 2 * MIN_PIECE_CHARS - 1, None)) is None
    with_heading = "# A\n" + "x " * 700 + "\n## B\n" + "y " * 700 + "\n"
    _, later = halve(with_heading, paper_chunks("p1", with_heading, len(with_heading))[0])
    assert later.heading == "B" and with_heading[later.start:].startswith("## B")


def test_corpus_lists_failures_and_checks_hashes(tmp_path):
    c = corpus(tmp_path)
    assert c.papers[:3] == ["p1", "p2", "p3"] and c.papers[-1] == "p99"
    assert c.failures == {"p99": "scanned"}
    assert c.text("p6") == papers()["2025-emnlp-main-1032"]
    with pytest.raises(Rejected):
        c.text("p99")
    (c.root / "p2.md").write_text("changed", encoding="utf-8")
    with pytest.raises(Rejected) as exc:
        c.text("p2")
    assert exc.value.reason == "corpus_file_hash_mismatch"


def test_index_cache_is_bounded(tmp_path):
    root = corpus(tmp_path).root
    c = GoldCorpus(root, root / "manifest.json", keep=2)
    first = c.index("p1.md")
    c.index("p2.md")
    assert c.index("p1.md") is first
    c.index("p3.md")
    assert set(c._recent) == {"p1.md", "p3.md"}
