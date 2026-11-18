"""A plan keeps its sub-questions and how its answer is made; an old plan keeps its exact dump and sha256."""
from __future__ import annotations

import pytest

from evidence.plan import Plan, load_plan, with_answer, write_plan
from evidence.tests.test_plan_run import make_plan

OLD_SHA = "a4c7014d347d416a15fdea54179fe18823294e1b3a7e002fc254d58745c32587"

def test_an_old_plan_keeps_its_dump_and_sha256():
    old = make_plan()
    dumped = old.model_dump(mode="json")
    assert old.sha256 == OLD_SHA
    assert not {"sub_questions", "answer_by", "target", "writer_try"} & set(dumped)
    assert Plan.model_validate_json(old.model_dump_json()).answer_by == "lines"

def test_explicit_defaults_stay_out_of_the_dump_and_the_sha256():
    """m5: answer_by "lines" and writer_try 0 given on purpose are dumped and hashed as an old plan."""
    explicit = Plan.model_validate({**make_plan().model_dump(mode="json"), "answer_by": "lines", "writer_try": 0})
    assert not {"answer_by", "writer_try"} & set(explicit.model_dump(mode="json"))
    assert explicit.sha256 == OLD_SHA and explicit.model_dump_json() == make_plan().model_dump_json()

def test_new_fields_change_the_sha256_and_round_trip(tmp_path):
    p = with_answer(make_plan().model_copy(update={"sub_questions": ["Which papers measured it?"]}), "inventory", "metric")
    write_plan(p, tmp_path / "p.json")
    back = load_plan(tmp_path / "p.json")
    assert back == p and back.sha256 != OLD_SHA and back.target == "metric"
    assert back.model_copy(update={"writer_try": 1}).sha256 != back.sha256

def test_target_only_for_inventory_and_no_empty_sub_question():
    with pytest.raises(ValueError, match="target is only for an inventory answer"):
        with_answer(make_plan(), "written", "metric")
    with pytest.raises(ValueError, match="a sub-question is empty"):
        Plan.model_validate({**make_plan().model_dump(mode="json"), "sub_questions": [" "]})
    with pytest.raises(ValueError):
        with_answer(make_plan(), "chaining", None)
