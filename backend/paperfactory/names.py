"""Invented proper names for drafted world entities, made in code (22 Nov 2026).

The world model returns each entity's kind, name_parts (plain words the pack asks for, e.g. a court type) and attrs.
`assign` fills the pack's name pattern for the kind ("kinds".<kind>."name") with fresh invented words. Each word goes
to one entity only, so no entity's name can sit inside another's. Why: at 20 papers Qwen ran out of fresh names and
reused them ("Mora v. DataFlow Ltd" / "Mora App", model "Zephyr" / study "Zephyr 2024"); world.check rejected the
entities after the repair, twice per field (runs/paperfactory/qwen-law*.log, qwen-llm*.log, 22 Nov 2026).

Pattern slots: {W} {W2} fresh words of this entity; {w} / {WU} the first one in lower / upper case; {COUNTRY} one
word for the whole world; {D} a digit 2-9; {a:<attr>} an attribute; {<part>} a name part.
"""
from __future__ import annotations

import json
import random
import re
from typing import Any

from paperfactory.packs import Field

ONSETS = ["b", "d", "f", "g", "h", "k", "l", "m", "n", "p", "r", "s", "t", "v", "z", "br", "dr", "gr", "kr", "tr",
          "st", "th"]
VOWELS = ["a", "e", "i", "o", "u", "a", "e", "o"]
CODAS = ["", "", "n", "r", "l", "s", "m"]
SLOT = re.compile(r"\{([^{}]+)\}")
MAX_PART_WORDS = 5


def parts_of(f: Field, kind: str) -> dict[str, str]:
    """The name parts the model gives for a kind: {part: what it is}."""
    return f.kinds.get(kind, {}).get("name", {}).get("parts", {})


class Namer:
    """Fresh invented words from a seed: the same seed and field give the same words in the same order. Words of
    the pack text and its real names are never used (the model's examples, e.g. 'Tamsel', stay examples)."""

    def __init__(self, seed: Any, f: Field) -> None:
        self.rng = random.Random(f"{seed}:{f.name}")
        self.used = set(re.findall(r"[a-z]+", json.dumps(f.raw).lower()))
        self.used |= {x for r in f.raw.get("real_names", []) for x in re.findall(r"[a-z]+", r.lower())}
        self.country = ""

    def word(self) -> str:
        while True:
            w = "".join(self.rng.choice(ONSETS) + self.rng.choice(VOWELS)
                        for _ in range(self.rng.choice((2, 2, 3)))) + self.rng.choice(CODAS)
            if len(w) >= 5 and w not in self.used:
                self.used.add(w)
                return w.capitalize()


def fill(pattern: str, parts: dict[str, str], attrs: dict[str, Any], mine: dict[str, str], namer: Namer) -> str:
    def one(m: re.Match) -> str:
        k = m.group(1)
        if k in ("W", "W2", "w", "WU"):
            key = "W2" if k == "W2" else "W"
            if key not in mine:
                mine[key] = namer.word()
            return mine[key].lower() if k == "w" else mine[key].upper() if k == "WU" else mine[key]
        if k == "D":
            if "D" not in mine:
                mine["D"] = str(namer.rng.randint(2, 9))
            return mine["D"]
        if k == "COUNTRY":
            namer.country = namer.country or namer.word()
            return namer.country
        if k.startswith("a:"):
            return str(attrs.get(k[2:], ""))
        return str(parts.get(k, "")).strip(" -")
    return re.sub(r"\s+", " ", SLOT.sub(one, pattern)).strip()


def part_errors(eid: str, kind: str, parts: Any, f: Field) -> list[str]:
    want = parts_of(f, kind)
    if not isinstance(parts, dict):
        return [f"{eid}: name_parts must be an object"]
    err = [f"{eid}: name part {k!r} missing (a {kind} needs {sorted(want)})" for k in want
           if not str(parts.get(k, "")).strip(" -")]
    err += [f"{eid}: name part {k!r} is not one of a {kind}'s parts {sorted(want)}" for k in parts if k not in want]
    err += [f"{eid}: name part {k!r} is longer than {MAX_PART_WORDS} words" for k, v in parts.items()
            if len(str(v).split()) > MAX_PART_WORDS]
    return err


def assign(got: list[dict[str, Any]], f: Field, seed: Any, namer: Namer | None = None) -> tuple[dict[str, Any],
                                                                                           list[str]]:
    """The model's entities (id, kind, name_parts, attrs) -> world entities (kind, label, alt, attrs), and the
    errors in the name parts. A kind without a name pattern in the pack is an error, never a guess. Pass one `namer`
    to several calls (one per kind) so no word is used twice."""
    namer, ents, err = namer or Namer(seed, f), {}, []
    for e in got:
        eid, kind, parts = e.get("id", ""), e.get("kind", ""), e.get("name_parts") or {}
        pat = f.kinds.get(kind, {}).get("name")
        if kind in f.kinds and not pat:
            err.append(f"{eid}: the field pack has no name pattern for kind {kind!r}")
        if kind in f.kinds and pat:
            err += part_errors(eid, kind, parts, f)
        mine: dict[str, str] = {}
        p = parts if isinstance(parts, dict) else {}
        label = fill(pat["label"], p, e.get("attrs", {}), mine, namer) if pat else ""
        alt = [fill(a, p, e.get("attrs", {}), mine, namer) for a in pat.get("alt", [])] if pat else []
        ents[eid] = {"kind": kind, "label": label, "alt": list(dict.fromkeys(a for a in alt if a and a != label)),
                     "attrs": e.get("attrs", {})}
    return ents, err
