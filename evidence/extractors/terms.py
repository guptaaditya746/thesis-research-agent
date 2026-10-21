"""Patterns of the regex extractors: condition, metric and claim wording, and how mentions are found.

The patterns are data: they go into each regex extractor's `config`, so a changed pattern is a changed
extractor id (contract principle 6). Inline flags carry case sensitivity ("RAG" is matched in capitals
only, "accuracy" in any case).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

_NOUNS = r"(?:\s+(?:model|variant|system|setting|pipeline|condition|configuration|LLM|approach))?+"

# "RAG with reranking", "RAG without reranking", "retrieval-augmented model without reranking" name other
# systems (ablations), not the rag condition: the optional parts are possessive so the lookahead cannot be
# dodged by matching less.
CONDITIONS: dict[str, list[str]] = {
    "rag": [
        r"(?i)\bretrieval[- ]augmented(?:\s+generation)?+" + _NOUNS + r"(?!\s+without\b)",
        r"\bRAG\b(?:\s+(?i:model|variant|system|setting|pipeline|condition|configuration|LLM|approach))?+"
        r"(?!\s+(?i:with|without)\b)",
        r"(?i)\b(?:model|LLM|system|variant|generator)\s+with\s+retrieval\b",
    ],
    "baseline": [
        r"(?i)\bclosed[- ]book(?:\s+(?:baseline|model|variant|system|setting|condition|LLM|generation))?",
        r"(?i)\b(?:(?:model|LLM|system|variant|baseline|generation)\s+)?without\s+(?:any\s+)?retrieval\b",
        r"(?i)\bno[- ]retrieval(?:\s+(?:baseline|model|variant|setting|condition))?",
        r"(?i)\bvanilla\s+(?:LLM|model)\b",
    ],
}

METRICS: list[tuple[str, str, bool]] = [   # pattern, canonical, higher_is_better
    (r"(?i)\bfactual(?:ity)?\s+accuracy\b", "factual_accuracy", True),
    (r"(?i)\b(?:answer|exact[- ]match|EM|QA)\s+accuracy\b", "factual_accuracy", True),
    (r"(?i)\baccuracy\b", "factual_accuracy", True),
    (r"(?i)\bexact[- ]match\b", "factual_accuracy", True),
    (r"(?i)\bFActScore\b|\bfactuality\s+score\b", "factual_accuracy", True),
    (r"(?i)\bhallucination[- ]rate\b|\brate\s+of\s+hallucinat(?:ion|ions|ed\s+answers)\b", "hallucination_rate", False),
    (r"(?i)\blatency\b", "other", False),
    (r"\bBLEU\b|\bROUGE(?:-[12L])?\b", "other", True),
    (r"(?i)\bperplexity\b", "other", False),
    (r"(?i)\bfluency\b", "other", True),
    (r"\bF1\b", "other", True),
]

# Author claims: a sentence that names retrieval and states an effect. Checked in this order, so a
# negated statement ("does not measurably reduce", "does not make the answers more accurate") is no_effect,
# never improves: any words (adverbs, objects) may stand between "not" and the verb or the comparison.
CLAIM_SUBJECT = r"(?i)\bretriev\w*|\bRAG\b"
_NOT = r"\b(?:does|did|do|is|was|are|were)\s+not\b|\b(?:doesn't|didn't|don't|isn't|wasn't)\b"
_VERBS = (r"improve|help|increase|change|reduce|lower|decrease|raise|boost|enhance|affect|alter|make|lead|yield"
          r"|matter")
CLAIMS: list[tuple[str, str]] = [
    # Match verb endings, rather than arbitrary suffixes ("alternative" is not "alter").
    (r"(?i)(?:" + _NOT + r")(?:\s+\w+){0,3}?\s+(?:" + _VERBS + r")(?:s|d|ed|ing)?\b"
     r"|(?:" + _NOT + r")[^.;]{0,80}?\bmore\s+(?:accurate|factual|reliable|correct)"
     r"|\b(?:fails?|failed)\s+to\s+(?:improve|help)|\bno\s+(?:significant\s+|clear\s+|measurable\s+)?"
     r"(?:improvement|effect|difference|gain|benefit|change)|\bon\s+par\s+with\b|\b(?:essentially\s+)?unchanged\b",
     "no_effect"),
    (r"(?i)\b(?:increases?|increased|raises?|raised)\s+(?:the\s+)?(?:rate\s+of\s+)?hallucinat"
     r"|\bmore\s+hallucinat|\bless\s+(?:accurate|factual|correct)\b"
     r"|\b(?:hurts?|harms?|harmed|degrades?|degraded|worsens?|worsened|impairs?|impaired)\b"
     r"|\b(?:reduces?|reduced|lowers?|lowered|decreases?|decreased)\s+(?:the\s+)?(?:factual\s+|answer\s+)?accuracy",
     "worsens"),
    (r"(?i)\b(?:reduces?|reduced|lowers?|lowered|decreases?|decreased|cuts?)\s+(?:the\s+)?(?:rate\s+of\s+)?hallucinat"
     r"|\b(?:fewer|less)\s+hallucinat"
     r"|\b(?:improves?|improved|improving|increases?|increased|boosts?|boosted|raises?|raised|enhances?|enhanced)\b"
     r"|\b(?:outperforms?|outperformed)\b|\bmore\s+(?:factual|accurate)\b",
     "improves"),
]

ALIAS = r"\s*\(\s*([A-Za-z][\w+\-]{0,5})\s*\)"   # a short code in brackets right after a mention: "(R)"
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


def condition_patterns(conditions: dict[str, list[str]] | None = None) -> list[tuple[str, str, bool]]:
    return [(p, role, True) for role, ps in (conditions or CONDITIONS).items() for p in ps]


def norm(label: str) -> str:
    """A label for comparison: case folded, dashes and runs of spaces as one space, no leading article."""
    out = re.sub(r"[\s\-‐–—]+", " ", label.casefold()).strip()
    return re.sub(r"^(?:the|a|an|our|its)\s+", "", out)


def aliases(text: str, mentions: list[Mention]) -> list[tuple[Mention, str, int, int]]:
    """(mention, code, start, end) for each mention followed by a bracketed code, e.g. "variant (R)"."""
    out = []
    for m in mentions:
        hit = re.match(ALIAS, text[m.end:m.end + 12])
        if hit:
            out.append((m, hit.group(1), m.start, m.end + hit.end()))
    return out
