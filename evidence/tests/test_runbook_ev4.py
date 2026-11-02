"""The EV4 Codex runbook (docs/runbook-ev4.md): every command it names exists, and it names the hand-back branch and
tag and never pushes `main` or `results` (plan 3 Task 15; preflight F18: synth and packbuilder lines are checked too)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from evaluation import cli as evaluation_cli
from evidence import cli as evidence_cli
from packbuilder import cli as packbuilder_cli
from synth import cli as synth_cli

REPO = Path(__file__).resolve().parents[2]
RUNBOOK = REPO / "docs/runbook-ev4.md"
MAINS = {"evidence": evidence_cli.main, "evaluate": evaluation_cli.main, "synth": synth_cli.main,
         "packbuilder": packbuilder_cli.main}
# a command at the start of a line, bare or after `uv run`, as a shell line or a code span of the runbook
COMMAND = re.compile(r"^\s*(?:[-*]\s+)?`?(?:uv run )?(evidence|evaluate|synth|packbuilder) ([a-z-]+)", re.M)


def _text() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def test_every_command_in_the_runbook_exists():
    found = set(COMMAND.findall(_text()))
    assert {tool for tool, _ in found} == set(MAINS), found      # the runbook names each of the four tools
    for tool, sub in sorted(found):
        with pytest.raises(SystemExit) as e:
            MAINS[tool]([sub, "--help"])
        assert e.value.code == 0, f"{tool} {sub}"


def test_every_uv_run_command_anywhere_in_a_line_exists():
    """`uv run <tool> <sub>` inside a line too (a pipe, a loop body, a `$( ... )`), not only at its start."""
    for tool, sub in sorted(set(re.findall(r"uv run (evidence|evaluate|synth|packbuilder) ([a-z-]+)", _text()))):
        with pytest.raises(SystemExit) as e:
            MAINS[tool]([sub, "--help"])
        assert e.value.code == 0, f"{tool} {sub}"


def test_runbook_names_branch_tag_and_never_main():
    text = _text()
    assert "results-ev4" in text and "git tag -a ev4" in text and "Never push to `main` or `results`" in text
    assert "git push origin main" not in text and "git push origin results\n" not in text


def test_runbook_checks_verify_by_exit_code_and_syncs_without_the_fetch_group():
    """verify is read by its exit code, never by grepping its JSON (Task 4 review I2); Slurm syncs without the
    heavy fetch group (F44); the first commit on results-ev4 pins reports/ to LF (F29); drug trials run names on."""
    text = _text()
    assert '"ok": true' not in text and "uv sync --locked --all-groups" not in text
    assert "uv sync --locked\n" in text and "uv sync --group fetch" in text
    assert "reports/** -text" in text
    assert "--names on" in text
