"""CallCache in mode run: a call made in this process is `fresh` when asked again, and never retried."""
from __future__ import annotations

from agent.anchor import Index, text_sha256
from evidence import protocol
from evidence.calls import CallCache, EngineContext
from evidence.contract import (DocumentRef, ExtractionError, ExtractionResult, ExtractionTask, ExtractorSpec,
                               ProtocolRef)
from modelcall import JsonlCache

from .conftest import PAPERS, PROTOCOL

TEXT = (PAPERS / "S001.md").read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
DOC = DocumentRef(id="S001", file="papers/S001.md", sha256=text_sha256(TEXT))
PROTO = protocol.load(PROTOCOL)
SPEC = ExtractorSpec(name="counting", version=1, kind="regex", evidence_types=("condition",),
                     code_sha256="0" * 64, determinism="exact")


class Counting:
    spec = SPEC

    def __init__(self, fail: bool = False, status: str = "ok", reason: str | None = None) -> None:
        self.runs, self.fail, self.status, self.reason = 0, fail, status, reason

    def extract(self, task, ctx) -> ExtractionResult:
        self.runs += 1
        if self.fail:
            raise ValueError("always fails")
        error = ExtractionError(reason=self.reason) if self.reason else None
        return ExtractionResult(extractor_id=SPEC.extractor_id, task_sha256=task.task_sha256, status=self.status,
                                error=error)


def make_task() -> ExtractionTask:
    spec = PROTO.evidence_types["condition"]
    return ExtractionTask(protocol=ProtocolRef(id=PROTO.id, sha256=PROTO.sha256), evidence_type="condition",
                          field_schema_sha256=spec.schema_sha256, document=DOC)


def make_ctx() -> EngineContext:
    return EngineContext(TEXT, Index(TEXT), [], {}, None)


def test_a_call_made_in_this_process_is_reported_fresh_on_the_second_ask(tmp_path) -> None:
    ext, cache = Counting(), CallCache(JsonlCache(tmp_path / "c.jsonl"), "run")
    first, second = cache.call(ext, make_task(), make_ctx), cache.call(ext, make_task(), make_ctx)
    assert first.source == second.source == "fresh" and ext.runs == 1
    assert second.raw == first.raw and second.model_calls == first.model_calls


def test_a_cache_hit_from_an_earlier_process_stays_cache(tmp_path) -> None:
    ext = Counting()
    CallCache(JsonlCache(tmp_path / "c.jsonl"), "run").call(ext, make_task(), make_ctx)
    again = CallCache(JsonlCache(tmp_path / "c.jsonl"), "run").call(ext, make_task(), make_ctx)
    assert again.source == "cache" and ext.runs == 1


def test_retry_errors_retries_a_made_error_only_once(tmp_path) -> None:
    path, ext = tmp_path / "c.jsonl", Counting(fail=True)
    CallCache(JsonlCache(path), "run").call(ext, make_task(), make_ctx)          # attempt 0, earlier process
    cache = CallCache(JsonlCache(path), "run", retry_errors=True)
    a, b = cache.call(ext, make_task(), make_ctx), cache.call(ext, make_task(), make_ctx)
    assert (a.attempt, b.attempt) == (1, 1) and ext.runs == 2 and b.source == "fresh"


def test_retry_errors_retries_a_partial_result_and_never_an_ok_one(tmp_path) -> None:
    path, partial = tmp_path / "c.jsonl", Counting(status="partial", reason="service_call")
    CallCache(JsonlCache(path), "run").call(partial, make_task(), make_ctx)       # attempt 0: one chunk failed
    assert CallCache(JsonlCache(path), "run").call(partial, make_task(), make_ctx).source == "cache"   # no flag: reused
    fixed = Counting()
    again = CallCache(JsonlCache(path), "run", retry_errors=True).call(fixed, make_task(), make_ctx)
    assert (again.attempt, again.source, again.raw.status, fixed.runs) == (1, "fresh", "ok", 1)
    later = CallCache(JsonlCache(path), "run", retry_errors=True).call(fixed, make_task(), make_ctx)
    assert (later.attempt, later.source, fixed.runs) == (1, "cache", 1)          # an ok result is never asked again


def test_retry_errors_leaves_an_agent_that_ran_out_of_budget(tmp_path) -> None:
    path, agent = tmp_path / "c.jsonl", Counting(status="partial", reason="no_final_answer")
    CallCache(JsonlCache(path), "run").call(agent, make_task(), make_ctx)
    again = CallCache(JsonlCache(path), "run", retry_errors=True).call(agent, make_task(), make_ctx)
    assert (again.source, again.attempt, agent.runs) == ("cache", 0, 1)     # the costly agent is not run again
