"""LLM calls outside the agent loop (gold builder, judge, chat), shared by gold/, scoring/ and webapp/.

pydantic-ai on LiteLLM's OpenAI-compatible endpoint. Every call has thinking off, a fixed temperature
and seed, and (for `structured`) its reply decoded under the output type's JSON schema: pydantic-ai's
NativeOutput sends `response_format: json_schema`, which vLLM enforces with structured outputs. The
sub-model replicas are used round robin, so concurrent calls spread over both GPUs. The API key is
read from $LITELLM_MASTER_KEY when a model is made and never logged or hashed.
"""
from __future__ import annotations

import itertools
import json
import os
import threading
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from agent.canonical import canonical_bytes, sha256_hex
from agent.rundir import SUBAGENTS

DEFAULT_BASE_URL = "http://127.0.0.1:4000/v1"
SUB_ALIASES = tuple(s["alias"] for s in SUBAGENTS)  # sub-model-1, sub-model-2
SUB_MODEL = {"name": SUBAGENTS[0]["name"], "revision": SUBAGENTS[0].get("revision")}
T = TypeVar("T", bound=BaseModel)


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


def settings(*, temperature: float = 0.0, seed: int = 0, max_tokens: int = 4096) -> ModelSettings:
    return ModelSettings(temperature=temperature, seed=seed, max_tokens=max_tokens,
                         extra_body={"chat_template_kwargs": {"enable_thinking": False}})


def prompt_sha256(instructions: str, output_type: type[BaseModel] | None = None) -> str:
    """Hash of a prompt template and its output schema: recorded with every result it produced."""
    schema = output_type.model_json_schema() if output_type else None
    return sha256_hex(canonical_bytes({"instructions": instructions, "schema": schema}))


def model_name(model: Model) -> str:
    return getattr(model, "model_name", type(model).__name__)


async def structured(instructions: str, user_prompt: str, output_type: type[T], *, model: Model,
                     model_settings: ModelSettings | None = None, retries: int = 1) -> T:
    """One call whose reply must be an `output_type` object.

    Schema-constrained decoding (NativeOutput) where the model supports it, as the LiteLLM models do;
    pydantic-ai's test models get their tool-call output mode instead.
    """
    native = bool(model.profile.get("supports_json_schema_output"))
    agent: Agent[None, T] = Agent(model, output_type=NativeOutput(output_type) if native else output_type,
                                  instructions=instructions, retries=retries)
    result = await agent.run(user_prompt, model_settings=model_settings or settings())
    return result.output


def cache_key(payload: dict[str, Any]) -> str:
    """Key for a result cache line: sha256 of the canonical call input (prompt hash, model, inputs)."""
    return sha256_hex(canonical_bytes(payload))


class JsonlCache:
    """Append-only `{key, value}` lines; a rerun with the same inputs costs no model call."""

    def __init__(self, path: os.PathLike[str] | str) -> None:
        self.path = os.fspath(path)
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        row = json.loads(line)
                        self._data[row["key"]] = row["value"]

    def get(self, key: str) -> Any | None:
        return self._data.get(key)

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"key": key, "value": value}, ensure_ascii=False, sort_keys=True) + "\n")


@dataclass(frozen=True)
class Reply(Generic[T]):
    """A `structured` reply with what produced it: the alias asked, the model name the server reported
    (LiteLLM passes vLLM's served name through), and token usage for cost accounting."""
    output: T
    model: str
    served_model: str | None
    input_tokens: int
    output_tokens: int


async def structured_reply(instructions: str, user_prompt: str, output_type: type[T], *, model: Model,
                           model_settings: ModelSettings | None = None, retries: int = 1) -> Reply[T]:
    """`structured`, keeping the served model name and usage (the gold builder records both per line)."""
    native = bool(model.profile.get("supports_json_schema_output"))
    agent: Agent[None, T] = Agent(model, output_type=NativeOutput(output_type) if native else output_type,
                                  instructions=instructions, retries=retries)
    result = await agent.run(user_prompt, model_settings=model_settings or settings())
    usage = result.usage() if callable(result.usage) else result.usage
    return Reply(result.output, model_name(model), result.response.model_name,
                 usage.input_tokens or 0, usage.output_tokens or 0)
