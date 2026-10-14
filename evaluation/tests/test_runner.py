"""ResearchAgentRunner attempts: a rerun into the same work directory must not collide (review item 5)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("minisweagent")

import agent.loop  # noqa: E402
from evaluation.baselines import agent as baseline  # noqa: E402
from evidence.agentic.runner import AgentJob, AgentSettings, ResearchAgentRunner  # noqa: E402

from . import fixtures as fx  # noqa: E402
from .helpers import Scripted  # noqa: E402


def fake_research_run(**kw: Any) -> tuple[Any, Any, dict]:
    """As agent.loop.research_run creates its run directory: refusing one that exists (agent/rundir.py)."""
    root = Path(kw["runs_root"]) / kw["run_id"]
    root.mkdir(parents=True, exist_ok=False)
    for name in ("events.jsonl", "claims.jsonl"):
        (root / name).touch()
    (root / "answer.json").write_text(json.dumps({"rows": [], "notes": ""}), encoding="utf-8")
    return SimpleNamespace(root=root), agent.loop.Outcome("submitted", 1, 1, 10, 0, "final"), {}


def test_rerun_into_the_same_work_dir_gets_a_fresh_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent.loop, "research_run", fake_research_run)
    runner = ResearchAgentRunner(AgentSettings(sandbox_mode="unsandboxed"), work_dir=tmp_path)
    job = AgentJob(run_id="agentic-0123456789abcdef", files={"S001.md": fx.S001}, concept={})
    first, second = runner.run(job), runner.run(job)
    assert first["run_id"] == second["run_id"] == job.run_id  # the record does not name the attempt directory
    assert first == second
    assert len(list(tmp_path.iterdir())) == 2


def test_agent_baseline_failure_is_redacted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-secret-key-1234")

    class Failing:
        def run(self, job: AgentJob) -> dict:
            raise ConnectionError("proxy refused key sk-secret-key-1234")

    with pytest.raises(RuntimeError) as err:
        baseline.agent_baseline(fx.write_corpus(tmp_path), runner=Failing(), model=Scripted({}).model())
    assert "sk-secret" not in str(err.value) and "agent run failed: ConnectionError" in str(err.value)
