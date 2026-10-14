"""Corpus papers split into chunks at Markdown headings (M3, plan "Gold": chunks.jsonl).

The builder screens every chunk of every paper, so no ranker decides what a model reads (the
labelling repo screened each paper's top passages by the harness ranker; gold/README.md). A chunk is
a run of whole sections, from one heading line to the next, packed greedily up to `max_chars`
(GOLD_CHUNK_CHARS, default 40,000 characters, about 10-16k tokens, so a chunk, the prompt and the
reply fit the sub-model's 32,768-token context). A section longer than that is cut at paragraph
breaks (blank lines), a paragraph longer than that at the last line break or space before the
limit, and only failing those at the limit itself.

Headings are found by a CommonMark parser (markdown-it-py), not a pattern: a `#` line inside a fenced
or indented code block (the prompt templates papers print in their appendices) is not a heading,
and setext headings (a line underlined with === or ---) are. Only top-level headings start sections
(not one quoted in a block quote or a list).

Offsets are raw code-point offsets into the file text exactly as stored (agent/anchor.read_text),
the offsets anchors use. Chunks are contiguous and cover the file, so the chunk texts in order give
the file back. `heading` is the heading text the chunk starts in (without the #s); a chunk that
continues a cut section repeats that section's heading.

When a chunk is too long for a call (gold/calls.py `too_long`: the reply hit max_tokens, or the
prompt did not fit the context), the builder cuts that chunk alone in two (`halve`, at the paragraph
break nearest its middle) and asks again for each piece, so the other chunks keep their boundaries,
cache entries and candidate ids. A piece keeps its chunk's number; `piece` says which half ("1",
"2", "21" for the first half of the second half).

The corpus is the broker's `Corpus` (agent/broker.py): file names, manifest hashes, the hash check on
read, the same anchoring a claim gets. The broker keeps every index it built, which suits a run that
reads a few papers; the builder reads all of them, so `GoldCorpus` keeps only the most recent ones (an
anchor index costs about 70 bytes per character of the paper).
"""
from __future__ import annotations

import json
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt

from agent.anchor import Index
from agent.broker import Corpus, Rejected
from agent.canonical import file_sha256, sha256_hex

MAX_CHARS = 40_000
MIN_PIECE_CHARS = 1_000  # `halve` does not cut a chunk into pieces smaller than this
LINE_BREAK = re.compile(r"\r\n?|\n")  # markdown-it's line breaks, so its line numbers map to offsets
SEPARATORS = ("\n\n", "\n", " ")


@dataclass(frozen=True)
class Chunk:
    paper_id: str
    chunk: int          # 0-based position in the paper
    start: int
    end: int
    heading: str | None
    piece: str = ""     # "" for a whole chunk; "1", "2", "12", ... for the halves `halve` cut

    @property
    def chars(self) -> int:
        return self.end - self.start

    def json(self) -> dict[str, Any]:
        return {"paper_id": self.paper_id, "chunk": self.chunk, "start": self.start, "end": self.end,
                "heading": self.heading, "chars": self.chars}


_PARSER = MarkdownIt("commonmark")


def headings(text: str) -> list[tuple[int, str | None]]:
    """(offset of the heading's first line, heading text) of every top-level heading, in order."""
    starts = [0] + [m.end() for m in LINE_BREAK.finditer(text)]
    tokens = _PARSER.parse(text)
    found = []
    for n, token in enumerate(tokens):
        if token.type == "heading_open" and token.level == 0 and token.map:
            inline = tokens[n + 1] if n + 1 < len(tokens) and tokens[n + 1].type == "inline" else None
            found.append((starts[token.map[0]], (inline.content.strip() if inline else "") or None))
    return found


def sections(text: str) -> list[tuple[int, int, str | None]]:
    """(start, end, heading) of each section: a heading line up to the next one; text before the first
    heading is a section without a heading."""
    found = headings(text)
    if not found or found[0][0] != 0:
        found.insert(0, (0, None))
    ends = [start for start, _ in found[1:]] + [len(text)]
    return [(start, end, heading) for (start, heading), end in zip(found, ends, strict=True) if end > start]


def _cut(text: str, start: int, end: int, max_chars: int) -> list[tuple[int, int]]:
    """Cut [start, end) into pieces of at most max_chars: at a blank line, else a line break, else a
    space, else at the limit. Each cut keeps the separator with the piece before it."""
    pieces = []
    while end - start > max_chars:
        limit = start + max_chars
        for sep in SEPARATORS:
            at = text.rfind(sep, start + 1, limit)
            if at > start:
                cut = at + len(sep)
                break
        else:
            cut = limit
        pieces.append((start, cut))
        start = cut
    pieces.append((start, end))
    return pieces


