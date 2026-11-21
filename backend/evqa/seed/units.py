"""Freeze the unit table that `evqa/norm.py` reads: backend/evqa/units.json.

norm.py runs inside the pipeline (Extract, Answer), which may never open data/seed (seed wall). So the unit facts it
needs (QUDT IRI, symbol, conversion multiplier, dimension, the words a paper may use) are copied once into a small
file inside the package. Sources:
  - the units the seed uses: data/seed/vocab/qudt-subset.ttl and our own ex:PercentagePoint in glue.ttl;
  - a few more units a writer may use instead (g, %, mg/dL, days, ...): the cached QUDT download (`evqa seed vocab`).
The words list is the English labels and symbols from QUDT plus the hand-written ALIASES below.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import rdflib
from rdflib import RDFS, Literal, URIRef

from evqa.paths import BACKEND_EVQA, SCHEMA, VOCAB
from evqa.seed import vocab
from evqa.seed.vocab import QUDT, UNIT

EX = "https://w3id.org/evqa/seed#"
PP = EX + "PercentagePoint"
OUT = BACKEND_EVQA / "units.json"
# Units a paper may write although the seed does not store values in them.
EXTRA = ("GM", "MicroGM", "LB", "PERCENT", "MilliGM-PER-DeciL", "DAY", "MO", "YR")
# Plain-word spellings QUDT lacks. Matching ignores case and treats "-" like a space.
ALIASES: dict[str, list[str]] = {
    PP: ["percentage points", "percentage point", "percent points", "percent point", "% points", "% point",
         "%-points", "pp", "p.p."],
    str(UNIT.PERCENT): ["%", "percent", "per cent"],
    str(UNIT.KiloGM): ["kg", "kilogram", "kilograms", "kilogramme", "kilogrammes"],
    str(UNIT.GM): ["g", "gram", "grams", "gramme", "grammes"],
    str(UNIT.MilliGM): ["mg", "milligram", "milligrams", "milligramme", "milligrammes"],
    str(UNIT.MicroGM): ["µg", "μg", "ug", "mcg", "microgram", "micrograms"],
    str(UNIT.LB): ["lb", "lbs", "pound", "pounds"],
    str(UNIT["MilliMOL-PER-L"]): ["mmol/l", "mmol l-1", "mmol per litre", "mmol per liter", "millimoles per litre",
                                  "millimoles per liter", "millimole per litre", "millimole per liter"],
    str(UNIT["MilliGM-PER-DeciL"]): ["mg/dl", "mg per decilitre", "mg per deciliter", "milligrams per decilitre",
                                     "milligrams per deciliter"],
    str(UNIT.WK): ["week", "weeks", "wk", "wks"],
    str(UNIT.MilliM_HG): ["mmhg", "mm hg", "millimetres of mercury", "millimeters of mercury",
                          "millimetre of mercury", "millimeter of mercury"],
    str(UNIT.DAY): ["day", "days"],
    str(UNIT.MO): ["month", "months"],
    str(UNIT.YR): ["year", "years"],
}
# How the brief writes a value in each seed unit ("-0.78 percentage points").
WRITE_AS = {PP: "percentage points", str(UNIT.KiloGM): "kg", str(UNIT.MilliGM): "mg",
            str(UNIT["MilliMOL-PER-L"]): "mmol/L", str(UNIT.WK): "weeks", str(UNIT.MilliM_HG): "mmHg"}


def _english(g: rdflib.Graph, u: URIRef) -> list[str]:
    return sorted({str(o).lower() for o in g.objects(u, RDFS.label)
                   if isinstance(o, Literal) and o.language in (None, "en")})


def _entry(g: rdflib.Graph, full: rdflib.Graph, u: URIRef, source: str) -> dict[str, Any]:
    iri = str(u)
    mult = g.value(u, QUDT.conversionMultiplier)
    symbol = g.value(u, QUDT.symbol)
    dim = full.value(u, QUDT.hasDimensionVector)
    words = set(ALIASES.get(iri, []))
    words |= set(_english(g, u)) | {w + "s" for w in _english(g, u) if " " not in w}
    if symbol is not None and len(str(symbol)) > 1:   # one-letter symbols ("a" = year, "d" = day) only via ALIASES
        words.add(str(symbol).lower())
    return {"symbol": str(symbol) if symbol is not None else iri.rsplit("/", 1)[-1],
            "label": (_english(g, u) or [iri])[0],
            "multiplier": format(Decimal(str(mult)), "f"),
            # Percentage points have their own kind, so they never match percent although both scale by 0.01.
            "dimension": "percentage-point" if iri == PP else str(dim).rsplit("/", 1)[-1],
            "words": sorted(words, key=lambda w: (-len(w), w)),
            "write_as": WRITE_AS.get(iri, str(symbol) if symbol is not None else iri),
            "source": source}


def build() -> dict[str, Any]:
    """The unit table as a dict (what `freeze` writes)."""
    subset = rdflib.Graph()
    subset.parse(VOCAB / "qudt-subset.ttl")
    subset.parse(SCHEMA / "glue.ttl")
    qudt_file = vocab.folder() / vocab.SOURCES["qudt"][0]
    if not qudt_file.is_file():
        raise FileNotFoundError(f"{qudt_file} missing: run `evqa seed vocab` first (it downloads QUDT)")
    full = rdflib.Graph()
    full.parse(qudt_file, format="turtle")
    units: dict[str, Any] = {}
    for u in sorted(set(subset.subjects(rdflib.RDF.type, QUDT.Unit))):
        units[str(u)] = _entry(subset, full, u, "glue.ttl" if str(u).startswith(EX) else "qudt-subset.ttl")
    for name in EXTRA:
        units[str(UNIT[name])] = _entry(full, full, UNIT[name], "QUDT download")
    return {"about": "Unit table for evqa/norm.py. Made by evqa.seed.units.freeze(); do not edit by hand.",
            "qudt_sha256": vocab.sha256(qudt_file), "units": units}


def freeze(path: Path = OUT) -> Path:
    path.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
