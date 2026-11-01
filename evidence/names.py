"""Corpus-wide name grouping (D38). Mentions of one thing written differently join one group, by general code:
  seed   a pack's `names_seed` variants (after `clean`) form groups first;
  clean  the same name after `clean` (case, hyphens, Greek, full-width, plural);
  alias  the paper defines it ("compound 12 (hereafter Drug A)", abbrev.definitions), with the defining quote;
  near   a close spelling (rapidfuzz token_sort_ratio) whose digit runs and single-letter tokens are equal, so
         "GPT-3" / "GPT-3.5" and "Drug A" / "Drug B" stay apart;
  model  a model check for what is left (the engine step, not done here).
A name left alone gets a singleton group (answers keep it) and is listed in `unresolved`."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from rapidfuzz import fuzz

from evidence.extractors import abbrev

Step = Literal["clean", "alias", "near", "seed", "model"]
GREEK = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "κ": "kappa", "μ": "mu"}
_SEPARATORS = re.compile(r"[-_/\s]+")


def clean(name: str) -> str:
    """The comparison form of a name: NFKC, case-folded, Greek letters spelled out, hyphens, underscores and
    slashes as spaces, one trailing plural "s" dropped from words longer than 3 letters."""
    text = unicodedata.normalize("NFKC", name).casefold()
    text = "".join(GREEK.get(c, c) for c in text)
    words = _SEPARATORS.sub(" ", text).split()
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


@dataclass(frozen=True)
class Mention:
    name: str
    doc: str
    start: int
    end: int
    etype: str


@dataclass(frozen=True)
class Match:
    mention: Mention
    group: str
    step: Step
    quote: str | None


@dataclass(frozen=True)
class NameGroups:
    groups: dict[str, list[str]]
    matches: list[Match]
    unresolved: list[Mention]

    def group_of(self, name: str) -> str | None:
        for key, forms in self.groups.items():
            if name in forms:
                return key
        return None


def _guard(a: str, b: str) -> bool:
    """Different digit runs or different single-letter tokens mean different things."""
    def shape(s: str) -> tuple[list[str], list[str]]:
        return re.findall(r"\d+", s), [w for w in s.split() if len(w) == 1 and w.isalpha()]
    return shape(a) == shape(b)


def _sentence(text: str, start: int, end: int) -> str:
    left = max((text.rfind(c, 0, start) for c in ".!?\n"), default=-1) + 1
    ends = [i for i in (text.find(c, end) for c in ".!?\n") if i >= 0]
    return text[left:(min(ends) + 1) if ends else len(text)].strip()


def group_names(mentions: list[Mention], texts: dict[str, str], seed: dict[str, list[str]] | None = None,
                threshold: int = 92) -> NameGroups:
    keys = {m: clean(m.name) for m in mentions}
    parent: dict[str, str] = {k: k for k in keys.values()}
    how: dict[str, tuple[Step, str | None]] = {}      # how a key joined its group: (step, quote)
    canon: dict[str, str] = {}                         # key -> seed group name

    def find(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a: str, b: str, step: Step, quote: str | None = None) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
            how.setdefault(b if rb == b else rb, (step, quote))

    for name, variants in (seed or {}).items():
        seeded = [k for k in {clean(v) for v in [name, *variants]} if k in parent]
        for k in seeded:
            canon[k] = name
        for k in seeded[1:]:
            union(seeded[0], k, "seed")

    doc_mentions: dict[str, list[Mention]] = {}
    for m in mentions:
        doc_mentions.setdefault(m.doc, []).append(m)
    for doc, in_doc in doc_mentions.items():
        text = texts.get(doc, "")
        for d in abbrev.definitions(text) if text else []:
            folded = text.casefold()
            at = folded.find(d.short.casefold(), d.start, d.end + 1)   # where the short form starts
            long_key = clean(d.long)
            if long_key not in {keys[m] for m in in_doc}:
                continue
            # the paper may write a longer short form than the extractor's token ("Drug A" for "Drug"): the alias
            # is a mention of this paper that begins exactly where the short form begins
            for m in in_doc:
                k = keys[m]
                if k != long_key and (at >= 0 and folded.startswith(m.name.casefold(), at)):
                    union(long_key, k, "alias", _sentence(text, d.start, d.end))

    distinct = sorted(parent)
    for i, a in enumerate(distinct):
        for b in distinct[i + 1:]:
            if find(a) != find(b) and _guard(a, b) and fuzz.token_sort_ratio(a, b) >= threshold:
                union(a, b, "near")

    members: dict[str, list[Mention]] = {}
    for m, k in keys.items():
        members.setdefault(find(k), []).append(m)
    groups: dict[str, list[str]] = {}
    root_name: dict[str, str] = {}
    for root, ms in members.items():
        seeded = next((canon[k] for k in sorted({keys[m] for m in ms}) if k in canon), None)
        counts = Counter(m.name for m in ms)
        name = seeded or min(counts, key=lambda n: (-counts[n], len(n), n))
        root_name[root] = name
        groups[name] = sorted(counts, key=lambda n: (-counts[n], n))

    matches: list[Match] = []
    seen: set[str] = set()
    unresolved: list[Mention] = []
    for m in mentions:
        k = keys[m]
        root = find(k)
        name = root_name[root]
        if k in canon:
            matches.append(Match(m, name, "seed", None))
        elif k in seen:
            matches.append(Match(m, name, "clean", None))
        elif k in how:
            step, quote = how[k]
            matches.append(Match(m, name, step, quote))
        elif any(keys[o] == k for o in members[root] if o is not m) or len({keys[o] for o in members[root]}) > 1:
            matches.append(Match(m, name, "clean", None))
        seen.add(k)
        if len(members[root]) == 1:
            unresolved.append(m)
    return NameGroups(groups, matches, unresolved)
