"""Structured paper sources (arXiv LaTeX, PMC JATS XML) turned into Markdown with exact table cells."""
from __future__ import annotations


def markdown_table(rows: list[list[str]]) -> str:
    """Rows of cell text as a Markdown table; the first row is the header. Cell text is kept exactly (only `|`
    is escaped and newlines become spaces)."""
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [[*r, *[""] * (width - len(r))] for r in rows]

    def line(r: list[str]) -> str:
        return "| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in r) + " |"

    return "\n".join([line(rows[0]), "|" + " --- |" * width, *(line(r) for r in rows[1:])])
