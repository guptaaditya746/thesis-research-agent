"""A model answered through files: each call is written as a request, and its reply is read from a file.

For models without an API in this setup (a Claude Code subagent writing synthetic papers): the caller
runs unchanged (`call.ask`, its cache key, every check after the reply), and whoever plays the model
answers the requests on disk. Under `root`:

    pending/<id>.json   the request: model, seed, instructions, prompt, the reply's JSON schema
    replies/<id>.json   the reply: one JSON object under that schema, written by the answerer
    done/<id>.json      the request once its reply was accepted

The id is the sha256 of the model name, the seed, the instructions and the conversation so far, so a
rerun asks the same request again and an answered reply is reused. A reply that does not parse or
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
from pathlib import Path
from typing import Any

import jsonschema
from pydantic_ai.messages import ModelMessage, ModelResponse, RetryPromptPart, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.profiles.openai import OpenAIModelProfile

PREFIX = "exchange:"


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _conversation(messages: list[ModelMessage]) -> str:
    """The user prompt, and any retry pydantic-ai sent back, in order."""
    parts = []
    for m in messages:
        for p in getattr(m, "parts", []):
            if isinstance(p, UserPromptPart):
                parts.append(str(p.content))
            elif isinstance(p, RetryPromptPart):
                parts.append(p.model_response())
    return "\n\n".join(parts)


def _schema(info: AgentInfo) -> tuple[dict[str, Any], str | None]:
    """The reply's JSON schema, and the output tool's name when the output comes as a tool call."""
    obj = info.model_request_parameters.output_object
    if obj is not None:
        return obj.json_schema, None
    if info.output_tools:
        return info.output_tools[0].parameters_json_schema, info.output_tools[0].name
    return {"type": "string"}, None


def request_id(model: str, seed: Any, instructions: str, prompt: str) -> str:
    blob = json.dumps([model, seed, instructions, prompt], ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def problem(reply_file: Path, schema: dict[str, Any]) -> str | None:
    """Why this reply is not accepted, or None."""
    try:
        data = json.loads(reply_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"not JSON: {exc}"
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        return f"does not fit the schema: {exc.message} (at {'/'.join(map(str, exc.absolute_path)) or 'top level'})"
    return None


def exchange_model(root: Path | str, name: str, *, poll_s: float = 1.0) -> FunctionModel:
    """A pydantic-ai model named `name` whose calls are answered through files under `root`."""
    root = Path(root)

    async def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        instructions = info.instructions or ""
        prompt = _conversation(messages)
        seed = (info.model_settings or {}).get("seed")
        schema, tool = _schema(info)
        rid = request_id(name, seed, instructions, prompt)
        request = {"id": rid, "model": name, "seed": seed, "instructions": instructions, "prompt": prompt,
                   "output_schema": schema}
        pending, reply, done = root / "pending" / f"{rid}.json", root / "replies" / f"{rid}.json", root / "done" / f"{rid}.json"
        if not reply.exists():
            _write(pending, request)
        rejected: list[str] = []
        while True:
            if reply.exists():
                why = problem(reply, schema)
                if why is None:
                    data = json.loads(reply.read_text(encoding="utf-8"))
                    _write(done, request)
                    pending.unlink(missing_ok=True)
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
            why = problem(reply, json.loads(f.read_text(encoding="utf-8"))["output_schema"])
            if why:
                bad += 1
                print(f"{f.stem}: {why}")
    print(f"{bad} invalid repl{'y' if bad == 1 else 'ies'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
