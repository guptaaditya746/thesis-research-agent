from __future__ import annotations

import sys
from pathlib import Path

import pytest

from webapp.settings import Settings


def test_settings_from_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    for name in ("RUNS", "GOLD", "CONCEPTS", "QUESTIONS", "AGENT_ROOT", "WEBAPP_DIST", "WEBAPP_PYTHON"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CORPUS", "corpus")
    monkeypatch.setenv("GOLD", "")  # empty: unset
    monkeypatch.setenv("LITELLM_BASE_URL", "http://proxy:4000/v1")
    monkeypatch.setenv("WEBAPP_POLL_S", "0.25")
    monkeypatch.setenv("PYTHON", "/not/this/python")  # only WEBAPP_PYTHON sets the job interpreter
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-never-a-setting")
    s = Settings()
    assert (s.corpus, s.runs, s.gold) == (tmp_path / "corpus", tmp_path / "runs", tmp_path / "gold-data")
    assert s.corpus_manifest == tmp_path / "corpus" / "manifest.json" and s.jobs_dir == tmp_path / "runs" / ".jobs"
    assert (s.litellm_base_url, s.poll_s, s.python) == ("http://proxy:4000/v1", 0.25, sys.executable)
    assert "sk-never-a-setting" not in s.model_dump_json()
    assert Settings(runs="elsewhere", WEBAPP_POLL_S=1).runs == tmp_path / "elsewhere"


def test_evidence_dirs_default_under_ev(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    for name in ("EV", "CORPORA", "EV_RUNS", "SCORES", "EV_PROPOSALS", "EV_CACHE", "EV_AGENT_WORK", "EV_PROTOCOLS", "RUNS"):
        monkeypatch.delenv(name, raising=False)
    assert Settings().corpora_dir is None and Settings().ev_runs_dir is None
    monkeypatch.setenv("EV", "ev")
    monkeypatch.setenv("SCORES", "/elsewhere/scores")
    s = Settings()
    assert (s.corpora_dir, s.ev_runs_dir, s.proposals_dir) == (tmp_path / "ev" / "corpora", tmp_path / "ev" / "runs",
                                                               tmp_path / "ev" / "proposals")
    assert s.scores_dir == Path("/elsewhere/scores").resolve()
    assert (s.ev_cache_dir, s.agent_work_dir) == (tmp_path / "ev" / "cache" / "engine", tmp_path / "ev" / "agent-work")
    assert s.runs == tmp_path / "runs"   # $RUNS stays the earlier app's batch root
