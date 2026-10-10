"""Quote anchors on corpus Markdown (milestones-1-2.md, row 1.5; plan.md 5.5).

A selector is a Web Annotation TextQuoteSelector (exact, prefix, suffix) plus a TextPositionSelector
(start, end) plus the sha256 of the whole file. Offsets count Unicode code points in the file's
UTF-8 text exactly as stored (no newline translation): read files with `read_text` below.

`find` accepts quotes the model retyped. Both the file and the quote are normalised the same way,
and a match in the normalised text is mapped back to RAW offsets in the file:

- NFKC per character cluster (base + combining marks), so ligatures (ﬁ, ﬂ), full-width forms and
  decomposed accents compare equal to their plain forms;
- curly and prime quote marks become ' and ";
- whitespace (spaces, newlines, NBSP) is dropped;
- all dash characters (-, ‐, –, —, −, ...) and soft hyphens are dropped, so `solu- tions`,
  `solutions`, `a — b` and `a-b` compare equal;
- HTML entities that Docling writes (&amp; &lt; &gt; &quot; &#39;) and Markdown backslash escapes
  (\\_ \\*) compare equal to the character they stand for.

Letters, digits and other punctuation must match exactly and in order, so a paraphrased, elided
('...') or partly invented quote is rejected. Matching is case-sensitive.
"""
from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

CONTEXT = 32
QUOTES = {**dict.fromkeys("‘’‚‛′‵`´", "'"), **dict.fromkeys("“”„‟″‶«»", '"')}
DASHES = set("-‐‑‒–—―−⁃﹘﹣－")
INVISIBLE = set("­​‌‍⁠﻿")
ENTITY = re.compile(r"&(?:amp|lt|gt|quot|apos|#[0-9]{1,6}|#x[0-9a-fA-F]{1,6});")
MD_ESCAPABLE = set("\\`*_{}[]()#+-.!|<>~")


class AnchorError(ValueError):
    """A quote could not be anchored. `reason` is one of: empty_quote, not_found, ambiguous."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


@dataclass(frozen=True)
class Selector:
    file: str
    start: int
    end: int
    exact: str
    prefix: str
    suffix: str
    sha256: str

    def json(self) -> dict[str, Any]:
        return asdict(self)


def read_text(path: Path | str) -> str:
    """The file's text exactly as stored: offsets in selectors refer to this string."""
    return Path(path).read_bytes().decode("utf-8")


def text_sha256(text: str) -> str:
    """sha256 of the file bytes (UTF-8 of `text`), comparable with manifest markdown_sha256."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def selector_at(text: str, start: int, end: int, file: str = "", sha256: str | None = None) -> Selector:
    if not (0 <= start < end <= len(text)):
        raise ValueError(f"span [{start}, {end}) must be non-empty and inside the text ({len(text)})")
    return Selector(file=file, start=start, end=end, exact=text[start:end],
                    prefix=text[max(0, start - CONTEXT):start], suffix=text[end:end + CONTEXT],
                    sha256=sha256 or text_sha256(text))


def anchor(file: Path | str, start: int, end: int) -> Selector:
    """Selector for raw offsets [start, end) in `file`, hashing the whole file."""
    return selector_at(read_text(file), start, end, file=Path(file).name)


def _fold(chars: str) -> str:
    out = []
    for ch in unicodedata.normalize("NFKC", chars):
        if ch.isspace() or ch in DASHES or ch in INVISIBLE:
            continue
        out.append(QUOTES.get(ch, ch))
    return "".join(out)


class Index:
    """The normalised form of one text and, per normalised character, its raw span."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.sha256 = text_sha256(text)
        chars: list[str] = []
        starts: list[int] = []
        ends: list[int] = []
        i, n = 0, len(text)
        while i < n:
            ch = text[i]
            if ch == "&" and (m := ENTITY.match(text, i)):
                unit, j = html.unescape(m.group()), m.end()
            elif ch == "\\" and i + 1 < n and text[i + 1] in MD_ESCAPABLE:
                unit, j = text[i + 1], i + 2
            else:
                j = i + 1
                while j < n and unicodedata.combining(text[j]):
                    j += 1
                unit = text[i:j]
            for c in _fold(unit):
                chars.append(c)
                starts.append(i)
                ends.append(j)
            i = j
        self.norm = "".join(chars)
        self.starts = starts
        self.ends = ends

    def spans(self, folded_quote: str) -> list[tuple[int, int]]:
        """Raw spans of every (possibly overlapping) occurrence of a normalised quote."""
        out: list[tuple[int, int]] = []
        k = self.norm.find(folded_quote)
        while k >= 0:
            out.append((self.starts[k], self.ends[k + len(folded_quote) - 1]))
            k = self.norm.find(folded_quote, k + 1)
        return out


