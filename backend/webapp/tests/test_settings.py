from __future__ import annotations

import sys
from pathlib import Path

import repo_paths

import pytest

from webapp.settings import REPO, Settings


def test_settings_from_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    for name in ("EV", "AGENT_ROOT", "WEBAPP_DIST", "WEBAPP_PYTHON", "WEBAPP_USER", "EV_QUESTIONS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AGENT_ROOT", "")  # empty: unset
    monkeypatch.setenv("LITELLM_BASE_URL", "http://proxy:4000/v1")
    monkeypatch.setenv("WEBAPP_MODEL_JOBS", "2")
    monkeypatch.setenv("PYTHON", "/not/this/python")  # only WEBAPP_PYTHON sets the job interpreter
    monkeypatch.setenv("USER", "not-this-one")       # only WEBAPP_USER (else the login name) sets `by`
    monkeypatch.setenv("WEBAPP_USER", "aditya")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-never-a-setting")
    s = Settings()
    assert (s.agent_root, s.litellm_base_url, s.python, s.model_jobs, s.cpu_jobs) == (
        None, "http://proxy:4000/v1", sys.executable, 2, 2)
    assert s.user == "aditya" and s.questions == repo_paths.DOMAINS / "rag" / "questions.yaml"
    assert s.jobs_dir is None   # no jobs without $EV
    assert "sk-never-a-setting" not in s.model_dump_json()
    assert Settings(EV="ev").jobs_dir == tmp_path / "ev" / ".jobs"   # type: ignore[call-arg]


@pytest.mark.parametrize("name", ["model", "", "   ", " model "])
def test_the_user_is_never_the_model_nor_blank(name: str) -> None:
    with pytest.raises(ValueError, match="WEBAPP_USER"):
        Settings(WEBAPP_USER=name)  # type: ignore[call-arg]
    assert Settings(WEBAPP_USER=" aditya ").user == "aditya"  # type: ignore[call-arg]


def test_evidence_dirs_default_under_ev(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    for name in ("EV", "CORPORA", "EV_RUNS", "SCORES", "EV_PROPOSALS", "EV_CACHE", "EV_AGENT_WORK", "EV_PROTOCOLS",
                 "EVIDENCE_AGENT_WORK_DIR"):
        monkeypatch.delenv(name, raising=False)
    assert Settings().corpora_dir is None and Settings().ev_runs_dir is None and Settings().cache_root is None
    monkeypatch.setenv("EV", "ev")
    monkeypatch.setenv("SCORES", "/elsewhere/scores")
    s = Settings()
    assert (s.corpora_dir, s.ev_runs_dir, s.proposals_dir) == (tmp_path / "ev" / "corpora", tmp_path / "ev" / "runs",
                                                               tmp_path / "ev" / "proposals")
    assert s.scores_dir == Path("/elsewhere/scores").resolve()
    assert (s.ev_cache_dir, s.agent_work_dir) == (tmp_path / "ev" / "cache" / "engine", tmp_path / "ev" / "agent-work")
    assert s.cache_root == tmp_path / "ev" / "cache" and s.jobs_dir == tmp_path / "ev" / ".jobs"
