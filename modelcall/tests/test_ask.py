"""`ask`: the one cached, redacted, schema-constrained model call."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from modelcall import (Answer, CachedFailure, JsonlCache, ModelCallError, Prompt, ask, ask_sync, cache_key,
                       default_key,
                       run_sync)
from modelcall.gateway import CallSettings
from modelcall.call import PlainTextReply


class Out(BaseModel):
    answer: str


PROMPT = Prompt.inline("Answer.", Out)


def test_plain_text_reply_keeps_dspy_json_unwrapped_and_cacheable(tmp_path: Path) -> None:
    calls = []

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(info)
        assert not info.output_tools
        return ModelResponse(parts=[TextPart('{"is_claim": true}')])

    model = FunctionModel(reply, model_name="plain-model")
    prompt = Prompt.inline("", PlainTextReply)
    cache = JsonlCache(tmp_path / "plain.jsonl")
    first = ask_sync(prompt, "sentence", model=model, cache=cache, key={"test": "plain"})
    second = ask_sync(prompt, "sentence", model=model, cache=cache, key={"test": "plain"})
    assert first.output.text == '{"is_claim": true}'
    assert second.output == first.output and second.cached and len(calls) == 1


class Counted:
    """A FunctionModel answering `args` (or doing `act`), counting its calls."""

    def __init__(self, args: dict[str, Any] | None = None, act: Any = None) -> None:
        self.calls = 0
        self.args = args or {"answer": "a"}
        self.act = act

    def model(self) -> FunctionModel:
        def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            self.calls += 1
            if self.act:
                self.act()
            if info.output_tools:
                return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, self.args)])
            return ModelResponse(parts=[TextPart(json.dumps(self.args))])
        return FunctionModel(reply, model_name="ask-model")


def lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_miss_calls_and_stores_new_shape(tmp_path: Path) -> None:
    counted = Counted()
    model = counted.model()
    cache = JsonlCache(tmp_path / "c.jsonl")
    key = default_key(PROMPT, "P", model, CallSettings())
    answer = ask_sync(PROMPT, "P", model=model, cache=cache, key=key)
    assert counted.calls == 1
    assert isinstance(answer, Answer) and answer.output == Out(answer="a") and not answer.cached
    assert answer.key == cache_key(key) and answer.model == "ask-model" and answer.messages
    [line] = lines(tmp_path / "c.jsonl")
    assert line["key"] == answer.key
    assert sorted(line["value"]) == ["model", "output", "served_model", "usage"]
    assert line["value"]["output"] == {"answer": "a"}
    assert sorted(line["value"]["usage"]) == ["input_tokens", "output_tokens"]


def test_extra_is_stored_with_the_value(tmp_path: Path) -> None:
    model = Counted().model()
    cache = JsonlCache(tmp_path / "c.jsonl")
    ask_sync(PROMPT, "P", model=model, cache=cache, key={"k": 1}, extra={"task": "t"})
    [line] = lines(tmp_path / "c.jsonl")
    assert line["value"]["task"] == "t"


def test_hit_makes_no_call(tmp_path: Path) -> None:
    counted = Counted()
    model = counted.model()
    cache = JsonlCache(tmp_path / "c.jsonl")
    first = ask_sync(PROMPT, "P", model=model, cache=cache, key={"k": 1})
    again = ask_sync(PROMPT, "P", model=model, cache=JsonlCache(tmp_path / "c.jsonl"), key={"k": 1})
    assert counted.calls == 1
    assert again.cached and again.output == first.output and again.messages == []
    assert (again.input_tokens, again.output_tokens) == (first.input_tokens, first.output_tokens)


def test_refresh_calls_again_and_last_line_wins(tmp_path: Path) -> None:
    counted = Counted()
    model = counted.model()
    cache = JsonlCache(tmp_path / "c.jsonl")
    ask_sync(PROMPT, "P", model=model, cache=cache, key={"k": 1})
    counted.args = {"answer": "b"}
    fresh = ask_sync(PROMPT, "P", model=model, cache=cache, key={"k": 1}, refresh=True)
    assert counted.calls == 2 and fresh.output == Out(answer="b") and not fresh.cached
    assert len(lines(tmp_path / "c.jsonl")) == 2
    hit = ask_sync(PROMPT, "P", model=model, cache=JsonlCache(tmp_path / "c.jsonl"), key={"k": 1})
    assert hit.cached and hit.output == Out(answer="b") and counted.calls == 2


def test_cache_without_key_raises_value_error(tmp_path: Path) -> None:
    counted = Counted()
    with pytest.raises(ValueError):
        ask_sync(PROMPT, "P", model=counted.model(), cache=JsonlCache(tmp_path / "c.jsonl"))
    assert counted.calls == 0


def test_no_cache_has_no_key() -> None:
    answer = ask_sync(PROMPT, "P", model=Counted().model())
    assert answer.key is None and not answer.cached


def test_error_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-secret123")

    def boom() -> None:
        raise RuntimeError("bad sk-secret123")

    with pytest.raises(ModelCallError) as info:
        ask_sync(PROMPT, "P", model=Counted(act=boom).model())
    err = info.value
    assert "secret123" not in err.reason and "secret123" not in str(err)
    assert err.reason.startswith("RuntimeError: ") and len(err.reason) <= 1000
    assert isinstance(err.cause, RuntimeError) and "secret123" in str(err.cause)
    assert err.__cause__ is None and err.__context__ is None and err.__suppress_context__
    assert err.messages  # the request that was sent


def test_timeout_raises_model_call_error() -> None:
    async def slow(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        await asyncio.sleep(1)
        return ModelResponse(parts=[TextPart('{"answer": "late"}')])

    start = time.monotonic()
    with pytest.raises(ModelCallError) as info:
        ask_sync(PROMPT, "P", model=FunctionModel(slow, model_name="slow"), timeout_s=0.05)
    assert isinstance(info.value.cause, TimeoutError)
    assert time.monotonic() - start < 0.9


OUT = {"answer": "a"}
LEGACY = {
    # evaluation.baselines.common.cached_reply: served model inside usage
    "baseline": ({"output": OUT, "usage": {"served_model": "srv", "input_tokens": 3, "output_tokens": 4}},
                 "srv", 3, 4),
    # evidence.propose.common.ask: the output's own fields, nothing else
    "propose": (OUT, None, 0, 0),
    # gold.judge: the output's own fields beside the call's metadata
    "judge": ({**OUT, "alias": "x", "created_at": "t", "input": {}, "model": "x", "prompt_sha256": "p",
               "served_model": "srv", "settings": {}, "task": "support", "user_prompt_sha256": "u",
               "usage": {"input_tokens": 3, "output_tokens": 4}}, "srv", 3, 4),
    # gold.calls.Caller: the new shape plus the time and the prompt hash
    "gold_calls": ({"at": "t", "model": "x", "output": OUT, "prompt_sha256": "p", "served_model": "srv",
                    "usage": {"input_tokens": 3, "output_tokens": 4}}, "srv", 3, 4),
    # synth.render_llm: tokens at the top level
    "synth": ({"output": OUT, "model": "x", "served_model": "srv", "input_tokens": 3, "output_tokens": 4},
              "srv", 3, 4),
}


@pytest.mark.parametrize("name", sorted(LEGACY))
def test_decode_legacy_shapes(tmp_path: Path, name: str) -> None:
    value, served, input_tokens, output_tokens = LEGACY[name]
    cache = JsonlCache(tmp_path / "c.jsonl")
    cache.put(cache_key({"legacy": name}), value)
    counted = Counted()
    answer = ask_sync(PROMPT, "P", model=counted.model(), cache=cache, key={"legacy": name})
    assert counted.calls == 0 and answer.cached
    assert answer.output == Out(answer="a")
    assert (answer.served_model, answer.input_tokens, answer.output_tokens) == (served, input_tokens, output_tokens)


def test_ask_from_another_running_loop() -> None:
    answer = asyncio.run(ask(PROMPT, "P", model=Counted().model()))
    assert answer.output == Out(answer="a")

    async def nested() -> Answer[Out]:
        return ask_sync(PROMPT, "P", model=Counted().model())

    with pytest.raises(RuntimeError, match="wait for itself"):
        run_sync(nested())


def test_cached_too_long_raises_cached_failure(tmp_path: Path) -> None:
    value = {"too_long": True, "reason": "prompt too long: 70000 tokens", "model": "x", "prompt_sha256": "p",
             "at": "2026-10-20T00:00:00Z"}  # gold.calls.Caller's line for a prompt over the context
    cache = JsonlCache(tmp_path / "c.jsonl")
    cache.put(cache_key({"k": 1}), value)
    counted = Counted()
    with pytest.raises(CachedFailure) as info:
        ask_sync(PROMPT, "P", model=counted.model(), cache=cache, key={"k": 1})
    assert counted.calls == 0
    err = info.value
    assert isinstance(err, ModelCallError) and err.reason == "prompt too long: 70000 tokens"
    assert err.value == value and err.cause is None and err.messages == []


def test_flat_legacy_value_missing_fields_is_not_made_up(tmp_path: Path) -> None:
    cache = JsonlCache(tmp_path / "c.jsonl")
    cache.put(cache_key({"k": 1}), {"label": "x"})  # none of Out's fields
    with pytest.raises(ValidationError):
        ask_sync(PROMPT, "P", model=Counted().model(), cache=cache, key={"k": 1})


@pytest.mark.parametrize("name", ["output", "model", "served_model", "usage"])
def test_extra_cannot_overwrite_stored_fields(tmp_path: Path, name: str) -> None:
    counted = Counted()
    with pytest.raises(ValueError, match=name):
        ask_sync(PROMPT, "P", model=counted.model(), cache=JsonlCache(tmp_path / "c.jsonl"), key={"k": 1},
                 extra={name: "x"})
    assert counted.calls == 0
