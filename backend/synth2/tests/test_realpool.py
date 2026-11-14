import json

from synth2 import realpool
from synth2.realpool import body_blocks, clean_text, cut_pieces, split_pool, words


def row(pid, title, summary="", year="2022", content=""):
    return {"arxiv_id": pid, "title": title, "summary": summary, "published": f"{year}-01-01", "content": content}


def test_split_has_no_paper_on_both_sides_and_drops_old_style_papers():
    rows = [row("a1", "Retrieval augmented QA"), row("a2", "RAG retrieval for facts"), row("a3", "Open-domain QA retrieval"),
            row("old", "Retrieval augmented reading"), row("sty", "Retrieval augmented style paper"),
            row("img", "Dense retrieval of images"), row("far", "Retrieval of rocks"), row("no", "Graph networks")]
    old = {"style": ["sty"], "eval": ["old"]}
    out = split_pool(rows, old)
    assert not set(out["test"]) & set(out["sources"])
    assert "sty" not in out["test"] + out["sources"] and out["style_excluded"] == ["sty"]
    assert "old" in out["test"] and out["old_eval_in_test"] == ["old"]
    assert "no" not in out["test"] + out["sources"]          # off topic
    assert {"img", "far"} <= set(out["sources"])             # on topic but not on the QA side
    assert out["counts"]["test"] == len(out["test"])
    assert split_pool(rows, old) == out                      # seeded: same split every time


def test_split_draw_is_seeded_and_capped():
    rows = [row(f"p{i:02d}", "Retrieval augmented generation") for i in range(45)]
    out = split_pool(rows, {"style": [], "eval": []})
    assert len(out["test"]) == 30 and len(out["sources"]) == 15
    assert out["test"] == sorted(out["test"])


def test_split_file_writes_json(tmp_path):
    rows = tmp_path / "rows.jsonl"
    rows.write_text("\n".join(json.dumps(r) for r in [row("a1", "RAG retrieval for facts"), row("b", "Dense retrieval")]),
                    encoding="utf-8")
    old = tmp_path / "old.json"
    old.write_text(json.dumps({"style": [], "eval": []}), encoding="utf-8")
    out = realpool.split_file(rows, old, tmp_path / "x" / "split.json")
    assert json.loads((tmp_path / "x" / "split.json").read_text(encoding="utf-8")) == out
    assert out["test"] == ["a1"] and out["sources"] == ["b"]


DOCLING = """# A Paper Title

Some Author, Another Author

## Abstract

Skipped abstract before the body.

## 1 Introduction

Retrieval helps recogni- tion of facts, e.g . ( see below ) , and more .

<!-- image -->

<!-- formula-not-decoded -->

Figure 1: A caption that must go.

* Equal contribution footnote.

## 2 Method

### 2.1 Retriever

| a  |  b |
|:--|---|
| 1 |  2 |

## Acknowledgements

Thanks to everyone.

## 3 Results

The name snake\\_case is fine &amp; clean.

## References

[1] Should never appear.
"""


def test_docling_cleaning():
    blocks = body_blocks(DOCLING)
    text = "\n\n".join(b for _, b in blocks)
    assert "<!--" not in text and "image" not in text and "formula" not in text    # comment markers
    assert "recognition of facts, e.g. (see below), and more." in text             # hyphen break, spaced punctuation
    assert "| a | b |\n|---|---|\n| 1 | 2 |" in text                              # table cells compacted
    assert "caption" not in text and "Equal contribution" not in text              # figure captions, footnotes
    assert "Skipped abstract" not in text                                          # before the first body heading
    assert "Thanks to everyone" not in text and "Acknowledgements" not in text
    assert "## Introduction" in text and "## Method" in text and "### Retriever" in text   # numbers stripped
    assert "snake_case is fine & clean." in text
    assert "Should never appear" not in text and "References" not in text          # stops at References


def test_docling_blocks_keep_their_section():
    sections = {b: s for s, b in body_blocks(DOCLING)}
    assert sections["## Introduction"] == "Introduction"
    assert sections["### Retriever"] == "Method"