def normalize(text: str) -> str:
    return Index(text).norm


def _context_score(index: Index, span: tuple[int, int], prefix: str, suffix: str) -> int:
    """Characters of normalised prefix/suffix that agree with the text around `span`."""
    text = index.text
    before = normalize(text[max(0, span[0] - 4 * CONTEXT):span[0]])
    after = normalize(text[span[1]:span[1] + 4 * CONTEXT])
    p, s = normalize(prefix), normalize(suffix)
    score = 0
    for a, b in zip(reversed(before), reversed(p)):
        if a != b:
            break
        score += 1
    for a, b in zip(after, s):
        if a != b:
            break
        score += 1
    return score


def _pick(index: Index, quote: str, prefix: str, suffix: str) -> tuple[int, int]:
    folded = normalize(quote)
    if not folded:
        raise AnchorError("empty_quote", "the quote has no letters, digits or punctuation")
    spans = index.spans(folded)
    if not spans:
        raise AnchorError("not_found", "the quote does not occur in the file")
    if len(spans) == 1:
        return spans[0]
    if prefix or suffix:
        ranked = sorted(((_context_score(index, s, prefix, suffix), s) for s in spans), reverse=True)
        if ranked[0][0] > ranked[1][0]:
            return ranked[0][1]
    raise AnchorError("ambiguous", f"the quote occurs {len(spans)} times with equal context")


def find(file_text: str | Index, quote: str, file: str = "", prefix: str = "", suffix: str = "") -> Selector:
    """Anchor a (possibly retyped) quote; raise AnchorError if it is absent or ambiguous.

    `prefix`/`suffix` are optional context hints that break ties between repeated occurrences.
    Pass an `Index` to reuse the normalisation of a file across many quotes.
    """
    index = file_text if isinstance(file_text, Index) else Index(file_text)
    start, end = _pick(index, quote, prefix, suffix)
    return selector_at(index.text, start, end, file=file, sha256=index.sha256)


@dataclass(frozen=True)
class Resolution:
    """status: ok (offsets used), relocated (found by quote), ambiguous, broken."""
    status: str
    selector: Selector | None
    file_matches_manifest: bool
    reason: str = ""


def resolve(selector: Selector, file_text: str | Index, manifest_hash: str) -> Resolution:
    """Re-find an anchor in the current file.

    If the selector, the manifest and the text all have the same hash, the offsets are used (and
    must still hold `exact`). Otherwise the quote is searched again, ties broken by prefix and
    suffix; failing that the anchor is reported broken.
    """
    index = file_text if isinstance(file_text, Index) else Index(file_text)
    in_manifest = index.sha256 == manifest_hash
    if selector.sha256 == manifest_hash and in_manifest:
        if index.text[selector.start:selector.end] == selector.exact:
            return Resolution("ok", selector, True)
        return Resolution("broken", None, True, "offsets do not hold the exact text")
    try:
        start, end = _pick(index, selector.exact, selector.prefix, selector.suffix)
    except AnchorError as exc:
        status = "ambiguous" if exc.reason == "ambiguous" else "broken"
        return Resolution(status, None, in_manifest, str(exc))
    moved = selector_at(index.text, start, end, file=selector.file, sha256=index.sha256)
    return Resolution("relocated", moved, in_manifest, "file hash changed; found by quote")
