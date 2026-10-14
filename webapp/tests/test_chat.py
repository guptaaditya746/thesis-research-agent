"""The chat endpoint: an AI SDK v5 UI-message stream from the pydantic-ai agent (scripted model)."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

from webapp.app import create_app

from .world import World

TOOLS = {"list_runs", "get_run", "get_answer", "get_claims", "walk_fact", "sparql", "read_passage", "get_results"}


def body(text: str, **extra: Any) -> dict[str, Any]:
    return {"trigger": "submit-message", "id": "chat-1",
            "messages": [{"id": "m1", "role": "user", "parts": [{"type": "text", "text": text}]}], **extra}


def frames(response: Any) -> list[Any]:
    out = []
    for line in response.text.splitlines():
        if line.startswith("data: "):
            payload = line[len("data: "):]
            out.append(payload if payload == "[DONE]" else json.loads(payload))
    return out


class Script:
    """A streamed model: first the given tool calls (one per turn), then a text reply."""

    def __init__(self, *calls: tuple[str, dict[str, Any]], text: tuple[str, ...] = ("There are ", "2 runs.")) -> None:
        self.calls = list(calls)
        self.text = text
        self.seen: list[tuple[list[ModelMessage], AgentInfo]] = []

    async def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        self.seen.append((messages, info))
        returned = sum(isinstance(p, ToolReturnPart) for m in messages if isinstance(m, ModelRequest) for p in m.parts)
        if returned < len(self.calls):
            name, args = self.calls[returned]
            yield {0: DeltaToolCall(name=name, json_args=json.dumps(args), tool_call_id=f"call-{returned + 1}")}
            return
        for chunk in self.text:
            yield chunk

    def outputs(self) -> list[Any]:
        """What the tools returned to the model, in order."""
        messages = self.seen[-1][0]
        return [p.content for m in messages if isinstance(m, ModelRequest) for p in m.parts if isinstance(p, ToolReturnPart)]


def test_chat_streams_a_tool_call_and_text(world: World) -> None:
    script = Script(("list_runs", {"qid": "q01"}))
    with TestClient(create_app(world.settings, chat_model=FunctionModel(stream_function=script))) as c:
        response = c.post("/api/chat", params={"run_id": "research-r1"}, json=body("How many runs has q01?"))
    assert response.status_code == 200
    assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
    assert response.headers["content-type"].startswith("text/event-stream")
    got = frames(response)
    kinds = [f["type"] if isinstance(f, dict) else f for f in got]
    assert kinds[0] == "start" and kinds[-2:] == ["finish", "[DONE]"]
    assert kinds.index("tool-input-start") < kinds.index("tool-input-available") < kinds.index("tool-output-available") \
        < kinds.index("text-start") < kinds.index("text-end")
    call = next(f for f in got if isinstance(f, dict) and f["type"] == "tool-input-available")
    assert (call["toolName"], call["input"], call["toolCallId"]) == ("list_runs", {"qid": "q01"}, "call-1")
    output = next(f for f in got if isinstance(f, dict) and f["type"] == "tool-output-available")["output"]
    assert sorted(r["run_id"] for r in output) == ["baseline-r1", "research-r1"]
    text = "".join(f["delta"] for f in got if isinstance(f, dict) and f["type"] == "text-delta")
    assert text == "There are 2 runs."
    messages, info = script.seen[0]
    assert {t.name for t in info.function_tools} == TOOLS  # read-only tools, nothing else
    assert "research-r1" in (messages[-1].instructions or "")  # scoped to the run the user is on


def test_chat_tools_read_and_refuse_writes(world: World) -> None:
    script = Script(("walk_fact", {"run_id": "research-r1", "fact_id": "f1"}),
                    ("sparql", {"query": "DELETE WHERE { ?s ?p ?o }"}),
                    ("sparql", {"query": "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }", "run_id": "research-r1"}),
                    ("read_passage", {"paper_id": "p1", "start": 0, "end": 10, "context": 5}),
                    ("get_claims", {"run_id": "research-r1", "status": "rejected"}),
                    ("get_answer", {"run_id": "nope"}),
                    ("get_results", {}),
                    text=("Done.",))
    with TestClient(create_app(world.settings, chat_model=FunctionModel(stream_function=script))) as c:
        response = c.post("/api/chat", json=body("Check fact f1", runId="baseline-r1"))
    assert response.status_code == 200
    walk, refused, count, passage, rejected, missing, results = script.outputs()
    assert walk["claims"][0]["claim_id"] == "claim-000001" and walk["claims"][0]["passage"]["highlight"]
    assert "error" in refused and "only SELECT" in refused["error"]
    assert int(count["rows"][0]["n"]) > 0
    assert passage["highlight"] == {"start": 0, "end": 10} and passage["paper_id"] == "p1"
    assert [c["reason"] for c in rejected] == ["not_found"]
    assert "error" in missing
    assert results == {"primary": {"p_value": 0.03}}
    assert "baseline-r1" in (script.seen[0][0][-1].instructions or "")  # run id from the request body


def test_tool_results_fit_a_32k_model() -> None:
    """A list longer than the budget is cut and says how many it left out (claims of a long claim_on run
    would otherwise overflow sub-model-1's 32k context on the next request)."""
    from webapp.chat import BUDGET, _fit
    claims = [{"claim_id": f"claim-{n:06d}", "quote": "q" * 600, "s": "s", "p": "p", "o": "o"} for n in range(100)]
    fitted = _fit(claims)
    assert len(json.dumps(fitted)) <= BUDGET + 200 and fitted[-1]["more"] == 100 - (len(fitted) - 1)
    assert fitted[:-1] == claims[:len(fitted) - 1]
    assert _fit(claims[:3]) == claims[:3]  # small lists are whole, with no marker


def test_get_claims_leaves_out_what_the_chat_does_not_need(world: World) -> None:
    script = Script(("get_claims", {"run_id": "research-r1"}), text=("Done.",))
    with TestClient(create_app(world.settings, chat_model=FunctionModel(stream_function=script))) as c:
        assert c.post("/api/chat", json=body("Which claims?")).status_code == 200
    [claims] = script.outputs()
    assert claims and all("quote_submitted" not in c and "task_id" not in c for c in claims)


def test_chat_rejects_a_malformed_request(world: World) -> None:
    script = Script()
    with TestClient(create_app(world.settings, chat_model=FunctionModel(stream_function=script))) as c:
        assert c.post("/api/chat", json={"messages": "no"}).status_code == 422
        assert c.post("/api/chat", content=b"{}", headers={"content-type": "text/plain"}).status_code == 403  # guard
        assert c.post("/api/chat", content=b"{}", headers={"content-type": "text/plain",
                                                            "x-requested-with": "test"}).status_code == 415
    assert script.seen == []
