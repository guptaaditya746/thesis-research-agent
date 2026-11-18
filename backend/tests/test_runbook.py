"""docs/runbook-slurm.md (the Codex runbook): every `uv run <tool> <sub>` it names exists, and every repo path it
names in backticks under backend/, data/ or scripts/ is there (a folder move must update the runbook)."""
from __future__ import annotations

import re

import pytest

import repo_paths
from evaluation import cli as evaluation_cli
from evidence import cli as evidence_cli
from synth import cli as synth_cli
from synth3 import cli as synth3_cli

RUNBOOK = repo_paths.REPO / "docs" / "runbook-slurm.md"
MAINS = {"evidence": evidence_cli.main, "evaluate": evaluation_cli.main, "synth": synth_cli.main,
         "synth3": synth3_cli.main}


def _text() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def test_every_uv_run_command_exists() -> None:
    found = sorted(set(re.findall(r"uv run (evidence|evaluate|synth3|synth) ([a-z][a-z-]*)", _text())))
    assert {tool for tool, _ in found} == set(MAINS)
    for tool, sub in found:
        with pytest.raises(SystemExit) as e:
            MAINS[tool]([sub, "--help"])
        assert e.value.code == 0, f"{tool} {sub}"


def test_named_repo_paths_exist() -> None:
    repo_part = _text().split("## Codex:")[0]   # the Codex prompt names cluster folders (data/real), not repo ones
    paths = set(re.findall(r"(?<![\w/$.-])((?:backend|data|scripts)/[\w./-]+?)(?=[`\s\"']|$)", repo_part, re.M))
    missing = sorted(p for p in paths if "<" not in p and "*" not in p and "tuned" not in p
                     and not (repo_paths.REPO / p.rstrip(".")).exists())
    assert missing == []
