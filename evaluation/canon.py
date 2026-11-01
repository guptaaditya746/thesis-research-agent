"""Canonical keys for the names a paper or an answer gives a metric, a condition or a dataset (evaluation only).

`key(target, name)` maps any form the default pack's generator recipe knows (domains/<pack>/generator.yaml,
read with synth.recipe.load_recipe until plan 2 Task 12 reads it without synth; case-folded, whitespace
collapsed) to one stable key: a metric's name, abbreviation or description gives the metric name; a
condition's label or synonym gives its label; a dataset's name gives the name. A name the recipe does not know
gives None (a baseline's unknown name is then a false positive, never an error).

`KIND_OF` maps a condition label to its method kind for the `best` questions: the control side's names are
no-retrieval, the treatment side's rag, and each other condition its own kind, in the order and with the names of
`best.kinds` in domains/rag/protocols/best-accuracy.yaml and best-hallucination.yaml (a test checks that they
agree).
"""
from __future__ import annotations

from typing import Literal

from evidence.protocol import DEFAULT_PACK
from synth.recipe import NameForms, load_recipe

Target = Literal["metric", "condition", "dataset"]
OTHER_KINDS = ("rag-no-rerank", "rag-random", "fine-tuned", "chain-of-thought", "self-consistency", "query-rewriting")
RECIPE = load_recipe(DEFAULT_PACK)


def side_names(role: str) -> list[NameForms]:
    """The names of the recipe's side whose role is `role` (control, treatment)."""
    return [n for side in RECIPE.sides.values() if side.role == role for n in side.names]


def fold(name: str) -> str:
    return " ".join(str(name).split()).casefold()


def _table() -> dict[str, dict[str, str]]:
    metric: dict[str, str] = {}
    for spec in (*RECIPE.question_metrics, *RECIPE.other_metrics):
        for name, abbr, description in spec.forms:
            for form in (name, abbr, description):
                metric.setdefault(fold(form), name)
    condition: dict[str, str] = {}
    for n in (*side_names("control"), *side_names("treatment"), *RECIPE.others):
        for form in (n.label, n.synonym):
            condition.setdefault(fold(form), n.label)
    dataset = {fold(name): name for name in RECIPE.contexts}
    return {"metric": metric, "condition": condition, "dataset": dataset}


KEYS = _table()
assert len(OTHER_KINDS) == len(RECIPE.others), "every other condition has its own kind"
KIND_OF: dict[str, str] = {**{n.label: "no-retrieval" for n in side_names("control")},
                           **{n.label: "rag" for n in side_names("treatment")},
                           **{n.label: kind for n, kind in zip(RECIPE.others, OTHER_KINDS, strict=True)}}


def key(target: Target, name: str) -> str | None:
    """The stable key of `name` as a `target`, or None when the recipe does not know it."""
    return KEYS[target].get(fold(name))
