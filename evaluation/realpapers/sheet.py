"""Hand-check sheets (spec 6.12 item 3, 6.15): a run's items with their source sentences, for a person to mark right
or wrong, and the sampled precision with its Wilson 95% interval. On arXiv papers (no gold) this is a
demonstration, not an evaluation.

`sheet` takes N random items (`sample`, random.Random(seed)) or every item of the first N papers in manifest order
(`papers`); rows are in paper order, then by position. The CSV is written with a byte-order mark so Excel reads
UTF-8; `summarise` reads it back in the forms Excel saves (with or without the mark, the Windows code page, ';').
"""
from __future__ import annotations

import csv
import io
import json
import math
import random
from pathlib import Path
from typing import Any

from evidence.contract import Item
from evidence.extractors.base import sentences
from evidence.rundir import Corpus

from .common import items_of

COLUMNS = ("item_id", "paper", "type", "fields", "sentence", "right_or_wrong", "note")
RIGHT, WRONG = {"right", "r", "yes", "y"}, {"wrong", "w", "no", "n"}
Z95 = 1.96
TITLE = "arXiv hand-check sheet, demonstration, not an evaluation"


def _around(text: str, start: int, end: int, cuts: list[tuple[int, int]]) -> str:
    """The sentence(s) holding text[start:end]; a span in a table or heading line gives that line."""
    hit = [(a, b) for a, b in cuts if a < max(end, start + 1) and b > start]
    if hit:
        return " ".join(text[hit[0][0]:hit[-1][1]].split())
    a = text.rfind("\n", 0, start) + 1
    b = text.find("\n", end)
    return text[a:b if b >= 0 else len(text)].strip()


def _fields(item: Item, by_id: dict[str, Item]) -> str:
    """The item's fields as JSON, then each link as `-> key: <the linked item's fields>` (what the checker judges)."""
    out = json.dumps(item.fields, sort_keys=True, ensure_ascii=False)
    for key, target in sorted(item.links.items()):
        linked = by_id.get(target)
        out += f" -> {key}: " + (json.dumps(linked.fields, sort_keys=True, ensure_ascii=False) if linked else target)
    return out


def sheet(run: Path, corpus: Path, *, sample: int | None = None, papers: int | None = None,
          seed: int = 0) -> list[dict[str, str]]:
    """The sheet rows (COLUMNS) of `sample` random items of the run or of every item of its first `papers` papers;
    exactly one of the two is given. ValueError for an item whose file is not in the corpus manifest."""
    if (sample is None) == (papers is None):
        raise ValueError("give sample or papers (one of the two)")
    c = Corpus(corpus)
    order = {p.file: n for n, p in enumerate(c.papers)}
    paper_of = {p.file: p for p in c.papers}
    items = items_of(run)
    by_id = {i.item_id: i for i in items}
    for item in items:
        if item.spans[0].selector["file"] not in order:
            raise ValueError(f"item {item.item_id}: {item.spans[0].selector['file']} is not in {corpus}/manifest.json")
    if sample is not None:
        chosen = random.Random(seed).sample(items, min(sample, len(items)))
    else:
        keep = {p.file for p in c.papers[:papers]}
        chosen = [i for i in items if i.spans[0].selector["file"] in keep]
    chosen.sort(key=lambda i: (order[i.spans[0].selector["file"]], i.first_start(), i.item_id))
    texts: dict[str, tuple[str, list[tuple[int, int]]]] = {}
    rows = []
    for item in chosen:
        paper = paper_of[item.spans[0].selector["file"]]
        if paper.file not in texts:
            text = c.text(paper)
            texts[paper.file] = (text, sentences(text))
        text, cuts = texts[paper.file]
        around = dict.fromkeys(_around(text, s.selector["start"], s.selector["end"], cuts)
                               for s in sorted(item.spans, key=lambda s: s.selector["start"]))
        rows.append({"item_id": item.item_id, "paper": paper.id, "type": item.evidence_type,
                     "fields": _fields(item, by_id), "sentence": " ... ".join(a for a in around if a),
                     "right_or_wrong": "", "note": ""})
    return rows


def write_sheet(rows: list[dict[str, str]], out: Path) -> Path:
    """The CSV at `out`, UTF-8 with a byte-order mark (Excel reads it as UTF-8)."""
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(buf.getvalue().encode("utf-8-sig"))
    return out


def _read(path: Path) -> list[dict[str, str]]:
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    header = text.split("\n", 1)[0]
    delimiter = ";" if header.count(";") > header.count(",") else ","
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)
    if "right_or_wrong" not in (reader.fieldnames or []):
        raise ValueError(f"{path}: not a hand-check sheet, no right_or_wrong column")
    return list(reader)


def wilson(right: int, n: int, z: float = Z95) -> list[float]:
    """The Wilson score interval of `right` out of `n` (n > 0)."""
    p = right / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [centre - half, centre + half]


def summarise(path: Path) -> dict[str, Any]:
    """{n, right, precision, wilson95: [lo, hi]} over the marked rows (right/r/yes/y or wrong/w/no/n, any case);
    blank rows are not counted, anything else is a ValueError naming the row. With no marked row, precision and
    the interval are None."""
    n = right = 0
    for number, row in enumerate(_read(path), start=2):     # line 1 is the header
        cell = (row.get("right_or_wrong") or "").strip().lower()
        if not cell:
            continue
        if cell not in RIGHT | WRONG:
            raise ValueError(f"row {number} ({row.get('item_id', '')}): right_or_wrong is {cell!r}; "
                             "write right or wrong, or leave it empty")
        n += 1
        right += cell in RIGHT
    return {"n": n, "right": right, "precision": right / n if n else None, "wilson95": wilson(right, n) if n else None}
