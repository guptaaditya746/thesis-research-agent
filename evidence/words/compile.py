"""Compile a word list into the extractor config a pack's words fill today (`Pack.extractor_config`), so a plan run
reads its words from the locked word list and never from a pack. Pure: the same list gives the same config.

A name becomes a word-bounded pattern exactly as `screen.term_pattern` builds it (a capitals-only name matches in
capitals, any other in any case, a space is any white space); the names of one thing become one pattern, longest
name first. The first thing is the treatment side; every later thing is a control and gets `not_a_system` appended,
as a pack's conditions do. Things named in `metric_things` become metrics instead of conditions."""
from __future__ import annotations

from typing import Any

from ..extractors.screen import term_pattern
from ..plan import WordList

NOT_A_SYSTEM = r"(?!\s+(?:failures?|errors?|calls?|latency|costs?|steps?)\b)"
CUE_LABEL = "cue"


def _scoped(term: str) -> str:
    """`term_pattern` with its flag scoped to the term, so terms can be joined with `|`."""
    pattern = term_pattern(term)
    return f"(?i:{pattern[len('(?i)'):]})" if pattern.startswith("(?i)") else pattern


def any_of(names: list[str]) -> str:
    """One pattern matching any of the names, the longest first."""
    ordered = sorted(dict.fromkeys(n for n in names if n.strip()), key=lambda n: (-len(n), n))
    return "|".join(_scoped(n) for n in ordered)


def _all_names(words: WordList) -> dict[str, list[str]]:
    """Per thing: its written names, then the ontology's, one per case-folded spelling."""
    out: dict[str, list[str]] = {}
    for thing in dict.fromkeys([*words.things, *words.ontology_names]):
        seen: dict[str, str] = {}
        for name in [*words.things.get(thing, []), *words.ontology_names.get(thing, [])]:
            name = " ".join(name.split())
            if name:
                seen.setdefault(name.casefold(), name)
        out[thing] = list(seen.values())
    return out


def compile_words(words: WordList, *, metric_things: frozenset[str] | set[str] = frozenset(),
                  lower_is_better: frozenset[str] | set[str] = frozenset()) -> dict[str, Any]:
    names = _all_names(words)
    conditions = {t: [any_of(ns) + (NOT_A_SYSTEM if i else "")]
                  for i, (t, ns) in enumerate((t, ns) for t, ns in names.items() if t not in metric_things) if ns}
    metrics = [[any_of(ns), t, t not in lower_is_better] for t, ns in names.items() if t in metric_things and ns]
    everything = [n for ns in names.values() for n in ns]
    screen_terms = list(dict.fromkeys(everything))
    cues = list(dict.fromkeys(c for c in (" ".join(c.split()) for c in words.cues) if c))
    return {
        "conditions": conditions,
        "not_a_system": NOT_A_SYSTEM,
        "metrics": metrics,
        "screen_terms": screen_terms,
        "subject": any_of(everything),
        "claims": [[any_of(cues), CUE_LABEL]] if cues else [],
    }

