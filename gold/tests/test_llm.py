"""gold/llm.py: structured calls, rotation, prompt hashes, the result cache."""
from __future__ import annotations

import asyncio

from pydantic import BaseModel
from pydantic_ai.models.test import TestModel

from gold import llm


class Verdict(BaseModel):
    relevant: bool
    findings: list[str]


def test_structured_returns_the_output_type():
    out = asyncio.run(llm.structured("Screen the text.", "some text", Verdict,
                                     model=TestModel(custom_output_args={"relevant": True, "findings": ["x"]})))
    assert out == Verdict(relevant=True, findings=["x"])


def test_litellm_models_use_schema_constrained_output(monkeypatch):
    monkeypatch.setenv("LITELLM_MASTER_KEY", "k")
    model = llm.openai_model("sub-model-1")
    assert model.model_name == "sub-model-1"
    assert model.profile.get("supports_json_schema_output")


def test_rotation_alternates():
    a, b = TestModel(), TestModel()
    rot = llm.Rotation([a, b])
    assert [rot.next() for _ in range(4)] == [a, b, a, b]


def test_prompt_hash_changes_with_schema_and_text():
    class Other(BaseModel):
        x: int

    h = llm.prompt_sha256("p", Verdict)
    assert h == llm.prompt_sha256("p", Verdict)
    assert h != llm.prompt_sha256("q", Verdict)
    assert h != llm.prompt_sha256("p", Other)


def test_settings_turn_thinking_off():
    s = llm.settings(seed=3)
    assert s["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert s["seed"] == 3 and s["temperature"] == 0.0


def test_cache_survives_reload(tmp_path):
    path = tmp_path / "c.jsonl"
    cache = llm.JsonlCache(path)
    key = llm.cache_key({"a": 1})
    assert cache.get(key) is None
    cache.put(key, {"label": "supports"})
    assert llm.JsonlCache(path).get(key) == {"label": "supports"}
