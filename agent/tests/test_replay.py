"""Replay (row 2.13, C6) on runs the real loop made with a scripted model (mode unsandboxed)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("minisweagent")
pytest.importorskip("litellm")

import litellm  # noqa: E402

from agent import replay  # noqa: E402
from agent.cli import main as cli  # noqa: E402
from agent.loop import ResearchAgent  # noqa: E402

from .test_loop import (bash, claim_cmd, corpus, final, go, main_script, posix_only, row,  # noqa: E402,F401
                        unique_quote)


def report_of(run_root: Path) -> dict[str, Any]:
    return json.loads((run_root / "replay.json").read_text(encoding="utf-8"))


@posix_only
def test_replay_rebuilds_every_call(tmp_path: Path, corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    run, _, _, model = go(tmp_path, corpus, main_script(unique_quote()))
    assert cli(["replay", str(run.root)]) == 0
    assert "PASS replay r1: 8/8 model calls rebuilt from trajectory.json, 5/5 outputs match" in capsys.readouterr().out
    report = report_of(run.root)
    assert report["ok"] and report["errors"] == [] and report["skipped"] == {}
    assert [(s["step"], s["prompt"], s["reply"]) for s in report["steps"]] == [(n, "match", "match") for n in range(1, 9)]
    assert report["trajectory_sha256"] and report["commands"] == report["outputs_ok"] == 5
    # The rebuilt prompts are exactly what the model was sent, and replay prepares them as mini does.
    messages = json.loads((run.root / "trajectory.json").read_text(encoding="utf-8"))["messages"]
    for step, prompt in enumerate(model.prompts, 1):
        assert replay.prepared(messages[:len(prompt)], step) == prompt
    assert replay.prepared(messages, 99) == model._prepare_messages_for_api(messages)


@posix_only
def test_replay_finds_what_does_not_fit(tmp_path: Path, corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    run, _, _, _ = go(tmp_path, corpus, [bash("echo one"), bash("echo two"), final([row([])])])
    trajectory = run.root / "trajectory.json"
    original = trajectory.read_bytes()
    assert replay.replay_run(run.root)["ok"]
    # An observation edited afterwards: the calls that saw it no longer match, and it no longer shows out/.
    data = json.loads(original)
    data["messages"][3]["content"] = data["messages"][3]["content"].replace("one\n", "uno\n")
    trajectory.write_text(json.dumps(data), encoding="utf-8")
    report = replay.replay_run(run.root)
    assert not report["ok"] and [s["prompt"] for s in report["steps"]] == ["match", "differs", "differs"]
    assert "step 1: the observation does not show the start of out/step-0001.txt" in report["errors"]
    assert cli(["replay", str(run.root)]) == 1
    assert "FAIL replay r1: 1/3 model calls" in capsys.readouterr().out
    # A reply the log does not record, and an output file changed after the run.
    data = json.loads(original)
    data["messages"][4]["content"] += " (edited)"
    trajectory.write_text(json.dumps(data), encoding="utf-8")
    (run.out / "step-0002.txt").write_bytes(b"two!\n")
    errors = replay.replay_run(run.root)["errors"]
    assert "step 2: the reply in the trajectory is not the recorded response" in errors
    assert "step 2: out/step-0002.txt does not hash to the recorded output" in errors
    trajectory.unlink()
    assert replay.replay_run(run.root)["errors"] == ["no trajectory.json: nothing to replay"]


@posix_only
@pytest.mark.parametrize("keep", [True, False])
def test_masked_messages_replay_only_when_kept(tmp_path: Path, corpus: tuple[Path, Path],
                                               monkeypatch: pytest.MonkeyPatch, keep: bool) -> None:
    """Observation masking (row 1.15) changes messages the model has seen; replay needs replay.rewrite()."""
    query = ResearchAgent.query

    def masking_query(self: ResearchAgent) -> dict[str, Any]:
        seen = [m for m in self.messages if (m.get("extra") or {}).get("kind") == "observation"]
        for m in seen[:-1]:  # every output but the newest becomes a stub
            stub = f"[output of step {m['extra']['step_id']} masked]"
            if keep:
                replay.rewrite(m, stub, last_step=self.n_calls)
            else:
                m["content"] = stub
        return query(self)

    monkeypatch.setattr(ResearchAgent, "query", masking_query)
    run, outcome, _, model = go(tmp_path, corpus, [bash("echo one"), bash("echo two"), bash("echo three"),
                                                   final([row([])])])
    assert outcome.exit_status == "submitted"
    assert model.prompts[3][3]["content"] == "[output of step 1 masked]"  # what step 4 was sent
    report = replay.replay_run(run.root)
    if keep:
        assert report["ok"] and report["matched"] == 4
        history = json.loads((run.root / "trajectory.json").read_text(encoding="utf-8"))["messages"][3]["extra"]
        assert history[replay.HISTORY][0]["until_step"] == 2 and "one" in history[replay.HISTORY][0]["content"]
    else:
        assert [s["prompt"] for s in report["steps"]] == ["match", "differs", "differs", "match"]
        assert not report["ok"] and any("without keeping what the model saw" in e for e in report["errors"])


def test_rewrite_and_content_at() -> None:
    message = {"role": "user", "content": "full output", "extra": {"kind": "observation"}}
    replay.rewrite(message, "stub", last_step=4)
    replay.rewrite(message, "stub", last_step=6)  # no change: nothing kept
    replay.rewrite(message, "", last_step=9)
    assert [replay.content_at(message, s) for s in (2, 4, 5, 9, 10)] == ["full output", "full output", "stub", "stub", ""]
    assert replay.first_content(message) == "full output"
    assert replay.prepared([message], 3) == [{"role": "user", "content": "full output"}]


@posix_only
def test_context_full_run(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    overflow = litellm.exceptions.ContextWindowExceededError("70000 tokens > 65536", "orch-model", "openai")
    run, outcome, _, _ = go(tmp_path, corpus, [bash(claim_cmd(unique_quote())), bash("echo two"), overflow,
                                               final([row(["claim-000001"])])])
    assert outcome.exit_status == "submitted"
    steps = replay.replay_run(run.root)["steps"]
    assert [s["status"] for s in steps] == ["finished", "finished", "failed", "finished"]
    assert steps[0]["prompt"] == steps[3]["prompt"] == "match" and steps[2]["reply"] is None
    # Calls 2 and 3 saw the outputs before the overflow stubbed them: they replay once the loop keeps
    # what the model saw (replay.rewrite); until then replay says which calls cannot be rebuilt.
    errors = replay.replay_run(run.root)["errors"]
    for s in steps[1:3]:
        assert s["prompt"] == "match" or any(e.startswith(f"step {s['step']}: the first") for e in errors)
