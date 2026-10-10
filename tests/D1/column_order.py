"""D1 column order: compare Docling paragraph order with the PDF's two-column reading order.

For each PDF page, words are assigned to the left or right column by their x position and read
as (page, column, top, x). Each Docling body paragraph is located in that stream by a 40-char
alphanumeric probe from its start and its end. The script reports:

- two-column pages per paper;
- order inversions: a paragraph whose start lies before the previous paragraph's end in PDF order;
- column breaks crossed inside one Docling paragraph (start and end in different columns/pages);
- sentences split by Docling at a column break (paragraph ends without terminal punctuation and
  the next paragraph starts lower-case), with what Docling put between the two halves.

Usage: python tests/D1/column_order.py --pdfs DIR --docling tests/D1/docling --json out.json
Needs pdfplumber (not a project dependency; used only for this check).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pdfplumber

PROBE = 40
FLOAT = re.compile(r"^(Figure|Fig\.|Table|Algorithm|Listing)\s*[0-9A-Z]|^\d{1,2} [A-Z]|^[*†‡§¶]")


def classify(between: str) -> str:
    """Name what Docling put between two halves of one sentence ('' = only a paragraph break)."""
    kinds = []
    for block in between.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("|"):
            kinds.append("table")
        elif block.startswith("<!-- image"):
            kinds.append("image")
        elif block.startswith("<!-- formula"):
            kinds.append("formula")
        elif block.startswith("#"):
            kinds.append("heading")
        elif FLOAT.match(block):
            kinds.append("caption" if block[0].isalpha() else "footnote")
        else:
            kinds.append("text")
    return "+".join(dict.fromkeys(kinds))


def alnum_stream(chunks: list[tuple[str, tuple[int, int]]]) -> tuple[str, list[tuple[int, int]]]:
    text, where = [], []
    for word, loc in chunks:
        for ch in word.lower():
            if ch.isalnum():
                text.append(ch)
                where.append(loc)
    return "".join(text), where


def pdf_stream(pdf_path: Path) -> tuple[str, list[tuple[int, int]], dict[str, int]]:
    words: list[tuple[str, tuple[int, int]]] = []
    two_col = 0
    pages = 0
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages):
            pages += 1
            mid = page.width / 2
            items = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            left = [w for w in items if w["x1"] <= mid + 2]
            right = [w for w in items if w["x0"] >= mid - 2]
            if len(left) > 50 and len(right) > 50:
                two_col += 1
            ordered = sorted(items, key=lambda w: (0 if w["x0"] < mid - 2 else 1, round(w["top"]), w["x0"]))
            for w in ordered:
                col = 0 if w["x0"] < mid - 2 else 1
                words.append((w["text"], (pno, col)))
    text, where = alnum_stream(words)
    return text, where, {"pages": pages, "two_column_pages": two_col}


def body_paragraphs(md: str) -> list[tuple[int, str]]:
    out = []
    pos = 0
    for block in md.split("\n\n"):
        start = md.index(block, pos)
        pos = start + len(block)
        line = block.strip()
        if not line or line.startswith(("#", "|", "<!--", "- ", "$$")):
            continue
        out.append((start, line))
    return out


def norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def locate(stream: str, probe: str) -> int | None:
    if len(probe) < 20:
        return None
    first = stream.find(probe)
    if first < 0 or stream.find(probe, first + 1) >= 0:
        return None
    return first


def check(pdf_path: Path, md_path: Path) -> dict:
    stream, where, stats = pdf_stream(pdf_path)
    md = md_path.read_text(encoding="utf-8")
    paras = body_paragraphs(md)
    located = []
    for offset, para in paras:
        n = norm(para)
        s = locate(stream, n[:PROBE])
        e = locate(stream, n[-PROBE:])
        located.append({"offset": offset, "text": para, "start": s, "end": None if e is None else e + PROBE - 1})
    inversions, crossings, splits = [], [], []
    prev_end = None
    for i, p in enumerate(located):
        if (p["start"] is not None and prev_end is not None and p["start"] < prev_end
                and not FLOAT.match(p["text"])):
            inversions.append({"offset": p["offset"], "head": p["text"][:80],
                               "at": where[p["start"]], "prev_end_at": where[prev_end]})
        if p["start"] is not None and p["end"] is not None and where[p["start"]] != where[p["end"]]:
            crossings.append({"offset": p["offset"], "from": where[p["start"]], "to": where[p["end"]],
                              "head": p["text"][:60]})
        if p["end"] is not None and not FLOAT.match(p["text"]):
            prev_end = p["end"]
    for i, a in enumerate(located):
        # Prose only: figure-internal fragments are short and have no sentence structure.
        if len(a["text"]) < 80 or re.search(r"[.!?:)\]\"”]\s*$", a["text"]):
            continue
        b = None
        for cand in located[i + 1:i + 5]:
            if FLOAT.match(cand["text"]):
                continue  # a caption or footnote placed between the two halves
            b = cand
            break
        if b is None or not re.match(r"[a-z(]", b["text"]):
            continue
        a_end = a["offset"] + len(a["text"])
        between = md[a_end:b["offset"]].strip()
        splits.append({"offset": a_end, "tail": a["text"][-50:], "head": b["text"][:50],
                       "between": between[:120], "inserted": classify(between),
                       "pdf_from": None if a["end"] is None else where[a["end"]],
                       "pdf_to": None if b["start"] is None else where[b["start"]]})
    found = sum(p["start"] is not None for p in located)
    return {"paper": md_path.stem, **stats, "body_paragraphs": len(located), "located": found,
            "inversions": inversions, "column_crossings_inside_paragraph": len(crossings),
            "crossings": crossings, "split_sentences": splits}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdfs", type=Path, required=True)
    parser.add_argument("--docling", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    results = []
    for md in sorted(args.docling.glob("*.md")):
        pdf = args.pdfs / f"{md.stem}.pdf"
        if not pdf.exists():
            print(f"{md.stem}: no PDF")
            continue
        r = check(pdf, md)
        results.append(r)
        print(f"{r['paper']}: pages={r['pages']} two_col={r['two_column_pages']} paras={r['body_paragraphs']} "
              f"located={r['located']} inversions={len(r['inversions'])} "
              f"crossings={r['column_crossings_inside_paragraph']} splits={len(r['split_sentences'])} "
              f"inserted={[s['inserted'] for s in r['split_sentences'] if s['inserted']]}")
    args.json.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
