"""What the pack-builder agent proposes (`PackProposal`), and the code checks a proposal must pass before any file is
written. Every check is deterministic; `problems` lists what fails, in words the model can act on.

The checks:
- every source quote is a verbatim substring of the paper it names (a paper of the corpus), at least MIN_QUOTE
  non-space characters long;
- every word (`sourced_words`: the topic words of words.yaml, the display names, the limitation categories and the
  name seeds) is the `claim` of at least one source, and a pattern word (a regex) compiles and matches at least one
  of its own quotes, so a pattern is shown to find text the papers really hold; a plain word as the papers write
  it (`plain_words`: display names, screen and query terms, system nouns, name seeds) occurs, ignoring case, in at
  least one of its own quotes;
- the type names that words.yaml keys by (`gliner_labels`, `query`) are types of the proposal;
- the display names hold the requested keys (DISPLAY_KEYS);
- prefixes are global across packs (evidence/pack.py): a type's prefix may not belong to another type name, and a
  type name already known must keep a prefix it has (`known_prefixes`: the contract's registered types and every
  pack.yaml under the domain roots and the test fixtures).
What code cannot check, whether a word means what its slot says (a screen term that is really a metric, a claim
pattern with the wrong direction, the treatment role not first), a second model judges word by word (`word_slots`,
the verifier prompt propose-check-v1.md); `drop` removes the words it rejects.
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


def plain_words(p: PackProposal) -> list[str]:
    """The words written as the papers write them, so each must occur (ignoring case) in one of its quotes: display
    names, screen and query terms, system nouns and name seeds. Not the snake_case names the proposal makes up
    (condition roles, canonical metric names, limitation categories) nor GLiNER labels, which describe a type
    ("treatment arm") rather than quote one."""
    w = p.words
    out = [*p.display.values(), *w.screen_terms, *w.system_nouns, *(x for xs in w.query.values() for x in xs)]
    out += [x for k, xs in p.names_seed.items() for x in (k, *xs)]
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
    for word in plain_words(p):
        if word in quotes and not any(word.casefold() in q.casefold() for q in quotes[word]):
            out.append(f"word {word!r} occurs in none of its quotes {quotes[word]}: quote a span that holds it")
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
        # several prefixes for one name happen only between test fixtures (rag-renamed `arm: ar`, drugtoy
        # `arm: xa`), which never load together; any of them keeps the name's item ids apart from other types
        held = sorted({prefix for n, prefix, _ in known if n == name})
        if held and decl.prefix not in held:
            out.append(f"type {name!r} already has prefix {' or '.join(map(repr, held))} in another pack, not "
                       f"{decl.prefix!r}: the same type name keeps its prefix")
    return out


def problems(p: PackProposal, papers: dict[str, str], known: Known) -> list[str]:
    """Every failed check of proposal `p` over the corpus `papers` (id -> text), given the `known` type prefixes."""
    return _quote_problems(p, papers) + _source_problems(p) + _type_problems(p, known)


# --- word by word, for the verifier ---------------------------------------------------------------------------------

Slot = tuple   # where a word sits in the proposal: ("role", role), ("condition", role, pattern), ("metric", i), ...


def word_slots(p: PackProposal) -> list[tuple[str, str, Slot]]:
    """Every proposed word with its slot, in words a reader understands, and its locator for `drop`, in proposal
    order. A metric, supplement or claim entry is one item (its pattern; the slot names its canonical name or
    direction)."""
    w = p.words
    roles = list(w.conditions)
    side = {r: "the treatment side (the thing the question asks about)" if i == 0 else "a control side"
            for i, r in enumerate(roles)}
    out: list[tuple[str, str, Slot]] = []
    for r in roles:
        out.append((r, f"name of a condition role, {side[r]}", ("role", r)))
        out += [(x, f"pattern naming the condition role {r!r}, {side[r]}", ("condition", r, x))
                for x in w.conditions[r]]
    for field, entries in (("metric", w.metrics), ("supplement", w.metric_supplement)):
        out += [(m[0], f"pattern of the metric {m[1]!r} (higher is better: {str(m[2]).lower()})"
                 + (", a looser wording" if field == "supplement" else ""), (field, i))
                for i, m in enumerate(entries)]
    out.append((w.claim_subject, "pattern for the treatment as the subject of a claim the authors make",
                ("claim_subject",)))
    out += [(c[0], f"pattern of a claim by the authors that the treatment {c[1]}", ("claim", i))
            for i, c in enumerate(w.claims)]
    out.append((w.dataset_pattern, "pattern of a context name (a cohort, a site, a named study)",
                ("dataset_pattern",)))
    out += [(x, f"label phrase for finding items of type {t!r}", ("gliner", t, x))
            for t, xs in w.gliner_labels.items() for x in xs]
    out += [(x, "metric reported as a fraction or percentage", ("fraction", x)) for x in w.fraction_metrics]
    out += [(x, "screen term: marks a paper as on topic", ("screen", x)) for x in w.screen_terms]
    out += [(x, f"search word for evidence of type {t!r}", ("query", t, x)) for t, xs in w.query.items() for x in xs]
    out += [(x, "noun that follows the name of a compared thing", ("noun", x)) for x in w.system_nouns]
    out += [(v, f"display name of the {k} side", ("display", k)) for k, v in p.display.items()]
    out += [(x, "category of a limitation the papers state", ("category", x)) for x in p.limitation_categories]
    for k, xs in p.names_seed.items():
        out.append((k, "canonical name of a compared thing", ("seed", k)))
        out += [(x, f"another spelling of {k!r}", ("alias", k, x)) for x in xs]
    return out


REQUIRED = {"claim_subject", "dataset_pattern", "display"}   # slots the pack cannot lose: a rejection refuses


def drop(p: PackProposal, slots: list[Slot]) -> PackProposal:
    """`p` without the words at `slots`, and without the sources only they used. A rejected required word (claim
    subject, context pattern, display name) cannot be dropped and raises ValueError; so does a pack left with fewer
    than two condition roles or no metric."""
    gone = set(slots)
    hard = sorted({s[0] for s in gone if s[0] in REQUIRED})
    if hard:
        raise ValueError(f"the verifier rejected required words ({', '.join(hard)}); the proposal cannot be used")
    d = p.model_dump(mode="json")
    w = d["words"]
    w["conditions"] = {r: [x for x in xs if ("condition", r, x) not in gone]
                       for r, xs in w["conditions"].items() if ("role", r) not in gone}
    w["conditions"] = {r: xs for r, xs in w["conditions"].items() if xs}
    w["metrics"] = [m for i, m in enumerate(w["metrics"]) if ("metric", i) not in gone]
    w["metric_supplement"] = [m for i, m in enumerate(w["metric_supplement"]) if ("supplement", i) not in gone]
    w["claims"] = [c for i, c in enumerate(w["claims"]) if ("claim", i) not in gone]
    w["gliner_labels"] = {t: [x for x in xs if ("gliner", t, x) not in gone] for t, xs in w["gliner_labels"].items()}
    w["query"] = {t: [x for x in xs if ("query", t, x) not in gone] for t, xs in w["query"].items()}
    for field, kind in (("fraction_metrics", "fraction"), ("screen_terms", "screen"), ("system_nouns", "noun")):
        w[field] = [x for x in w[field] if (kind, x) not in gone]
    d["limitation_categories"] = [x for x in d["limitation_categories"] if ("category", x) not in gone]
    d["names_seed"] = {k: [x for x in xs if ("alias", k, x) not in gone]
                       for k, xs in d["names_seed"].items() if ("seed", k) not in gone}
    if len(w["conditions"]) < 2 or not w["metrics"]:
        raise ValueError("after the verifier's rejections the pack has fewer than two condition roles or no metric")
    kept = PackProposal.model_validate(d)
    used = set(sourced_words(kept))
    return kept.model_copy(update={"sources": [s for s in kept.sources if s.claim in used]})
