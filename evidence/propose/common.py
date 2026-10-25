"""What the proposal steps share: the directory's file names, reading and writing them, the one cached
model call, and the error every step raises for a refusal (the CLI prints it and exits 2)."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError
from pydantic_ai.models import Model

from jsonio import file_sha256, sha256_hex
import modelcall

HERE = Path(__file__).resolve().parent
EXAMPLE_PROTOCOL = HERE.parent / "protocols" / "rag-factuality.yaml"   # the draft's template for an effect question
# The draft starts from the hand-written protocol of the question's kind.
KIND_TEMPLATES = {"effect": EXAMPLE_PROTOCOL,
                  "consistency": HERE.parent / "protocols" / "cons-accuracy.yaml",
                  "inventory": HERE.parent / "protocols" / "inv-metrics.yaml",
                  "best": HERE.parent / "protocols" / "best-accuracy.yaml"}
DEFAULT_MODEL = "orch-model"   # the one model of every extractor and both baselines (Part G.3)

FRAME, DRAFT, SOURCES, CRITIC = "frame.json", "draft.yaml", "draft.sources.json", "critic.json"
CARDS, DECISIONS, PROTOCOL, PROPOSAL = "cards.json", "decisions.yaml", "protocol.yaml", "proposal.json"
AMENDMENTS, CACHE, WRITTEN = "amendments.jsonl", "cache.jsonl", "written.json"

T = TypeVar("T", bound=BaseModel)


class ProposalError(ValueError):
    """A step refuses: a missing input, a stale input, a decision without a reason, an empty amendment."""


def prompt(name: str) -> str:
    """A prompt template from prompts/ with LF line ends, so its hash is the same on every checkout."""
    return modelcall.load_prompt(HERE / "prompts" / name, strip=True).text


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


def guard(directory: Path, name: str, force: bool) -> None:
    """Refuse to overwrite a file the person may have edited: DIR/written.json holds the sha256 of what the
    flow last wrote to each human-edited file (frame.json, decisions.yaml); an existing file whose bytes
    differ from it, or that the flow never recorded, is kept unless `force`."""
    path = Path(directory) / name
    if force or not path.exists():
        return
    written = read_json(Path(directory) / WRITTEN) if (Path(directory) / WRITTEN).exists() else {}
    if written.get(name) != sha(path):
        raise ProposalError(f"{path} has been edited (or was not written by this step); move it away, or pass "
                            "--force to overwrite it")


def mark_written(directory: Path, name: str) -> None:
    path = Path(directory) / WRITTEN
    written = read_json(path) if path.exists() else {}
    written[name] = sha(Path(directory) / name)
    write_json(path, written)


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def slug_id(name: str) -> str:
    """A protocol id (evidence/protocol.py: ^[a-z0-9][a-z0-9_.-]*$) from a directory name."""
    out = re.sub(r"[^a-z0-9_.-]+", "-", name.casefold()).strip("-._")
    return out or "proposal"


def model_for(alias: str | None, model: Model | None) -> Model:
    """The model of a step: an injected one (tests), else the LiteLLM alias (default orch-model)."""
    return model if model is not None else modelcall.openai_model(alias or DEFAULT_MODEL)


REDO = "the reply is cached in {cache} (key {key}); run the step again with --refresh to ask the model again"


def ask(directory: Path, step: str, instructions: str, user_prompt: str, output_type: type[T], *,
        model: Model, refresh: bool = False) -> tuple[T, dict[str, Any]]:
    """One schema-constrained call through modelcall.ask, cached in DIR/cache.jsonl.

    The key is modelcall.cache_key over the step, the prompt hash (instructions and output schema), the model
    identity (the pinned weights of an alias, modelcall.model_identity) and the user prompt's sha256, so a
    rerun with the same inputs answers from the cache and makes no model call. `refresh` skips the cached
    reply and asks again (the new reply is appended under the same key and wins on the next load; a step
    whose cached reply it cannot use says so, `REDO`). Returns the output and the call's record {step,
    model, prompt_sha256, cache_key, cached}. A failed call is modelcall.ModelCallError (a RuntimeError)
    with a redacted reason: provider errors can echo the key.
    """
    cache = modelcall.JsonlCache(Path(directory) / CACHE)
    record = {"step": step, "prompt_sha256": modelcall.prompt_sha256(instructions, output_type),
              "model": modelcall.model_identity([model]), "input_sha256": sha256_hex(user_prompt.encode("utf-8")),
              "settings": {"temperature": 0.0, "seed": 0, "max_tokens": 4096}}
    key = modelcall.cache_key(record)
    try:
        answer = modelcall.ask_sync(modelcall.Prompt.inline(instructions, output_type), user_prompt, model=model,
                                    settings=modelcall.CallSettings(seed=0, max_tokens=4096), cache=cache,
                                    key=record, refresh=refresh)
    except ValidationError as exc:   # only a cached reply is decoded without the model: it no longer validates
        raise ProposalError(f"{step}: the cached reply does not validate ({exc}); "
                            + REDO.format(cache=Path(directory) / CACHE, key=key)) from exc
    return answer.output, {**_public(record), "cache_key": key, "cached": answer.cached}


def _public(record: dict[str, Any]) -> dict[str, Any]:
    return {k: record[k] for k in ("step", "model", "prompt_sha256")}
