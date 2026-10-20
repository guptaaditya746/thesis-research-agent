"""Characterization: the cache key and stored value shape of every model-call site, pinned.

Each test drives the real caller once with a FunctionModel and a fresh cache, reads the single line it
wrote, and compares its `key` to a hex literal and the sorted top-level keys of its `value`. A refactor
of the call sites must keep these green: a changed key silently invalidates every cache on the cluster."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from evaluation.baselines.common import cached_reply
from evidence import calls as engine_calls
from evidence.propose.common import CACHE, ask
from gold import judge
from gold.calls import Caller, PromptFile
from gold.llm import JsonlCache, Rotation, run_sync
from synth.render_llm import LlmRenderer, PaperReply


class Out(BaseModel):
    answer: str


def fm(args: dict[str, Any]) -> FunctionModel:
    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if info.output_tools:
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])
        return ModelResponse(parts=[TextPart(json.dumps(args))])
    return FunctionModel(reply, model_name="golden-model")


def only_line(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])


def shape(line: dict[str, Any]) -> list[str]:
    return sorted(line["value"])


def test_baseline_key(tmp_path: Path) -> None:
    model = fm({"label": "supported", "studies": [], "answer_text": "a"})
    cached_reply(JsonlCache(tmp_path / "c.jsonl"), "I", "P", model=model, model_id="orch")
    line = only_line(tmp_path / "c.jsonl")
    assert line["key"] == "5818658ab3e5de5731890e0923e5dd7da1bfe4c0c9720dca0199ba22572a5c69"
    assert shape(line) == ["output", "usage"]


def test_propose_key(tmp_path: Path) -> None:
    ask(tmp_path, "frame", "I", "P", Out, model=fm({"answer": "a"}))
    line = only_line(tmp_path / CACHE)
    assert line["key"] == "51525078a1730eefee773e483a9b3e2d68240fab8b836892df268704a178edd4"
    assert shape(line) == ["answer"]


def test_judge_key(tmp_path: Path) -> None:
    model = fm({"rationale": "r", "label": "supports"})
    judge.Judge(tmp_path, [model]).support(judge.PROBE_FACT, "q")
    line = only_line(tmp_path / judge.CACHE_FILE)
    assert line["key"] == "b1878b9519950bfd8a002213342fa06569cdce36e3c4ede333d852277af9c845"
    assert shape(line) == ["alias", "created_at", "input", "label", "model", "prompt_sha256", "rationale",
                           "served_model", "settings", "task", "usage", "user_prompt_sha256"]


def test_gold_calls_key(tmp_path: Path) -> None:
    prompt = PromptFile("p.txt", "P", "0" * 64, "1" * 64)
    caller = Caller(Rotation([fm({"answer": "a"})]), JsonlCache(tmp_path / "c.jsonl"))
    run_sync(caller.call("s", prompt, Out, "P", max_tokens=100))
    line = only_line(tmp_path / "c.jsonl")
    assert line["key"] == "b48e4e37154f70d504a6d542468609c95eb07d55acb2ba6d21726a58eb7d3346"
    assert shape(line) == ["at", "model", "output", "prompt_sha256", "served_model", "usage"]


def test_synth_render_key(tmp_path: Path) -> None:
    model = fm({"markdown": "# T\n"})
    renderer = LlmRenderer(model, tmp_path / "c.jsonl")
    run_sync(renderer._call("I", "P", PaperReply, model, 1))
    line = only_line(tmp_path / "c.jsonl")
    assert line["key"] == "fb1bd1e765ccbbd97d91a9933f42335087b77c6352e5e3ad660cc3a60180565c"
    assert shape(line) == ["input_tokens", "model", "output", "output_tokens", "served_model"]


def test_engine_callcache_key() -> None:
    assert engine_calls.cache_key("x@1", "t" * 64, 0) == "ac2cb2f4b39247794a4bfe22ba4e9d56d32931229d36bde55aac8668d416e5d2"
