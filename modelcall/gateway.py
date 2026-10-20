"""The model side of a call: pinned models, LiteLLM endpoints, rotation, settings. The call itself is `call.ask`.

pydantic-ai on LiteLLM's OpenAI-compatible endpoint. Every call has thinking off, a fixed temperature
and seed, and (in `call.ask`) its reply decoded under the output type's JSON schema: pydantic-ai's
NativeOutput sends `response_format: json_schema`, which vLLM enforces with structured outputs. The
sub-model replicas are used round robin, so concurrent calls spread over both GPUs. The API key is
read from $LITELLM_MASTER_KEY when a model is made and never logged or hashed.
"""
from __future__ import annotations

import itertools
import os
import threading
from dataclasses import dataclass

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

DEFAULT_BASE_URL = "http://127.0.0.1:4000/v1"

# Fixed run settings (docs/earlier-work.md, Fixed run settings).
ORCHESTRATOR = {"alias": "orch-model", "name": "Qwen/Qwen3.8-27B-FP8", "revision": "017b9c7",
                "thinking": False, "max_tokens": 4096, "context_tokens": 65536}
SUBAGENTS = [{"alias": f"sub-model-{i}", "name": "Qwen/Qwen3-30B-A3B-Instruct-2507-FP8",
              "revision": "5a5a776", "context_tokens": 32768} for i in (1, 2)]
SUB_ALIASES = tuple(s["alias"] for s in SUBAGENTS)  # sub-model-1, sub-model-2
SUB_MODEL = {"name": SUBAGENTS[0]["name"], "revision": SUBAGENTS[0].get("revision")}
ORCH_ALIAS = ORCHESTRATOR["alias"]  # orch-model: the one model of every extractor and both baselines
ORCH_MODEL = {"name": ORCHESTRATOR["name"], "revision": ORCHESTRATOR.get("revision")}


def base_url() -> str:
    return os.environ.get("LITELLM_BASE_URL", DEFAULT_BASE_URL)


def openai_model(alias: str, *, url: str | None = None) -> OpenAIChatModel:
    """One LiteLLM alias as a pydantic-ai model; vLLM behind it honours `response_format: json_schema`."""
    key = os.environ.get("LITELLM_MASTER_KEY") or "none"
    profile = OpenAIModelProfile(supports_json_schema_output=True, supports_json_object_output=True)
    return OpenAIChatModel(alias, provider=OpenAIProvider(base_url=url or base_url(), api_key=key), profile=profile)


class Rotation:
    """Round robin over model aliases (thread-safe); tests pass pydantic-ai Test/FunctionModels instead."""

    def __init__(self, models: list[Model] | None = None, aliases: tuple[str, ...] = SUB_ALIASES) -> None:
        self.models = models if models is not None else [openai_model(a) for a in aliases]
        self._cycle = itertools.cycle(range(len(self.models)))
        self._lock = threading.Lock()

    def next(self) -> Model:
        with self._lock:
            return self.models[next(self._cycle)]


@dataclass(frozen=True)
class CallSettings:
    """The sampling settings of a call; thinking is always off."""
    temperature: float = 0.0
    seed: int = 0
    max_tokens: int = 4096

    def model_settings(self) -> ModelSettings:
        return ModelSettings(temperature=self.temperature, seed=self.seed, max_tokens=self.max_tokens,
                             extra_body={"chat_template_kwargs": {"enable_thinking": False}})


def settings(*, temperature: float = 0.0, seed: int = 0, max_tokens: int = 4096) -> ModelSettings:
    return CallSettings(temperature, seed, max_tokens).model_settings()


def model_name(model: Model) -> str:
    return getattr(model, "model_name", type(model).__name__)


def model_identity(models: list[Model]) -> str:
    """The model identity for cache keys: the pinned sub-model (name@revision, modelcall/gateway.SUBAGENTS)
    for its replicas, so it does not matter which replica answered; the pinned orchestrator model
    (modelcall/gateway.ORCHESTRATOR) for `orch-model`; else the sorted model names.

    The identity is the pin, not observed from the server: the serving profile pins the same revision
    and serves it as `sub-model` (vLLM's served name), which names no weights. Serving other weights
    behind the aliases needs a new pin in modelcall/gateway, which changes every key."""
    names = sorted({model_name(m) for m in models})
    if set(names) <= set(SUB_ALIASES):
        return f"{SUB_MODEL['name']}@{SUB_MODEL['revision']}"
    if set(names) == {ORCH_ALIAS}:
        return f"{ORCH_MODEL['name']}@{ORCH_MODEL['revision']}"
    return "+".join(names)
