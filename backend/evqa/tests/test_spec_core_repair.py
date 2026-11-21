"""Spec ReadQuestionCore: a part not written in the question gets one repair call with feedback (Haiku practice
run, 21 Nov: "body weight reduction" for "reduction in body weight" lost the measure and stopped the question)."""
from __future__ import annotations

import json
import re

import dspy

import evqa.lm
from evqa.contracts import StepLLM
from evqa.spec import build

Q = "Would veloranide 50 mg lead to a greater reduction in body weight than placebo?"


def feedback(prompt: str) -> str:
    m = re.search(r"\[\[ ## feedback ## \]\]\n(.*?)(?=\n\n\[\[ ## |\n\nRespond with|\Z)", prompt.split("[user]")[-1], re.S)
    return m.group(1).strip() if m else ""


def run_core(monkeypatch, tmp_path, replies):
    monkeypatch.setattr(evqa.lm, "CACHE_FILE", tmp_path / "lm.jsonl")
    monkeypatch.setattr(evqa.lm, "_caches", {})
    seen: list[str] = []

    def ask(prompt: str) -> str:
        seen.append(feedback(prompt))
        return json.dumps(replies[len(seen) - 1])
    lm = evqa.lm.make_lm(StepLLM(), ask=ask)
    with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
        return build.read_core(Q), seen


def test_paraphrased_measure_is_repaired_once(monkeypatch, tmp_path):
    core, seen = run_core(monkeypatch, tmp_path, [
        {"subjects": ["veloranide"], "comparator": "placebo", "measure": "body weight reduction"},
        {"subjects": ["veloranide"], "comparator": "placebo", "measure": "reduction in body weight"}])
    assert core.measure == "reduction in body weight"
    assert seen[0] == "" and '"body weight reduction"' in seen[1] and len(seen) == 2


def test_exact_reply_needs_no_repair(monkeypatch, tmp_path):
    core, seen = run_core(monkeypatch, tmp_path, [
        {"subjects": ["veloranide"], "comparator": "placebo", "measure": "body weight"}])
    assert core.measure == "body weight" and len(seen) == 1


def test_still_wrong_after_repair_is_dropped_by_code(monkeypatch, tmp_path):
    bad = {"subjects": ["veloranide"], "comparator": "placebo", "measure": "weight loss"}
    core, seen = run_core(monkeypatch, tmp_path, [bad, bad])
    assert len(seen) == 2 and build._in_question(core.measure, Q) is None


def test_per_row_dimension_takes_the_row_field_name():
    # Haiku named the time "duration" (p22) and Link judged it on the whole paper; row_field renames it
    from evqa.spec.dimensions_v3 import DraftDimension, checked
    q = "How much does ordenvik change fasting plasma glucose at 8 weeks?"
    dims, errors = checked([
        DraftDimension(key="duration", question="When?", why="changes over time", fixed_value="8 weeks",
                       quote="8 weeks", row_field="time_point"),
        DraftDimension(key="population", question="Who?", why="differs by group"),
        DraftDimension(key="treatment_length", question="How long?", why="x", row_field="time_point")], q)
    assert [d.key for d in dims] == ["time_point", "population"]
    assert dims[0].fixed_value == "8 weeks" and len(errors) == 1
