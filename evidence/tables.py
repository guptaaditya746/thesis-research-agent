"""Two readers for the tables of a PDF: Docling and pdfplumber each read every table; a cell they disagree on is
"table unsure".

    read_tables(pdf) -> list[Table]       Table(page, cells, unsure): Docling's cells, `unsure` = (row, col) pairs
    table_markdown(table) -> str          a Markdown table, then one `<!-- table unsure: r,c -->` line per unsure cell
    unsure_spans(markdown) -> list[(start, end)]   character spans of the unsure cells in such Markdown, for the
                                                   value check (evidence/checks.py) to mark values "table unsure"

Rules: the tables of one page are matched by the cells they share (the same text at the same place). A Docling
table that has no pdfplumber table on its page, or none that shares a cell with it, keeps Docling's cells with
EVERY cell unsure (never dropped: Review Focus 5). A cell pdfplumber does not have (a merged cell it read
smaller, a shorter row) is unsure too. Cell text is compared after whitespace is collapsed. No vision model.
The readers are plain functions, so tests pass their own; the defaults import Docling and pdfplumber on first use."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

UNSURE = "table unsure"
COMMENT = re.compile(r"<!-- table unsure: (\d+),(\d+) -->")
SEPARATOR = re.compile(r"\|(\s*:?-+:?\s*\|)+")

Raw = list[tuple[int, list[list[str]]]]   # (page number from 1, rows of cell text)
Reader = Callable[[Path], Raw]


@dataclass(frozen=True)
class Table:
    page: int
    cells: list[list[str]]
    unsure: set[tuple[int, int]] = field(default_factory=set)


def _norm(text: str) -> str:
    return " ".join((text or "").split())


def docling_tables(pdf: Path) -> Raw:
    """Every table Docling finds, with its page. ImportError when Docling is not installed (`uv sync --group fetch`)."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    out: Raw = []
    for table in converter.convert(pdf).document.tables:
        page = table.prov[0].page_no if table.prov else 0
        out.append((page, [[cell.text for cell in row] for row in table.data.grid]))
    return out


def plumber_tables(pdf: Path) -> Raw:
    """Every table pdfplumber finds in the PDF's text layer, with its page."""
    import pdfplumber

    out: Raw = []
    with pdfplumber.open(pdf) as doc:
        for n, page in enumerate(doc.pages, start=1):
            for rows in page.extract_tables():
                out.append((n, [[c or "" for c in row] for row in rows]))
    return out


def _agree(a: list[list[str]], b: list[list[str]]) -> int:
    return sum(_norm(x) == _norm(b[r][c]) for r, row in enumerate(a) if r < len(b)
               for c, x in enumerate(row) if c < len(b[r]) and _norm(x))


def read_tables(pdf: Path, *, docling: Reader = docling_tables, plumber: Reader = plumber_tables) -> list[Table]:
    """Docling's tables of `pdf`, each with the cells pdfplumber reads differently marked unsure."""
    return compare(docling(pdf), plumber(pdf))


def compare(docling_raw: Raw, mine: Raw) -> list[Table]:
    """Docling's tables with the cells the pdfplumber tables `mine` do not confirm marked unsure."""
    free = list(range(len(mine)))
    out: list[Table] = []
    for page, cells in docling_raw:
        cells = [[_norm(c) for c in row] for row in cells]
        best = max((i for i in free if mine[i][0] == page), key=lambda i: _agree(cells, mine[i][1]), default=None)
        if best is None or _agree(cells, mine[best][1]) == 0:
            out.append(Table(page, cells, {(r, c) for r, row in enumerate(cells) for c in range(len(row))}))
            continue
        free.remove(best)
        other = mine[best][1]
        unsure = {(r, c) for r, row in enumerate(cells) for c, x in enumerate(row)
                  if r >= len(other) or c >= len(other[r]) or _norm(other[r][c]) != x}
        out.append(Table(page, cells, unsure))
    return out


def table_markdown(table: Table) -> str:
    """The table as Markdown (first row the header), then one `<!-- table unsure: r,c -->` line per unsure cell."""
    from evidence.sources import markdown_table

    text = markdown_table(table.cells)
    marks = [f"<!-- {UNSURE}: {r},{c} -->" for r, c in sorted(table.unsure)]
    return "\n".join([text, *marks])


def unsure_spans(markdown: str) -> list[tuple[int, int]]:
    """Character spans, in `markdown`, of the cells named by `<!-- table unsure: r,c -->` lines that follow a
    Markdown table written by `table_markdown` (row 0 is the header line, row r >= 1 is the line r + 1)."""
    lines = markdown.split("\n")
    starts, pos = [], 0
    for ln in lines:
        starts.append(pos)
        pos += len(ln) + 1
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        if not COMMENT.fullmatch(lines[i].strip()):
            i += 1
            continue
        run = i
        while i < len(lines) and COMMENT.fullmatch(lines[i].strip()):
            i += 1
        top = run
        while top > 0 and lines[top - 1].startswith("|"):
            top -= 1
        for line in lines[run:i]:
            r, c = map(int, COMMENT.fullmatch(line.strip()).groups())   # type: ignore[union-attr]
            at = top + (0 if r == 0 else r + 1)
            if at >= run:
                continue
            bars = [m.start() for m in re.finditer(r"(?<!\\)\|", lines[at])]
            if c + 1 < len(bars):
                spans.append((starts[at] + bars[c] + 1, starts[at] + bars[c + 1]))
    return spans


def annotate(markdown: str, docling_raw: Raw, plumber_raw: Raw) -> str:
    """`markdown` (Docling's export) with the `<!-- table unsure: r,c -->` lines of each table written right after
    its Markdown block. Docling's tables are matched to the blocks in export order; when the counts differ nothing
    can be matched, so every cell of every block is marked unsure (never silently sure)."""
    tables = compare(docling_raw, plumber_raw)
    lines = markdown.split(chr(10))
    blocks: list[tuple[int, int]] = []     # (first line, last line + 1) of each run of `|` lines
    i = 0
    while i < len(lines):
        if lines[i].startswith("|"):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            blocks.append((i, j))
            i = j
        else:
            i += 1
    out: list[str] = []
    last = 0
    for k, (a, b) in enumerate(blocks):
        out += lines[last:b]
        last = b
        if len(blocks) == len(tables):
            unsure = tables[k].unsure
        else:
            rows = [x for x in lines[a:b] if not SEPARATOR.fullmatch(x)]
            unsure = {(r, c) for r, row in enumerate(rows) for c in range(max(row.count("|") - 1, 0))}
        out += [f"<!-- {UNSURE}: {r},{c} -->" for r, c in sorted(unsure)]
    out += lines[last:]
    return chr(10).join(out)
