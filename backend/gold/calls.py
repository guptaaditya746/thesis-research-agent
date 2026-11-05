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


def classify(exc: BaseException | None, messages: list[Any]) -> tuple[str, str]:
    """(kind, reason) of a failed call, from the original exception (`modelcall.ModelCallError.cause`) and the
    messages the run exchanged (`.messages`). Only the redacted reason leaves this function."""
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


class _Staged:
    """The cache as `modelcall.ask` sees it: reads go to the cache, the one write is held back until the caller's
    `accept` passes (a refused reply is never cached)."""

    def __init__(self, cache: modelcall.JsonlCache) -> None:
        self.cache = cache
        self.line: tuple[str, Any] | None = None

    def get(self, key: str) -> Any | None:
        return self.cache.get(key)

    def put(self, key: str, value: Any) -> None:
        self.line = (key, value)


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

    def _key(self, stage: str, prompt: PromptFile, user_prompt: str, max_tokens: int) -> dict[str, Any]:
        return {"stage": stage, "prompt_sha256": prompt.sha256, "user_sha256": sha256_hex(user_prompt.encode("utf-8")),
                "model": self.model_key, "temperature": self.temperature, "seed": self.seed, "max_tokens": max_tokens}

    def key(self, stage: str, prompt: PromptFile, user_prompt: str, max_tokens: int) -> str:
        return modelcall.cache_key(self._key(stage, prompt, user_prompt, max_tokens))

    def settings(self) -> dict[str, Any]:
        return {"model_key": self.model_key, "concurrency": self.concurrency, "timeout_s": self.timeout_s,
                "temperature": self.temperature, "seed": self.seed}

    def _changed(self) -> None:
        if self.on_change is not None:
            self.on_change()

    async def call(self, stage: str, prompt: PromptFile, output_type: type[T], user_prompt: str, *,
                   max_tokens: int, accept: Callable[[T], str | None] | None = None) -> Result[T]:
        """One structured call through modelcall.ask. `accept(output)` may return a reason to refuse a reply: it
        then counts as a failed call and is not cached (a rerun asks again)."""
        record = self._key(stage, prompt, user_prompt, max_tokens)
        key = modelcall.cache_key(record)
        ask_prompt = modelcall.Prompt(f"gold/prompts/{prompt.name}", prompt.text, output_type)
        call_settings = modelcall.CallSettings(temperature=self.temperature, seed=self.seed, max_tokens=max_tokens)
        staged = _Staged(self.cache)
        hit = self.cache.get(key)
        try:
            if hit is not None:  # a cached result or verdict: no slot, no replica, no model call
                answer = await modelcall.ask(ask_prompt, user_prompt, model=self.rotation.models[0],
                                             settings=call_settings, cache=staged, key=record)  # type: ignore[arg-type]
            else:
                async with self._slots:
                    model = self.rotation.next()
                    self.counters.in_flight += 1
                    self._changed()
                    try:
                        answer = await modelcall.ask(ask_prompt, user_prompt, model=model, settings=call_settings,
                                                     cache=staged, key=record,  # type: ignore[arg-type]
                                                     extra={"prompt_sha256": prompt.sha256, "at": utc_now()},
                                                     timeout_s=self.timeout_s)
                    except modelcall.CachedFailure:
                        raise
                    except modelcall.ModelCallError as err:  # any failure is recorded, and retried or cut
                        kind, reason = classify(err.cause, err.messages)
                        if kind == "too_long":
                            self.counters.too_long += 1
                            self.cache.put(key, {"too_long": True, "reason": reason,
                                                 "model": modelcall.model_name(model),
                                                 "prompt_sha256": prompt.sha256, "at": utc_now()})
                        else:
                            self.counters.failed += 1
                        raise CallError(stage, reason, kind=kind) from None
                    finally:
                        self.counters.in_flight -= 1
                        self._changed()
        except modelcall.CachedFailure as err:
            self.counters.too_long += 1
            self._changed()
            raise CallError(stage, err.value["reason"], kind="too_long", cached=True) from None
        if answer.cached:  # the line read before the call, or (an identical call ahead of this one) after it
            stored = hit if hit is not None else self.cache.get(key)
            self.counters.cached += 1
            self.counters.cached_input_tokens += answer.input_tokens
            self.counters.cached_output_tokens += answer.output_tokens
            if answer.served_model:
                self.served.add(answer.served_model)
            self._changed()
            meta = {k: v for k, v in stored.items() if k != "output"}
            return Result(answer.output, {**meta, "cached": True})
        self.counters.input_tokens += answer.input_tokens
        self.counters.output_tokens += answer.output_tokens
        refused = accept(answer.output) if accept is not None else None
        if refused:
            self.counters.failed += 1
            self._changed()
            raise CallError(stage, modelcall.redact(refused)[:300])
        self.counters.made += 1
        if answer.served_model:
            self.served.add(answer.served_model)
        assert staged.line is not None
        self.cache.put(*staged.line)
        self._changed()
        meta = {k: v for k, v in staged.line[1].items() if k != "output"}
        return Result(answer.output, {**meta, "cached": False})
