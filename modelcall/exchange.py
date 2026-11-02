"""A model answered through files: each call is written as a request, and its reply is read from a file.

For models without an API in this setup (a Claude Code subagent writing synthetic papers): the caller
runs unchanged (`call.ask`, its cache key, every check after the reply), and whoever plays the model
answers the requests on disk. Under `root`:

    pending/<id>.json   the request: model, seed, instructions, prompt, the reply's JSON schema
    replies/<id>.json   the reply: one JSON object under that schema, written by the answerer
    done/<id>.json      the request once its reply was accepted

A call that offers tools (an agent with a toolset, such as the pack builder over the corpus tool server) also lists
them in the request under `tools` ({name, description, parameters}). Its reply is then either the output, as above,
or `{"tool_calls": [{"tool": <name>, "args": {...}}]}` (its schema is under `tool_calls_schema`): the tools run,
and the next request's prompt holds the calls and their results (`[tool call <id>] name {args}`,
`[tool result <id>] name: <result>`, `[tool error <id>] name: <message>`), so every turn is a request of its own.

The id is the sha256 of the model name, the seed, the instructions and the conversation so far, so a
rerun asks the same request again and an answered reply is reused. A reply is read only after it has
not changed for a moment (`settle_s`), so a file still being written is never taken half done. A reply that does not parse or
does not fit the schema is moved to `replies/<id>.rejected-<n>.json` and the request is rewritten
with the reason under `rejected`; the call waits for a new reply. The call waits as long as it takes
(the caller's timeout applies); stopping the process leaves the pending requests for the next run.

`python -m modelcall.exchange status ROOT` counts the requests; `check ROOT` validates the replies
present without consuming them.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import jsonschema
from pydantic_ai.messages import (ModelMessage, ModelResponse, RetryPromptPart, TextPart, ToolCallPart,
                                  ToolReturnPart, UserPromptPart)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.profiles.openai import OpenAIModelProfile

PREFIX = "exchange:"


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _conversation(messages: list[ModelMessage], tools: frozenset[str] = frozenset(),
                  outputs: frozenset[str] = frozenset()) -> str:
    """The user prompt, and any retry pydantic-ai sent back, in order; with the calls the model made of the function
    tools `tools`, and their results or errors. With tools, an output given through an output tool of `outputs` is
    shown too (`[output <id>] name {args}`), so a retry shows the rejected output it is about. A call without tools
    renders as before."""
    parts = []
    for m in messages:
        for p in getattr(m, "parts", []):
            if isinstance(p, UserPromptPart):
                parts.append(str(p.content))
            elif isinstance(p, ToolCallPart) and p.tool_name in tools:
                parts.append(f"[tool call {p.tool_call_id}] {p.tool_name} {_json(p.args_as_dict())}")
            elif isinstance(p, ToolCallPart) and tools and p.tool_name in outputs:
                parts.append(f"[output {p.tool_call_id}] {p.tool_name} {_json(p.args_as_dict())}")
            elif isinstance(p, ToolReturnPart) and p.tool_name in tools:
                parts.append(f"[tool result {p.tool_call_id}] {p.tool_name}: {_json(p.content)}")
            elif isinstance(p, RetryPromptPart) and p.tool_name in tools:
                parts.append(f"[tool error {p.tool_call_id}] {p.tool_name}: {p.model_response()}")
            elif isinstance(p, RetryPromptPart):
                parts.append(p.model_response())
    return "\n\n".join(parts)


def _tools(info: AgentInfo) -> list[dict[str, Any]]:
    """The function tools offered on this call (not the output tool), as {name, description, parameters}."""
    return [{"name": t.name, "description": t.description or "", "parameters": t.parameters_json_schema}
            for t in info.function_tools]


def tool_calls_schema(tools: list[dict[str, Any]]) -> dict[str, Any]:
    """The schema of a reply that calls tools: {"tool_calls": [{"tool": one of `tools`, "args": {...}}, ...]}."""
    return {"type": "object", "additionalProperties": False, "required": ["tool_calls"],
            "properties": {"tool_calls": {"type": "array", "minItems": 1, "items": {
                "type": "object", "additionalProperties": False, "required": ["tool", "args"],
                "properties": {"tool": {"enum": [t["name"] for t in tools]}, "args": {"type": "object"}}}}}}


def _schema(info: AgentInfo) -> tuple[dict[str, Any], str | None]:
    """The reply's JSON schema, and the output tool's name when the output comes as a tool call."""
    obj = info.model_request_parameters.output_object
    if obj is not None:
        return obj.json_schema, None
    if info.output_tools:
        return info.output_tools[0].parameters_json_schema, info.output_tools[0].name
    return {"type": "string"}, None


def request_id(model: str, seed: Any, instructions: str, prompt: str,
               tools: list[dict[str, Any]] | None = None) -> str:
    """The request's id; the tools offered count only when there are some, so a call without tools keeps its id."""
    fields: list[Any] = [model, seed, instructions, prompt, *([tools] if tools else [])]
    blob = json.dumps(fields, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _invalid(data: Any, schema: dict[str, Any]) -> str | None:
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        return f"does not fit the schema: {exc.message} (at {'/'.join(map(str, exc.absolute_path)) or 'top level'})"
    return None


def is_tool_call(data: Any) -> bool:
    """A reply that calls tools: an object whose only key is `tool_calls`."""
    return isinstance(data, dict) and set(data) == {"tool_calls"}


def problem(reply_file: Path, schema: dict[str, Any], tools: list[dict[str, Any]] | None = None) -> str | None:
    """Why this reply is not accepted, or None. With `tools`, a reply may call them instead (`is_tool_call`): each
    call must name an offered tool, and its args must fit that tool's parameters."""
    try:
        data = json.loads(reply_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"not JSON: {exc}"
    if tools and is_tool_call(data):
        if why := _invalid(data, tool_calls_schema(tools)):
            return why
        params = {t["name"]: t["parameters"] for t in tools}
        for n, call in enumerate(data["tool_calls"]):
            if why := _invalid(call["args"], params[call["tool"]]):
                return f"tool call {n} ({call['tool']}): its args {why}"
        return None
    return _invalid(data, schema)


def exchange_model(root: Path | str, name: str, *, poll_s: float = 1.0, settle_s: float = 2.0,
                   timeout_s: float | None = None) -> FunctionModel:
    """A pydantic-ai model named `name` whose calls are answered through files under `root`. A reply is read
    once it has not changed for `settle_s` seconds, so a file still being written is not taken half done. A call
    waits as long as it takes, or `timeout_s` seconds (then TimeoutError; tests set it so they fail, not hang)."""
    root = Path(root)

    async def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        instructions = info.instructions or ""
        tools = _tools(info)
        prompt = _conversation(messages, frozenset(t["name"] for t in tools),
                               frozenset(t.name for t in info.output_tools))
        seed = (info.model_settings or {}).get("seed")
        schema, tool = _schema(info)
        rid = request_id(name, seed, instructions, prompt, tools)
        request = {"id": rid, "model": name, "seed": seed, "instructions": instructions, "prompt": prompt,
                   "output_schema": schema}
        if tools:
            request |= {"tools": tools, "tool_calls_schema": tool_calls_schema(tools)}
        pending, reply, done = root / "pending" / f"{rid}.json", root / "replies" / f"{rid}.json", root / "done" / f"{rid}.json"
        if not reply.exists():
            _write(pending, request)
        rejected: list[str] = []
        deadline = None if timeout_s is None else time.monotonic() + timeout_s
        while True:
            if deadline is not None and time.monotonic() > deadline:
                raise TimeoutError(f"exchange {name}: no accepted reply to request {rid} in {timeout_s} s")
            if reply.exists() and time.time() - reply.stat().st_mtime >= settle_s:
                why = problem(reply, schema, tools)
                if why is None:
                    data = json.loads(reply.read_text(encoding="utf-8"))
                    _write(done, request)
                    pending.unlink(missing_ok=True)
                    if tools and is_tool_call(data):
                        return ModelResponse(parts=[ToolCallPart(c["tool"], c["args"], tool_call_id=f"{rid[:8]}-{n}")
                                                    for n, c in enumerate(data["tool_calls"], 1)], model_name=name)
                    if tool is not None:
                        return ModelResponse(parts=[ToolCallPart(tool, data)], model_name=name)
                    return ModelResponse(parts=[TextPart(json.dumps(data, ensure_ascii=False))], model_name=name)
                rejected.append(why)
                os.replace(reply, reply.with_name(f"{rid}.rejected-{len(rejected)}.json"))
                _write(pending, {**request, "rejected": rejected})
            await asyncio.sleep(poll_s)

    profile = OpenAIModelProfile(supports_json_schema_output=True, supports_json_object_output=True)
    return FunctionModel(answer, model_name=name, profile=profile)


def model_for(alias: str, exchange: Path | str):
    """`exchange:<name>` → an exchange model under `exchange/<name>`; anything else → the LiteLLM alias."""
    if alias.startswith(PREFIX):
        name = alias[len(PREFIX):]
        if not name or any(c in name for c in "/\\:"):
            raise ValueError(f"exchange model name must be a plain name: {alias!r}")
        return exchange_model(Path(exchange) / name, alias)
    import modelcall
    return modelcall.openai_model(alias)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m modelcall.exchange", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd in ("status", "check"):
        p = sub.add_parser(cmd)
        p.add_argument("root", type=Path)
    args = parser.parse_args(argv)
    pending = sorted((args.root / "pending").glob("*.json"))
    if args.command == "status":
        replies = [f for f in (args.root / "replies").glob("*.json") if ".rejected-" not in f.name]
        done = list((args.root / "done").glob("*.json"))
        print(json.dumps({"pending": len(pending), "answered_waiting": sum((args.root / "replies" / f.name).exists()
                                                                           for f in pending),
                          "replies": len(replies), "done": len(done)}))
        return 0
    bad = 0
    for f in pending:
        reply = args.root / "replies" / f.name
        if reply.exists():
            req = json.loads(f.read_text(encoding="utf-8"))
            why = problem(reply, req["output_schema"], req.get("tools"))
            if why:
                bad += 1
                print(f"{f.stem}: {why}")
    print(f"{bad} invalid repl{'y' if bad == 1 else 'ies'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
