"""Quote anchors on paper Markdown. Copied from agent/anchor.py (plan: copy, do not import old packages), with
`spans` added so Extract can pick among repeated occurrences by the passage offsets.

A selector is a Web Annotation TextQuoteSelector (exact, prefix, suffix) plus a TextPositionSelector
(start, end) plus the sha256 of the whole file. Offsets count Unicode code points in the file's
UTF-8 text exactly as stored (no newline translation): read files with `read_text` below.

`find` accepts quotes the model retyped. Both the file and the quote are normalised the same way,
and a match in the normalised text is mapped back to RAW offsets in the file:

- NFKC per character cluster (base + combining marks), so ligatures (ﬁ, ﬂ), full-width forms and
  decomposed accents compare equal to their plain forms;
- curly and prime quote marks become ' and ";
- whitespace (spaces, newlines, NBSP) is dropped, except between a digit (or '.') and a digit,
  where it becomes one space, so `0.5 12` never equals `0.51 2` and `2023. 15` never `2023.15`;
- dash characters (-, ‐, –, —, −, ...) and soft hyphens are dropped, so `solu- tions`,
  `solutions`, `a — b` and `a-b` compare equal, EXCEPT a run of dashes before a digit (or '.'
  and a digit) that either touches the digit (`-0.5`, `x -5`, `GPT-4`) or sits between two
  digits (`3-5`, `8 - 19`): it becomes one minus sign U+2212, so `−0.5`, `-0.5` and `–0.5` match
  each other and `3–5` matches `3-5`, but none matches `0.5` or `35`. A spaced dash after a
  non-digit (`models - 138.72%`, `- 3 items`) is punctuation and is still dropped;
- HTML entities that Docling writes (&amp; &lt; &gt; &quot; &#39;) and Markdown backslash escapes
  (\\_ \\*) compare equal to the character they stand for.

Letters, digits and other punctuation must match exactly and in order, so a paraphrased, elided
('...') or partly invented quote is rejected. Matching is case-sensitive.

A match may not cut a number: one that starts with a digit right after a digit, a decimal point
or a minus sign in the file (quote `5` in `15`, `0.5` in `-0.5` or `10.5`), or ends with a digit
right before a digit or a decimal (quote `0.5` in `0.55`), is not counted (reason
`partial_number` when no other occurrence is left).
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
MINUS = "−"
GAP, DASH = " ", "-"  # what _fold yields for whitespace/invisibles and for any dash


class AnchorError(ValueError):
    """A quote could not be anchored.

    `reason` is one of: empty_quote, not_found, partial_number (found only where it cuts a number
    or drops its sign), ambiguous.
    """

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
    """NFKC and quote folding; whitespace and invisibles become GAP, dashes DASH (see _resolve_runs)."""
    out = []
    for ch in unicodedata.normalize("NFKC", chars):
        if ch.isspace() or ch in INVISIBLE:
            out.append(GAP)
        elif ch in DASHES:
            out.append(DASH)
        else:
            out.append(QUOTES.get(ch, ch))
    return "".join(out)


def _number_at(chars: str | list[str], j: int) -> bool:
    """chars[j] starts a number: a digit, or '.' and a digit."""
    if j >= len(chars):
        return False
    return chars[j].isdigit() or (chars[j] == "." and j + 1 < len(chars) and chars[j + 1].isdigit())


def _resolve_runs(chars: list[str], starts: list[int], ends: list[int]) -> tuple[str, list[int], list[int]]:
    """Drop each GAP/DASH run, but keep a minus sign or a space where it carries a number's meaning."""
    out: list[str] = []
    out_s: list[int] = []
    out_e: list[int] = []
    i, n = 0, len(chars)
    while i < n:
        if chars[i] not in (GAP, DASH):
            out.append(chars[i])
            out_s.append(starts[i])
            out_e.append(ends[i])
            i += 1
            continue
        j = i
        while j < n and chars[j] in (GAP, DASH):
            j += 1
        left = out[-1] if out else ""
        if _number_at(chars, j):
            dashes = [k for k in range(i, j) if chars[k] == DASH]
            if dashes and (chars[j - 1] == DASH or left.isdigit()):
                out.append(MINUS)
                out_s.append(starts[dashes[0]])
                out_e.append(ends[dashes[-1]])
            elif not dashes and chars[j].isdigit() and (left.isdigit() or left == "."):
                out.append(GAP)
                out_s.append(starts[i])
                out_e.append(ends[j - 1])
        i = j
    return "".join(out), out_s, out_e


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
        self.norm, self.starts, self.ends = _resolve_runs(chars, starts, ends)

    def _cuts_number(self, k: int, length: int) -> bool:
        """norm[k:k+length] starts or ends inside a number, or leaves out the number's minus sign."""
        norm = self.norm
        first, last = norm[k], norm[k + length - 1]
        if k > 0:
            before = norm[k - 1]
            if first.isdigit() and (before == MINUS or (before == "." and k > 1 and norm[k - 2].isdigit())):
                return True
            if before.isdigit() and (first == MINUS or _number_at(norm, k)):
                return True
        return last.isdigit() and _number_at(norm, k + length)

    def matches(self, folded_quote: str) -> list[int]:
        """Normalised start of every (possibly overlapping) occurrence, including number cuts."""
        out: list[int] = []
        k = self.norm.find(folded_quote)
        while k >= 0:
            out.append(k)
            k = self.norm.find(folded_quote, k + 1)
        return out

    def spans(self, folded_quote: str) -> list[tuple[int, int]]:
        """Raw spans of every occurrence of a normalised quote that does not cut a number."""
        n = len(folded_quote)
        return [(self.starts[k], self.ends[k + n - 1]) for k in self.matches(folded_quote)
                if not self._cuts_number(k, n)]


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
        if index.matches(folded):
            raise AnchorError("partial_number", "the quote occurs only where it cuts a number or "
                                                "leaves out its minus sign; quote the whole number")
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


def spans(file_text: str | Index, quote: str) -> list[tuple[int, int]]:
    """Raw spans of every occurrence of a (possibly retyped) quote that does not cut a number; [] when absent."""
    index = file_text if isinstance(file_text, Index) else Index(file_text)
    folded = normalize(quote)
    return index.spans(folded) if folded else []
