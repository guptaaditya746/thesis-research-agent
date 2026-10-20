"""Recorded model calls: the only way an extractor reaches a model (contract section 12, `ctx.llm()`).

Every call goes through modelcall.ask (schema-constrained output, thinking off, fixed temperature and
seed, run on the one model loop, so a pooled keep-alive connection is never reused from a closed loop) and
leaves a record: the request (model alias, prompt hash, instructions, user
prompt, settings), the response (the decoded output, the served model name), token usage, or the
redacted error. The engine stores the records with the extractor's result in the cache, so a replay
needs no model. The model itself is injected (`provider`: alias -> pydantic-ai Model), so tests use
FunctionModels and real runs modelcall.openai_model, which reads the key from $LITELLM_MASTER_KEY only.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.models import Model

import modelcall

from .contract import digest

T = TypeVar("T", bound=BaseModel)
Provider = Callable[[str], Model]


class ModelCallError(Exception):
    """A model call of an extractor failed; `reason` is short and redacted. The engine's own error, carrying the
    record id: not `modelcall.ModelCallError` (the failure of `modelcall.ask`), which `Recorder` turns into this."""

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
        request = {"model": alias, "prompt_sha256": modelcall.prompt_sha256(instructions, output_type),
                   "instructions": instructions, "user_prompt": user_prompt,
                   "settings": {"temperature": temperature, "seed": seed, "max_tokens": max_tokens}}
        call_id = f"mc-{digest([request, len(self.records)])[:16]}"
        record: dict[str, Any] = {"id": call_id, "request": request}
        self.records.append(record)
        if self.provider is None:
            record["error"] = "no model provider: this run cannot make model calls"
            raise NoModel(record["error"], call_id)
        prompt = modelcall.Prompt.inline(instructions, output_type)
        settings = modelcall.CallSettings(temperature=temperature, seed=seed, max_tokens=max_tokens)
        try:
            answer = modelcall.ask_sync(prompt, user_prompt, model=self.provider(alias), settings=settings)
        except modelcall.ModelCallError as exc:
            record["error"] = exc.reason[:300]
            record["messages"] = _messages(exc.messages)
            raise ModelCallError(record["error"], call_id) from None
        except Exception as exc:  # noqa: BLE001 - the provider failed before a call was made
            record["error"] = modelcall.redact(f"{type(exc).__name__}: {exc}")[:300]
            record["messages"] = _messages([])
            raise ModelCallError(record["error"], call_id) from None
        record["response"] = {"output": answer.output.model_dump(mode="json"), "model": answer.model,
                              "served_model": answer.served_model}
        record["usage"] = {"input_tokens": answer.input_tokens, "output_tokens": answer.output_tokens}
        record["messages"] = _messages(answer.messages)
        return answer.output, call_id


def _messages(messages: list[Any]) -> Any:
    """The exchanged messages as JSON (for the record only; they carry timestamps, so never hashed)."""
    try:
        return ModelMessagesTypeAdapter.dump_python(list(messages), mode="json")
    except Exception:  # noqa: BLE001 - a record without messages is still a record
        return None


def usage(records: list[dict[str, Any]]) -> tuple[int, int]:
    return (sum((r.get("usage") or {}).get("input_tokens", 0) for r in records),
            sum((r.get("usage") or {}).get("output_tokens", 0) for r in records))