def test_clean_text_repairs_spacing():
    assert clean_text("a ( b ) , c ; d .") == "a (b), c; d."
    assert clean_text("a\ttwo   spaces") == "a two spaces"


def body_of(n_blocks, per_block=90):
    return [("Results", " ".join(f"w{i}x{j}" for j in range(per_block)) + (" accuracy baseline" if i % 2 else ""))
            for i in range(n_blocks)]


def test_piece_cutting_respects_word_limits(tmp_path):
    body = body_of(30)
    pieces = cut_pieces("# T", ["## Abstract", "Short abstract."], body)
    assert 1 <= len(pieces) <= 3
    assert pieces[0].startswith("# T\n\n## Abstract\n\nShort abstract.")
    assert all(p.startswith("# T") for p in pieces)
    assert words(pieces[0]) <= realpool.HIGH
    index, notes = [], []
    realpool.write_pieces("P1", pieces, tmp_path, index, notes)
    assert index and all(realpool.LOW <= x["words"] <= realpool.HIGH for x in index)
    assert len(index) + len(notes) == len(pieces)
    assert (tmp_path / "P1_p1.md").is_file() and index[0]["paper"] == "P1"


def test_short_pieces_are_left_out_with_a_note(tmp_path):
    index, notes = [], []
    realpool.write_pieces("P2", ["# T\n\nfar too short"], tmp_path, index, notes)
    assert index == [] and "piece 1 skipped" in notes[0] and not list(tmp_path.iterdir())


def test_windows_stay_within_the_cap():
    body = body_of(40)
    for run in realpool.windows(body):
        assert sum(words(body[i][1]) for i in run) <= realpool.BODY_CAP


def long_body(n=25):
    return "\n\n".join(" ".join(f"w{i}x{j}" for j in range(90)) + " accuracy" for i in range(n))


def test_cut_side_writes_full_papers_and_pieces(tmp_path):
    content = "# T\n\n## 1 Introduction\n\n" + long_body() + "\n\n## References\n\nx"
    rows = tmp_path / "rows.jsonl"
    rows.write_text("\n".join(json.dumps(r) for r in [row("t1", "Title  One", "An  abstract.", content=content),
                                                      row("t2", "No body", content="nothing here")]),
                    encoding="utf-8")
    split = tmp_path / "split.json"
    split.write_text(json.dumps({"test": ["t1", "t2"], "sources": []}), encoding="utf-8")
    done = realpool.cut_side(rows, split, "test", tmp_path / "out")
    assert done["no_body"] == ["t2"] and done["full"] == 1 and done["papers"] == 1
    assert (tmp_path / "out" / "full" / "t1.md").read_text(encoding="utf-8").startswith("# Title One\n\n## Abstract")
    index = json.loads((tmp_path / "out" / "pieces" / "index.json").read_text(encoding="utf-8"))
    assert {x["paper"] for x in index} == {"t1"} and done["pieces"] == len(index) >= 1
    again = realpool.cut_side(rows, split, "sources", tmp_path / "src")   # sources: whole papers only
    assert again["full"] == 0 and not (tmp_path / "src" / "pieces").exists()


def test_slice_papers_drops_the_author_line_and_numbers(tmp_path):
    paper = f"# Our Title\n\nLee et al. (2021)\n\n## Abstract\n\nShort.\n\n## 1 Methods\n\n{long_body()}\n"
    src = tmp_path / "papers"
    src.mkdir()
    (src / "S001.md").write_text(paper, encoding="utf-8")
    (src / "other.md").write_text(paper, encoding="utf-8")        # not S*.md: ignored
    done = realpool.slice_papers(src, tmp_path / "out")
    first = (tmp_path / "out" / "S001_p1.md").read_text(encoding="utf-8")
    assert first.startswith("# Our Title\n\n## Abstract\n\nShort.\n\n## Methods")
    assert "Lee et al." not in first and done["papers"] == 1
    assert not list((tmp_path / "out").glob("other*"))
