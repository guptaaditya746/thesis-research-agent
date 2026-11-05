"""The answer model accepts every question kind's answer.json, and an old effect answer (no `kind` key)."""
from __future__ import annotations

from typing import Any

import pytest

from webapp.evmodels import (EV_ANSWER, BestAnswer, BuildsOnAnswer, ChainingAnswer, ConsistencyAnswer, EffectAnswer,
                             InventoryAnswer, LimitationsAnswer, UnknownAnswer)

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

# plan 2's kinds, in the shapes evidence/kinds/{chaining,limitations,builds_on}.py write (preflight F43)
CHAINING = {"kind": "chaining", "system": "engine", "source": "A", "target": "C", "metric": "score", "verdict": "better",
            "inferred": True, "via": ["B"], "studies": ["p1", "p2"],
            "paths": [{"via": ["B"], "verdict": "better", "reason": None,
                       "steps": [{"comparison": "cmp-1", "document": "p1", "from": "A", "to": "B", "metric": "score",
                                  "direction": "better", "context": None},
                                 {"comparison": "cmp-2", "document": "p2", "from": "B", "to": "C", "metric": "score",
                                  "direction": "better", "context": None}]}],
            "reason": None, "note": "inferred through B, not tested directly"}
LIMITATIONS = {"kind": "limitations", "system": "engine", "thing": None,
               "entries": [{"thing": "A", "category": "small_sample", "papers": ["p1"], "items": ["l1"]},
                           {"thing": None, "category": "other", "papers": ["p2"], "items": ["l2"]}],
               "counts": {"A": {"small_sample": 1}}, "unlinked": {"other": 1}}
BUILDS_ON = {"kind": "builds_on", "system": "engine", "thing": None,
             "links": [{"from": "p2", "to": "p1", "reuses": "method", "items": ["d1"]}],
             "origins": {"A": "p1"}, "followers": {"A": ["p2"]}, "influence": {"A": 1}, "ranking": ["A"],
             "unresolved": ["Someone 1999"]}


@pytest.mark.parametrize(("raw", "model"), [(OLD_EFFECT, EffectAnswer), (INVENTORY, InventoryAnswer),
                                            (CONSISTENCY, ConsistencyAnswer), (BEST, BestAnswer),
                                            (CHAINING, ChainingAnswer), (LIMITATIONS, LimitationsAnswer),
                                            (BUILDS_ON, BuildsOnAnswer)])
def test_each_kind_loads_as_its_model(raw: dict[str, Any], model: type) -> None:
    answer = EV_ANSWER.validate_python(raw)
    assert isinstance(answer, model)
    dumped = EV_ANSWER.dump_python(answer, mode="json")
    assert {k: v for k, v in raw.items() if k != "studies"}.items() <= dumped.items() or model is EffectAnswer


def test_an_old_effect_answer_without_kind_still_loads() -> None:
    answer = EV_ANSWER.validate_python(OLD_EFFECT)
    assert answer.kind == "effect" and answer.label == "supports"


def test_an_unknown_kind_still_loads_as_written() -> None:
    raw = {"kind": "ranking", "system": "engine", "order": ["a", "b"]}
    answer = EV_ANSWER.validate_python(raw)
    assert isinstance(answer, UnknownAnswer)
    assert EV_ANSWER.dump_python(answer)["order"] == ["a", "b"]


def test_from_keys_keep_their_name_both_ways() -> None:
    """`from` is a Python keyword, so the models name the field `from_`; the JSON keeps `from`."""
    chain = EV_ANSWER.dump_python(EV_ANSWER.validate_python(CHAINING), mode="json")
    links = EV_ANSWER.dump_python(EV_ANSWER.validate_python(BUILDS_ON), mode="json")["links"]
    assert chain["paths"] == CHAINING["paths"] and links == BUILDS_ON["links"]
