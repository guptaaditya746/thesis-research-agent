"""Recorded model calls: the only way an extractor reaches a model (contract section 12, `ctx.llm()`).

Every call goes through gold/llm.structured_reply (schema-constrained output, thinking off, fixed
temperature and seed) and leaves a record: the request (model alias, prompt hash, instructions, user
prompt, settings), the response (the decoded output, the served model name), token usage, or the
redacted error. The engine stores the records with the extractor's result in the cache, so a replay
needs no model. The model itself is injected (`provider`: alias -> pydantic-ai Model), so tests use
FunctionModels and real runs gold/llm.openai_model, which reads the key from $LITELLM_MASTER_KEY only.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic_ai import capture_run_messages
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.models import Model

from gold import llm

from .contract import digest

T = TypeVar("T", bound=BaseModel)
Provider = Callable[[str], Model]


class ModelCallError(Exception):
    """A model call failed; `reason` is short and redacted."""

    def __init__(self, reason: str, call_id: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.call_id = call_id         # the record of the failed call (empty when none was made)


class NoModel(ModelCallError):
    pass


class Recorder:
    """Makes and records the model calls of one extractor call."""

    def __init__(self, provider: Provider | None) -> None:
        self.provider = provider
        self.records: list[dict[str, Any]] = []

    def structured(self, alias: str, instructions: str, user_prompt: str, output_type: type[T], *,
                   temperature: float = 0.0, seed: int = 0, max_tokens: int = 4096) -> tuple[T, str]:
        """One schema-constrained call; returns the output and the id of its record."""
        request = {"model": alias, "prompt_sha256": llm.prompt_sha256(instructions, output_type),
                   "instructions": instructions, "user_prompt": user_prompt,
                   "settings": {"temperature": temperature, "seed": seed, "max_tokens": max_tokens}}
        call_id = f"mc-{digest([request, len(self.records)])[:16]}"
        record: dict[str, Any] = {"id": call_id, "request": request}
        self.records.append(record)
        if self.provider is None:
            record["error"] = "no model provider: this run cannot make model calls"
            raise NoModel(record["error"], call_id)
        settings = llm.settings(temperature=temperature, seed=seed, max_tokens=max_tokens)
        with capture_run_messages() as messages:
            try:
                reply = _run(llm.structured_reply(instructions, user_prompt, output_type,
                                                  model=self.provider(alias), model_settings=settings))
            except Exception as exc:  # noqa: BLE001 - every failure becomes a recorded, redacted reason
                record["error"] = llm.redact(f"{type(exc).__name__}: {exc}")[:300]
                record["messages"] = _messages(messages)
                raise ModelCallError(record["error"], call_id) from exc
        record["response"] = {"output": reply.output.model_dump(mode="json"), "model": reply.model,
                              "served_model": reply.served_model}
        record["usage"] = {"input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens}
        record["messages"] = _messages(messages)
        return reply.output, call_id


def _run(coro: Any) -> Any:
    """Run a coroutine to completion from sync code, also when the caller is inside an event loop (then on a
    worker thread with its own loop), so the engine can be driven from async code too."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _messages(messages: list[Any]) -> Any:
    """The exchanged messages as JSON (for the record only; they carry timestamps, so never hashed)."""
    try:
        return ModelMessagesTypeAdapter.dump_python(list(messages), mode="json")
    except Exception:  # noqa: BLE001 - a record without messages is still a record
        return None


def usage(records: list[dict[str, Any]]) -> tuple[int, int]:
    return (sum((r.get("usage") or {}).get("input_tokens", 0) for r in records),
            sum((r.get("usage") or {}).get("output_tokens", 0) for r in records))
