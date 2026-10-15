"""The agentic extractor takes the node's paths from the environment, never into its id."""
from __future__ import annotations

from pathlib import Path

import pytest

from evidence.agentic.extractor import AgenticExtractor

CONFIG = {"evidence_type": "measurement", "links": {"condition": "condition", "metric": "metric"}}


def test_agent_root_and_work_dir_come_from_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("AGENT_ROOT", raising=False)
    monkeypatch.delenv("EVIDENCE_AGENT_WORK_DIR", raising=False)
    bare = AgenticExtractor.from_config(dict(CONFIG))
    monkeypatch.setenv("AGENT_ROOT", str(tmp_path / "root"))
    monkeypatch.setenv("EVIDENCE_AGENT_WORK_DIR", str(tmp_path / "work"))
    placed = AgenticExtractor.from_config(dict(CONFIG))
    assert placed.runner.settings.agent_root == str(tmp_path / "root")
    assert placed.runner.work_dir == tmp_path / "work"
    assert placed.spec.extractor_id == bare.spec.extractor_id
