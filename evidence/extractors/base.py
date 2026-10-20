"""Helpers every extractor kind shares: source hashes, spans at raw offsets, numbers, sentences, tables.

Offsets are raw code-point offsets into the document text exactly as stored (agent/anchor.read_text), the
offsets every selector uses. Source files are hashed with LF line ends, so an extractor has the same
`code_sha256` (and so the same id) on a Windows checkout and on the cluster.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.anchor import selector_at
from jsonio import sha256_hex

from ..contract import Coverage, ExtractionTask, Item, Span, digest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# Modules every extractor's behaviour depends on: offsets and anchoring, sections and chunks, these helpers.
SHARED_SOURCES = (HERE / "base.py", ROOT / "agent" / "anchor.py", ROOT / "jsonio" / "__init__.py",
                  ROOT / "gold" / "chunks.py", ROOT / "evidence" / "contract.py")


def source_sha256(*paths: Path) -> str:
    """Hash of source files (repository path and LF-normalised bytes), the `code_sha256` of an extractor:
    a change to any module its behaviour depends on gives a new id, so a stale cache entry is never used."""
    parts = []
    for path in paths:
        data = path.read_bytes().replace(b"\r\n", b"\n")
        parts.append([path.resolve().relative_to(ROOT).as_posix(), sha256_hex(data)])
    return digest(parts)


def span(task: ExtractionTask, text: str, start: int, end: int, role: str) -> Span:
    """A span at raw offsets of the task's document."""
    return Span.of(role, selector_at(text, start, end, file=task.document.file, sha256=task.document.sha256))


def ranges(task: ExtractionTask, text: str) -> list[tuple[int, int]]:
    """The parts of the document the task allows, in order (the whole text for a document scope)."""
    if task.scope.kind == "document":
        return [(0, len(text))]
    return sorted((max(0, a), min(len(text), b)) for a, b in task.scope.ranges if b > a)


def coverage(parts: list[tuple[int, int]], items: list[Item]) -> tuple[Coverage, ...]:
    """found/none per examined part, counting items whose first span starts in it."""
    out = []
    for a, b in parts:
        found = sum(1 for item in items if a <= item.first_start() < b)
        out.append(Coverage(range=(a, b), status="found" if found else "none", found=found))
    return tuple(out)


def group(evidence_type: Any, found: list[tuple[dict[str, Any], dict[str, str], list[Span]]]) -> list[Item]:
    """Items from (fields, links, spans) triples; equal fields and links become one item with all spans
    (the same value reported in the abstract and in a table is one item with two value spans)."""
    merged: dict[str, tuple[dict[str, Any], dict[str, str], list[Span]]] = {}
    for fields, links, spans in found:
        key = digest([fields, links])
        if key in merged:
            merged[key][2].extend(spans)
        else:
            merged[key] = (fields, links, list(spans))
    items = []
    for fields, links, spans in merged.values():
        unique = {(s.role, s.selector["start"], s.selector["end"]): s for s in spans}
        ordered = [unique[k] for k in sorted(unique, key=lambda k: (k[1], k[2], k[0]))]
        items.append(Item.build(evidence_type, fields, ordered, links=links))
    return items


# Numbers -----------------------------------------------------------------------------------------------

NUMBER = re.compile(r"(?<![\w.,])(\d{1,3}(?:\.\d+)?|0?\.\d+)(\s?%)?(?![\w.]*\d)")


def to_fraction(raw: str, *, percent: bool, rate_like: bool) -> float | None:
    """A reported number as a fraction: "62%", "0.62" and "62.0" under a % header all give 0.62.

    `percent`: the cell, its header or the caption marks the number as a percentage. `rate_like`: the
    metric is an accuracy or a rate, so 1 < x <= 100 can only be a percentage."""
    text = raw.strip().rstrip("%").strip()
    try:
        value = float(text)
    except ValueError:
        return None
    if percent or raw.strip().endswith("%"):
        value /= 100
    elif rate_like and 1 < value <= 100:
        value /= 100
    if value < 0:
        return None
    return round(value, 6)


