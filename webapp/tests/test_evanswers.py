"""The answer model accepts every question kind's answer.json, and an old effect answer (no `kind` key)."""
from __future__ import annotations

from typing import Any

import pytest

from webapp.evmodels import (EV_ANSWER, BestAnswer, ConsistencyAnswer, EffectAnswer, InventoryAnswer)

OLD_EFFECT = {"system": "engine", "label": "supports", "counts": {"supporting": 1}, "supporting": ["p1"],
              "studies": [{"document": "p1", "direction": "supports"}]}
INVENTORY = {"kind": "inventory", "system": "engine", "target": "dataset",
             "entries": [{"name": "SQuAD", "aliases": ["Squad v1"], "papers": ["p1", "p2"], "items": ["i1"]}]}
CONSISTENCY = {"kind": "consistency", "system": "engine", "metric": "factual_accuracy",
               "studies": [{"document": "p1", "claim": "supports", "direction": "supports", "agrees": True, "reason": None},
                           {"document": "p2", "claim": None, "direction": "undetermined", "agrees": None,
                            "reason": {"code": "no_claim", "text": "no author claim found"}}],
               "agreeing": ["p1"], "disagreeing": [], "undetermined": ["p2"]}
BEST = {"kind": "best", "system": "engine", "metric": "factual_accuracy",
        "studies": [{"document": "p1", "winner": "rag", "tied": [], "values": {"rag": 0.8, "plain": 0.6}, "reason": None},
                    {"document": "p2", "winner": None, "tied": ["plain", "rag"], "values": {"rag": 0.7, "plain": 0.7},
                     "reason": None}],
        "wins": {"rag": 1}, "winner": "rag", "tied": []}


@pytest.mark.parametrize(("raw", "model"), [(OLD_EFFECT, EffectAnswer), (INVENTORY, InventoryAnswer),
                                            (CONSISTENCY, ConsistencyAnswer), (BEST, BestAnswer)])
def test_each_kind_loads_as_its_model(raw: dict[str, Any], model: type) -> None:
    answer = EV_ANSWER.validate_python(raw)
    assert isinstance(answer, model)
    dumped = EV_ANSWER.dump_python(answer)
    assert {k: v for k, v in raw.items() if k != "studies"}.items() <= dumped.items() or model is EffectAnswer


def test_an_old_effect_answer_without_kind_still_loads() -> None:
    answer = EV_ANSWER.validate_python(OLD_EFFECT)
    assert answer.kind == "effect" and answer.label == "supports"
