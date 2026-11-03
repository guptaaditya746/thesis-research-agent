"""MeasEval checks (SemEval-2021 Task 8; spec 6.12): do the engine's measured values carry the right number, unit and
measured entity?

Layout assumed (UNVERIFIED until the release is opened; `_read` is the one reader to change), a simplified JSON:
  measeval.json  {"fields": [str] | absent,
                  "papers": [{"id", "text", "field": str | absent,
                              "quantities": [{"value": float, "unit": str | null, "entity": str | null}]}]}
`fields` reports which fields the papers come from; the spec marks this unverified, so an absent list is reported as
"unverified" rather than guessed.

Units are compared as QUDT units: a unit written as a symbol or a name is mapped to its QUDT IRI by `QUDT` (a small
built-in table, no network); a unit not in the table is compared by `names.clean` of its text.

`values_check(run, src)`: `run` is the run's measured-value items as dicts (`document`, `value`, `unit`, `entity`) or
has them as `run.values`. A gold quantity is found when a run value of the same paper has its number (relative
tolerance 1e-6); then its unit and its measured entity are checked on that value.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evidence.names import clean

SOURCE_FILE = "measeval.json"
LAYOUT_VERIFIED = False   # the release layout is assumed (module docstring): quote no number before this is True
QUDT_BASE = "http://qudt.org/vocab/unit/"
QUDT: dict[str, str] = {
    "%": "PERCENT", "percent": "PERCENT", "per cent": "PERCENT",
    "mg": "MilliGM", "milligram": "MilliGM", "milligrams": "MilliGM", "g": "GM", "gram": "GM", "grams": "GM",
    "kg": "KiloGM", "kilogram": "KiloGM", "kilograms": "KiloGM",
    "ml": "MilliL", "milliliter": "MilliL", "millilitre": "MilliL", "l": "L", "liter": "L", "litre": "L",
    "mg/l": "MilliGM-PER-L", "mg/ml": "MilliGM-PER-MilliL", "g/l": "GM-PER-L",
    "mm": "MilliM", "cm": "CentiM", "m": "M", "km": "KiloM", "nm": "NanoM", "um": "MicroM", "μm": "MicroM",
    "s": "SEC", "sec": "SEC", "second": "SEC", "seconds": "SEC", "min": "MIN", "minute": "MIN", "minutes": "MIN",
    "h": "HR", "hr": "HR", "hour": "HR", "hours": "HR", "day": "DAY", "days": "DAY", "year": "YR", "years": "YR",
    "k": "K", "kelvin": "K", "°c": "DEG_C", "degc": "DEG_C", "celsius": "DEG_C", "pa": "PA", "kpa": "KiloPA",
    "mpa": "MegaPA", "hz": "HZ", "khz": "KiloHZ", "w": "W", "kw": "KiloW", "v": "V", "mv": "MilliV", "a": "A",
    "ma": "MilliA", "mol": "MOL", "mmol": "MilliMOL", "mol/l": "MOL-PER-L", "ppm": "PPM", "ev": "EV",
}


def _read(src: Path) -> dict[str, Any]:
    return json.loads((Path(src) / SOURCE_FILE).read_text(encoding="utf-8"))


def fields(src: Path) -> dict[str, Any]:
    """Which fields the papers come from: the release's own list, else "unverified" (the spec marks it unverified)."""
    data = _read(src)
    listed = sorted({str(f) for f in data.get("fields") or []} | {str(p["field"]) for p in data["papers"]
                                                                  if p.get("field")})
    return {"layout_verified": LAYOUT_VERIFIED, "fields": listed, "status": "listed in the release" if listed else "unverified"}


def qudt(unit: str | None) -> str | None:
    """The QUDT IRI of a unit written as a symbol or name; None for no unit or one not in the table."""
    if unit is None or not str(unit).strip():
        return None
    key = str(unit).strip().lower()
    return QUDT_BASE + QUDT[key] if key in QUDT else None


def same_unit(a: str | None, b: str | None) -> bool:
    if not (a or "").strip() and not (b or "").strip():
        return True
    ia, ib = qudt(a), qudt(b)
    if ia is not None or ib is not None:
        return ia == ib
    return clean(a or "") == clean(b or "")


def _same_entity(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and clean(a) == clean(b)


def values_check(run: Any, src: Path) -> dict[str, Any]:
    """Scores of the run's values against the quantities (see the module docstring): the share found, and among the
    found the share with the right unit and the right measured entity."""
    values = list(getattr(run, "values", run))
    found = unit_ok = entity_ok = total = 0
    for paper in _read(src)["papers"]:
        mine = [v for v in values if str(v.get("document")) == str(paper["id"])]
        for gold in paper.get("quantities", []):
            total += 1
            hit = next((v for v in mine if abs(float(v["value"]) - float(gold["value"]))
                        <= 1e-6 * max(1.0, abs(float(gold["value"])))), None)
            if hit is None:
                continue
            found += 1
            unit_ok += same_unit(hit.get("unit"), gold.get("unit"))
            entity_ok += _same_entity(hit.get("entity"), gold.get("entity"))
    return {"layout_verified": LAYOUT_VERIFIED, "quantities": total, "values_found": found / total if total else None,
            "unit_correct": unit_ok / found if found else None,
            "entity_correct": entity_ok / found if found else None}
