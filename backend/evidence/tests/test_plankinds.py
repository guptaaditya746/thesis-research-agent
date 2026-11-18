"""A plan can answer by a fixed kind's rules: kind_protocol writes the protocol of that kind from the plan."""
from __future__ import annotations

import hashlib
import json

import pytest
import yaml

from evidence.plan import with_answer
from evidence.plankinds import answer_problems, kind_protocol
from evidence.planrun import protocol_for
from evidence.protocol import parse
from evidence.tests.test_plan_run import make_plan, plan_run

TODAYS_SHA = "3185792594ae71a4ad59c93181be51be80d5e79a9189c5475bc3b66de1cf5a26"   # sha256 of protocol_for(make_plan()) before this change


def test_effect_written_and_lines_are_todays_protocol():
    for by in ("lines", "written", "effect"):
        plan = with_answer(make_plan(), by, None)
        assert kind_protocol(plan) == protocol_for(plan)
    assert hashlib.sha256(kind_protocol(make_plan())).hexdigest() == TODAYS_SHA


@pytest.mark.parametrize("by, target", [("lines", None), ("written", None), ("effect", None), ("consistency", None),
                                        ("inventory", "condition"), ("best", None)])
def test_a_later_writer_try_keeps_the_protocol_bytes(by, target):
    plan = with_answer(make_plan(), by, target)
    assert kind_protocol(plan.model_copy(update={"writer_try": 2})) == kind_protocol(plan)


@pytest.mark.parametrize("by, target", [("consistency", None), ("inventory", "condition"), ("inventory", "metric"),
                                        ("best", None)])
def test_each_fixed_kind_parses_as_its_kind(by, target):
    p = parse(kind_protocol(with_answer(make_plan(), by, target)).decode("utf-8"))
    assert p.kind == by
    if by == "inventory":
        assert p.inventory.target == target and p.synthesis is None
    if by == "best":
        assert set(p.best.kinds) == {"rag", "closed_book"} and p.best.metric.canonical == "accuracy"
        assert "retrieval-augmented model" in p.best.kinds["rag"]
    if by == "consistency":
        assert p.consistency.by == "direction" and p.synthesis is not None


def test_best_without_a_measure_is_a_problem():
    plan = with_answer(make_plan(things={"rag": ["rag"], "closed_book": ["closed-book"]}, measures=()), "best", None)
    assert "a best answer needs a measure" in answer_problems(plan)
    assert answer_problems(with_answer(make_plan(), "best", None)) == []


def test_best_needs_two_compared_things():
    plan = with_answer(make_plan(things={"rag": ["rag"], "accuracy": ["accuracy"]}), "best", None)
    assert "a best answer needs two compared things" in answer_problems(plan)


def test_an_inventory_plan_run_answers_by_the_inventory_rule(tmp_path):
    root = plan_run(tmp_path, with_answer(make_plan(), "inventory", "condition"))
    answer = json.loads((root / "answer.json").read_text(encoding="utf-8"))
    assert answer["synthesis"]["kind"] == "inventory" and answer["synthesis"]["target"] == "condition"
    assert yaml.safe_load((root / "protocol.yaml").read_text(encoding="utf-8"))["kind"] == "inventory"
