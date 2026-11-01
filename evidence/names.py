"""Corpus-wide name grouping (D38). Mentions of one thing written differently join one group, by general code:
  seed   a pack's `names_seed` variants (after `clean`) form groups first;
  clean  the same name after `clean` (case, hyphens, Greek, full-width, plural);
  alias  the paper defines it ("compound 12 (hereafter Drug A)", abbrev.definitions), with the defining quote;
  near   a close spelling (rapidfuzz token_sort_ratio) whose digit runs and single-letter tokens are equal, so
         "GPT-3" / "GPT-3.5" and "Drug A" / "Drug B" stay apart;
  model  a model check for what is left (`confirm_leftovers`; the engine passes an `ask` whose calls are recorded).
A name left alone gets a singleton group (answers keep it) and is listed in `unresolved`."""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
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
        """The group of `name`: the group holding it as written (whitespace runs as one space, ends trimmed),
        else the first group holding a form with the same `clean` form; None when there is none."""
        plain = " ".join(name.split())
        for key, forms in self.groups.items():
            if name in forms or plain in (" ".join(f.split()) for f in forms):
                return key
        folded = clean(name)
        return next((key for key, forms in self.groups.items() if any(clean(f) == folded for f in forms)), None)


def _guard(a: str, b: str) -> bool:
    """Different digit runs, different tokens that hold a digit ("1a" / "1b", "x1" / "y1") or different
    single-letter tokens mean different things."""
    def shape(s: str) -> tuple[list[str], list[str], list[str]]:
        words = s.split()
        return (re.findall(r"\d+", s), [w for w in words if re.search(r"\d", w)],
                [w for w in words if len(w) == 1 and w.isalpha()])
    return shape(a) == shape(b)


def _sentence(text: str, start: int, end: int) -> str:
    left = max((text.rfind(c, 0, start) for c in ".!?\n"), default=-1) + 1
    ends = [i for i in (text.find(c, end) for c in ".!?\n") if i >= 0]
    return text[left:(min(ends) + 1) if ends else len(text)].strip()


def _starts_at(m: Mention, text: str, at: int) -> bool:
    """Whether mention `m` is the one that begins at offset `at` of its paper's text. Where the mention's offsets
    are real (the text there is its name, case aside) it must start at `at`; otherwise (a mention without real
    offsets) the text at `at` must begin with its name, case aside."""
    if text[m.start:m.end].casefold() == m.name.casefold():
        return m.start == at
    return re.compile(re.escape(m.name), re.IGNORECASE).match(text, at) is not None


LOCAL = "\x00"   # a paper-local key: "<clean name>\x00<doc>" (a short form a paper defines as an alias)


def group_names(mentions: list[Mention], texts: dict[str, str], seed: dict[str, list[str]] | None = None,
                threshold: int = 92) -> NameGroups:
    """Group `mentions` by the steps of the module docstring. An alias a paper defines ("compound 12 (hereafter
    Drug A)") is paper-local: the short form joins the long form only for the mentions of that paper (its key is
    paper-local), so another paper's "Drug A" is not pulled in; across papers names join only by clean, near,
    seed and (later) model."""
    keys = {m: clean(m.name) for m in mentions}
    doc_mentions: dict[str, list[Mention]] = {}
    for m in mentions:
        doc_mentions.setdefault(m.doc, []).append(m)

    aliases: list[tuple[str, str, str, str]] = []      # (long key, short key, doc, defining sentence)
    for doc, in_doc in doc_mentions.items():
        text = texts.get(doc, "")
        doc_keys = {keys[m] for m in in_doc}
        for d in abbrev.definitions(text) if text else []:
            long_key = clean(d.long)
            if long_key not in doc_keys:
                continue
            # the short form, found in the original text (case-insensitively: casefold may change the length,
            # as for "ß" or the "ﬁ" ligature, and would shift every later offset)
            hit = re.compile(re.escape(d.short), re.IGNORECASE).search(text, d.start, d.end + 1)
            if hit is None:
                continue
            # the paper may write a longer short form than the extractor's token ("Drug A" for "Drug"): the alias
            # is a mention of this paper that begins exactly where the short form begins
            for m in in_doc:
                if keys[m] != long_key and _starts_at(m, text, hit.start()):
                    aliases.append((long_key, keys[m], doc, _sentence(text, d.start, d.end)))
    local = {(doc, short) for _, short, doc, _ in aliases}
    for m in mentions:
        if (m.doc, keys[m]) in local:
            keys[m] = keys[m] + LOCAL + m.doc

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
            how.setdefault(a, (step, quote))
            how.setdefault(b, (step, quote))

    for name, variants in (seed or {}).items():
        seeded = [k for k in {clean(v) for v in [name, *variants]} if k in parent]
        for k in seeded:
            canon[k] = name
        for k in seeded[1:]:
            union(seeded[0], k, "seed")

    def in_paper(key: str, doc: str) -> str:
        return key + LOCAL + doc if (doc, key) in local else key

    for long_key, short, doc, quote in aliases:
        union(in_paper(long_key, doc), short + LOCAL + doc, "alias", quote)

    distinct = sorted(k for k in parent if LOCAL not in k)   # paper-local keys never join across papers
    for i, a in enumerate(distinct):
        for b in distinct[i + 1:]:
            if find(a) != find(b) and _guard(a, b) and fuzz.token_sort_ratio(a, b) >= threshold:
                union(a, b, "near")

    members: dict[str, list[Mention]] = {}
    for m, k in keys.items():
        members.setdefault(find(k), []).append(m)
    groups: dict[str, list[str]] = {}
    root_name: dict[str, str] = {}
    # groups with a paper-local key name themselves last, so a corpus-wide group keeps its plain name when a
    # paper's alias group would take the same one; a taken name falls to the next form, then to "<name> (<doc>)"
    order = sorted(members, key=lambda r: any(LOCAL in keys[m] for m in members[r]))
    for root in order:
        ms = members[root]
        seeded = next((canon[k] for k in sorted({keys[m] for m in ms}) if k in canon), None)
        counts = Counter(m.name for m in ms)
        ranked = sorted(counts, key=lambda n: (-counts[n], len(n), n))
        candidates = [seeded] if seeded else ranked
        name = next((n for n in candidates if n not in groups), f"{candidates[0]} ({ms[0].doc})")
        root_name[root] = name
        groups[name] = sorted(counts, key=lambda n: (-counts[n], n))

    matches: list[Match] = []
    unresolved: list[Mention] = []
    for m in mentions:
        k = keys[m]
        root = find(k)
        name = root_name[root]
        if k in canon:
            matches.append(Match(m, name, "seed", None))
        elif k in how:
            step, quote = how[k]
            matches.append(Match(m, name, step, quote))
        elif sum(keys[o] == k for o in mentions) > 1:
            matches.append(Match(m, name, "clean", None))
        if not matches or matches[-1].mention is not m:   # no step matched this mention
            unresolved.append(m)
    return NameGroups(groups, matches, unresolved)


