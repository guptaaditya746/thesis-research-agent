"""What the pack-builder agent proposes (`PackProposal`), and the code checks a proposal must pass before any file is
written. Every check is deterministic; `problems` lists what fails, in words the model can act on.

The checks:
- every source quote is a verbatim substring of the paper it names (a paper of the corpus), at least MIN_QUOTE
  non-space characters long;
- every word (`sourced_words`: the topic words of words.yaml, the display names, the limitation categories and the
  name seeds) is the `claim` of at least one source, and a pattern word (a regex) compiles and matches at least one
  of its own quotes, so a pattern is shown to find text the papers really hold;
- the type names that words.yaml keys by (`gliner_labels`, `query`) are types of the proposal;
- the display names hold the requested keys (DISPLAY_KEYS);
- prefixes are global across packs (evidence/pack.py): a type's prefix may not belong to another type name, and a
  type name already known must keep a prefix it has (`known_prefixes`: the contract's registered types and every
  pack.yaml under the domain roots and the test fixtures).
Left to the model, and said in its prompt: which condition role is the treatment (the first role of `conditions`;
every later role is a control) and what a word means.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import yaml

from evidence import contract
from evidence.evidence_types import PREFIX_PATTERN
from evidence.pack import TypeDecl, Words
from evidence.protocol import Strict

REPO = Path(__file__).resolve().parents[1]
FIXTURE_ROOTS = (REPO / "evidence" / "tests" / "fixtures",)   # test packs register their prefixes too
MIN_QUOTE = 8                                  # non-space characters a quote must hold
DISPLAY_KEYS = ("treatment", "control")        # the display names a pack gives (pack.display)


class Source(Strict):
    claim: str      # the word as written in the proposal (a pattern, a term, a display name, a category)
    paper: str      # the paper id (list_papers)
    quote: str      # a verbatim substring of that paper


class PackProposal(Strict):
    types: dict[str, TypeDecl]
    words: Words
    display: dict[str, str]
    limitation_categories: list[str]
    names_seed: dict[str, list[str]]
    sources: list[Source]


def pattern_words(p: PackProposal) -> list[str]:
    """The regexes of the proposal: condition, metric and claim patterns, the claim subject and the context pattern
    (not `not_a_system`, a cue for the words that do not follow a name, which no paper has to show)."""
    w = p.words
    out = [x for ps in w.conditions.values() for x in ps]
    out += [m[0] for m in (*w.metrics, *w.metric_supplement)]
    out += [w.claim_subject, *(c[0] for c in w.claims), w.dataset_pattern]
    return list(dict.fromkeys(x for x in out if x))


def sourced_words(p: PackProposal) -> list[str]:
    """Every word that needs a source: the patterns (`pattern_words`), the condition roles, the metric names (but
    the engine's `other`), the GLiNER labels, the screen and query terms, the system nouns, the display names, the
    limitation categories and the name seeds. Not the engine's own labels: claim directions, `not_a_system`, type
    names."""
    w = p.words
    out = [*w.conditions, *pattern_words(p)]
    out += [m[1] for m in (*w.metrics, *w.metric_supplement) if m[1] != "other"]
    out += [x for xs in w.gliner_labels.values() for x in xs]
    out += [*w.fraction_metrics, *w.screen_terms, *w.system_nouns, *(x for xs in w.query.values() for x in xs)]
    out += [*p.display.values(), *p.limitation_categories]
    out += [x for k, xs in p.names_seed.items() for x in (k, *xs)]
    return list(dict.fromkeys(x for x in out if x))


Known = list[tuple[str, str, str]]   # (type name, prefix, where it is declared)


def known_prefixes(roots: Iterable[Path], skip: Path | None = None) -> Known:
    """Every (type name, prefix, where) in use: the contract's registered types, then the types of every `pack.yaml`
    under `roots` (any depth), except the one in the folder `skip` (the pack being proposed). Test fixtures may
    give one type name two prefixes (they never load together), so a name can have several."""
    known = [(name, prefix, "registered") for name, prefix in contract.ITEM_PREFIX.items()]
    for root in roots:
        for f in sorted(Path(root).rglob("pack.yaml")) if Path(root).is_dir() else []:
            if skip is not None and f.parent.resolve() == Path(skip).resolve():
                continue
            types = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("types") or {}
            known += [(name, str(decl["prefix"]), f.parent.name) for name, decl in types.items()
                      if isinstance(decl, dict) and "prefix" in decl]
    return known


def _quote_problems(p: PackProposal, papers: dict[str, str]) -> list[str]:
    out = []
    for n, s in enumerate(p.sources):
        if s.paper not in papers:
            out.append(f"source {n} ({s.claim!r}): paper {s.paper!r} is not in the corpus; known: {', '.join(papers)}")
        elif len("".join(s.quote.split())) < MIN_QUOTE:
            out.append(f"source {n} ({s.claim!r}): the quote {s.quote!r} is shorter than {MIN_QUOTE} characters")
        elif s.quote not in papers[s.paper]:
            out.append(f"source {n} ({s.claim!r}): the quote {s.quote!r} is not a verbatim substring of paper "
                       f"{s.paper!r}; copy it exactly (read_paper or grep)")
    return out


def _source_problems(p: PackProposal) -> list[str]:
    quotes: dict[str, list[str]] = {}
    for s in p.sources:
        quotes.setdefault(s.claim, []).append(s.quote)
    out = [f"word {w!r} has no source: add a source whose claim is exactly {w!r}"
           for w in sourced_words(p) if w not in quotes]
    for pattern in pattern_words(p):
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            out.append(f"pattern {pattern!r} is not a valid regex: {exc}")
            continue
        if pattern in quotes and not any(rx.search(q) for q in quotes[pattern]):
            out.append(f"pattern {pattern!r} matches none of its quotes {quotes[pattern]}")
    return out


def _type_problems(p: PackProposal, known: Known) -> list[str]:
    out = []
    for field, keyed in (("gliner_labels", p.words.gliner_labels), ("query", p.words.query)):
        out += [f"words.{field} names {k!r}, which is not a type of the proposal ({', '.join(p.types)})"
                for k in keyed if k not in p.types]
    missing = [k for k in DISPLAY_KEYS if k not in p.display]
    if missing:
        out.append(f"display needs the keys {list(DISPLAY_KEYS)}; missing {missing}")
    seen: dict[str, str] = {}
    for name, decl in p.types.items():
        if not PREFIX_PATTERN.match(decl.prefix):
            out.append(f"type {name!r}: prefix {decl.prefix!r} must be lowercase letters a-z")
        if decl.prefix in seen:
            out.append(f"type {name!r}: prefix {decl.prefix!r} is also the prefix of type {seen[decl.prefix]!r}")
        seen[decl.prefix] = name
        others = [(n, where) for n, prefix, where in known if prefix == decl.prefix and n != name]
        if others:
            out.append(f"type {name!r}: prefix {decl.prefix!r} belongs to type {others[0][0]!r} ({others[0][1]}); "
                       "prefixes are global across packs, pick another")
        held = sorted({prefix for n, prefix, _ in known if n == name})
        if held and decl.prefix not in held:
            out.append(f"type {name!r} already has prefix {' or '.join(map(repr, held))} in another pack, not "
                       f"{decl.prefix!r}: the same type name keeps its prefix")
    return out


def problems(p: PackProposal, papers: dict[str, str], known: Known) -> list[str]:
    """Every failed check of proposal `p` over the corpus `papers` (id -> text), given the `known` type prefixes."""
    return _quote_problems(p, papers) + _source_problems(p) + _type_problems(p, known)
