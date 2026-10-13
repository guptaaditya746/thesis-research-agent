"""Corpus papers split into chunks at Markdown headings (M3, plan "Gold": chunks.jsonl).

The builder screens every chunk of every paper, so no ranker decides what a model reads (the
labelling repo screened each paper's top passages by the harness ranker; gold/README.md). A chunk is
a run of whole sections, from one heading line to the next, packed greedily up to `max_chars`
(GOLD_CHUNK_CHARS, default 40,000 characters, about 10-16k tokens, so a chunk, the prompt and the
reply fit the sub-model's 32,768-token context). A section longer than that is cut at paragraph
breaks (blank lines), a paragraph longer than that at the last line break or space before the
limit, and only failing those at the limit itself.

Offsets are raw code-point offsets into the file text exactly as stored (agent/anchor.read_text),
the offsets anchors use. Chunks are contiguous and cover the file, so the chunk texts in order give
the file back. `heading` is the heading line the chunk starts in (without the #s); a chunk that
continues a cut section repeats that section's heading.

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

from agent.anchor import Index
from agent.broker import Corpus, Rejected
from agent.canonical import file_sha256, sha256_hex

MAX_CHARS = 40_000
HEADING = re.compile(r"^#{1,6}[ \t]+(.*)$", re.M)


@dataclass(frozen=True)
class Chunk:
    paper_id: str
    chunk: int          # 0-based position in the paper
    start: int
    end: int
    heading: str | None

    @property
    def chars(self) -> int:
        return self.end - self.start

    def json(self) -> dict[str, Any]:
        return {"paper_id": self.paper_id, "chunk": self.chunk, "start": self.start, "end": self.end,
                "heading": self.heading, "chars": self.chars}


def sections(text: str) -> list[tuple[int, int, str | None]]:
    """(start, end, heading) of each section: a heading line up to the next one; text before the first
    heading is a section without a heading."""
    found = [(m.start(), m.group(1).strip().strip("#").strip() or None) for m in HEADING.finditer(text)]
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
        for sep in ("\n\n", "\n", " "):
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
