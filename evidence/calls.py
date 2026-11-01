"""One extractor call: the context the extractor gets, the record cache, and the cache policy per mode.

Cache key = digest([extractor_id, task_sha256]) (contract section 8); the value is what the extractor
returned (before the engine's checks, which are re-applied on every read) plus the records of every model
call inside it. Modes:

- `run`: the latest attempt is used, a miss runs the extractor and is stored (an error result too, so the
  run can be replayed); a call this process made itself is `fresh` when asked again and is never retried (the
  warm pass of parallel papers fills the cache, the sequential loop then reads it back at the right cost);
  `retry_errors` runs a cached error result again, and a partial one the service failed (rundir.service_failed:
  a GLiNER timeout on one chunk, a failed LLM chunk or quote retry; not an agentic run out of budget, which would
  only repeat a costly agent), and stores it as a NEW attempt under digest([key, n]), so the records earlier runs
  rest on are never overwritten;
- `replay`: cache only, the attempt the recorded run used (its events record it), a miss is NotRecorded;
- `reexec`: extractors chosen by `bypass` run again from scratch and are not stored (the record stays the
  reference); the others use the recorded attempt and run fresh only when the cache has no entry.

`recorded` is the same policy for a model call of the engine's own that is not an extractor (the names check of
D38): its records sit in the same cache, keyed by the call's owner id and the digest of its request.
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from agent.anchor import Index
from modelcall import JsonlCache, redact

from .contract import ExtractionError, ExtractionResult, ExtractionTask, Extractor, ExtractorSpec, Item, digest
from .recording import Provider, Recorder
from .rundir import service_failed

Mode = Literal["run", "replay", "reexec"]


def retried(result: dict[str, Any]) -> bool:
    """What `retry_errors` asks again: any error, and a partial result the model gateway or GLiNER failed."""
    return result.get("status") == "error" or service_failed(result)


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
    attempt: int = 0


@dataclass
class Asked:
    """A recorded call of the engine's own (`CallCache.recorded`): its value as stored, its model-call records."""
    value: dict[str, Any]
    model_calls: list[dict[str, Any]]
    source: Literal["cache", "fresh"]
    attempt: int = 0


