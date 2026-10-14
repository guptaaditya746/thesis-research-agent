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
