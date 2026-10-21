"""Regression coverage for the observed pilot failures and hybrid assembly."""
import json
from pathlib import Path

import pytest
from pydantic_ai.models.function import FunctionModel

from synth import corpus, truth
from synth.levels import LEVELS, make_plan, plan_rng
from synth.protected import assemble
from synth.render_llm import LlmRenderer, locate
from synth.fidelity import check_paper
import modelcall
from synth.tests.test_llm import prompt_of, respond


def test_saved_pilot_drafts_repeat_values():
    rows = json.loads((Path(__file__).parent / "fixtures/pilot-repeated-values.json").read_text())
    for row in rows:
        study = truth.generate(row["seed"], 3)[0]
        plan = make_plan(study, row["level"], plan_rng(row["seed"], study.study_id, row["level"]))
        assert any("ambiguous" in p for p in locate(row["markdown"], plan)[2])


@pytest.mark.parametrize("level", LEVELS)
def test_protected_blocks_keep_level_and_anchors(level):
    for study in truth.generate(1, 3):
        plan = make_plan(study, level, plan_rng(1, study.study_id, level))
        text = assemble(plan, 1, {"Introduction": "We compare answer-generation conditions in a common setting.",
                                  "Discussion": "The benchmark may limit coverage of question types."})
        ps, decoys, errors = locate(text, plan)
        assert errors == []
        assert all(c.ok for c in check_paper(text, plan, ps, decoys))


def test_protected_pipeline_repairs_only_rejected_passage_and_caches(tmp_path):
    calls = []

    def writer(messages, info):
        prompt = prompt_of(messages)
        calls.append(prompt)
        task = json.loads(prompt)
        if task["section"] == "Introduction" and "rejected" not in task:
            return respond(info, {"text": "The benchmark contains 29.9 percent successful answers."})
        return respond(info, {"text": "The comparison has a limited benchmark scope. Broader question coverage may warrant further evaluation."})

    cache = tmp_path / "cache.jsonl"
    renderer = LlmRenderer(FunctionModel(writer, model_name="context-writer"), cache, assembly="protected")
    result = corpus.build(name="p", seed=1, studies=1, renderer=renderer, out=tmp_path / "c", levels=["contradictory"])
    assert result["excluded"] == {}
    assert len(calls) == 3
    assert '"rejected"' in calls[1] and '"Discussion"' in calls[2]
    meta = json.loads((tmp_path / "c/p-contradictory/corpus.json").read_text())
    assert meta["models"]["assembly"] == "protected"
    assert meta["models"]["statements"] is False
    renderer = LlmRenderer(FunctionModel(writer, model_name="context-writer"), cache, assembly="protected")
    corpus.build(name="p", seed=1, studies=1, renderer=renderer, out=tmp_path / "d", levels=["contradictory"])
    assert len(calls) == 3


def test_protected_does_not_accept_unrepaired_prose(tmp_path):
    def writer(messages, info):
        return respond(info, {"text": "This passage invents 99 percent accuracy for the system."})
    renderer = LlmRenderer(FunctionModel(writer, model_name="bad-writer"), tmp_path / "c.jsonl",
                           assembly="protected", attempts=2)
    result = corpus.build(name="p", seed=1, studies=1, renderer=renderer, out=tmp_path / "c", levels=["distributed"])
    assert result["excluded"] == {"S001": ["distributed"]}


def test_protected_still_requires_independent_verification(tmp_path):
    def writer(messages, info):
        return respond(info, {"text": "The comparison has a limited benchmark scope. Broader question coverage may warrant further evaluation."})
    def verifier(messages, info):
        return respond(info, {"direct": [], "relative": []})
    renderer = LlmRenderer(FunctionModel(writer, model_name="context-writer"), tmp_path / "c.jsonl",
                           assembly="protected", verify_model=FunctionModel(verifier, model_name="blind-reader"))
    result = corpus.build(name="p", seed=3, studies=1, renderer=renderer, out=tmp_path / "c", levels=["explicit"])
    assert result["excluded"] == {"S001": ["explicit"]}
    record = json.loads((tmp_path / "c/p-explicit/fidelity.json").read_text())["papers"][0]
    assert any(c["name"] == "blind_reextraction" and not c["ok"] for c in record["checks"])


def test_blind_reading_repairs_source_errors_without_private_truth(tmp_path):
    calls = []
    quote = "System A scores 33.5% accuracy."

    def verifier(messages, info):
        prompt = prompt_of(messages)
        calls.append(prompt)
        return respond(info, {"direct": [{"condition": "System A", "metric": "accuracy", "dataset": "Set",
                                         "number": "33.5" if "failed_checks" in prompt else "99.9",
                                         "unit": "percent", "quote": quote}], "relative": []})
    model = FunctionModel(verifier, model_name="source-reader")
    renderer = LlmRenderer(model, tmp_path / "c.jsonl", assembly="protected", verify_model=model)
    history = []
    result = modelcall.run_sync(renderer._blind(quote, 1, history))
    assert result.measurements[0].value == 0.335 and len(calls) == 2
    assert len(history) == 1 and history[0]["rejected"]["direct"][0]["number"] == "99.9"
    assert "private" not in calls[1] and "does not contain" in calls[1]
