"""`ask`: the one cached, redacted, schema-constrained model call, run on the model loop.

A call is a `Prompt` (instructions and output type), a user prompt, a model and its `CallSettings`. With a cache
it is keyed by `cache_key(key)`: the caller's own key recipe, or `default_key` for new callers. A hit costs no
model call; a miss runs on the model loop and stores `{"output", "model", "served_model", "usage", **extra}`.
Every failure, a timeout included, is a `ModelCallError` whose `reason` is redacted and short, so no key or key
hash reaches a file or a log; the original exception stays on `cause` for classification only."""
from __future__ import annotations

import asyncio
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent, NativeOutput, capture_run_messages
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from jsonio import sha256_hex

from .cache import JsonlCache, cache_key, decode
from .gateway import CallSettings, model_identity, model_name, settings as default_settings
from .loop import on_model_loop, run_sync
from .prompt import Prompt

T = TypeVar("T", bound=BaseModel)

_SECRET_PATTERNS = (re.compile(r"sk-[A-Za-z0-9._\-]{4,}"), re.compile(r"\b[0-9a-fA-F]{64}\b"))


def redact(text: str) -> str:
    """`text` with the API key, its sha256 and anything shaped like a key or a key hash replaced by
    `***`: provider error bodies (LiteLLM's auth errors) can echo a shortened key and its hash, and
    error reasons are written to output files and logs."""
    key = os.environ.get("LITELLM_MASTER_KEY") or ""
    if len(key) >= 4:
        text = text.replace(key, "***").replace(sha256_hex(key.encode("utf-8")), "***")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("***", text)
    return text


@dataclass(frozen=True)
class Reply(Generic[T]):
    """A structured reply with what produced it: the alias asked, the model name the server reported
    (LiteLLM passes vLLM's served name through), and token usage for cost accounting."""
    output: T
    model: str
    served_model: str | None
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class Answer(Generic[T]):
    """What `ask` returns: the reply, whether it came from the cache, and under which key."""
    output: T
    model: str                 # alias asked
    served_model: str | None
    input_tokens: int
    output_tokens: int
    cached: bool
    key: str | None            # None without a cache
    messages: list[Any]        # pydantic-ai ModelMessages of a made call; [] when cached


class ModelCallError(RuntimeError):
    """A model call failed. `reason` is redacted and at most 1000 characters; `cause` (the original exception)
    is never printed by callers, only classified; `messages` are the messages exchanged before the failure."""

    def __init__(self, reason: str, cause: BaseException, messages: list[Any]) -> None:
        super().__init__(reason)
        self.reason = reason
        self.cause = cause
        self.messages = messages


async def _reply(instructions: str, user_prompt: str, output_type: type[T], *, model: Model,
                 model_settings: ModelSettings | None = None, retries: int = 1) -> Reply[T]:
    """One call whose reply must be an `output_type` object, with the served model name and usage.

    Schema-constrained decoding (NativeOutput) where the model supports it, as the LiteLLM models do;
    pydantic-ai's test models get their tool-call output mode instead."""
    native = bool(model.profile.get("supports_json_schema_output"))
    agent: Agent[None, T] = Agent(model, output_type=NativeOutput(output_type) if native else output_type,
                                  instructions=instructions, retries=retries)
    result = await agent.run(user_prompt, model_settings=model_settings or default_settings())
    usage = result.usage() if callable(result.usage) else result.usage
    return Reply(result.output, model_name(model), result.response.model_name,
                 usage.input_tokens or 0, usage.output_tokens or 0)


# Until Task 5 ports their callers onto `ask`: the old public names, as thin wrappers over `_reply`.
async def structured_reply(instructions: str, user_prompt: str, output_type: type[T], *, model: Model,
                           model_settings: ModelSettings | None = None, retries: int = 1) -> Reply[T]:
    return await _reply(instructions, user_prompt, output_type, model=model, model_settings=model_settings,
                        retries=retries)


async def structured(instructions: str, user_prompt: str, output_type: type[T], *, model: Model,
                     model_settings: ModelSettings | None = None, retries: int = 1) -> T:
    return (await _reply(instructions, user_prompt, output_type, model=model, model_settings=model_settings,
                         retries=retries)).output


def default_key(prompt: Prompt, user_prompt: str, model: Model, settings: CallSettings) -> dict[str, Any]:
    """The cache key recipe for new callers: prompt (text and schema), pinned model, input and settings."""
    return {"prompt_sha256": prompt.sha256, "model": model_identity([model]),
            "input_sha256": sha256_hex(user_prompt.encode("utf-8")), "settings": asdict(settings)}


async def _attempt(prompt: Prompt, user_prompt: str, model: Model, settings: CallSettings,
                   timeout_s: float | None) -> tuple[Reply[Any], list[Any]]:
    """One model call on the current (model) loop; every failure becomes a redacted `ModelCallError`."""
    assert prompt.output_type is not None
    with capture_run_messages() as messages:
        try:
            call = _reply(prompt.text, user_prompt, prompt.output_type, model=model,
                          model_settings=settings.model_settings())
            reply = await (asyncio.wait_for(call, timeout_s) if timeout_s is not None else call)
        except Exception as exc:  # noqa: BLE001 - every failure leaves only as a redacted reason
            raise ModelCallError(redact(f"{type(exc).__name__}: {exc}")[:1000], exc, list(messages)) from None
    return reply, list(messages)


async def ask(prompt: Prompt, user_prompt: str, *, model: Model, settings: CallSettings = CallSettings(),
              cache: JsonlCache | None = None, key: dict[str, Any] | None = None, refresh: bool = False,
              extra: dict[str, Any] | None = None, timeout_s: float | None = None) -> Answer[Any]:
    """One structured call of `prompt` on `user_prompt`, cached under `cache_key(key)` when `cache` is given.

    A hit (unless `refresh`) makes no call. A miss runs on the model loop, with `timeout_s` when given, and
    appends `{"output", "model", "served_model", "usage": {"input_tokens", "output_tokens"}, **extra}`."""
    if prompt.output_type is None:
        raise ValueError(f"prompt {prompt.name} has no output type")
    if cache is not None and key is None:
        raise ValueError("a cached call needs a key: the caller's key recipe, or default_key(...)")
    k = cache_key(key) if cache is not None and key is not None else None
    if cache is not None and k is not None and not refresh:
        hit = cache.get(k)
        if hit is not None:
            output, _, served, input_tokens, output_tokens = decode(hit, prompt.output_type)
            return Answer(output, model_name(model), served, input_tokens, output_tokens, True, k, [])
    reply, messages = await on_model_loop(_attempt(prompt, user_prompt, model, settings, timeout_s))
    if cache is not None and k is not None:
        cache.put(k, {"output": reply.output.model_dump(mode="json"), "model": reply.model,
                      "served_model": reply.served_model,
                      "usage": {"input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens},
                      **(extra or {})})
    return Answer(reply.output, reply.model, reply.served_model, reply.input_tokens, reply.output_tokens,
                  False, k, messages)


def ask_sync(prompt: Prompt, user_prompt: str, *, model: Model, settings: CallSettings = CallSettings(),
             cache: JsonlCache | None = None, key: dict[str, Any] | None = None, refresh: bool = False,
             extra: dict[str, Any] | None = None, timeout_s: float | None = None) -> Answer[Any]:
    """`ask` from sync code (any thread, or inside a loop other than the model loop)."""
    return run_sync(ask(prompt, user_prompt, model=model, settings=settings, cache=cache, key=key,
                        refresh=refresh, extra=extra, timeout_s=timeout_s))
