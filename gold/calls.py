"""Model calls of the gold builder and triage (M3): prompt files, result cache, concurrency, timeout.

Every call goes through modelcall (pydantic-ai on LiteLLM, schema-constrained output, thinking off,
temperature and seed fixed) and the sub-model replicas in turn (`modelcall.Rotation`). Around it:

- Prompts are files in gold/prompts/. Each output line records `prompt_sha256` = modelcall.prompt_sha256 of
  the template and its output schema (the extraction schema depends on the concept, so its hash
  does too); the template's own file hash is recorded in doc.json.built.prompts. Templates are read
  with LF line ends whatever the checkout, so a hash is the same on Windows and on the cluster.
- A call is keyed by the sha256 of its whole input: stage, prompt hash, the user prompt, the model
  identity and the sampling settings (modelcall.cache_key). The key leaves out which replica answered:
  sub-model-1 and -2 serve the same pinned model (modelcall.model_identity), so a rerun that happens to
  rotate differently, or runs on one replica, still hits the cache. A rerun with the same inputs
  makes no model call; a stopped build resumes where it stopped (cache.jsonl).
- Failures come in two kinds (`CallError.kind`). `failed` (a timeout, a server error, a reply the
  caller's `accept` check refuses) may pass on the next try, so it is never cached and the next run
  retries exactly those calls. `too_long` (the reply hit max_tokens, or the prompt and max_tokens do
  not fit the context: HTTP 400 context window exceeded) fails the same way every time at
  temperature 0, so the verdict is cached and the caller cuts its input instead (gold/build.py).
- At most `concurrency` calls are in flight (GOLD_CONCURRENCY, default 6: the 3 sequences per replica
  that ran without preemption in L3), and each has its own timeout; waiting for a slot does not count.
- Error reasons are short and pass modelcall.redact, so no key or key hash reaches a file or a log.

This module is model-agnostic apart from the gold prompts directory: C2's judge can use `Caller` too.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from pydantic_ai import capture_run_messages
from pydantic_ai.exceptions import IncompleteToolCall, ModelHTTPError
from pydantic_ai.messages import ModelResponse

from jsonio import sha256_hex
from agent.rundir import utc_now

import modelcall

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
T = TypeVar("T", bound=BaseModel)
# Words of a context-window 400 from LiteLLM (ContextWindowExceededError, STATE.md L8) or vLLM
# ("maximum context length is 32768 tokens"), compared without spaces and underscores.
CONTEXT_MARKERS = ("contextwindowexceeded", "contextlengthexceeded", "maximumcontextlength", "contextlength")


@dataclass(frozen=True)
class PromptFile:
    """One prompt template and the output type it is used with."""
    name: str           # file name in gold/prompts/
    text: str           # LF line ends
    file_sha256: str    # sha256 of `text` (UTF-8)
    sha256: str         # modelcall.prompt_sha256(text, output_type): what every output line records

    def json(self) -> dict[str, str]:
        return {"file": f"gold/prompts/{self.name}", "file_sha256": self.file_sha256, "prompt_sha256": self.sha256}


def load_prompt(name: str, output_type: type[BaseModel]) -> PromptFile:
    prompt = modelcall.load_prompt(PROMPT_DIR / name, output_type)
    return PromptFile(name, prompt.text, prompt.file_sha256, prompt.sha256)


def model_key(models: list[Any]) -> str:
    """The model identity in cache keys (modelcall.model_identity)."""
    return modelcall.model_identity(models)


class CallError(Exception):
    """A model call failed; `reason` is short and redacted. `kind` is `failed` (try again later) or
    `too_long` (the same input fails every time: cut it); `cached` when the verdict came from the cache."""

    def __init__(self, stage: str, reason: str, kind: str = "failed", cached: bool = False) -> None:
        super().__init__(f"{stage}: {reason}")
        self.stage = stage
        self.reason = reason
        self.kind = kind
        self.cached = cached


def classify(exc: BaseException, messages: list[Any]) -> tuple[str, str]:
    """(kind, reason) of a failed call, from the exception and the messages the run exchanged."""
    if isinstance(exc, TimeoutError):
        return "failed", "timeout"
    cut = any(isinstance(m, ModelResponse) and m.finish_reason == "length" for m in messages)
    if cut or isinstance(exc, IncompleteToolCall):
        return "too_long", "too_long: the reply reached max_tokens"
    text = f"{type(exc).__name__}: {exc}"
    squashed = text.casefold().replace(" ", "").replace("_", "")
    if isinstance(exc, ModelHTTPError) and exc.status_code == 400 and any(m in squashed for m in CONTEXT_MARKERS):
        return "too_long", "too_long: the prompt and max_tokens exceed the context window (HTTP 400)"
    return "failed", modelcall.redact(text)[:300]


class _Failed(Exception):
    """A failed structured call with the messages its run exchanged (for `classify`)."""

    def __init__(self, exc: Exception, messages: list[Any]) -> None:
        super().__init__(str(exc))
        self.exc, self.messages = exc, messages


@dataclass
class Counters:
    """Calls of one process. `made` and `cached` are results; `total` is every result D rests on with
    what it cost when it was made. `failed` (retried next time) and `too_long` (made now or a cached
    verdict; the input is cut instead) are not results."""
    made: int = 0
    cached: int = 0
    failed: int = 0
    too_long: int = 0
    in_flight: int = 0
    input_tokens: int = 0          # calls made by this process (refused replies too)
    output_tokens: int = 0
    cached_input_tokens: int = 0   # what the cached results cost when they were made
    cached_output_tokens: int = 0

    def json(self) -> dict[str, Any]:
        out: dict[str, Any] = asdict(self)
        out["total"] = {"calls": self.made + self.cached, "input_tokens": self.input_tokens + self.cached_input_tokens,
                        "output_tokens": self.output_tokens + self.cached_output_tokens}
        return out


@dataclass(frozen=True)
class Result(Generic[T]):
    output: T
    meta: dict[str, Any]  # model (alias), served_model, prompt_sha256, usage, cached


@dataclass
class Caller:
    """Cached, bounded, timed structured calls over a model rotation (see the module docstring)."""
    rotation: modelcall.Rotation
    cache: modelcall.JsonlCache
    concurrency: int = 6
    timeout_s: float = 300.0
    temperature: float = 0.0
    seed: int = 0
    on_change: Callable[[], None] | None = None
    counters: Counters = field(default_factory=Counters)
    served: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._slots = asyncio.Semaphore(max(1, self.concurrency))
        self.model_key = model_key(self.rotation.models)

    def key(self, stage: str, prompt: PromptFile, user_prompt: str, max_tokens: int) -> str:
        return modelcall.cache_key({
            "stage": stage, "prompt_sha256": prompt.sha256, "user_sha256": sha256_hex(user_prompt.encode("utf-8")),
            "model": self.model_key, "temperature": self.temperature, "seed": self.seed, "max_tokens": max_tokens,
        })

    def settings(self) -> dict[str, Any]:
        return {"model_key": self.model_key, "concurrency": self.concurrency, "timeout_s": self.timeout_s,
                "temperature": self.temperature, "seed": self.seed}

    def _changed(self) -> None:
        if self.on_change is not None:
            self.on_change()

    async def _ask(self, prompt: PromptFile, output_type: type[T], user_prompt: str, model: Any,
                   max_tokens: int) -> modelcall.Reply[T]:
        with capture_run_messages() as messages:
            try:
                return await modelcall.structured_reply(
                    prompt.text, user_prompt, output_type, model=model,
                    model_settings=modelcall.settings(temperature=self.temperature, seed=self.seed, max_tokens=max_tokens))
            except Exception as exc:
                raise _Failed(exc, list(messages)) from exc

    async def call(self, stage: str, prompt: PromptFile, output_type: type[T], user_prompt: str, *,
                   max_tokens: int, accept: Callable[[T], str | None] | None = None) -> Result[T]:
        """One structured call. `accept(output)` may return a reason to refuse a reply: it then counts
        as a failed call and is not cached (a rerun asks again)."""
        key = self.key(stage, prompt, user_prompt, max_tokens)
        hit = self.cache.get(key)
        if hit is not None and hit.get("too_long"):
            self.counters.too_long += 1
            self._changed()
            raise CallError(stage, hit["reason"], kind="too_long", cached=True)
        if hit is not None:
            self.counters.cached += 1
            usage = hit.get("usage") or {}
            self.counters.cached_input_tokens += usage.get("input_tokens", 0)
            self.counters.cached_output_tokens += usage.get("output_tokens", 0)
            if hit.get("served_model"):
                self.served.add(hit["served_model"])
            self._changed()
            meta = {k: v for k, v in hit.items() if k != "output"}
            return Result(output_type.model_validate(hit["output"]), {**meta, "cached": True})
        async with self._slots:
            model = self.rotation.next()
            self.counters.in_flight += 1
            self._changed()
            try:
                reply = await asyncio.wait_for(self._ask(prompt, output_type, user_prompt, model, max_tokens),
                                               timeout=self.timeout_s)
            except Exception as exc:  # noqa: BLE001 - any failure is recorded, and retried or cut
                kind, reason = classify(exc.exc, exc.messages) if isinstance(exc, _Failed) else classify(exc, [])
                if kind == "too_long":
                    self.counters.too_long += 1
                    self.cache.put(key, {"too_long": True, "reason": reason, "model": modelcall.model_name(model),
                                         "prompt_sha256": prompt.sha256, "at": utc_now()})
                else:
                    self.counters.failed += 1
                raise CallError(stage, reason, kind=kind) from exc
            finally:
                self.counters.in_flight -= 1
                self._changed()
        self.counters.input_tokens += reply.input_tokens
        self.counters.output_tokens += reply.output_tokens
        refused = accept(reply.output) if accept is not None else None
        if refused:
            self.counters.failed += 1
            self._changed()
            raise CallError(stage, modelcall.redact(refused)[:300])
        self.counters.made += 1
        if reply.served_model:
            self.served.add(reply.served_model)
        value = {"output": reply.output.model_dump(mode="json"), "model": reply.model,
                 "served_model": reply.served_model, "prompt_sha256": prompt.sha256, "at": utc_now(),
                 "usage": {"input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens}}
        self.cache.put(key, value)
        self._changed()
        meta = {k: v for k, v in value.items() if k != "output"}
        return Result(reply.output, {**meta, "cached": False})
