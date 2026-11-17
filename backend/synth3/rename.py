"""Renaming one real source paper for a domain: lower-case drug names first (an invented prefix, the real stem
kept), then synth2's renamer for every other name, with the config's keep words and the invented drug names
hidden from it. No invented word is a planted word (`avoid`: arm labels, setting names, spec author surnames)."""
from __future__ import annotations

import random
import re

from synth2.realedit import SURNAME_POOL, _new_part, apply_map, build_map, surviving, unsayable
from synth3.realspec import RealSpec

_EDGE_L, _EDGE_R = r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9])"
_HOLD = re.compile(r"qqkeep[a-j]+qq0?")
_HEADING = re.compile(r"^#.*$", re.M)
_TITLE_WORD = re.compile(r"(?<![\w-])[A-Z][a-z]+(?![\w-])")
# Roman numerals are runs of capitals, so synth2 would rename them ("angiotensin II" -> "angiotensin UI").
ROMAN = ("II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII")


def lower_names(rs: RealSpec) -> re.Pattern:
    """Whole words ending in a name stem (with at least 3 letters before it) or equal to a name word, any case.
    A name word keeps its last 3 letters, so it needs more than 3."""
    short = [w for w in rs.name_words if len(w) <= 3]
    if short:
        raise ValueError(f"name_words: {short} have 3 letters or fewer; a name word keeps its last 3 letters")
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
    """Each whole word of `words` (case-sensitive) -> a lower-case placeholder synth2 never renames. It ends the way
    the word does (a lower-case letter, or a digit for an upper-case or digit end), so synth2 judges the next word
    as it would after the real one: "WHO Guidelines" must not look like "... qqkeep Guidelines" mid-sentence."""
    words = sorted(set(words), key=lambda w: (-len(w), w))
    if not words:
        return text, {}
    held = {w: f"qqkeep{_letters(i)}qq" + ("" if w[-1].islower() else "0") for i, w in enumerate(words)}
    pat = re.compile(_EDGE_L + "(" + "|".join(map(re.escape, words)) + ")" + _EDGE_R)
    return pat.sub(lambda m: held[m.group(1)], text), {p: w for w, p in held.items()}


def _avoid_values(mapping: dict[str, str], avoid: set[str], seed: str, real: set[str]) -> dict[str, str]:
    """Every word of a mapped value whose lower case is in `avoid` gets a new word, the same in every value: a
    cited surname the next pool surname (not in `avoid`, not already a value, not a word of the source `real`),
    any other word a `_new_part`."""
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
                new[w] = next(p for p in nxt if p.lower() not in avoid and p not in values and p not in real)
            else:
                new[w] = _new_part(w, seed, taken)
                while new[w].lower() in avoid:
                    new[w] = _new_part(w, seed, taken)
            values.add(new[w])
    return {k: re.sub(r"[^- ]+", lambda m: new.get(m.group(0), m.group(0)), v) for k, v in mapping.items()}


_PLURAL = re.compile(r"[A-Z]{2,}s")


def _plural_acronyms(mapping: dict[str, str], text: str, seed: str) -> dict[str, str]:
    """Every acronym plural in a key ("NCDs", "LMICs") gets its singular's invented acronym plus "s": synth2 reads
    "NCDs" as "NC" + the word "Ds" and invents "GHZatio". A singular in the text that synth2 kept stays, and so
    does its plural; a singular not in the text gets a new acronym."""
    taken = set(mapping) | set(mapping.values())
    single: dict[str, str] = {}

    def plural(word: str) -> str:
        s = word[:-1]
        if s not in single:
            if s in mapping:
                single[s] = mapping[s]
            elif re.search(_EDGE_L + re.escape(s) + _EDGE_R, text):
                single[s] = s
            else:
                single[s] = _new_part(s, seed, taken)
        return single[s] + "s"

    out = {}
    for key, value in mapping.items():
        kw, vw = re.split(r"([- ])", key), re.split(r"([- ])", value)
        if len(kw) == len(vw) and any(_PLURAL.fullmatch(w) for w in kw):
            value = "".join(plural(k) if _PLURAL.fullmatch(k) else v for k, v in zip(kw, vw))
        if value != key:
            out[key] = value
    return out


def hard_to_say(mapping: dict[str, str]) -> list[str]:
    """synth2's `unsayable`, with an acronym plural judged as its singular ("GHZs" is "GHZ" read aloud plus s)."""
    return unsayable({k: re.sub(r"\b([A-Z]{2,})s\b", r"\1", v) for k, v in mapping.items()})


def _map_base(text: str) -> str:
    """The text the name map is built from: heading lines lose their plain capitalised words, which are names to
    synth2 only because headings are in title case ("Results and Discussion"). Acronyms and names with digits in a
    heading ("HOPE-3") stay names; a word that is a name in the body is renamed everywhere, headings included."""
    return _HEADING.sub(lambda m: _TITLE_WORD.sub("", m.group(0)), text)


def rename_source(text: str, rs: RealSpec, seed: str, avoid: set[str]) -> tuple[str, dict[str, str]]:
    """The renamed text and the map real -> invented (drug names in lower case). `avoid` holds lower-case words
    no invented name may be: every word of the arm labels and setting names, and every spec author surname."""
    source_words = set(re.findall(r"[^\W\d_]+", text))
    drugs = _drug_map(text, rs, seed, avoid)
    pat = lower_names(rs)
    text = pat.sub(lambda m: _case_like(drugs[m.group(0).lower()], m.group(0)), text)
    forms = [f for new in drugs.values() for f in (new, new.capitalize(), new.upper())]
    keep = [*rs.keep, *ROMAN]
    keep += [w + "s" for w in keep if w[-1].isupper()]   # "BPs" stays as "BP" does
    text, held = _hold(text, [*keep, *forms])
    base = _map_base(text)
    mapping = _avoid_values(_plural_acronyms(build_map(base, seed), base, seed), avoid, seed, source_words)
    text = apply_map(text, mapping, seed)
    real_of = {_case_like(new, form): _case_like(old, form) for old, new in drugs.items()
               for form in ("x", "Xx", "XX")} | {w: w for w in keep}

    def restore(s: str, real: bool) -> str:
        return _HOLD.sub(lambda m: real_of[held[m.group(0)]] if real else held[m.group(0)], s)

    mapping = {restore(k, True): restore(v, False) for k, v in mapping.items()}
    return restore(text, False), {**drugs, **mapping}


def names_left(text: str, mapping: dict[str, str], rs: RealSpec) -> list[str]:
    """Real names of the map still in the text, then every drug-like word that is not an invented name."""
    invented = {v.lower() for v in mapping.values()}
    drugs = sorted({m.group(0) for m in lower_names(rs).finditer(text) if m.group(0).lower() not in invented})
    return surviving(text, mapping) + drugs
