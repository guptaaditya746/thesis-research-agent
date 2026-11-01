"""How the regex extractors find mentions of condition, metric and claim wording.

The wording itself is topic data: it lives in the domain pack (domains/<name>/words.yaml) and reaches each
extractor through its `config` (the engine fills it, evidence/pack.py `Pack.extractor_config`), so a changed
pattern is a changed extractor id (contract principle 6). Inline flags carry case sensitivity ("RAG" is
matched in capitals only, "accuracy" in any case). Only generic wording (alias codes, qualifiers, negation,
system head nouns) stays here.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

_NOUNS = r"(?:\s+(?:model|variant|system|setting|pipeline|condition|configuration|LLM|approach))?+"


def control_cue(term: str, not_a_system: str) -> str:
    """A control term's pattern that does not match where a negated object follows ("no retrieval failures");
    `not_a_system` is the pack's lookahead for such objects (words.yaml `not_a_system`)."""
    return term + not_a_system


ALIAS = r"\s*\(\s*([A-Za-z][\w+\-]{0,5})\s*\)"   # a short code in brackets right after a mention: "(R)"
QUALIFIER = r"\s*\(([^)]{1,40})\)"                 # a bracketed qualifier after a condition: "RAG (no retrieval)"
NEGATION = r"(?i)\b(?:no|without|w/o)\b"
# a system noun the condition's own pattern left out, between it and its code: "closed-book baseline (B)"
_HEAD_NOUNS = r"(?i:model|baseline|system|variant|setting|pipeline|condition|configuration|LLM|approach|generator)"
_HEAD = r"(?:\s+" + _HEAD_NOUNS + r")?"
# a mention that is a negated term on its own ("no retrieval"), not one ending in its system ("no-retrieval baseline")
_BARE_NEGATION = r"(?i)^(?:no|without|w/o)\b(?!.*[\s-]" + _HEAD_NOUNS + r"$)"
CLAIM_SECTIONS = ("conclusion", "abstract", "discussion", "summary")   # where an author claim is looked for first


@dataclass(frozen=True)
class Mention:
    start: int
    end: int
    key: str            # the role (conditions) or the canonical metric (metrics)
    text: str
    higher_is_better: bool = True


@lru_cache(maxsize=256)
def _compiled(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def find_all(text: str, patterns: list[tuple[str, str, bool]], start: int = 0, end: int | None = None) -> list[Mention]:
    """Non-overlapping mentions in text[start:end]: at one place the longest match wins, then the earliest pattern."""
    end = len(text) if end is None else end
    found: list[tuple[int, int, int, Mention]] = []
    for order, (pattern, key, hib) in enumerate(patterns):
        for m in _compiled(pattern).finditer(text, start, end):
            if m.end() > m.start():
                found.append((m.start(), -(m.end() - m.start()), order,
                              Mention(m.start(), m.end(), key, m.group(), hib)))
    found.sort(key=lambda f: f[:3])
    out: list[Mention] = []
    for _, _, _, mention in found:
        if out and mention.start < out[-1].end:
            continue
        out.append(mention)
    return out


def condition_patterns(conditions: dict[str, list[str]]) -> list[tuple[str, str, bool]]:
    return [(p, role, True) for role, ps in conditions.items() for p in ps]


def _negated_object(text: str, m: Mention, end: int, not_a_system: str) -> bool:
    """A bare negated term followed by an object: "no retrieval failures" names no system ("no-retrieval
    baseline errors" does: the errors are the baseline's)."""
    return bool(_compiled(_BARE_NEGATION).match(m.text)) and _compiled(not_a_system).match(text, m.end, end) is None


def find_conditions(text: str, patterns: list[tuple[str, str, bool]], roles: Sequence[str],
                    start: int = 0, end: int | None = None, treatment: str | None = None, *,
                    not_a_system: str) -> list[Mention]:
    """Condition mentions in text[start:end] as `find_all` finds them, with their local qualifier: a bracketed
    part right after a mention that names a role ("RAG (no retrieval)": that role) or holds a negation ("RAG
    (no reranking)": other) belongs to the mention; an alias code ("(B)") does not. Only a treatment head
    becomes other (an ablation); any other head keeps its role ("the closed-book model (no fine-tuning)"). A
    negated object ("no retrieval failures", by the pack's `not_a_system` lookahead) is no mention. `roles`: the
    role enum; without "other" an "other" mention is dropped. `treatment`: the treatment role (default: the first pattern's)."""
    end = len(text) if end is None else end
    treatment = treatment if treatment is not None else (patterns[0][1] if patterns else None)
    out: list[Mention] = []
    covered = start
    for m in find_all(text, patterns, start, end):
        if m.start < covered or _negated_object(text, m, end, not_a_system):
            continue
        covered = m.end
        q = _compiled(QUALIFIER).match(text, m.end, end)
        if q and not _compiled(ALIAS).fullmatch(text, m.end, q.end()):
            inner = [i for i in find_all(text, patterns, q.start(1), q.end(1)) if not _negated_object(text, i, q.end(1), not_a_system)]
            role = inner[0].key if inner else "other" if _compiled(NEGATION).search(q.group(1)) else None
            if role == "other" and m.key != treatment:
                role = None   # a qualified control is still the control
            if role is not None:
                covered = q.end()   # an inner mention is part of this one, never reported again
                if role != "other" or "other" in roles:
                    out.append(Mention(m.start, q.end(), role, text[m.start:q.end()], m.higher_is_better))
                continue
        out.append(m)
    return out


def norm(label: str) -> str:
    """A label for comparison: case folded, dashes and runs of spaces as one space, no leading article."""
    out = re.sub(r"[\s\-‐–—]+", " ", label.casefold()).strip()
    return re.sub(r"^(?:the|a|an|our|its)\s+", "", out)


def aliases(text: str, mentions: list[Mention]) -> list[tuple[Mention, str, int, int]]:
    """(mention, code, start, end) for each mention followed by a bracketed code, e.g. "variant (R)"."""
    out = []
    for m in mentions:
        hit = re.match(_HEAD + ALIAS, text[m.end:m.end + 30])
        if hit:
            out.append((m, hit.group(1), m.start, m.end + hit.end()))
    return out
