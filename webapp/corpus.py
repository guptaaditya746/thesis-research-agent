"""Passages from the frozen corpus: the window around a quote, for the claim walk (`/api/corpus`).

Offsets are raw code-point offsets into the file's text exactly as stored (agent/anchor.py: the
selectors' start/end, `read_text`), so the highlight is `start - offset, end - offset` in the
returned window. The frontend slices in JavaScript, whose strings count UTF-16 code units: any
character outside the BMP before the quote (math italic letters are common in converted PDFs)
shifts a code-point highlight, so the same span is also given in UTF-16 units (`highlight_utf16`).
A paper is known by its manifest id (`p12`, `2025-acl-long-892`; `.md` optional); papers whose
conversion failed have no text. The title is the file's first Markdown heading.
"""
from __future__ import annotations

import re
import threading
from collections import OrderedDict
from pathlib import Path

from agent.anchor import read_text

from .files import NotFound, check_id, inside, read_json, signature
from .models import Highlight, Passage

HEADING = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t#]*$", re.M)
MAX_CONTEXT = 20_000
CACHE_FILES = 32


class Corpus:
    """One corpus directory and its manifest.json; recently read texts are cached by file signature."""

    def __init__(self, root: Path | None) -> None:
        self.root = root
        self._texts: OrderedDict[Path, tuple[tuple, str]] = OrderedDict()
        self._papers: tuple[tuple, dict[str, dict]] | None = None
        self._lock = threading.Lock()

    @property
    def manifest(self) -> Path | None:
        return self.root / "manifest.json" if self.root else None

    def papers(self) -> dict[str, dict]:
        """Manifest entries with text, by id."""
        if self.manifest is None:
            return {}
        key = signature(self.manifest)
        if self._papers is not None and self._papers[0] == key:
            return self._papers[1]
        data = read_json(self.manifest)
        papers = {p["id"]: p for p in (data.get("papers", []) if isinstance(data, dict) else [])
                  if p.get("failure") is None and p.get("markdown_sha256")}
        self._papers = (key, papers)
        return papers

    def paper_id(self, value: str) -> str:
        """`p12`, `p12.md`, `P12` -> the manifest id; NotFound for anything else."""
        if self.root is None:
            raise NotFound("no corpus configured (set $CORPUS)")
        name = check_id(value, "paper")
        name = name[:-3] if name.lower().endswith(".md") else name
        papers = self.papers()
        found = papers.get(name) or next((p for k, p in papers.items() if k.casefold() == name.casefold()), None)
        if found is None:
            raise NotFound(f"no such paper in the corpus manifest: {value!r}")
        return found["id"]

    def text(self, paper_id: str) -> str:
        path = inside(self.root, f"{paper_id}.md")
        key = signature(path)
        with self._lock:
            hit = self._texts.get(path)
            if hit and hit[0] == key:
                self._texts.move_to_end(path)
                return hit[1]
        try:
            text = read_text(path)
        except OSError as exc:
            raise NotFound(f"cannot read {path.name}: {exc.strerror}") from exc
        with self._lock:
            self._texts[path] = (key, text)
            while len(self._texts) > CACHE_FILES:
                self._texts.popitem(last=False)
        return text

    def manifest_hash(self, paper_id: str) -> str | None:
        return (self.papers().get(paper_id) or {}).get("markdown_sha256")

    def passage(self, paper: str, start: int | None = None, end: int | None = None,
                context: int = 1500) -> Passage:
        """The window [start - context, end + context) of the paper's text, with the span highlighted.

        Without a span: the first 2 * context characters and no highlight.
        """
        paper_id = self.paper_id(paper)
        text = self.text(paper_id)
        context = max(0, min(int(context), MAX_CONTEXT))
        if start is None and end is None:
            lo, hi, highlight = 0, min(len(text), 2 * context), None
        else:
            if start is None or end is None or not (0 <= start <= end <= len(text)):
                raise ValueError(f"span [{start}, {end}) must lie inside the paper (0..{len(text)})")
            lo, hi = max(0, start - context), min(len(text), end + context)
            highlight = Highlight(start=start - lo, end=end - lo)
        window = text[lo:hi]
        utf16 = Highlight(start=utf16_len(window[:highlight.start]),
                          end=utf16_len(window[:highlight.end])) if highlight else None
        return Passage(paper_id=paper_id, title=title(text, paper_id), text=window, highlight=highlight,
                       highlight_utf16=utf16, offset=lo, length=len(text))


def utf16_len(text: str) -> int:
    """Length of `text` in UTF-16 code units (JavaScript's string length)."""
    return len(text.encode("utf-16-le")) // 2


def title(text: str, fallback: str) -> str:
    """The first Markdown heading (Docling writes the paper title as the first `##` line)."""
    match = HEADING.search(text, 0, min(len(text), 50_000))
    return match.group(1).strip() if match else fallback