# Sentences and sections --------------------------------------------------------------------------------

SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"(\[])")
TABLE_LINE = re.compile(r"^\s*\|")
HEADING_LINE = re.compile(r"^\s{0,3}#{1,6}\s")


def sentences(text: str, start: int = 0, end: int | None = None) -> list[tuple[int, int]]:
    """(start, end) of each prose sentence in text[start:end]; table and heading lines are left out."""
    end = len(text) if end is None else end
    out: list[tuple[int, int]] = []
    pos = start
    for para in re.finditer(r"(?:[^\n]|\n(?!\s*\n))+", text[start:end]):
        a, b = start + para.start(), start + para.end()
        lines = text[a:b].split("\n")
        if any(TABLE_LINE.match(ln) for ln in lines) or all(HEADING_LINE.match(ln) or not ln.strip() for ln in lines):
            continue
        pos = a
        for cut in SENTENCE_END.finditer(text, a, b):
            out.append(_trim(text, pos, cut.start()))
            pos = cut.end()
        out.append(_trim(text, pos, b))
    return [(a, b) for a, b in out if b > a]


def _trim(text: str, a: int, b: int) -> tuple[int, int]:
    while a < b and text[a].isspace():
        a += 1
    while b > a and text[b - 1].isspace():
        b -= 1
    if a < b and HEADING_LINE.match(text[a:b]):  # a heading glued to the paragraph: skip its marks
        a += len(text[a:b]) - len(text[a:b].lstrip("# "))
    return a, b


# Markdown tables ---------------------------------------------------------------------------------------

SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")


@dataclass(frozen=True)
class Cell:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Table:
    header: tuple[Cell, ...]
    rows: tuple[tuple[Cell, ...], ...]
    start: int
    end: int
    caption: str


def _cells(text: str, a: int, b: int) -> tuple[Cell, ...]:
    """Cells of one table line at raw offsets, without the outer pipes and surrounding spaces."""
    line = text[a:b]
    bounds = [m.start() for m in re.finditer(r"(?<!\\)\|", line)]
    if not bounds:
        return ()
    if line[:bounds[0]].strip():
        bounds.insert(0, -1)
    if line[bounds[-1] + 1:].strip():
        bounds.append(len(line))
    cells = []
    for left, right in zip(bounds, bounds[1:]):
        s, e = left + 1, right
        while s < e and line[s].isspace():
            s += 1
        while e > s and line[e - 1].isspace():
            e -= 1
        cells.append(Cell(line[s:e], a + s, a + e))
    return tuple(cells)


def tables(text: str) -> list[Table]:
    """Every pipe table: a header line, a separator line, then body lines starting with a pipe."""
    spans = []
    pos = 0
    for raw in text.split("\n"):
        spans.append((pos, pos + len(raw)))
        pos += len(raw) + 1
    out = []
    i = 0
    while i + 1 < len(spans):
        a, b = spans[i]
        if TABLE_LINE.match(text[a:b]) and SEPARATOR.match(text[spans[i + 1][0]:spans[i + 1][1]]):
            header = _cells(text, a, b)
            j = i + 2
            rows = []
            while j < len(spans) and TABLE_LINE.match(text[spans[j][0]:spans[j][1]]):
                rows.append(_cells(text, *spans[j]))
                j += 1
            out.append(Table(header, tuple(rows), a, spans[j - 1][1], _caption(text, spans, i, j)))
            i = j
        else:
            i += 1
    return out


def _caption(text: str, spans: list[tuple[int, int]], first: int, after: int) -> str:
    """The nearest non-empty line above the table and below it, when one starts with "Table"."""
    found = []
    for k in (range(first - 1, -1, -1), range(after, len(spans))):
        for n in k:
            line = text[spans[n][0]:spans[n][1]].strip()
            if line:
                if re.match(r"^\W*Table\b", line):
                    found.append(line)
                break
    return " ".join(found)
