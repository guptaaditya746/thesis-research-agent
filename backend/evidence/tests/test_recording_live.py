"""The engine's Recorder over real keep-alive HTTP: two LLM extractor calls in one process.

EV1 regression: each call used to run in its own `asyncio.run`, so the second call reused the pooled keep-alive
connection of the first, closed loop and was recorded as "Event loop is closed" after the server had answered.
The provider hands out one model per alias, as a long-lived provider does: with pydantic-ai 2.x each model owns
its HTTP client, so a fresh model per call would hide the bug (and open a connection pool per call)."""
from __future__ import annotations

from functools import cache
from typing import Any

from evidence.extractors import llm_schema
from evidence.extractors.screen import ScreenReply
from evidence.recording import Recorder
from modelcall import openai_model
from modelcall.tests.server import keepalive_server


def reply(prompt: str) -> dict[str, Any]:
    return {"relevant": True, "reason": "it compares RAG with a closed-book model", "quote": "We compare"}


def test_two_llm_extractor_calls_over_keepalive() -> None:
    instructions = llm_schema.read_prompt("screen-v1.md").format(question="Does RAG help?")
    with keepalive_server(reply) as url:
        recorder = Recorder(provider=cache(lambda alias: openai_model(alias, url=url)))
        first, _ = recorder.structured("orch-model", instructions, "paper one", ScreenReply, max_tokens=256)
        second, _ = recorder.structured("orch-model", instructions, "paper two", ScreenReply, max_tokens=256)
    assert url.prompts == ["paper one", "paper two"]
    assert first.relevant and second.relevant
    for record in recorder.records:
        assert "error" not in record, record.get("error")
        assert record["response"]["output"]["quote"] == "We compare"
        assert record["response"]["served_model"] == "m"
        assert record["usage"] == {"input_tokens": 5, "output_tokens": 5}
        assert record["messages"]
