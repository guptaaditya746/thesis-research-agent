"""Canonical keys for the names a paper or an answer gives a metric, a condition or a dataset (evaluation only).

`key(target, name)` maps any form `synth/vocab.py` knows (case-folded, whitespace collapsed) to one stable key:
a metric's name, abbreviation or description gives the vocab metric name; a condition's label or synonym gives
its label; a dataset's name gives the name. A name vocab does not know gives None (a baseline's unknown name is
then a false positive, never an error).

`KIND_OF` maps a condition label to its method kind for the `best` questions: the BASELINES are no-retrieval,
the RAGS rag, and each OTHERS entry its own kind, in the order and with the names of `best.kinds` in
domains/rag/protocols/best-accuracy.yaml and best-hallucination.yaml (a test checks that they agree).
"""
from __future__ import annotations

from typing import Literal

from synth import vocab

Target = Literal["metric", "condition", "dataset"]
OTHER_KINDS = ("rag-no-rerank", "rag-random", "fine-tuned", "chain-of-thought", "self-consistency", "query-rewriting")


def fold(name: str) -> str:
    return " ".join(str(name).split()).casefold()


def _table() -> dict[str, dict[str, str]]:
    metric: dict[str, str] = {}
    for forms in vocab.QUESTION_METRICS.values():
        for name, abbr, description in forms:
            for form in (name, abbr, description):
                metric.setdefault(fold(form), name)
    for _key, name, abbr, description, _hib, _unit in vocab.OTHER_METRICS:
        for form in (name, abbr, description):
            metric.setdefault(fold(form), name)
    condition: dict[str, str] = {}
    for label, synonym, _description in (*vocab.BASELINES, *vocab.RAGS, *vocab.OTHERS):
        for form in (label, synonym):
            condition.setdefault(fold(form), label)
    dataset = {fold(name): name for name in vocab.DATASETS}
    return {"metric": metric, "condition": condition, "dataset": dataset}


KEYS = _table()
assert len(OTHER_KINDS) == len(vocab.OTHERS), "every OTHERS condition has its own kind"
KIND_OF: dict[str, str] = {**{label: "no-retrieval" for label, _, _ in vocab.BASELINES},
                           **{label: "rag" for label, _, _ in vocab.RAGS},
                           **{label: kind for (label, _, _), kind in zip(vocab.OTHERS, OTHER_KINDS, strict=True)}}


def key(target: Target, name: str) -> str | None:
    """The stable key of `name` as a `target`, or None when vocab does not know it."""
    return KEYS[target].get(fold(name))
