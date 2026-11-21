"""Code search over the corpus: tolerant exact-word regex, and passages ranked by how many search terms they hold.

Regex: a name matches as a whole word, case-insensitive, and any run of spaces/hyphens/underscores inside the name
may be written as a space, a hyphen, a dash or nothing ("BRN-233" matches "brn 233", "BRN233", "Brn–233").
No BM25 and no embeddings (Aditya, 21 Nov): the words searched come from the spec, the model's SearchTerms and the
gap agent; code only matches them exactly."""
from __future__ import annotations

import re
from dataclasses import dataclass

from evqa.contracts import Passage

_SEP = r"[\s\-‐-―_]?"


def pattern(term: str) -> re.Pattern[str]:
    """Whole-word, case-insensitive pattern for `term`, tolerant of hyphen/space variants."""
    parts = [re.escape(p) for p in re.split(r"[\s\-‐-―_]+", term.strip()) if p]
    if not parts:
        raise ValueError("empty search term")
    return re.compile(r"(?<!\w)" + _SEP.join(parts) + r"(?!\w)", re.I)


def find_term(term: str, text: str) -> list[tuple[int, int]]:
    """Character spans of every match of `term` in `text`."""
    return [(m.start(), m.end()) for m in pattern(term).finditer(text)]


@dataclass(frozen=True)
class Ref:
    paper: str
    index: int            # index of the passage in that paper's passage list


def rank_passages(passages: dict[str, list[Passage]], terms: list[str], k: int) -> list[tuple[Ref, int]]:
    """The `k` passages that contain the most of `terms` (distinct terms, exact whole-word matches), best first;
    ties in reading order. Passages with no term are left out. No index, no word weights: a plain grep."""
    pats = [pattern(t) for t in dict.fromkeys(t.strip() for t in terms) if t]
    got = []
    for pid, ps in passages.items():
        for i, p in enumerate(ps):
            n = sum(1 for pat in pats if pat.search(p.section + "\n" + p.text))
            if n:
                got.append((Ref(pid, i), n))
    got.sort(key=lambda x: -x[1])
    return got[:max(k, 0)]
