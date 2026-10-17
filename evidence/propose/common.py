"""What the proposal steps share: the directory's file names, reading and writing them, the one cached
model call, and the error every step raises for a refusal (the CLI prints it and exits 2)."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel
from pydantic_ai.models import Model

from agent.canonical import file_sha256, sha256_hex
from gold import llm

HERE = Path(__file__).resolve().parent
EXAMPLE_PROTOCOL = HERE.parent / "protocols" / "rag-factuality.yaml"   # the draft's template
DEFAULT_MODEL = "orch-model"   # the one model of every extractor and both baselines (Part G.3)

FRAME, DRAFT, SOURCES, CRITIC = "frame.json", "draft.yaml", "draft.sources.json", "critic.json"
CARDS, DECISIONS, PROTOCOL, PROPOSAL = "cards.json", "decisions.yaml", "protocol.yaml", "proposal.json"
AMENDMENTS, CACHE = "amendments.jsonl", "cache.jsonl"

T = TypeVar("T", bound=BaseModel)


class ProposalError(ValueError):
    """A step refuses: a missing input, a stale input, a decision without a reason, an empty amendment."""


def prompt(name: str) -> str:
    """A prompt template from prompts/ with LF line ends, so its hash is the same on every checkout."""
    return (HERE / "prompts" / name).read_text(encoding="utf-8").replace("\r\n", "\n").strip() + "\n"


def need(directory: Path, name: str, step: str) -> Path:
    path = Path(directory) / name
    if not path.exists():
        raise ProposalError(f"{path} does not exist: run `evidence propose {step}` first")
    return path


def read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ProposalError(f"{path}: not valid JSON: {exc}") from exc


def write_json(path: Path, obj: Any) -> Path:
    Path(path).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return Path(path)


def read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProposalError(f"{path}: not valid YAML: {exc}") from exc


def dump_yaml(obj: Any) -> str:
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=110)


def write_text(path: Path, text: str) -> Path:
    Path(path).write_text(text, encoding="utf-8", newline="\n")
    return Path(path)


def sha(path: Path) -> str:
    """sha256 of a file's bytes: what a later step records of the input it read."""
    return file_sha256(path)


def fresh(directory: Path, name: str, recorded: str | None, step: str) -> None:
    """Refuse when an input changed after a step read it (its recorded sha256 differs from the file's)."""
    path = Path(directory) / name
    if recorded != sha(path):
        raise ProposalError(f"{path} changed after `evidence propose {step}` read it: run {step} again")


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def slug_id(name: str) -> str:
    """A protocol id (evidence/protocol.py: ^[a-z0-9][a-z0-9_.-]*$) from a directory name."""
    out = re.sub(r"[^a-z0-9_.-]+", "-", name.casefold()).strip("-._")
    return out or "proposal"


def model_for(alias: str | None, model: Model | None) -> Model:
    """The model of a step: an injected one (tests), else the LiteLLM alias (default orch-model)."""
    return model if model is not None else llm.openai_model(alias or DEFAULT_MODEL)


def ask(directory: Path, step: str, instructions: str, user_prompt: str, output_type: type[T], *,
        model: Model) -> tuple[T, dict[str, Any]]:
    """One schema-constrained call through gold.llm.structured, cached in DIR/cache.jsonl.

    The key is gold.llm.cache_key over the step, the prompt hash (instructions and output schema), the model
    identity (the pinned weights of an alias, gold.llm.model_identity) and the user prompt's sha256, so a
    rerun with the same inputs answers from the cache and makes no model call. Returns the output and the
    call's record {step, model, prompt_sha256, cache_key, cached}.
    """
    cache = llm.JsonlCache(Path(directory) / CACHE)
    record = {"step": step, "prompt_sha256": llm.prompt_sha256(instructions, output_type),
              "model": llm.model_identity([model]), "input_sha256": sha256_hex(user_prompt.encode("utf-8")),
              "settings": {"temperature": 0.0, "seed": 0, "max_tokens": 4096}}
    key = llm.cache_key(record)
    hit = cache.get(key)
    if hit is not None:
        return output_type.model_validate(hit), {**_public(record), "cache_key": key, "cached": True}
    try:
        output = asyncio.run(llm.structured(instructions, user_prompt, output_type, model=model,
                                            model_settings=llm.settings(seed=0, max_tokens=4096)))
    except Exception as exc:   # provider errors can echo the key: never let it reach a file or a log
        raise RuntimeError(llm.redact(f"{type(exc).__name__}: {exc}")) from None
    cache.put(key, output.model_dump(mode="json"))
    return output, {**_public(record), "cache_key": key, "cached": False}


def _public(record: dict[str, Any]) -> dict[str, Any]:
    return {k: record[k] for k in ("step", "model", "prompt_sha256")}
