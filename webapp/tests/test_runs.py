"""Exit status from the records (scoring's rules), live versus post-processing, and the score summary."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agent.canonical import write_json
from agent.rundir import ATTACH_FILE, RunDir
from agent.tests.conftest import fixture
from agent.tests.runs import Driver
from agent.tests.test_rundir import SETTINGS
from webapp.app import create_app
from webapp.corpus import Corpus
from webapp.runs import Digest, Runs, score_summary
from webapp.settings import Settings

from .test_stream import events
from .world import World


def record(subtype: str, step: int = 1, reason: str | None = None, detail: Any = None, **meta: Any) -> dict[str, Any]:
    generated: dict[str, Any] = {"usage": {"total_tokens": 10}} if subtype == "ai_model_invocation" else {}
    if reason:
        generated = {"reason": reason, **({"detail": detail} if detail is not None else {})}
    return {"subtype": subtype, "step_id": step, "agent_id": "main", "task_id": f"t{step:06d}", "status": "finished",
            "started_at": "2026-10-13T10:00:00.000000Z", "ended_at": "2026-10-13T10:00:01.000000Z",
            "used": {}, "generated": generated, "custom_metadata": meta}


@pytest.mark.parametrize("records, answer, live, status", [
    ([record("ai_model_invocation", final_answer=True)], True, False, "submitted"),
    ([record("ai_model_invocation"), record("coverage", 2, "no_final_answer", {"exit_status": "budget"})], True, False,
     "budget"),
    ([record("coverage", 2, "no_final_answer", {"exit_status": "context_full"})], True, False, "context_full"),
    ([record("coverage", 1, "run_error", {"error": "boom"}), record("coverage", 1, "no_final_answer",
                                                                    {"exit_status": "error"})], True, False, "error"),
    ([record("ai_model_invocation"), record("coverage", 1, "job_time_limit", {"phase": "research"})], False, False, "cut"),
    ([record("ai_model_invocation", final_answer=True), record("coverage", 9, "interrupted", {})], True, False, "cut"),
    ([record("ai_model_invocation")], False, True, "running"),
    ([record("ai_model_invocation")], False, False, "incomplete"),
    ([record("ai_model_invocation")], True, False, "unknown"),
    # WP A: no valid final answer, the harness took the agent's draft (loop.finish_without_answer).
    ([record("ai_model_invocation"), record("coverage", 60, "answer_from_draft", {"exit_status": "budget", "rows": 3})],
     True, False, "budget"),
    # The attach step's own coverage records say nothing about how the research run ended.
    ([record("ai_model_invocation", final_answer=True), record("coverage", 5, "no_source_found", {}, origin="attach"),
      record("coverage", 6, "job_time_limit", {"phase": "attach"}, origin="attach")], True, False, "submitted"),
])
def test_exit_status(tmp_path: Path, records: list[dict[str, Any]], answer: bool, live: bool, status: str) -> None:
    if answer:
        (tmp_path / "answer.json").write_text("{}", encoding="utf-8")
    assert Runs.exit_status(RunDir(tmp_path), Digest.of(records), live) == status


@pytest.mark.parametrize("records, answer_from", [
    ([record("ai_model_invocation", final_answer=True)], "final"),
    ([record("coverage", 9, "answer_from_draft", {"exit_status": "context_full"})], "draft"),
    ([record("coverage", 9, "no_final_answer", {"exit_status": "budget"})], "none"),
    ([record("ai_model_invocation")], None),
])
def test_answer_from(records: list[dict[str, Any]], answer_from: str | None) -> None:
    assert Digest.of(records).answer_from == answer_from


def test_the_trajectory_tells_when_the_records_do_not(tmp_path: Path) -> None:
    runs = Runs(Settings(runs=tmp_path), Corpus(None))
    run = RunDir(tmp_path / "r1")
    run.root.mkdir()
    (run.root / "answer.json").write_text("{}", encoding="utf-8")
    digest = Digest.of([record("ai_model_invocation")])
    assert runs.status(run, digest, False) == "unknown"
    (run.root / "trajectory.json").write_text(json.dumps({"info": {"exit_status": "LimitsExceeded"}, "messages": []}),
                                              encoding="utf-8")
    assert runs.status(run, digest, False) == "LimitsExceeded"


def test_score_summary_prefers_the_soft_fact_match() -> None:
    assert score_summary(None) is None
    assert score_summary({"facts": {"strict": {"f1": 0.2}}, "rows": {"f1": 0.5}}).model_dump() == \
        {"support_share": None, "fact_f1": 0.2, "row_f1": 0.5, "key_version": None, "provisional": None}
    assert score_summary({"facts": {"strict": {"f1": 0.2}, "soft": {"f1": 0.7}},
                          "support": {"support_share": 0.4}}).fact_f1 == 0.7


def test_a_score_against_the_draft_key_is_provisional() -> None:
    assert score_summary({"key_version": "v1-draft", "provisional": True}).provisional is True
    assert score_summary({"key_version": "v1-draft"}).provisional is True  # from the version alone
    assert score_summary({"key_version": "v1", "provisional": False}).provisional is False


def test_a_web_run_is_live_until_its_attach_step_ends_not_its_post_steps(fresh: World) -> None:
    """The job says which step runs: the stream ends with attach, verify ... score run after it."""
    concept = fixture("concept_graph.json")
    run = RunDir.create(fresh.runs / "web", "q01-claim_off-s1-web1", concept, corpus_manifest=fresh.manifest,
                        **(SETTINGS | {"condition": "claim_off"}))
    driver = Driver(run, fresh.corpus, fresh.manifest)
    driver.model_call(1, final_answer=True)
    driver.close()
    write_json(run.answer, {"concept_sha256": run.load_config()["hashes"]["concept_sha256"], "kind": "graph", "rows": []})
    old = 1_000_000_000
    os.utime(run.events, (old, old))  # long quiet: only the job can make it live
    states = {"run": "done", "attach": "pending", "verify": "pending", "score": "pending"}
    runs = Runs(fresh.settings, Corpus(fresh.corpus),
                job_steps=lambda run_id: (states or None) if run_id == "web~" + run.root.name else None)
    assert runs.live(run)  # the answer is there, the attach step is still to come
    states.update(attach="running")
    assert runs.live(run)
    states.update(attach="failed", verify="running")
    summary = runs.summary(run)
    assert (summary.live, summary.post_processing, summary.run_id, summary.batch) == \
        (False, True, "web~q01-claim_off-s1-web1", "web")
    (run.root / ATTACH_FILE).write_text("{}", encoding="utf-8")
    states.clear()  # what a finished job looks like to a run: no active job
    assert not runs.live(run) and not runs.summary(run).post_processing


def test_the_stream_ends_with_the_attach_step(fresh: World) -> None:
    """A claim_off run of a web job: `done` while the job still runs verify ... score."""
    concept = fixture("concept_graph.json")
    run = RunDir.create(fresh.runs / "web", "r2", concept, corpus_manifest=fresh.manifest,
                        **(SETTINGS | {"condition": "claim_off"}))
    Driver(run, fresh.corpus, fresh.manifest).close()
    write_json(run.answer, {"concept_sha256": run.load_config()["hashes"]["concept_sha256"], "kind": "graph", "rows": []})
    app = create_app(fresh.settings)
    app.state.services.runs.job_steps = lambda run_id: {"run": "done", "attach": "done", "score": "running"}
    with TestClient(app) as c:
        with c.stream("GET", "/api/runs/web~r2/stream") as response:
            got = events(response)
    assert got[-1]["event"] == "done"
