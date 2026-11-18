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


def test_a_best_plan_with_no_measure_is_refused_at_the_run(tmp_path):
    from evidence.planrun import PlanNotRunnable, check_request
    from evidence.plan import write_plan
    plan = with_answer(make_plan(things={"rag": ["rag"], "closed_book": ["closed-book"]}, measures=()), "best", None)
    write_plan(plan, tmp_path / "plan.json")
    with pytest.raises(PlanNotRunnable, match="a best answer needs a measure"):
        check_request(tmp_path / "plan.json")
    with pytest.raises(PlanNotRunnable, match="a best answer needs a measure"):
        plan_run(tmp_path / "run", plan)
    assert not (tmp_path / "run" / "runs").exists()   # nothing was run


def test_best_needs_two_compared_things():
    plan = with_answer(make_plan(things={"rag": ["rag"], "accuracy": ["accuracy"]}), "best", None)
    assert "a best answer needs two compared things" in answer_problems(plan)


def test_an_inventory_plan_run_answers_by_the_inventory_rule(tmp_path):
    root = plan_run(tmp_path, with_answer(make_plan(), "inventory", "condition"))
    answer = json.loads((root / "answer.json").read_text(encoding="utf-8"))
    assert answer["synthesis"]["kind"] == "inventory" and answer["synthesis"]["target"] == "condition"
    assert yaml.safe_load((root / "protocol.yaml").read_text(encoding="utf-8"))["kind"] == "inventory"


def _best_condition() -> dict:
    raw = yaml.safe_load(kind_protocol(with_answer(make_plan(), "best", None)).decode("utf-8"))
    return raw["evidence_types"]["condition"]


def test_a_best_condition_may_be_none_of_the_compared_things():
    """Review round 1, engine-C2: `kind` was a required string of the compared ids, so the LLM extractor had to
    file a paper's third method under one of them."""
    from evidence.extractors.llm_schema import output_model
    condition = _best_condition()
    kind = condition["fields"]["properties"]["kind"]
    assert kind["type"] == ["string", "null"] and kind["enum"] == ["rag", "closed_book", None]
    protocol = parse(kind_protocol(with_answer(make_plan(), "best", None)).decode("utf-8"))
    et = protocol.evidence_types["condition"]
    model = output_model("condition", condition["fields"], {}, list(et.roles))

    def reply(value):
        fields = dict.fromkeys(condition["fields"]["properties"]) | {"label": "Method Z", "role": "other",
                                                                      "kind": value}
        return {"items": [{"fields": fields, "quotes": dict.fromkeys(et.roles, "Method Z")}]}

    assert model.model_validate(reply(None)).items[0].fields.kind is None
    assert model.model_validate(reply("rag")).items[0].fields.kind == "rag"
    with pytest.raises(ValueError):
        model.model_validate(reply("other"))   # one way to say it: null


def test_the_best_condition_type_tells_the_model_about_null():
    """The text the model reads (docs/prompt-writing.md: allowed values and the missing case stated)."""
    condition = _best_condition()
    said = "kind is the id of the compared thing this condition is (rag or closed_book), or null when it is neither"
    assert condition["description"].endswith(said + "; a condition with kind null is left out of the comparison.")
    assert condition["fields"]["properties"]["kind"]["description"] == (
        "rag or closed_book when the condition is that compared thing; null when it is neither")


def test_a_condition_of_no_compared_kind_is_left_out_of_the_best_answer():
    """A third method (kind null) with the lowest value must not stand in for a compared thing."""
    from evidence import kinds
    from evidence.tests.readable_cases import item
    protocol = parse(kind_protocol(with_answer(make_plan(), "best", None)).decode("utf-8"))
    metric = item("metric", {"name": "Accuracy", "canonical": "accuracy", "higher_is_better": True},
                  exact="Accuracy", start=20)
    items = [metric]
    for label, role, kind, value, start in (("Method Z", "other", None, 0.2, 100), ("RAG model", "rag", "rag", 0.9, 200),
                                            ("Closed-book", "closed_book", "closed_book", 0.6, 300)):
        thing = item("condition", {"label": label, "role": role, "kind": kind}, exact=label, start=start)
        items += [thing, item("measurement", {"value": value, "dataset": "NQ"},
                              {"condition": thing.item_id, "metric": metric.item_id}, exact=str(value),
                              start=start + 30)]
    answer, _ = kinds.of(protocol).answer(protocol, ["S001"], {"S001": items}, roles=protocol.roles())
    assert answer["studies"][0]["values"] == {"rag": 0.9, "closed_book": 0.6} and answer["winner"] == "rag"
