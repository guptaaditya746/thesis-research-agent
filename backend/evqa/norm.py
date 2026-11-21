"""Read numbers as papers write them, and compare a paper number with a seed number. No LLM.

Standard form of a value (`Value`):
    value       Decimal, signed; None for a range
    low, high   Decimal bounds of a range ("0.6 to 0.9"), else None
    unit        QUDT IRI (or ex:PercentagePoint), None when the text states no unit and no default was given
    decimals    how many decimals the text printed (for a range: the fewer of the two bounds)
    sign_basis  "change" when a word made it a change ("reduced by 1.1" -> -1.1), else "level"
    raw         the text exactly as written

Rules (plan, "Value matching"):
  - "reduced by 1.1", "1.1 lower", "a 1.1 kg loss" -> -1.1 (change). An explicit sign always wins.
  - unicode minus and en dash before a digit are minus signs; "1,234.5" is 1234.5.
  - same(paper, seed): convert the paper value to the seed unit with QUDT conversion multipliers; equal when
    |a - b| <= half of the last decimal the paper printed (so -1.1 matches -1.10 and -1.12, not -1.16).
    Ranges match bound by bound. Percent and percentage points are never equal. Anything else that does not fit
    (no unit, unknown unit, units of a different kind, range vs single number) is CANT_COMPARE, not DIFFERENT.

This module is used by the pipeline too, so it reads only backend/evqa/units.json (made by evqa.seed.units).
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, NamedTuple

UNITS_FILE = Path(__file__).with_name("units.json")
PP = "https://w3id.org/evqa/seed#PercentagePoint"
PERCENT = "http://qudt.org/vocab/unit/PERCENT"
MINUS = "-−–‒—﹣－"   # hyphen, minus, en/figure/em dash, small/full-width hyphen-minus

DOWN = {"reduce", "reduced", "reduces", "reducing", "reduction", "reductions", "decrease", "decreased", "decreases",
        "decreasing", "lower", "lowered", "lowers", "lowering", "fell", "fall", "falls", "falling", "drop", "dropped",
        "drops", "decline", "declined", "declines", "loss", "lost", "less", "smaller", "cut"}
# After a number only nouns and comparisons count ('0.5 kg lower'); '40 mg reduced ...' must not flip the dose.
AFTER = {"lower", "higher", "less", "more", "greater", "smaller", "reduction", "decrease", "increase", "gain", "loss",
         "drop", "decline", "rise", "fall"}
UP = {"increase", "increased", "increases", "increasing", "raise", "raised", "raises", "rose", "rise", "rises",
      "rising", "gain", "gained", "gains", "higher", "grew", "more", "greater"}
NUMBER = re.compile(r"(?P<sign>[" + MINUS + r"+](?=\.?\d))?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)")
LIST_GAP = re.compile(r"\s*(?:,|,?\s*and|,?\s*or|/)\s*", re.I)
RANGE_GAP = re.compile(r"\s*(?:to|–|—)\s*|-", re.I)


class Verdict(str, Enum):
    SAME = "same"
    DIFFERENT = "different"
    CANT_COMPARE = "cant_compare"


class Match(NamedTuple):
    verdict: Verdict
    reason: str


@dataclass(frozen=True)
class Value:
    value: Decimal | None
    unit: str | None
    decimals: int
    sign_basis: Literal["change", "level"] = "level"
    low: Decimal | None = None
    high: Decimal | None = None
    raw: str = ""

    @property
    def is_range(self) -> bool:
        return self.low is not None

    def as_json(self) -> dict[str, Any]:
        return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in asdict(self).items()}


@dataclass(frozen=True)
class Found:
    """One value found in a text: character span [start, end) of the number(s) as written, and the value."""
    start: int
    end: int
    value: Value
    unit_from: Literal["text", "list", "default", "none"]


# ---------- units ----------

@lru_cache(maxsize=1)
def units() -> dict[str, dict[str, Any]]:
    return json.loads(UNITS_FILE.read_text(encoding="utf-8"))["units"]


def _key(word: str) -> str:
    return re.sub(r"[\s\-]+", " ", word.lower()).strip()


@lru_cache(maxsize=1)
def _unit_words() -> tuple[re.Pattern[str], dict[str, str]]:
    lookup: dict[str, str] = {}
    for iri, u in units().items():
        for w in u["words"]:
            lookup.setdefault(_key(w), iri)
    alts = sorted(lookup, key=len, reverse=True)
    body = "|".join(r"[\s\-]+".join(re.escape(part) for part in w.split(" ")) for w in alts)
    return re.compile(r"(?:" + body + r")(?![A-Za-z0-9])", re.I), lookup


def unit_of_word(word: str) -> str | None:
    """'mg' -> the QUDT IRI of milligram; None when the word is no known unit."""
    return _unit_words()[1].get(_key(word))


def unit_in(text: str) -> str | None:
    """The unit a label names, e.g. a table header 'HbA1c change (percentage points)' or 'Weight, kg'.

    A unit inside brackets wins; otherwise the first unit word of 2+ letters standing on its own."""
    pattern, lookup = _unit_words()
    for inner in re.findall(r"[(\[]([^()\[\]]*)[)\]]", text):
        m = pattern.search(inner)
        if m and (len(m.group()) > 1 or inner.strip() == m.group()):
            return lookup[_key(m.group())]
    for m in pattern.finditer(text):
        before = text[m.start() - 1] if m.start() else " "
        if len(m.group()) > 1 and not (before.isalnum() or before in "/"):
            return lookup[_key(m.group())]
    return None


def _unit_after(text: str, pos: int) -> tuple[str | None, int]:
    """Unit written right after a number ('1.2 kg', '0.5%', '24-week'): (IRI, end position) or (None, pos)."""
    m = re.compile(r"[ \t ]?-?[ \t ]?").match(text, pos)
    start = m.end() if m else pos
    pattern, lookup = _unit_words()
    u = pattern.match(text, start)
    if not u:
        return None, pos
    return lookup[_key(u.group())], u.end()


def _unit_word_before(text: str, pos: int) -> str | None:
    """Unit named just before a number, as in 'week 12' or 'day 3'."""
    m = re.search(r"([A-Za-z]+)\s*$", text[max(0, pos - 20):pos])
    return unit_of_word(m.group(1)) if m else None


# ---------- reading numbers ----------

def _decimal(sign: str | None, num: str) -> tuple[Decimal, int]:
    digits = num.replace(",", "")
    d = Decimal(digits)
    if sign and sign != "+":
        d = -d
    return d, len(digits.split(".")[1]) if "." in digits else 0


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def _direction(text: str, start: int, end: int, prev_end: int) -> int:
    """-1 / +1 when a word makes the number(s) text[start:end] a fall / rise, else 0.

    The first word after the number (and its unit) wins: '0.5 kg lower'. Otherwise the last direction word in the
    6 words before it, not crossing the previous number or a clause end: 'reduced HbA1c by 0.57'."""
    after = _words(text[end:end + 20])
    if after and after[0] in AFTER:
        if after[0] in DOWN:
            return -1
        if after[0] in UP:
            return 1
    window = text[max(prev_end, 0):start]
    cut = max((m.end() for m in re.finditer(r"[;|]|\n\s*\n|\.(?=\s)", window)), default=0)
    window = window[cut:]
    if re.search(r"\bfrom\s*$", window, re.I):
        return 0
    for w in reversed(_words(window)[-6:]):
        if w in DOWN:
            return -1
        if w in UP:
            return 1
    return 0


def _numbers(text: str) -> list[tuple[int, int, Decimal, int, bool]]:
    """(start, end, value, decimals, explicit sign) of every stand-alone number. Skips digits inside words or ids
    ('HbA1c', 'BRN-233', 'P-med-01')."""
    out = []
    for m in NUMBER.finditer(text):
        s, sign = m.start(), m.group("sign")
        if sign and sign in MINUS and s and text[s - 1].isalnum():
            if not text[s - 1].isdigit():
                continue      # hyphen in an id: 'BRN-233', 'P-med-01'
            s, sign = s + 1, None   # '0.6-0.9': the dash joins a range
        prev = text[s - 1] if s else " "
        if prev.isalnum() or prev in "._" or (prev == "," and s >= 2 and text[s - 2].isdigit()):
            continue
        if not sign and prev in MINUS and s >= 2 and text[s - 2].isalpha():
            continue
        nxt = text[m.end()] if m.end() < len(text) else " "
        if nxt.isalpha() and _unit_after(text, m.end())[0] is None and nxt not in "x×":
            continue          # '3rd', '2a' are not values
        value, dec = _decimal(sign, m.group("num"))
        out.append((s, m.end(), value, dec, bool(sign)))
    return out


def find_values(text: str, default_unit: str | None = None) -> list[Found]:
    """Every value in `text`, in order. Ranges ('0.6 to 0.9', '0.6-0.9') become one value. A number without a unit
    takes the unit of the list it ends in ('0.57, 0.78 and 0.91 percentage points'), else `default_unit`."""
    nums = _numbers(text)
    items: list[dict[str, Any]] = []
    i = 0
    while i < len(nums):
        s, e, v, dec, signed = nums[i]
        unit, uend = _unit_after(text, e)
        item = {"start": s, "end": e, "value": v, "dec": dec, "signed": signed, "unit": unit, "uend": uend,
                "low": None, "high": None}
        if i + 1 < len(nums):
            s2, e2, v2, dec2, signed2 = nums[i + 1]
            gap_from = uend if unit else e
            gap = RANGE_GAP.fullmatch(text, gap_from, s2)
            # "from 8.1 to 7.3" is a before/after pair, and "week 12 to -0.84" no range either
            if gap and not re.search(r"\bfrom\s*$", text[max(0, s - 12):s], re.I) \
                    and _unit_word_before(text, s) is None:
                unit2, uend2 = _unit_after(text, e2)
                if unit is None or unit2 is None or unit == unit2:
                    item.update(end=e2, low=v, high=v2, value=None, dec=min(dec, dec2), signed=signed or signed2,
                                unit=unit2 or unit, uend=uend2 if unit2 else uend)
                    i += 1
        items.append(item)
        i += 1
    # a unit at the end of a list applies to the whole list
    for k in range(len(items) - 1, -1, -1):
        it = items[k]
        it["unit_from"] = "text" if it["unit"] else "none"
        if it["unit"] is None and k + 1 < len(items) and items[k + 1]["unit"]:
            nxt = items[k + 1]
            if LIST_GAP.fullmatch(text, it["end"], nxt["start"]):
                it["unit"], it["unit_from"] = nxt["unit"], "list"
    out = []
    prev_end = 0
    sentence_sign = 0
    k = 0
    while k < len(items):
        group = [items[k]]   # numbers joined by list gaps share a direction word
        while k + 1 < len(items) and LIST_GAP.fullmatch(text, group[-1]["uend"] if group[-1]["unit_from"] == "text"
                                                       else group[-1]["end"], items[k + 1]["start"]):
            k += 1
            group.append(items[k])
        last = group[-1]
        sign = _direction(text, group[0]["start"], last["uend"] if last["unit_from"] == "text" else last["end"],
                          prev_end)
        between = text[prev_end:group[0]["start"]]
        if re.search(r"[;|]|\n\s*\n|\.(?=\s)", between):
            sentence_sign = 0          # a new sentence forgets the last direction word
        if sign == 0 and re.search(r"\bby\s*$", between, re.I):
            sign = sentence_sign       # '... lowered HbA1c by 0.57 pp with 10 mg, by 0.78 pp with 20 mg'
        elif sign:
            sentence_sign = sign
        for it in group:
            unit, unit_from = it["unit"], it["unit_from"]
            if unit is None and default_unit:
                unit, unit_from = default_unit, "default"
            basis: Literal["change", "level"] = "change" if sign else "level"
            flip = -1 if (sign < 0 and not it["signed"]) else 1

            def signed(d: Decimal | None, flip: int = flip) -> Decimal | None:
                return None if d is None else d * flip
            low, high = signed(it["low"]), signed(it["high"])
            if low is not None and high is not None and low > high:
                low, high = high, low
            val = Value(value=signed(it["value"]), unit=unit, decimals=it["dec"], sign_basis=basis, low=low,
                        high=high, raw=text[it["start"]:it["end"]])
            out.append(Found(it["start"], it["end"], val, unit_from))
        prev_end = last["uend"]
        k += 1
    return out


def normalize_value(text: str, unit: str | None = None, sign_basis: Literal["change", "level"] | None = None
                    ) -> Value | None:
    """The first value in `text` in standard form; None when there is no number.

    `unit` is used when the text names none (e.g. the unit from a table header). `sign_basis` overrides what the
    words say (the caller knows the number is a change); the sign itself is never changed by it."""
    found = find_values(text, unit)
    if not found:
        return None
    v = found[0].value
    if unit is None and found[0].unit_from == "none":
        named = unit_in(text)
        if named:
            v = Value(v.value, named, v.decimals, v.sign_basis, v.low, v.high, v.raw)
    if sign_basis:
        v = Value(v.value, v.unit, v.decimals, sign_basis, v.low, v.high, v.raw)
    return Value(v.value, v.unit, v.decimals, v.sign_basis, v.low, v.high, text.strip())


def seed_value(value: str, unit: str, sign_basis: Literal["change", "level"] = "change") -> Value:
    """A seed number (its decimal string as stored, e.g. '-0.90') in standard form."""
    d = Decimal(value)
    dec = max(0, -d.as_tuple().exponent)   # type: ignore[operator]
    return Value(d, unit, dec, sign_basis, raw=value)


# ---------- comparing ----------

def factor(from_unit: str, to_unit: str) -> Decimal:
    """Multiply a number in `from_unit` by this to get it in `to_unit` (same kind of unit only)."""
    u = units()
    return Decimal(u[from_unit]["multiplier"]) / Decimal(u[to_unit]["multiplier"])


def same(paper: Value, seed: Value) -> Match:
    """Is the paper's number the seed's number? Tolerance: half the last decimal the paper printed."""
    if (paper.unit is None) != (seed.unit is None):
        return Match(Verdict.CANT_COMPARE, "only one side states a unit")
    f = Decimal(1)
    if paper.unit is not None and seed.unit is not None and paper.unit != seed.unit:
        u = units()
        if paper.unit not in u or seed.unit not in u:
            return Match(Verdict.CANT_COMPARE, "unknown unit")
        if {paper.unit, seed.unit} == {PP, PERCENT}:
            return Match(Verdict.DIFFERENT, "percent and percentage points are different things")
        if u[paper.unit]["dimension"] != u[seed.unit]["dimension"]:
            return Match(Verdict.CANT_COMPARE, "units of a different kind")
        f = factor(paper.unit, seed.unit)
    if paper.is_range != seed.is_range:
        return Match(Verdict.CANT_COMPARE, "a range against a single number")
    tol = Decimal(5).scaleb(-(paper.decimals + 1)) * abs(f)
    pairs = ([(paper.low, seed.low), (paper.high, seed.high)] if paper.is_range else [(paper.value, seed.value)])
    for a, b in pairs:
        assert a is not None and b is not None
        if abs(a * f - b) > tol:
            return Match(Verdict.DIFFERENT, f"{a * f} vs {b} (allowed gap {tol})")
    return Match(Verdict.SAME, f"within {tol}")
