"""Split one paper.md into passages with exact character offsets.

A passage is a paragraph (a block between blank lines) or a Markdown table together with its caption (the
"Table N: ..." paragraph just above it). Headings are not passages; each passage remembers the nearest heading
above it as `section`. `text == paper[start:end]` always holds (checked in tests and again in `check`)."""
from __future__ import annotations

import re

from evqa.contracts import Passage

_BLOCK = re.compile(r"[^\n]+(?:\n[^\n]+)*")       # lines up to the next blank line
_CAPTION = re.compile(r"^\s*Table\s+\w+[.:]", re.I)


def _is_table(block: str) -> bool:
    return any(line.lstrip().startswith("|") for line in block.splitlines())


def split(paper: str) -> list[Passage]:
    """Passages of `paper` in reading order."""
    blocks = [(m.start(), m.end(), m.group()) for m in _BLOCK.finditer(paper)]
    out: list[Passage] = []
    section = ""
    pending_caption: Passage | None = None   # a caption waiting for its table
    for start, end, text in blocks:
        if text.strip() == "":
            continue
        if text.lstrip().startswith("#") and "\n" not in text.strip():
            if pending_caption is not None:
                out.append(pending_caption)
                pending_caption = None
            section = text.strip().lstrip("#").strip()
            continue
        if _is_table(text):
            if pending_caption is not None:   # caption + table become one passage
                start = pending_caption.start
                pending_caption = None
            out.append(Passage(start=start, end=end, text=paper[start:end], kind="table", section=section))
            continue
        if pending_caption is not None:
            out.append(pending_caption)
            pending_caption = None
        p = Passage(start=start, end=end, text=paper[start:end], kind="text", section=section)
        if _CAPTION.match(text):
            pending_caption = p
        else:
            out.append(p)
    if pending_caption is not None:
        out.append(pending_caption)
    return out


def title(paper: str) -> str:
    m = re.search(r"^#\s+(.+)$", paper, re.M)
    return m.group(1).strip() if m else ""


def abstract(passages: list[Passage]) -> str:
    """The text of the passages under an "Abstract" heading (or the first passage when there is none)."""
    got = [p.text for p in passages if p.section.lower().strip(" .0123456789") == "abstract"]
    return "\n\n".join(got) if got else (passages[0].text if passages else "")


def check(paper: str, p: Passage) -> bool:
    """Code check: the passage's offsets point at exactly its text."""
    return 0 <= p.start < p.end <= len(paper) and paper[p.start:p.end] == p.text
