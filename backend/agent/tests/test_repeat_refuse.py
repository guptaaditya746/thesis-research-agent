"""Prompt v3: a repeated command is refused, not run, and research goes on (EV3 fixes, task 3).

In EV3 three hard-set agent runs ended after 9-15 steps because the sixth identical command in a
row ended research (v2's `repeats`), and scored 0. Under v3 (`repeat_action` "refuse") the sixth
and later identical commands are not run: a `command_refused` coverage record and a notice
instead, the step counts toward the budget, and research goes on until the budget or an answer.
v2 keeps ending research (test_loop_v2.test_six_identical_commands_end_research, and below).
Same harness as test_loop: everything but the model's HTTP call is real.
"""
from __future__ import annotations

import json
from pathlib import Path

import repo_paths
from typing import Any

import pytest

pytest.importorskip("minisweagent")
pytest.importorskip("litellm")

from agent import schema  # noqa: E402
from agent.loop import LEGACY_V1, LoopSettings, settings_for  # noqa: E402
from agent.rundir import RunDir  # noqa: E402

from .test_loop import Reply, bash, corpus, final, go, posix_only, records, row  # noqa: E402, F401

REPO_M1 = repo_paths.TESTS / "M1-real"


def tools_of(run: RunDir) -> list[dict[str, Any]]:
    return [r for r in records(run) if r["subtype"] == "agent_tool"]


def refused_of(run: RunDir) -> list[dict[str, Any]]:
    return [r for r in records(run) if r["subtype"] == "coverage" and r["generated"]["reason"] == "command_refused"]


# --- settings and config (any OS) ----------------------------------------------------------------------

def test_config_has_repeat_action_only_for_refuse() -> None:
    """v3 is v2's loop with repeat_action "refuse"; the key is in config.json only then, so v2's config stays as it was."""
    assert settings_for("v3") == LoopSettings(repeat_action="refuse")
    assert settings_for("v2") == LoopSettings() and LoopSettings().repeat_action == "end"
    assert "repeat_action" not in LoopSettings().config() and "repeat_action" not in LEGACY_V1.config()
    refuse = LoopSettings(repeat_action="refuse").config()
    assert refuse == LoopSettings().config() | {"repeat_action": "refuse"}
    base = json.loads((REPO_M1 / "c3-on-2" / "config.json").read_text(encoding="utf-8"))
    config = base | {"loop": {"harness": "mini-swe-agent 2.4.6", "base_url": "x", **refuse}}
    assert schema.check("config", config) == []
    assert schema.check("config", base | {"loop": {**config["loop"], "repeat_action": "end"}})  # never written
    with pytest.raises(ValueError):
        LoopSettings(repeat_action="skip")


# --- the loop (POSIX) ----------------------------------------------------------------------------------

@posix_only
def test_v3_refuses_sixth_repeat(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    replies: list[Reply] = [bash('ls "$CORPUS"')] * 7 + [final([row([])])]
    run, outcome, _, model = go(tmp_path, corpus, replies, prompt_version="v3")
    assert outcome.exit_status == "submitted" and outcome.steps == 8
    assert [t["custom_metadata"]["repeat"] for t in tools_of(run)] == [1, 2, 3, 4, 5]  # the sandbox ran it 5 times
    assert [r["generated"]["detail"] for r in refused_of(run)] == [{"repeats": 6}, {"repeats": 7}]
    assert run.load_config()["loop"]["repeat_action"] == "refuse"
    assert "From 6 in a row it is not run." in model.prompts[3][-1]["content"]  # after the 3rd
    sixth = model.prompts[6][-1]["content"]
    assert sixth.startswith("[Not run: this is the same command 6 times in a row, and its output would not change. "
                            "Run a different command or give your answer.]")
    assert "[Budget: 6 of" in sixth  # the refused step counts toward the budget
    assert all(c["custom_metadata"]["phase"] == "research"
               for c in records(run) if c["subtype"] == "ai_model_invocation")


@posix_only
def test_refused_command_stays_refused_until_changed(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    replies: list[Reply] = ([bash('ls "$CORPUS"')] * 6 + [bash("echo other"), bash('ls "$CORPUS"')]
                            + [final([row([])])])
    run, outcome, _, _ = go(tmp_path, corpus, replies, prompt_version="v3")
    assert outcome.exit_status == "submitted"
    tools = tools_of(run)
    assert [t["used"]["command"] for t in tools[-2:]] == ["echo other", 'ls "$CORPUS"']  # both ran
    assert [t["custom_metadata"]["repeat"] for t in tools] == [1, 2, 3, 4, 5, 1, 1]  # the count starts again
    assert [r["generated"]["detail"] for r in refused_of(run)] == [{"repeats": 6}]


@posix_only
def test_v2_still_ends_research_at_6(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    replies: list[Reply] = [bash('ls "$CORPUS"')] * 7 + [final([row([])])]
    run, outcome, _, model = go(tmp_path, corpus, replies, prompt_version="v2")
    assert len(tools_of(run)) == 6 and refused_of(run) == []
    assert model.prompts[6][-1]["content"].startswith("Research ended: you ran the same command 6 times in a row.")
    assert "repeat_action" not in run.load_config()["loop"]
    assert [c["generated"]["reason"] for c in records(run) if c["subtype"] == "coverage"][0] == "command_not_run"
