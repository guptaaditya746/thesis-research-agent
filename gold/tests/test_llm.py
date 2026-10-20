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


def test_cache_survives_a_cut_last_line(tmp_path):
    path = tmp_path / "c.jsonl"
    cache = llm.JsonlCache(path)
    cache.put("a", {"output": 1})
    with open(path, "ab") as fh:
        fh.write(b'{"key": "b", "value": {"output": "a long reply cut by the time li')  # killed mid-append
    cache = llm.JsonlCache(path)
    assert cache.get("a") == {"output": 1} and cache.get("b") is None and cache.skipped == 1
    cache.put("c", {"output": 3})  # starts on a new line, so the cut line does not swallow it
    again = llm.JsonlCache(path)
    assert (again.get("a"), again.get("c"), again.skipped) == ({"output": 1}, {"output": 3}, 1)


def test_model_identity_is_the_pin_for_the_replicas():
    sub = [llm.openai_model("sub-model-1"), llm.openai_model("sub-model-2")]
    assert llm.model_identity(sub) == llm.model_identity(sub[:1]) == \
        f"{llm.SUB_MODEL['name']}@{llm.SUB_MODEL['revision']}"
    assert llm.model_identity([TestModel(), llm.openai_model("sub-model-1")]) == "sub-model-1+test"


def test_model_identity_is_the_pin_for_orch_model():
    """Part G.3: orch-model, the one model of every extractor and both baselines, maps to its pinned weights."""
    from agent.rundir import ORCHESTRATOR

    assert llm.model_identity([llm.openai_model("orch-model")]) == f"{ORCHESTRATOR['name']}@{ORCHESTRATOR['revision']}"
    assert llm.model_identity([llm.openai_model("orch-model")]) != llm.model_identity([llm.openai_model("sub-model-1")])
    assert llm.model_identity([llm.openai_model("orch-model"), llm.openai_model("sub-model-1")]) == "orch-model+sub-model-1"


def test_redact_removes_the_key_its_hash_and_key_shaped_tokens(monkeypatch):
    monkeypatch.setenv("LITELLM_MASTER_KEY", "my-secret-key")
    from jsonio import sha256_hex

    text = f"bad key my-secret-key (hash {sha256_hex(b'my-secret-key')}), seen as sk-abcd...wxyz"
    assert llm.redact(text) == "bad key *** (hash ***), seen as ***"
    assert llm.redact("HTTP 503: upstream connect error") == "HTTP 503: upstream connect error"