def cache_key(extractor_id: str, task_sha256: str, attempt: int = 0) -> str:
    base = digest([extractor_id, task_sha256])
    return base if attempt == 0 else digest([base, attempt])


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
                 retry_errors: bool = False, attempts: dict[str, int] | None = None) -> None:
        self.cache, self.mode, self.bypass, self.retry_errors = cache, mode, bypass, retry_errors
        self.attempts = attempts       # cache_key -> attempt the recorded run used (replay, reexec)
        self._warned: set[str] = set()
        self.made: set[str] = set()    # cache keys stored by call() in this process

    def _latest(self, extractor_id: str, task_sha256: str) -> tuple[int, dict[str, Any] | None]:
        n, hit = 0, self.cache.get(cache_key(extractor_id, task_sha256))
        while hit is not None and (more := self.cache.get(cache_key(extractor_id, task_sha256, n + 1))) is not None:
            n, hit = n + 1, more
        return n, hit

    def _recorded(self, extractor_id: str, task_sha256: str) -> tuple[int, dict[str, Any] | None]:
        if self.attempts is None:
            return self._latest(extractor_id, task_sha256)
        n = self.attempts.get(cache_key(extractor_id, task_sha256), 0)
        return n, self.cache.get(cache_key(extractor_id, task_sha256, n))

    def call(self, extractor: Extractor, task: ExtractionTask, make_ctx: Callable[[], EngineContext]) -> Outcome:
        spec = extractor.spec
        if self.mode == "replay":
            n, hit = self._recorded(spec.extractor_id, task.task_sha256)
            if hit is None:
                raise NotRecorded(f"not recorded: {spec.extractor_id} on {task.document.id} ({task.evidence_type}), "
                                  f"task {task.task_sha256[:12]}, attempt {n}")
            return self._from(hit, n)
        if self.mode == "reexec":
            n, hit = self._recorded(spec.extractor_id, task.task_sha256)
            if hit is not None and not (self.bypass and self.bypass(spec)):
                return self._from(hit, n)
            raw, records = execute(extractor, task, make_ctx())
            return Outcome(raw, records, "fresh", n)
        n, hit = self._latest(spec.extractor_id, task.task_sha256)
        if hit is not None and cache_key(spec.extractor_id, task.task_sha256, n) in self.made:
            return Outcome(ExtractionResult.model_validate(hit["result"]), list(hit.get("model_calls") or []),
                           "fresh", n)
        if hit is not None and not (self.retry_errors and retried(hit["result"])):
            return self._from(hit, n)
        n = n + 1 if hit is not None else 0
        self._check_version(spec)
        raw, records = execute(extractor, task, make_ctx())
        key = cache_key(spec.extractor_id, task.task_sha256, n)
        self.cache.put(key, {
            "extractor_id": spec.extractor_id, "spec": spec.model_dump(mode="json"), "attempt": n,
            "task": task.model_dump(mode="json"), "task_sha256": task.task_sha256,
            "result": raw.model_dump(mode="json"), "model_calls": records})
        self.made.add(key)
        return Outcome(raw, records, "fresh", n)

    def recorded(self, owner_id: str, request: dict[str, Any],
                 make: Callable[[], tuple[dict[str, Any], list[dict[str, Any]]]]) -> Asked:
        """A model call of the engine's own (the names check), under the same policy as `call`: the key is
        cache_key(owner_id, digest(request)); `make()` gives (value, model-call records), a value with status `error`
        is what `retry_errors` asks again. Replay reads the recorded attempt only (a miss is NotRecorded); reexec uses
        the record and asks only when there is none (no `bypass`: it names extractors)."""
        request_sha256 = digest(request)
        if self.mode in ("replay", "reexec"):
            n, hit = self._recorded(owner_id, request_sha256)
            if hit is not None:
                return Asked(hit["result"], list(hit.get("model_calls") or []), "cache", n)
            if self.mode == "replay":
                raise NotRecorded(f"not recorded: {owner_id}, request {request_sha256[:12]}, attempt {n}")
            value, records = make()
            return Asked(value, records, "fresh", n)
        n, hit = self._latest(owner_id, request_sha256)
        if hit is not None and cache_key(owner_id, request_sha256, n) in self.made:
            return Asked(hit["result"], list(hit.get("model_calls") or []), "fresh", n)
        if hit is not None and not (self.retry_errors and hit["result"].get("status") == "error"):
            return Asked(hit["result"], list(hit.get("model_calls") or []), "cache", n)
        n = n + 1 if hit is not None else 0
        value, records = make()
        key = cache_key(owner_id, request_sha256, n)
        self.cache.put(key, {"extractor_id": owner_id, "attempt": n, "task": request, "task_sha256": request_sha256,
                             "result": value, "model_calls": records})
        self.made.add(key)
        return Asked(value, records, "fresh", n)

    @staticmethod
    def _from(hit: dict[str, Any], attempt: int) -> Outcome:
        return Outcome(ExtractionResult.model_validate(hit["result"]), list(hit.get("model_calls") or []), "cache",
                       attempt)

    def _check_version(self, spec: ExtractorSpec) -> None:
        """Warn once when the cache holds this name@version with other code: the version was not bumped.
        (Another config of the same code is a deliberate variant, not a missed bump.)"""
        if spec.extractor_id in self._warned:
            return
        self._warned.add(spec.extractor_id)
        others = {v["extractor_id"] for _, v in self.cache.items()
                  if isinstance(v, dict) and isinstance(v.get("spec"), dict) and v["spec"].get("name") == spec.name
                  and v["spec"].get("version") == spec.version and v["spec"].get("code_sha256") != spec.code_sha256}
        if others:
            print(f"warning: {spec.extractor_id}: the cache holds {sorted(others)} for the same version with other "
                  f"code; bump the version when behaviour changes", file=sys.stderr)
