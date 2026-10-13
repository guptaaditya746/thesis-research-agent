"""Comparison keys for answer values: the `strict` and `normalised` matching levels (milestone 4, Scores).

The labelling repo's scorer (docs/EVALUATION.md there, section 3.3) has three levels: strict, entailed
(RDFS/OWL rules) and soft. This project has no ontology of its own predicates, so `normalised` takes the
place of `entailed`: rules in code, no model, nothing to dispute.

- strict: the value as typed, trimmed at the ends; a JSON number and its text are one value (2 and "2"),
  as in agent/attach.py `_same`.
- normalised: Unicode NFKC, case folded, punctuation and spacing dropped, so "evaluatesOn",
  "evaluates on" and "evaluates_on" are one predicate and "Natural Questions" equals "NaturalQuestions".
  Numbers stay apart from the words around them and compare by value: thousands separators go, "12.50"
  is 12.5, "−3" keeps its sign, "85 %" equals "85 percent". Count cells therefore compare exactly after
  normalisation, with no tolerance. A value that names a corpus paper ("p12", "p012.md", "$CORPUS/p12.md",
  "2025.acl-long.892", "2025-acl-long-892.md") becomes that paper's id: the paper-id aliasing. Lists
  (list<...> cells) compare as sets of their normalised items.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any

DASHES = str.maketrans({c: "-" for c in "−‐‑‒–—﹣－"})
# A number: a sign only where no word character precedes it ("GPT-4" is not minus four), digits with
# thousands separators or plain, an optional fraction. Words are runs of letters; "%" is a word.
TOKEN = re.compile(r"(?:(?<![\w.])-)?(?:\d{1,3}(?:,\d{3})+(?!\d)|\d+)(?:\.\d+)?|[^\W\d_]+|%")
PAPER_P = re.compile(r"p0*(\d+)", re.I)
PAPER_ANTHOLOGY = re.compile(r"(\d{4})[.-]((?:[a-z]+[.-])*[a-z]+)[.-]0*(\d+)", re.I)


def strict(item: Any) -> Any:
    """The strict comparison key of one value."""
    if item is None:
        return None
    if isinstance(item, bool):
        return "true" if item else "false"
    if isinstance(item, list):
        return tuple(strict(v) for v in item)
    return str(item).strip()


def number(digits: str) -> str:
    """A number's canonical text: no separators, no trailing zeros, no "-0"."""
    try:
        parsed = Decimal(digits.replace(",", "")).normalize()
    except InvalidOperation:
        return digits
    return "0" if parsed == 0 else format(parsed, "f")


def paper_id(item: Any) -> str | None:
    """The corpus paper id a value names, or None. Ids are the corpus file names without `.md`."""
    if not isinstance(item, str):
        return None
    name = re.split(r"[/\\]", item.strip())[-1]
    name = re.sub(r"\.(md|pdf)$", "", name, flags=re.I)
    if m := PAPER_P.fullmatch(name):
        return f"p{int(m.group(1))}"
    if m := PAPER_ANTHOLOGY.fullmatch(name):
        return f"{m.group(1)}-{re.sub(r'[.-]', '-', m.group(2).lower())}-{int(m.group(3))}"
    return None


def text(item: str) -> str:
    """The normalised key of one string, without paper-id aliasing (see `norm`)."""
    folded = unicodedata.normalize("NFKC", item).translate(DASHES).casefold()
    out = []
    for token in TOKEN.findall(folded):
        if token == "%":
            out.append("percent")
        elif token[0].isdigit() or token[0] == "-":
            out.append(f"<{number(token)}>")  # delimited, so "1 5" never equals "15"
        else:
            out.append(token)
    return "".join(out)


def norm(item: Any) -> Any:
    """The normalised comparison key of a cell, an edge end, or a fact's s, p or o (hashable)."""
    if item is None:
        return None
    if isinstance(item, bool):
        return "true" if item else "false"
    if isinstance(item, (int, float)):
        return f"<{number(repr(item))}>"
    if isinstance(item, list):
        return frozenset(norm(v) for v in item)
    if isinstance(item, dict):  # no answer type has one; compared by its sorted items
        return tuple(sorted((str(k), norm(v)) for k, v in item.items()))
    paper = paper_id(item)
    return f"paper:{paper}" if paper else text(str(item))


def fact_strict(fact: dict[str, Any]) -> tuple[Any, Any, Any]:
    return strict(fact["s"]), strict(fact["p"]), strict(fact["o"])


def fact_norm(fact: dict[str, Any]) -> tuple[Any, Any, Any]:
    return norm(fact["s"]), norm(fact["p"]), norm(fact["o"])


def is_number_key(key: Any) -> bool:
    return isinstance(key, str) and bool(re.fullmatch(r"<[^<>]*>", key))


def words(item: Any) -> set[Any]:
    """The normalised non-number values in a cell, list items one by one: what two rows can share."""
    if isinstance(item, list):
        return set().union(*(words(v) for v in item))
    if item is None or isinstance(item, (bool, int, float)):
        return set()
    key = norm(item)
    return set() if not key or is_number_key(key) else {key}
