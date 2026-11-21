"""Canonical forms of slot values, so rows that say the same thing in other words group together. No LLM.

    slot("time point") -> "time_point"        slot names from the spec (labels or ids) to one key
    time("week 24") == time("24 weeks") == time("24-week") == "24 wk"
    dose("20 mg daily") == dose("20mg") == "20 mg"
    group("Adults with type 2 diabetes who are taking metformin") == group("adults with type 2 diabetes on metformin")
    value(slot, text) -> the canonical text for any slot; sort_key(slot, text) orders time and dose by number.

Used by Extract (merge key) and Answer (filter, columns, groups). Text that does not parse stays as written
(lower-cased, spaces collapsed), so nothing is silently merged.
"""
from __future__ import annotations

import re
from decimal import Decimal

from evqa import norm

SLOTS = {"time_point": ("time point", "time", "week", "time_point", "timepoint", "visit"),
         "patient_group": ("patient group", "patient_group", "patients", "population", "context", "group"),
         "dose": ("dose", "dosage", "dose level"),
         "subject": ("subject", "drug", "treatment", "intervention", "candidate"),
         "comparator": ("comparator", "control"),
         "measure": ("measure", "outcome", "endpoint")}
_SLOT = {_w: key for key, words in SLOTS.items() for _w in words}

TIME_UNITS = {"week": "wk", "weeks": "wk", "wk": "wk", "wks": "wk", "month": "mo", "months": "mo", "mo": "mo",
              "day": "d", "days": "d", "d": "d", "year": "yr", "years": "yr", "yr": "yr", "yrs": "yr"}
TO_WEEKS = {"wk": Decimal(1), "mo": Decimal("4.348"), "d": Decimal(1) / Decimal(7), "yr": Decimal("52.18")}
_NUM = r"(\d+(?:\.\d+)?)"
_TUNIT = r"(weeks?|wks?|months?|mo|days?|d|years?|yrs?)"
TIME_BEFORE = re.compile(r"\b" + _TUNIT + r"\s*" + _NUM + r"\b", re.I)          # week 24
TIME_AFTER = re.compile(r"\b" + _NUM + r"\s*-?\s*" + _TUNIT + r"\b", re.I)       # 24 weeks, 24-week
# filler words that do not change who the patients are ("adults ... who are taking metformin" = "... on metformin")
FILLER = {"a", "an", "the", "who", "are", "is", "were", "was", "already", "with", "on", "taking", "take", "takes",
          "receiving", "treated", "using", "in", "of", "and", "patients", "patient", "people", "participants",
          "adults", "adult", "subjects", "background", "therapy", "treatment", "existing", "current", "currently",
          "stable", "t2d", "t2dm"}
SPELL = {"t2d": "type 2 diabetes", "t2dm": "type 2 diabetes", "type ii": "type 2"}


def slot(name: str) -> str:
    """The slot key of a spec column, fixed key or open-point id; unknown names keep their own key."""
    key = re.sub(r"[\s\-]+", " ", name.strip().lower())
    return _SLOT.get(key, key.replace(" ", "_"))


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower()).strip(" .,;:")


def _num(text: str) -> str:
    d = Decimal(text)
    return format(d.normalize(), "f") if d == d.to_integral_value() else text


def time(text: str) -> str:
    """'week 24', '24 weeks', '24-week', 'Week 24' -> '24 wk'. Text without a number and time unit stays plain."""
    m = TIME_BEFORE.search(text)
    if m:
        return f"{_num(m.group(2))} {TIME_UNITS[m.group(1).lower()]}"
    m = TIME_AFTER.search(text)
    if m:
        return f"{_num(m.group(1))} {TIME_UNITS[m.group(2).lower()]}"
    return _plain(text)


def dose(text: str) -> str:
    """'20 mg daily', '20mg once daily', 'Brenoxalin 20 mg' -> '20 mg'. Without a number with a unit: plain text."""
    for f in norm.find_values(text):
        if f.value.unit and f.value.value is not None:
            sym = norm.units().get(f.value.unit, {}).get("symbol", "")
            if sym and norm.units()[f.value.unit]["dimension"] not in ("A0E0L0I0M0H0T1D0",):   # not a time
                return f"{_num(str(abs(f.value.value)))} {sym}"
    return _plain(text)


def group(text: str) -> str:
    """Patient group as one comparable key: lower case, fillers dropped, words sorted."""
    low = _plain(text)
    for short, long in SPELL.items():
        low = re.sub(rf"\b{short}\b", long, low)
    words = [w for w in re.findall(r"[a-z0-9]+", low) if w not in FILLER]
    return " ".join(sorted(set(words)))


def value(slot_key: str, text: str | None) -> str:
    """The canonical text of a slot value (for keys and for table cells)."""
    if text is None or not str(text).strip():
        return ""
    if slot_key == "time_point":
        return time(text)
    if slot_key == "dose":
        return dose(text)
    if slot_key == "patient_group":
        return group(text)
    return _plain(text)


def sort_key(slot_key: str, text: str) -> tuple:
    """Orders time points and doses by size ('12 wk' < '24 wk' < '6 mo'; '5 mg' < '10 mg'), other text by letters."""
    if slot_key == "time_point":
        m = re.fullmatch(_NUM + r" (wk|mo|d|yr)", text)
        if m:
            return (0, Decimal(m.group(1)) * TO_WEEKS[m.group(2)], "")
    if slot_key == "dose":
        m = re.fullmatch(_NUM + r" (\S+)", text)
        if m:
            return (0, Decimal(m.group(1)), m.group(2))
    return (1, Decimal(0), text)