def halve(text: str, chunk: Chunk) -> tuple[Chunk, Chunk] | None:
    """`chunk` (of the paper `text`) cut in two near its middle: at the blank line nearest the middle,
    else a line break, else a space, else the middle itself; None when a half would be shorter than
    MIN_PIECE_CHARS. The second half's heading is the last section heading at or before its start."""
    if chunk.chars < 2 * MIN_PIECE_CHARS:
        return None
    middle = chunk.start + chunk.chars // 2
    low, high = chunk.start + MIN_PIECE_CHARS, chunk.end - MIN_PIECE_CHARS
    cut = middle
    for sep in SEPARATORS:
        before, after = text.rfind(sep, low, middle), text.find(sep, middle, high)
        options = [at + len(sep) for at in (before, after) if at >= 0 and low <= at + len(sep) <= high]
        if options:
            cut = min(options, key=lambda at: abs(at - middle))
            break
    heading = next((h for start, h in reversed(headings(text)) if start <= cut and chunk.start <= start), None)
    return (Chunk(chunk.paper_id, chunk.chunk, chunk.start, cut, chunk.heading, chunk.piece + "1"),
            Chunk(chunk.paper_id, chunk.chunk, cut, chunk.end, heading or chunk.heading, chunk.piece + "2"))


def split(text: str, max_chars: int = MAX_CHARS) -> list[tuple[int, int, str | None]]:
    """(start, end, heading) of each chunk; none for a file that is empty or only whitespace."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    if not text.strip():
        return []
    pieces = [(a, b, heading) for start, end, heading in sections(text)
              for a, b in _cut(text, start, end, max_chars)]
    chunks: list[tuple[int, int, str | None]] = []
    for a, b, heading in pieces:
        if chunks and b - chunks[-1][0] <= max_chars:
            chunks[-1] = (chunks[-1][0], b, chunks[-1][2])
        else:
            chunks.append((a, b, heading))
    return chunks


def paper_chunks(paper_id: str, text: str, max_chars: int = MAX_CHARS) -> list[Chunk]:
    return [Chunk(paper_id, n, a, b, heading) for n, (a, b, heading) in enumerate(split(text, max_chars))]


class GoldCorpus(Corpus):
    """The broker's corpus, plus every manifest entry (failed conversions too) and a bounded index cache."""

    def __init__(self, root: Path, manifest: Path, keep: int = 16) -> None:
        super().__init__(root, manifest)
        entries = json.loads(Path(manifest).read_text(encoding="utf-8"))["papers"]
        self.papers: list[str] = [str(p["id"]) for p in entries]           # manifest order
        self.failures = {str(p["id"]): p["failure"] for p in entries if p.get("failure") is not None}
        self.manifest_sha256 = file_sha256(manifest)
        self.keep = keep
        self._recent: OrderedDict[str, Index] = OrderedDict()
        self._building: dict[str, threading.Lock] = {}

    @staticmethod
    def file(paper_id: str) -> str:
        return f"{paper_id}.md"

    def text(self, paper_id: str) -> str:
        """The paper's text as stored, after the manifest hash check (Rejected: unknown_file, hash mismatch)."""
        name = self.name(self.file(paper_id))
        data = (self.root / name).read_bytes()
        if sha256_hex(data) != self.hashes[name]:
            raise Rejected("corpus_file_hash_mismatch")
        return data.decode("utf-8")

    def index(self, name: str) -> Index:
        """Corpus.index with the hash check, keeping the `keep` most recently used indexes."""
        with self._lock:
            found = self._recent.get(name)
            if found is not None:
                self._recent.move_to_end(name)
                return found
            lock = self._building.setdefault(name, threading.Lock())
        with lock:  # two chunks of one paper anchoring at once build its index once
            with self._lock:
                found = self._recent.get(name)
            if found is None:
                data = (self.root / name).read_bytes()
                if sha256_hex(data) != self.hashes[name]:
                    raise Rejected("corpus_file_hash_mismatch")
                found = Index(data.decode("utf-8"))
            with self._lock:
                self._recent[name] = found
                self._recent.move_to_end(name)
                while len(self._recent) > self.keep:
                    self._recent.popitem(last=False)
        return found