def _versions_differ(a: str, b: str) -> bool:
    """Both names carry digit runs and they differ ("GPT-3" / "GPT 3.5"): different versions, never asked."""
    da, db = re.findall(r"\d+", a), re.findall(r"\d+", b)
    return bool(da) and bool(db) and da != db


def _passage(texts: dict[str, str], m: Mention) -> str | None:
    """The sentence of the paper around a mention; None without the paper's text."""
    text = texts.get(m.doc)
    if not text or m.end > len(text):
        return None
    return _sentence(text, m.start, m.end) or None


def _verdict(reply: str, passages: list[str]) -> str | None:
    """The quote of a "same" reply whose quote is a verbatim substring of one of the given passages; None for
    anything else (no, not JSON, a quote not in the passages, an empty quote, an error)."""
    try:
        data = json.loads(reply)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("same") is not True or not isinstance(data.get("quote"), str):
        return None
    quote = data["quote"]
    return quote if quote.strip() and any(quote in p for p in passages) else None


def confirm_leftovers(groups: NameGroups, texts: dict[str, str], ask: Callable[[str], str],
                      limit: int = 3) -> NameGroups:
    """The `model` step: each unresolved mention (in order) is asked about the `limit` closest groups of its own
    evidence type (rapidfuzz token_set_ratio of the cleaned names, then the group name), leaving out groups whose
    digit runs differ from its own. One `ask(prompt)` per question; the prompt is JSON {name, type, group,
    group_names, passages} (the sentences of the mention and of the group's first mention), the reply JSON
    {same, quote}. Only `same: true` with a quote found verbatim in one passage joins the mention to the group
    (step `model`, with the quote); a leftover that was the group itself joins with the same quote. A mention
    without a passage is not asked, and a pair of groups is asked about once (two leftovers are not asked again the
    other way round). The first quoted yes ends the questions about a mention."""
    if not groups.unresolved:
        return groups
    out = {k: list(v) for k, v in groups.groups.items()}
    matches, unresolved = list(groups.matches), list(groups.unresolved)
    known = [x.mention for x in matches] + unresolved
    asked: set[frozenset[str]] = set()                # pairs of groups already asked about, either way round

    def key_of(name: str) -> str | None:
        return next((k for k, forms in out.items() if name in forms), None)

    for m in list(groups.unresolved):
        if m not in unresolved:
            continue                                  # an earlier answer joined it already
        own = key_of(m.name)
        first: dict[str, Mention] = {}
        for x in known:
            k = key_of(x.name)
            if k is not None and k != own and x.etype == m.etype:
                first.setdefault(k, x)
        name = clean(m.name)
        ranked = sorted((k for k in first if not _versions_differ(name, clean(k))),
                        key=lambda k: (-fuzz.token_set_ratio(name, clean(k)), k))[:limit]
        for k in ranked:
            pair = frozenset((own or m.name, k))
            if pair in asked:
                continue
            passages = list(dict.fromkeys(p for p in (_passage(texts, m), _passage(texts, first[k])) if p))
            if not passages:
                continue
            prompt = json.dumps({"name": m.name, "type": m.etype, "group": k, "group_names": out[k],
                                 "passages": passages}, ensure_ascii=False)
            asked.add(pair)
            quote = _verdict(ask(prompt), passages)
            if quote is None:
                continue
            for form in out.pop(own, []) if own is not None else [m.name]:
                if form not in out[k]:
                    out[k].append(form)
            matches = [Match(x.mention, k, x.step, x.quote) if x.group == own else x for x in matches]
            joined = [x for x in unresolved if x is m or key_of(x.name) == k]
            matches += [Match(x, k, "model", quote) for x in joined]
            unresolved = [x for x in unresolved if x not in joined]
            break
    return NameGroups(out, matches, unresolved)
