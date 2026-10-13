"""Model calls of the gold builder and triage (M3): prompt files, result cache, concurrency, timeout.

Every call goes through gold/llm.py (pydantic-ai on LiteLLM, schema-constrained output, thinking off,
temperature and seed fixed) and the sub-model replicas in turn (`llm.Rotation`). Around it:

- Prompts are files in gold/prompts/. Each output line records `prompt_sha256` = llm.prompt_sha256 of
  the template and its output schema (the extraction schema depends on the concept, so its hash
  does too); the template's own file hash is recorded in doc.json.built.prompts. Templates are read
  with LF line ends whatever the checkout, so a hash is the same on Windows and on the cluster.
- A call is keyed by the sha256 of its whole input: stage, prompt hash, the user prompt, the model
  identity and the sampling settings (llm.cache_key). The key leaves out which replica answered:
  sub-model-1 and -2 serve the same pinned model, so a rerun that happens to rotate differently, or
  runs on one replica, still hits the cache. A rerun with the same inputs makes no model call; a
  stopped build resumes where it stopped (cache.jsonl). Failures are never cached, so the next run
  retries exactly them.
- At most `concurrency` calls are in flight (GOLD_CONCURRENCY, default 6: the 3 sequences per replica
  that ran without preemption in L3), and each has its own timeout; waiting for a slot does not count.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from agent.canonical import sha256_hex
from agent.rundir import utc_now

from . import llm

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class PromptFile:
    """One prompt template and the output type it is used with."""
    name: str           # file name in gold/prompts/
    text: str           # LF line ends
    file_sha256: str    # sha256 of `text` (UTF-8)
    sha256: str         # llm.prompt_sha256(text, output_type): what every output line records

    def json(self) -> dict[str, str]:
        return {"file": f"gold/prompts/{self.name}", "file_sha256": self.file_sha256, "prompt_sha256": self.sha256}


def load_prompt(name: str, output_type: type[BaseModel]) -> PromptFile:
    text = (PROMPT_DIR / name).read_bytes().decode("utf-8").replace("\r\n", "\n")
    return PromptFile(name, text, sha256_hex(text.encode("utf-8")), llm.prompt_sha256(text, output_type))


def model_key(models: list[Any]) -> str:
    """The model identity in cache keys: the pinned sub-model for its replicas, else the model names."""
    names = sorted({llm.model_name(m) for m in models})
    if set(names) <= set(llm.SUB_ALIASES):
        return f"{llm.SUB_MODEL['name']}@{llm.SUB_MODEL['revision']}"
    return "+".join(names)


class CallError(Exception):
    """A model call failed or timed out; `reason` is short and safe to record (never the API key)."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(f"{stage}: {reason}")
        self.stage = stage
        self.reason = reason


@dataclass
class Counters:
    made: int = 0
    cached: int = 0
    failed: int = 0
    in_flight: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def json(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class Result(Generic[T]):
    output: T
    meta: dict[str, Any]  # model (alias), served_model, prompt_sha256, usage, cached


@dataclass
class Caller:
    """Cached, bounded, timed structured calls over a model rotation (see the module docstring)."""
    rotation: llm.Rotation
    cache: llm.JsonlCache
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
        return llm.cache_key({
            "stage": stage, "prompt_sha256": prompt.sha256, "user_sha256": sha256_hex(user_prompt.encode("utf-8")),
            "model": self.model_key, "temperature": self.temperature, "seed": self.seed, "max_tokens": max_tokens,
        })

    def _changed(self) -> None:
        if self.on_change is not None:
            self.on_change()

    async def call(self, stage: str, prompt: PromptFile, output_type: type[T], user_prompt: str, *,
                   max_tokens: int) -> Result[T]:
        key = self.key(stage, prompt, user_prompt, max_tokens)
        hit = self.cache.get(key)
        if hit is not None:
            self.counters.cached += 1
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
                reply = await asyncio.wait_for(
                    llm.structured_reply(prompt.text, user_prompt, output_type, model=model,
                                         model_settings=llm.settings(temperature=self.temperature, seed=self.seed,
                                                                     max_tokens=max_tokens)),
                    timeout=self.timeout_s)
            except Exception as exc:  # noqa: BLE001 - any failure is recorded and retried on the next run
                self.counters.failed += 1
                reason = "timeout" if isinstance(exc, TimeoutError) else f"{type(exc).__name__}: {exc}"
                raise CallError(stage, reason[:300]) from exc
            finally:
                self.counters.in_flight -= 1
                self._changed()
        self.counters.made += 1
        self.counters.input_tokens += reply.input_tokens
        self.counters.output_tokens += reply.output_tokens
        if reply.served_model:
            self.served.add(reply.served_model)
        value = {"output": reply.output.model_dump(mode="json"), "model": reply.model,
                 "served_model": reply.served_model, "prompt_sha256": prompt.sha256, "at": utc_now(),
                 "usage": {"input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens}}
        self.cache.put(key, value)
        self._changed()
        meta = {k: v for k, v in value.items() if k != "output"}
        return Result(reply.output, {**meta, "cached": False})
