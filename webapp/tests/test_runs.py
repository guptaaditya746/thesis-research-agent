"""Exit status from the records (no file holds it) and the score summary."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from agent.rundir import RunDir
from webapp.runs import Digest, Runs, score_summary


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
])
def test_exit_status(tmp_path: Path, records: list[dict[str, Any]], answer: bool, live: bool, status: str) -> None:
    if answer:
        (tmp_path / "answer.json").write_text("{}", encoding="utf-8")
    assert Runs.exit_status(RunDir(tmp_path), Digest.of(records), live) == status


def test_score_summary_prefers_the_soft_fact_match() -> None:
    assert score_summary(None) is None
    assert score_summary({"facts": {"strict": {"f1": 0.2}}, "rows": {"f1": 0.5}}).model_dump() == \
        {"support_share": None, "fact_f1": 0.2, "row_f1": 0.5}
    assert score_summary({"facts": {"strict": {"f1": 0.2}, "soft": {"f1": 0.7}},
                          "support": {"support_share": 0.4}}).fact_f1 == 0.7
