"""Renaming one real source paper for a domain: lower-case drug names first (an invented prefix, the real stem
kept), then synth2's renamer for every other name, with the config's keep words and the invented drug names
hidden from it. No invented word is a planted word (`avoid`: arm labels, setting names, spec author surnames)."""
from __future__ import annotations

import random
import re

from synth2.realedit import SURNAME_POOL, _new_part, apply_map, build_map, surviving, unsayable
from synth3.realspec import RealSpec

_EDGE_L, _EDGE_R = r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9])"
_HOLD = re.compile(r"qqkeep([a-j]+)qq")


def lower_names(rs: RealSpec) -> re.Pattern:
    """Whole words ending in a name stem (with at least 3 letters before it) or equal to a name word, any case."""
    alts = []
    if rs.name_stems:
        alts.append(r"[a-z]{3,}(?:" + "|".join(map(re.escape, rs.name_stems)) + ")")
    alts += [re.escape(w) for w in rs.name_words]
    return re.compile(r"\b(?:" + "|".join(alts) + r")\b" if alts else r"(?!x)x", re.I)


def _split(word: str, rs: RealSpec) -> tuple[str, str]:
    """(prefix, stem) of a lower-case drug name: the longest stem it ends with, else its last 3 letters."""
    stems = [s for s in rs.name_stems if word.endswith(s) and len(word) - len(s) >= 3]
    stem = max(stems, key=len) if stems else word[-3:]
    return word[:-len(stem)], stem


def _case_like(new: str, old: str) -> str:
    return new.upper() if old.isupper() else new.capitalize() if old[0].isupper() else new


def _drug_map(text: str, rs: RealSpec, seed: str, avoid: set[str]) -> dict[str, str]:
    """real drug name (lower case) -> invented one; drawn again when planted, already real or hard to say."""
    real = sorted({m.group(0).lower() for m in lower_names(rs).finditer(text)})
    taken = {_split(w, rs)[0] for w in real}
    out: dict[str, str] = {}
    for word in real:
        prefix, stem = _split(word, rs)
        while True:
            new = _new_part(prefix, seed, taken) + stem
            if new not in avoid and new not in real and not unsayable({word: new}):
                break
        out[word] = new
    return out


def _letters(i: int) -> str:
    return "".join("abcdefghij"[int(d)] for d in str(i))


def _hold(text: str, words: list[str]) -> tuple[str, dict[str, str]]:
    """Each whole word of `words` (case-sensitive) -> a lower-case letters-only placeholder."""
    words = sorted(set(words), key=lambda w: (-len(w), w))
    if not words:
        return text, {}
    held = {w: f"qqkeep{_letters(i)}qq" for i, w in enumerate(words)}
    pat = re.compile(_EDGE_L + "(" + "|".join(map(re.escape, words)) + ")" + _EDGE_R)
    return pat.sub(lambda m: held[m.group(1)], text), {p: w for w, p in held.items()}


def _avoid_values(mapping: dict[str, str], avoid: set[str], seed: str) -> dict[str, str]:
    """Every word of a mapped value whose lower case is in `avoid` gets a new word, the same in every value: a
    cited surname the next pool surname (not in `avoid`, not already a value), any other word a `_new_part`."""
    split = re.compile(r"[- ]")
    values = set(mapping.values())
    taken = values | {w for v in values for w in split.split(v)} | set(mapping)
    pool = list(SURNAME_POOL)
    random.Random(seed + "|avoid").shuffle(pool)
    nxt = iter(pool)
    new: dict[str, str] = {}
    for key in sorted(mapping):
        for w in split.split(mapping[key]):
            if not w or w.lower() not in avoid or w in new:
                continue
            if w in SURNAME_POOL and w not in split.split(key):
                new[w] = next(p for p in nxt if p.lower() not in avoid and p not in values)
            else:
                new[w] = _new_part(w, seed, taken)
                while new[w].lower() in avoid:
                    new[w] = _new_part(w, seed, taken)
            values.add(new[w])
    return {k: re.sub(r"[^- ]+", lambda m: new.get(m.group(0), m.group(0)), v) for k, v in mapping.items()}


def rename_source(text: str, rs: RealSpec, seed: str, avoid: set[str]) -> tuple[str, dict[str, str]]:
    """The renamed text and the map real -> invented (drug names in lower case). `avoid` holds lower-case words
    no invented name may be: every word of the arm labels and setting names, and every spec author surname."""
    drugs = _drug_map(text, rs, seed, avoid)
    pat = lower_names(rs)
    text = pat.sub(lambda m: _case_like(drugs[m.group(0).lower()], m.group(0)), text)
    forms = [f for new in drugs.values() for f in (new, new.capitalize(), new.upper())]
    text, held = _hold(text, [*rs.keep, *forms])
    mapping = _avoid_values(build_map(text, seed), avoid, seed)
    text = apply_map(text, mapping, seed)
    real_of = {_case_like(new, form): _case_like(old, form) for old, new in drugs.items()
               for form in ("x", "Xx", "XX")} | {w: w for w in rs.keep}

    def restore(s: str, real: bool) -> str:
        return _HOLD.sub(lambda m: real_of[held[m.group(0)]] if real else held[m.group(0)], s)

    mapping = {restore(k, True): restore(v, False) for k, v in mapping.items()}
    return restore(text, False), {**drugs, **mapping}


def names_left(text: str, mapping: dict[str, str], rs: RealSpec) -> list[str]:
    """Real names of the map still in the text, then every drug-like word that is not an invented name."""
    invented = {v.lower() for v in mapping.values()}
    drugs = sorted({m.group(0) for m in lower_names(rs).finditer(text) if m.group(0).lower() not in invented})
    return surviving(text, mapping) + drugs
