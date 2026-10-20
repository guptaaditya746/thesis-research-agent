"""Replay (row 2.13, C6) on runs the real loop made with a scripted model (mode unsandboxed), and on
runs written by hand the way the loop with observation masking (row 1.15) writes them."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("minisweagent")
pytest.importorskip("litellm")

import litellm  # noqa: E402

from agent import loop, replay  # noqa: E402
from agent.broker import Broker  # noqa: E402
from jsonio import canonical_bytes, sha256_hex  # noqa: E402
from agent.cli import main as cli  # noqa: E402
from agent.rundir import RunDir  # noqa: E402

from .test_loop import (bash, claim_cmd, corpus, final, go, main_script, posix_only, row,  # noqa: E402,F401
                        unique_quote)


def report_of(run_root: Path) -> dict[str, Any]:
    return json.loads((run_root / "replay.json").read_text(encoding="utf-8"))


def trajectory(run: RunDir) -> list[dict[str, Any]]:
    return json.loads((run.root / "trajectory.json").read_text(encoding="utf-8"))["messages"]


# --- the real loop -------------------------------------------------------------------------------------

@posix_only
def test_replay_rebuilds_every_call(tmp_path: Path, corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    run, _, _, model = go(tmp_path, corpus, main_script(unique_quote()))
    assert cli(["replay", str(run.root)]) == 0
    assert "PASS replay r1: 8/8 model calls rebuilt from trajectory.json, 5/5 outputs match" in capsys.readouterr().out
    report = report_of(run.root)
    assert report["ok"] and report["complete"] and report["errors"] == [] and report["skipped"] == {}
    assert (report["scope"], report["unchecked_calls"]) == ("research", 0)
    assert [(s["step"], s["prompt"], s["reply"]) for s in report["steps"]] == [(n, "match", "match") for n in range(1, 9)]
    assert report["trajectory_sha256"] and report["commands"] == report["outputs_ok"] == 5
    # The rebuilt prompts are exactly what the model was sent, and replay prepares them as mini does.
    messages = trajectory(run)
    for prompt in model.prompts:
        assert replay.prepared(messages[:len(prompt)]) == prompt
    assert replay.prepared(messages) == model._prepare_messages_for_api(messages)


@posix_only
def test_replay_finds_what_does_not_fit(tmp_path: Path, corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    run, _, _, _ = go(tmp_path, corpus, [bash("echo one"), bash("echo two"), final([row([])])])
    path = run.root / "trajectory.json"
    original = path.read_bytes()
    assert replay.replay_run(run.root)["ok"]
    # An observation edited afterwards: the calls that saw it no longer match, and it no longer shows out/.
    data = json.loads(original)
    data["messages"][3]["content"] = data["messages"][3]["content"].replace("one\n", "uno\n")
    path.write_text(json.dumps(data), encoding="utf-8")
    report = replay.replay_run(run.root)
    assert not report["ok"] and [s["prompt"] for s in report["steps"]] == ["match", "differs", "differs"]
    assert "step 1: the observation does not show the start of out/step-0001.txt" in report["errors"]
    assert cli(["replay", str(run.root)]) == 1
    assert "FAIL replay r1: 1/3 model calls" in capsys.readouterr().out
    # A reply the log does not record, and an output file changed after the run.
    data = json.loads(original)
    data["messages"][4]["content"] += " (edited)"
    path.write_text(json.dumps(data), encoding="utf-8")
    (run.out / "step-0002.txt").write_bytes(b"two!\n")
    errors = replay.replay_run(run.root)["errors"]
    assert "step 2: the reply in the trajectory is not the recorded response" in errors
    assert "step 2: out/step-0002.txt does not hash to the recorded output" in errors
    path.unlink()
    assert replay.replay_run(run.root)["errors"] == ["no trajectory.json: nothing to replay"]


@posix_only
def test_a_long_run_replays(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """More commands than the loop keeps whole (row 1.15: outputs older than the last 8 become stubs).

    With the masking loop (e2e/agent-fix) four outputs are stubs by the last call; every call that
    saw one of them whole still replays, from extra.original_content and masked_observations.
    """
    replies = [bash(claim_cmd(unique_quote()) + "; echo FIRST-OUTPUT")]
    replies += [bash(f"echo output-{n}") for n in range(2, 13)] + [final([row(["claim-000001"])])]
    run, outcome, _, _ = go(tmp_path, corpus, replies)
    assert outcome.exit_status == "submitted"
    report = replay.replay_run(run.root)
    assert report["errors"] == [] and report["ok"] and report["complete"]
    assert (report["calls"], report["matched"], report["commands"], report["outputs_ok"]) == (13, 13, 12, 12)
    if hasattr(loop, "LoopSettings"):  # the loop masks: make sure this run had stubs to replay through
        assert report["masked"] == 4


@posix_only
def test_context_full_run(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    overflow = litellm.exceptions.ContextWindowExceededError("70000 tokens > 65536", "orch-model", "openai")
    run, outcome, _, _ = go(tmp_path, corpus, [bash(claim_cmd(unique_quote())), bash("echo two"), overflow,
                                               final([row(["claim-000001"])])])
    assert outcome.exit_status == "submitted"
    report = replay.replay_run(run.root)
    steps = report["steps"]
    assert [s["status"] for s in steps] == ["finished", "finished", "failed", "finished"]
    assert steps[2]["reply"] is None
    outputs = [m for m in trajectory(run) if (m.get("extra") or {}).get("kind") == "observation"]
    if all(replay.ORIGINAL in m["extra"] for m in outputs):
        # The loop keeps what the model saw before the stubs (e2e/agent-fix): every call replays.
        assert [s["prompt"] for s in steps] == ["match"] * 4 and report["ok"]
    else:
        # The M1 loop overwrote the outputs: calls 2 and 3 saw them whole and cannot be rebuilt; replay says so.
        assert [s["prompt"] for s in steps] == ["match", "differs", "differs", "match"] and not report["ok"]
        assert [e.split(":")[0] for e in report["errors"] if "do not hash" in e] == ["step 2", "step 3"]


# --- runs written as the masking loop writes them ------------------------------------------------------

def written_like_the_loop(root: Path, script: list[str], *, keep: int, original: bool = True) -> RunDir:
    """A run directory written by hand the way the loop on e2e/agent-fix writes one (rows 1.15, C8).

    Per model call in `script`: "cmd" (a reply with a command, then its output), "refused" (the reply
    schema refused: no reply, the same messages are sent again), "overflow" (a context-full 400: every
    output becomes a stub, and after the second one the earlier replies are shortened), "final". Before
    each call the outputs older than the last `keep` become stubs. A stub keeps the text first shown
    in extra.original_content unless `original` is false; each call records how many outputs were
    stubs. Prompts are hashed from the messages as they are at that moment.
    """
    run = RunDir(root / "r1")
    run.out.mkdir(parents=True)
    run.events.touch()
    run.claims.touch()
    broker = Broker(run, corpus=None)
    messages: list[dict[str, Any]] = [{"role": "system", "content": "You research.", "extra": {}},
                                      {"role": "user", "content": "The task.", "extra": {}}]
    overflows = 0

    def stub(message: dict[str, Any], text: str, why: str = "") -> None:
        if original:
            message["extra"].setdefault(replay.ORIGINAL, message["content"])
        message["content"] = text
        if why:
            message["extra"]["masked"] = why

    def record(**rec: Any) -> None:
        meta = {"origin": "research", **rec.pop("custom_metadata")}
        assert broker.record({"agent_id": "main", **rec, "custom_metadata": meta})["ok"]

    for step, kind in enumerate(script, 1):
        outputs = [m for m in messages if m["extra"].get("kind") == "observation"]
        for m in outputs[:-keep]:
            if not m["extra"].get("masked"):
                stub(m, f"[Output of step {m['extra']['step_id']} removed to save context]", "masked")
        meta = {"masked_observations": sum(bool(m["extra"].get("masked")) for m in outputs)}
        used = {"prompt_sha256": sha256_hex(canonical_bytes([{k: v for k, v in m.items() if k != "extra"}
                                                             for m in messages])), "messages": len(messages)}
        if kind in ("refused", "overflow"):
            error = "guided_decoding_rejected" if kind == "refused" else replay.CONTEXT_FULL
            record(subtype="ai_model_invocation", step_id=step, used=used, generated={"error": error},
                   status="failed", custom_metadata=meta)
            if kind == "overflow":
                overflows += 1
                for m in outputs:
                    if not m["extra"].get("masked"):
                        stub(m, "[output removed: context full]", "context_full")
                for m in messages[2:] if overflows == 2 else []:
                    if m["role"] == "assistant":
                        stub(m, "[reply shortened: context full]")
                messages.append({"role": "user", "content": "Context full. Conclude now.", "extra": {"kind": "conclude"}})
            continue
        reply = f"Reply {step}."
        record(subtype="ai_model_invocation", step_id=step, used=used,
               generated={"response_sha256": sha256_hex(reply.encode("utf-8"))}, custom_metadata=meta)
        messages.append({"role": "assistant", "content": reply, "extra": {}})
        if kind == "cmd":
            data, name = f"output of step {step}\n".encode("utf-8"), f"out/step-{step:04d}.txt"
            (run.root / name).write_bytes(data)
            record(subtype="agent_tool", step_id=step, used={"command": f"echo {step}"},
                   generated={"output_file": name, "output_sha256": sha256_hex(data)}, custom_metadata={})
            messages.append({"role": "user", "content": f"<returncode>0</returncode>\n<output>\n{data.decode()}</output>",
                             "extra": {"kind": "observation", "step_id": step, "output_file": name}})
    broker.close()
    (run.root / "trajectory.json").write_text(json.dumps({"messages": messages}), encoding="utf-8")
    return run


def test_masked_outputs_replay_from_what_the_loop_kept(tmp_path: Path) -> None:
    run = written_like_the_loop(tmp_path / "kept", ["cmd"] * 5 + ["refused", "final"], keep=2)
    report = replay.replay_run(run.root)
    assert report["errors"] == [] and report["ok"] and (report["matched"], report["masked"]) == (7, 3)
    assert [s["status"] for s in report["steps"]][5:] == ["failed", "finished"]  # the same prompt sent again
    # A loop that overwrites without keeping the text: the calls that saw an output whole before its stub fail.
    run = written_like_the_loop(tmp_path / "lost", ["cmd"] * 5 + ["refused", "final"], keep=2, original=False)
    report = replay.replay_run(run.root)
    assert [s["prompt"] for s in report["steps"]] == ["match"] + ["differs"] * 4 + ["match"] * 2
    assert any("without keeping what the model saw (extra.original_content)" in e for e in report["errors"])
    assert [e for e in report["errors"] if "does not show" in e] == [
        f"step {n}: the observation does not show the start of out/step-000{n}.txt" for n in (1, 2, 3)]


def test_two_context_full_overflows_replay(tmp_path: Path) -> None:
    """The first overflow stubs every output; the second also shortens the replies, which call 5 still saw whole."""
    run = written_like_the_loop(tmp_path, ["cmd", "cmd", "cmd", "overflow", "overflow", "final"], keep=8)
    messages = trajectory(run)
    assert [m["content"] for m in messages if m["role"] == "assistant"][:3] == ["[reply shortened: context full]"] * 3
    report = replay.replay_run(run.root)
    assert report["errors"] == [] and report["ok"] and report["matched"] == 6
    assert [s["reply"] for s in report["steps"]] == ["match"] * 3 + [None, None, "match"]
    # What each call saw: call 4 the whole outputs and replies, call 5 the stubs, call 6 the short replies too.
    assert "output of step 1" in json.dumps(replay.prepared(messages[:8], replay.View(masked=0)))
    assert "output of step 1" not in json.dumps(replay.prepared(messages[:9], replay.View(masked=3)))
    assert "Reply 1." in json.dumps(replay.prepared(messages[:9], replay.View(masked=3)))
    assert "Reply 1." not in json.dumps(replay.prepared(messages, replay.View(masked=3, shortened=True)))


def test_prepared_and_first_content() -> None:
    output = {"role": "user", "content": "stub", "extra": {"kind": "observation", replay.ORIGINAL: "full output"}}
    reply = {"role": "assistant", "content": "short", "extra": {replay.ORIGINAL: "the whole reply"}}
    plain = {"role": "user", "content": "notice", "extra": {"kind": "conclude"}}
    assert replay.prepared([output, reply, plain]) == [{"role": "user", "content": "full output"},
                                                       {"role": "assistant", "content": "the whole reply"},
                                                       {"role": "user", "content": "notice"}]
    assert [m["content"] for m in replay.prepared([output, reply], replay.View(masked=1, shortened=True))] == [
        "stub", "short"]
    assert replay.first_content(output) == "full output" and replay.first_content(plain) == "notice"
