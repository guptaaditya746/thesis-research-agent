"""One general number reader (D35: no per-topic switches; one reader for every topic).

`read_numbers(text)` finds every number in a text and the form it is written in, with its value:

- `plain`      "0.68", "1,200", "7"           the number as written
- `percent`    "82.5%"                        divided by 100
- `fraction`   "41/120"                       k / n
- `k_of_n`     "41 of 120", "41 out of 120"   k / n
- `plus_minus` "0.61 ± 0.03", "61% +/- 3"     the centre (a % on either side makes it a percentage)
- `range`      "between 0.4 and 0.6", "0.4-0.6", "40 to 60%"   the low end

A compound form takes its numbers: "41 of 120" is one `k_of_n` span, not three. A count that cannot be a share
("0 of 0", "45 of 30") and a fraction with an empty or smaller denominator are no span at all and their numbers
are not read alone either, so a broken count never gives a value above 1.

The text's full- and half-width characters are NFKC-folded first ("８２．５％" reads as 82.5%; superscripts,
subscripts and fractions are left as they are, so "0.68¹" is no 0.681), and every offset (`start`, `end`, each
number's `parts`) is mapped back to the original text, so `raw == text[start:end]`. `parts` are the (start, end) of
each number of the span in order, a % sign that follows a number included. Nothing here knows a topic: whether a
number is a result (and not a year, a delta or a sample size) is the caller's decision (numbers.py).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

Form = Literal["plain", "percent", "fraction", "k_of_n", "range", "plus_minus"]


@dataclass(frozen=True)
class NumberSpan:
    start: int
    end: int
    value: float
    form: Form
    parts: tuple[tuple[int, int], ...]
    raw: str


_NUM = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)"   # 0.68, 1,200, .5
_INT = r"(?:\d{1,3}(?:,\d{3})+|\d+)"
_PCT = r"(?:\s?%)?"
# not inside a longer token ("v1.2", "1,000", "3/4/2020"), nor the number of a code name ("ZV-217", "COVID-19")
_START = r"(?<![\w.,/])(?<![A-Za-z]-)"
_STOP = r"(?![\d.,]\d|/\d|\w)"             # nor running on into one
_ONE = rf"({_NUM}{_PCT})"

PLUS_MINUS = re.compile(rf"{_START}{_ONE}\s*(?:±|\+/-|\+-)\s*{_ONE}{_STOP}")
K_OF_N = re.compile(rf"{_START}({_INT})\s+(?:out\s+of|of)\s+(?:the\s+)?({_INT})(?![\d.,]\d|\s?%|\w)", re.IGNORECASE)
FRACTION = re.compile(rf"{_START}({_INT})\s?/\s?({_INT})(?![\d.,]\d|/|\w)")
RANGE = re.compile(rf"(?i:\bbetween\s+){_ONE}\s*(?i:and)\s+{_ONE}{_STOP}|"
                   rf"{_START}{_ONE}\s*(?:-|–|—|(?i:to))\s*{_ONE}{_STOP}")
SINGLE = re.compile(rf"{_START}({_NUM})(\s?%)?")

# "N out of M" alone (measure.py, regex_measurement's count reading; moved from base.py).
COUNT = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})*|\d+)\s+out\s+of\s+(\d{1,3}(?:,\d{3})*|\d+)\b")


def count_fraction(num: str, den: str) -> float | None:
    """"N out of M" as a fraction; None for an empty denominator or more successes than trials."""
    n, d = int(num.replace(",", "")), int(den.replace(",", ""))
    if d == 0 or n > d:
        return None
    return round(n / d, 6)


def _normalise(text: str) -> tuple[str, list[int]]:
    """The text with full- and half-width forms folded (NFKC of a <wide> or <narrow> character only: "８２．５％"
    is "82.5%"; a superscript, subscript or vulgar fraction stays, so "0.68¹" is not 0.681) and, for each of its
    characters, the index of the original character it came from."""
    out: list[str] = []
    origin: list[int] = []
    for i, ch in enumerate(text):
        wide = ord(ch) > 127 and unicodedata.decomposition(ch).startswith(("<wide>", "<narrow>"))
        norm = unicodedata.normalize("NFKC", ch) if wide else ch
        out.append(norm)
        origin.extend([i] * len(norm))
    return "".join(out), origin


def _number(raw: str) -> float:
    return float(raw.replace(",", "").rstrip("%").strip())


def _scaled(raw: str, percent: bool) -> float:
    return round(_number(raw) / (100 if percent else 1), 6)


def read_numbers(text: str) -> list[NumberSpan]:
    """Every number of `text` with its form and value, in text order (see the module docstring)."""
    norm, origin = _normalise(text)
    origin.append(len(text))
    taken: list[tuple[int, int]] = []
    found: list[tuple[int, int, float, Form, list[tuple[int, int]]]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= x or a >= y for x, y in taken)

    def add(m: re.Match[str], value: float | None, form: Form, groups: tuple[int, ...]) -> None:
        if not free(m.start(), m.end()):
            return
        taken.append((m.start(), m.end()))
        if value is not None:
            found.append((m.start(), m.end(), value, form, [m.span(g) for g in groups if m.group(g)]))

    for m in PLUS_MINUS.finditer(norm):
        add(m, _scaled(m.group(1), "%" in m.group(1) or "%" in m.group(2)), "plus_minus", (1, 2))
    for rx, form in ((K_OF_N, "k_of_n"), (FRACTION, "fraction")):
        for m in rx.finditer(norm):
            k, n = int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))
            add(m, round(k / n, 6) if 0 < n and k <= n else None, form, (1, 2))   # broken: taken, no value
    for m in RANGE.finditer(norm):
        lo, hi = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        add(m, _scaled(lo, "%" in lo or "%" in hi), "range", (1, 2, 3, 4))
    for m in SINGLE.finditer(norm):
        pct = bool(m.group(2))
        add(m, _scaled(m.group(1), pct), "percent" if pct else "plain", (0,))

    spans = []
    for a, b, value, form, parts in sorted(found):
        start, end = origin[a], origin[b - 1] + 1
        spans.append(NumberSpan(start, end, value, form, tuple((origin[x], origin[y - 1] + 1) for x, y in parts),
                                text[start:end]))
    return spans
