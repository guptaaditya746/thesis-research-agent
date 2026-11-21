from __future__ import annotations

from pathlib import Path

import repo_paths

import pytest

from webapp.settings import Settings


def test_settings_from_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WEBAPP_DIST", raising=False)
    assert Settings().web_dist == repo_paths.FRONTEND / "dist"
    monkeypatch.setenv("WEBAPP_DIST", "dist")
    monkeypatch.setenv("WEBAPP_ALLOWED_HOSTS", " a , b,")
    s = Settings()
    assert s.web_dist == tmp_path / "dist" and s.hosts == ["a", "b"]
    monkeypatch.setenv("WEBAPP_DIST", "")   # empty: unset
    assert Settings().web_dist == repo_paths.FRONTEND / "dist"
