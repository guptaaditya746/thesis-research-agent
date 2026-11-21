"""The optional DeepEval step: runs through paperfactory's model layer, never stops the run."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperfactory import config, deepeval_step

deepeval = pytest.importorskip("deepeval")


def fill(schema: dict, defs: dict | None = None):
    """A minimal valid value for a JSON schema (a fake judge that always answers in form)."""
    defs = defs if defs is not None else schema.get("$defs", {})
    if "$ref" in schema:
        return fill(defs[schema["$ref"].rsplit("/", 1)[1]], defs)
    for k in ("anyOf", "oneOf"):
        if k in schema:
            return fill(next(x for x in schema[k] if x.get("type") != "null"), defs)
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "object" or "properties" in schema:
        return {k: fill(v, defs) for k, v in schema.get("properties", {}).items()}
    if t == "array":
        return [fill(schema.get("items", {"type": "string"}), defs)]
    return {"string": "yes", "integer": 1, "number": 1.0, "boolean": True}.get(t, "yes")


def fake_call(seen: list):
    def call(role, step, system, user, out, check=None):
        seen.append((role, step))
        schema = out.model_json_schema() if isinstance(out, type) else out
        return fill(schema)
    return call


def run_dir(tmp_path: Path) -> config.Settings:
    s = config.Settings("law", "argument", out=str(tmp_path), parallel=2)
    sent = "Rusk relied on section 14 of the Act."
    (tmp_path / "tagged.json").write_text(json.dumps({"papers": {"L-01": {
        "sentences": [[0, len(sent), sent]], "spans": {"K5-relies_on-S14": [[0, len(sent)]]}}}}))
    (tmp_path / "report.json").write_text(json.dumps({"qa": [
        {"id": "L-01:treat", "question": "How did Rusk treat section 14?", "papers": ["L-01"],
         "gold": ["K5-relies_on-S14"], "items": [{"answer_sentence": "Rusk relied on section 14.", "quote": sent}]},
        {"id": "L-01:relied", "question": "Which sources did Rusk rely on?", "papers": ["L-01"],
         "gold": ["K5-relies_on-S14"], "items": []}]}))
    return s


def test_deepeval_scores_gold_and_qa_through_the_judge_role(tmp_path: Path) -> None:
    seen: list = []
    res = deepeval_step.run(run_dir(tmp_path), fake_call(seen), lambda i: "Rusk: the court relied on section 14.")
    assert res["questions"] == 2 and res["summary"]["gold_grounding"]["n"] == 2
    assert res["summary"]["faithfulness"]["n"] + res["summary"]["faithfulness"]["errors"] == 1
    assert seen and all(r == "judge" and st.startswith("deepeval:") for r, st in seen)
    assert json.loads((tmp_path / "deepeval.json").read_text())["questions"] == 2


def test_a_judge_that_never_answers_is_recorded_not_fatal(tmp_path: Path) -> None:
    res = deepeval_step.run(run_dir(tmp_path), lambda *a, **k: None, lambda i: "x")
    assert res["summary"]["gold_grounding"]["errors"] == 2 and res["summary"]["gold_grounding"]["n"] == 0


def test_no_evaluation_yet_is_skipped(tmp_path: Path) -> None:
    res = deepeval_step.run(config.Settings("law", "argument", out=str(tmp_path)), fake_call([]), str)
    assert "skipped" in res
