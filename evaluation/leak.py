"""The leak split: how many of a corpus's facts have a name the word list already holds ("on the list") and how many
have a name it does not ("unseen"). A run that finds only listed names may just be echoing its list, so the score is
shown for both halves. Only the Claude-written corpora (id `rag-claude-...`) are split: the words are written by
another model, so the list cannot have seen those papers.

Only facts that carry a name are marked: conditions (`label`), metrics and datasets (`name`). A fact is "on the list"
when its name, after `names.clean`, equals a cleaned name of the list (the things' names and the ontology's).

`split_scores` reads `score_extraction`'s result: a fact is matched unless it is in `missed`. Precision cannot be
split: an unmatched item belongs to no fact, so each half reports recall only (precision and F1 are None)."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from evidence.names import clean
from evidence.plan import WordList
from evaluation.score import prf
from evaluation.truth import GroundTruth

CORPUS_PREFIX = "rag-claude-"
ON_LIST, UNSEEN = "on the list", "unseen"
Mark = Literal["on the list", "unseen"]
NAME_FIELDS = ("label", "name")


def _name(data: dict[str, Any]) -> str | None:
    return next((str(data[f]) for f in NAME_FIELDS if isinstance(data.get(f), str) and data[f].strip()), None)


def mark(truth: GroundTruth, words: WordList, types: Iterable[str] | None = None) -> dict[str, Mark]:
    """Fact id -> "on the list" | "unseen" for each named fact (of `types` when given: pass the score's
    `scored_types`). Refuses a corpus that is not Claude-written."""
    if not truth.corpus_id.startswith(CORPUS_PREFIX):
        raise ValueError(f"corpus {truth.corpus_id!r} is not a Claude-written corpus ({CORPUS_PREFIX}*): "
                         "the leak split is only defined for those")
    listed = {clean(n) for ns in (*words.things.values(), *words.ontology_names.values()) for n in ns}
    wanted = set(types) if types is not None else None
    marks: dict[str, Mark] = {}
    for fact in (*truth.facts.values(), *truth.datasets.values()):
        name = _name(fact.data)
        if name is None or (wanted is not None and fact.type not in wanted):
            continue
        marks[fact.id] = ON_LIST if clean(name) in listed else UNSEEN
    return marks


def split_scores(score_json: dict[str, Any], marks: dict[str, Mark]) -> dict[str, dict[str, Any]]:
    """Recall of the named facts, split by mark. `score_json` is a score's `extraction` part (or the whole score)."""
    extraction = score_json.get("extraction", score_json)
    missed = set(extraction.get("missed", []))
    out: dict[str, dict[str, Any]] = {}
    for label in (ON_LIST, UNSEEN):
        ids = [f for f, m in marks.items() if m == label]
        matched = sum(1 for f in ids if f not in missed)
        row = prf(matched, 0, len(ids))
        out[label] = {**row, "items": None, "precision": None, "f1": None}
    return out
