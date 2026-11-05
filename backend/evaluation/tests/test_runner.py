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


MODELS: list[Any] = []  # the model each fake research_run was given


def fake_research_run(**kw: Any) -> tuple[Any, Any, dict]:
    """As agent.loop.research_run creates its run directory: refusing one that exists (agent/rundir.py)."""
    MODELS.append(kw["model"])
    root = Path(kw["runs_root"]) / kw["run_id"]
    root.mkdir(parents=True, exist_ok=False)
    for name in ("events.jsonl", "claims.jsonl"):
        (root / name).touch()
    (root / "answer.json").write_text(json.dumps({"rows": [], "notes": ""}), encoding="utf-8")
    return SimpleNamespace(root=root), agent.loop.Outcome("submitted", 1, 1, 10, 0, "final"), {}


def test_runner_builds_the_agents_model_on_settings_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Part G.3: AgentSettings.model is the alias the agent calls, with the pinned name and revision of a
    pinned alias; orch-model gives what research_run builds by itself."""
    from agent.rundir import ORCHESTRATOR, SUBAGENTS

    monkeypatch.setattr(agent.loop, "research_run", fake_research_run)
    MODELS.clear()
    job = AgentJob(run_id="agentic-0123456789abcdef", files={"S001.md": fx.S001}, concept={})
    ResearchAgentRunner(AgentSettings(sandbox_mode="unsandboxed"), work_dir=tmp_path).run(job)
    ResearchAgentRunner(AgentSettings(sandbox_mode="unsandboxed", model="sub-model-1", base_url="http://x/v1",
                                      temperature=0.2, seed=9), work_dir=tmp_path).run(job)
    ResearchAgentRunner(AgentSettings(sandbox_mode="unsandboxed", model="other"), work_dir=tmp_path).run(job)
    orch, sub, other = MODELS
    assert all(isinstance(m, agent.loop.OrchestratorModel) for m in MODELS)
    default = agent.loop.OrchestratorModel(temperature=0.7, seed=1234)
    assert orch.settings == default.settings and orch.config.model_name == "openai/orch-model"
    assert orch.settings["model_name"] == ORCHESTRATOR["name"] and orch.context_tokens == ORCHESTRATOR["context_tokens"]
    assert sub.config.model_name == "openai/sub-model-1" and sub.base_url == "http://x/v1"
    assert (sub.settings["model"], sub.settings["model_name"], sub.settings["revision"], sub.settings["temperature"],
            sub.settings["seed"]) == ("sub-model-1", SUBAGENTS[0]["name"], SUBAGENTS[0]["revision"], 0.2, 9)
    assert sub.context_tokens == SUBAGENTS[0]["context_tokens"]
    assert (other.settings["model"], other.settings["model_name"], other.settings["revision"]) == (
        "other", "other", "unpinned")


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
