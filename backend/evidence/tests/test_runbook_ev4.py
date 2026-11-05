"""The EV4 Codex runbook (docs/runbook-ev4.md): every command it names exists, and it names the hand-back branch and
tag and never pushes `main` or `results` (plan 3 Task 15; preflight F18: synth and packbuilder lines are checked too)."""
from __future__ import annotations

import re
from pathlib import Path

import repo_paths

import pytest

from evaluation import cli as evaluation_cli
from evidence import cli as evidence_cli
from packbuilder import cli as packbuilder_cli
from synth import cli as synth_cli

REPO = repo_paths.REPO
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


def _section(title: str) -> str:
    text = _text()
    start = text.index(f"## {title}")
    nxt = text.find("\n## ", start + 1)
    return text[start:] if nxt == -1 else text[start:nxt]


def test_the_hand_back_copies_every_file_a_run_writes(tmp_path):
    """Final review I2: the hand-back copy list (section 9) names every file and folder a sealed EV4 run writes at
    its top level (names on, reason on), so a handed-back run can be replayed, re-scored and verified. The list is
    derived from a real run, so a new output file fails this test until the runbook copies it."""
    from .conftest import PROTOCOL, make_corpus, regex_run_dir
    run = regex_run_dir(make_corpus(tmp_path / "corpus"), tmp_path, PROTOCOL,
                        settings={"names": "on", "reason": "on"})
    copy = _section("9. Hand-back")
    written = sorted(p.name for p in run.iterdir())
    assert {"reason.json", "comparisons.json", "protocol.lock.json", "manifest.json", "names.json"} <= set(written)
    for name in written:
        kind = "-type d -name" if (run / name).is_dir() else "-name"
        assert re.search(rf"{kind} {re.escape(name)}(?![\w.])", copy), name


def test_losses_are_written_where_the_web_app_reads_them(tmp_path):
    """Final review I4: the web app reads `<scores root>/losses/` (webapp/evfiles.py `losses`, $SCORES on Slurm,
    reports/ev4/scores after the hand-back), so `evaluate losses` writes there and the hand-back copies it."""
    from webapp.settings import Settings
    assert Settings(EV=tmp_path).scores_dir == tmp_path / "scores"   # $SCORES=$EV/scores (slurm runbook 0.3)
    assert re.search(r'evaluate losses --scores "\$SCORES" --out "\$SCORES/losses"', _text())
    assert "-path './losses/losses.*'" in _section("9. Hand-back")


def test_the_offline_probe_asks_the_scorer_too():
    """Task 15 review I1: section 1 probes `evaluate score --question-id` beside the baselines."""
    probe = _section("1. Offline check")
    assert "evaluate rag-baseline --question-id" in probe and "evaluate score --question-id" in probe


def test_licence_stops_and_the_reasoner_note():
    text = " ".join(_text().split())   # one line: the runbook wraps at 120 characters
    assert "USER stop (licences)" in text and "USER stop (arXiv licence)" in text
    assert "licence decisions of steps 1 and 5" in text
    assert "`broader` is expected to be empty" in text and "do not replay" in text
