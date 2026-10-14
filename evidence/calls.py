"""One extractor call: the context the extractor gets, the record cache, and the cache policy per mode.

Cache key = digest([extractor_id, task_sha256]) (contract section 8); the value is what the extractor
returned (before the engine's checks, which are re-applied on every read) plus the records of every model
call inside it. Modes:

- `run`: a hit is used, a miss runs the extractor and is stored (an error result too, so the run can be
  replayed; `retry_errors` runs cached errors again);
- `replay`: cache only, a miss is NotRecorded, never a new call;
- `reexec`: extractors chosen by `bypass` run again from scratch and are not stored (the record stays the
  reference); the others use the cache and run fresh only when the cache has no entry for their task.
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from agent.anchor import Index
from gold.llm import JsonlCache, redact

from .contract import ExtractionError, ExtractionResult, ExtractionTask, Extractor, ExtractorSpec, Item, digest
from .recording import Provider, Recorder

Mode = Literal["run", "replay", "reexec"]


class NotRecorded(RuntimeError):
    """Replay asked for a call the cache does not hold."""


class EngineContext:
    """The RunContext of one call (contract section 12): the document, the declared context, the schema,
    and `llm()`, the recorded way to a model."""

    def __init__(self, text: str, index: Index, context: list[Item], schema: dict[str, Any],
                 provider: Provider | None) -> None:
        self._text, self._index, self._context, self._schema = text, index, context, schema
        self.recorder = Recorder(provider)

    def text(self) -> str:
        return self._text

    def index(self) -> Index:
        return self._index

    def context_items(self) -> list[Item]:
        return list(self._context)

    def field_schema(self) -> dict[str, Any]:
        return dict(self._schema)

    def llm(self) -> Recorder:
        return self.recorder


@dataclass
class Outcome:
    raw: ExtractionResult           # as the extractor returned it (or as recorded)
    model_calls: list[dict[str, Any]]
    source: Literal["cache", "fresh"]


def cache_key(extractor_id: str, task_sha256: str) -> str:
    return digest([extractor_id, task_sha256])


def execute(extractor: Extractor, task: ExtractionTask, ctx: EngineContext) -> tuple[ExtractionResult, list[dict[str, Any]]]:
    """Run the extractor; an exception becomes an error result (R6), with the identity the engine owns."""
    spec = extractor.spec
    try:
        raw = extractor.extract(task, ctx)
    except Exception as exc:  # noqa: BLE001 - failure is a status, not a lost call
        ids = tuple(r["id"] for r in ctx.recorder.records)
        raw = ExtractionResult(extractor_id=spec.extractor_id, task_sha256=task.task_sha256, status="error",
                               error=ExtractionError(reason=type(exc).__name__, detail=redact(str(exc))[:300]),
                               model_calls=ids)
    raw = raw.model_copy(update={"call_id": "", "extractor_id": spec.extractor_id, "task_sha256": task.task_sha256})
    return raw.canonical(), ctx.recorder.records


class CallCache:
    """The record cache with the policy of one mode."""

    def __init__(self, cache: JsonlCache, mode: Mode, bypass: Callable[[ExtractorSpec], bool] | None = None,
                 retry_errors: bool = False) -> None:
        self.cache, self.mode, self.bypass, self.retry_errors = cache, mode, bypass, retry_errors
        self._warned: set[str] = set()

    def call(self, extractor: Extractor, task: ExtractionTask, make_ctx: Callable[[], EngineContext]) -> Outcome:
        spec = extractor.spec
        key = cache_key(spec.extractor_id, task.task_sha256)
        hit = self.cache.get(key)
        if self.mode == "replay":
            if hit is None:
                raise NotRecorded(f"not recorded: {spec.extractor_id} on {task.document.id} ({task.evidence_type}), "
                                  f"task {task.task_sha256[:12]}")
            return self._from(hit)
        if self.mode == "reexec":
            if hit is not None and not (self.bypass and self.bypass(spec)):
                return self._from(hit)
            raw, records = execute(extractor, task, make_ctx())
            return Outcome(raw, records, "fresh")
        if hit is not None and not (self.retry_errors and hit["result"]["status"] == "error"):
            return self._from(hit)
        self._check_version(spec)
        raw, records = execute(extractor, task, make_ctx())
        self.cache.put(key, {"extractor_id": spec.extractor_id, "spec": spec.model_dump(mode="json"),
                             "task": task.model_dump(mode="json"), "task_sha256": task.task_sha256,
                             "result": raw.model_dump(mode="json"), "model_calls": records})
        return Outcome(raw, records, "fresh")

    @staticmethod
    def _from(hit: dict[str, Any]) -> Outcome:
        return Outcome(ExtractionResult.model_validate(hit["result"]), list(hit.get("model_calls") or []), "cache")

    def _check_version(self, spec: ExtractorSpec) -> None:
        """Warn once when the cache holds this name@version under other hashes: the version was not bumped."""
        if spec.extractor_id in self._warned:
            return
        self._warned.add(spec.extractor_id)
        prefix = f"{spec.name}@{spec.version}#"
        others = {v.get("extractor_id") for v in self.cache._data.values()
                  if isinstance(v, dict) and str(v.get("extractor_id", "")).startswith(prefix)} - {spec.extractor_id}
        if others:
            print(f"warning: {spec.extractor_id}: the cache holds {sorted(others)} for the same version with other "
                  f"code or config hashes; bump the version when behaviour changes", file=sys.stderr)
