"""gold/chunks.py: chunks cut at headings, raw offsets that give the file back, the corpus wrapper."""
from __future__ import annotations

import pytest

from agent.broker import Rejected
from agent.tests.conftest import papers
from gold.chunks import MAX_CHARS, GoldCorpus, paper_chunks, sections, split

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
