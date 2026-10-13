"""Replay (milestones-1-2.md row 2.13, test C6): rebuild a run's conversation and show that the log is complete.

`agent replay <run>` rebuilds the main agent's conversation from trajectory.json (mini-swe-agent's
copy of the messages, rewritten after every step) and out/ (each command's full output), and holds
it against the hash chain in events.jsonl:

- each `ai_model_invocation` of the main research loop (agent `main`, origin `research`): the prompt
  was the first `used.messages` messages of the conversation. Prepared as OrchestratorModel.query
  prepares them (mini's `_prepare_messages_for_api`: the `extra` field dropped) and hashed in
  canonical JSON, they must give the recorded `prompt_sha256`. For a call that returned, the next
  message is the reply and hashes to `response_sha256`; every reply in the trajectory is a
  recorded call;
- each command of the main loop (`agent_tool`): out/<file> hashes to the recorded `output_sha256`,
  and the observation the model saw for that step shows the first `output_cap_bytes` of it.

When every call matches, the log names every message the model saw, in order and byte for byte,
so the run can be shown again exactly as it happened (the trace viewer and the claim walk rely on
that). The result goes to <run>/replay.json.

Messages the loop changes after the model has seen them (observation masking, row 1.15; the stubs
after a context-full 400) must keep what the model saw: `rewrite()` moves the earlier content into
extra.content_history with the last step that saw it, and the replay uses it for the calls up to
that step. A loop that overwrites without it breaks the replay of every call that saw the earlier
text; the replay reports those calls as "same messages, other content".

Calls outside the main conversation (the attach step's per-fact conversations, subagents) are not
in trajectory.json; they are counted under `skipped`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes, file_sha256, sha256_hex, write_json
from .chain import verify
from .rundir import COMMAND_LIMITS, RunDir, utc_now

TRAJECTORY_FILE = "trajectory.json"
REPLAY_FILE = "replay.json"
HISTORY = "content_history"


# --- the contract with the loop: changing a message the model has already seen ------------------------------

def rewrite(message: dict[str, Any], content: str, *, last_step: int) -> None:
    """Replace a sent message's content, keeping the old content for replay.

    `last_step` is the last step (main loop call number) whose prompt carried the old content.
    `extra` never reaches the model (mini drops it before the call), so the kept text costs no tokens.
    """
    if message.get("content") == content:
        return
    extra = message.setdefault("extra", {})
    extra.setdefault(HISTORY, []).append({"content": message.get("content"), "until_step": last_step})
    message["content"] = content


def content_at(message: dict[str, Any], step: int) -> Any:
    """The content the model saw in this message at `step`."""
    for old in (message.get("extra") or {}).get(HISTORY, []):
        if step <= old["until_step"]:
            return old["content"]
    return message.get("content")


def first_content(message: dict[str, Any]) -> Any:
    """The content the model saw first in this message."""
    history = (message.get("extra") or {}).get(HISTORY, [])
    return history[0]["content"] if history else message.get("content")


def prepared(messages: list[dict[str, Any]], step: int) -> list[dict[str, Any]]:
    """The messages as they went to the model at `step`: each as sent then, without `extra`."""
    return [{k: (content_at(m, step) if k == "content" else v) for k, v in m.items() if k != "extra"}
            for m in messages]


def prompt_sha256(messages: list[dict[str, Any]], step: int) -> str:
    """What OrchestratorModel.query records as prompt_sha256 for these messages at `step`."""
    return sha256_hex(canonical_bytes(prepared(messages, step)))


# --- the check ----------------------------------------------------------------------------------------

def is_main(record: dict[str, Any]) -> bool:
    """A record of the main research loop (not the attach step, a subagent, the batch runner)."""
    return record["agent_id"] == "main" and (record.get("custom_metadata") or {}).get("origin") == "research"


def _records(run: RunDir) -> list[dict[str, Any]]:
    out = []
    for raw in run.events.read_bytes().splitlines() if run.events.is_file() else []:
        try:
            out.append(json.loads(raw))
        except ValueError:
            break  # the chain check reports it
    return out


def _check_calls(messages: list[dict[str, Any]], calls: list[dict[str, Any]], report: dict[str, Any]) -> None:
    replies = set()
    previous = 0
    for record in calls:
        step, n = record["step_id"], record["used"].get("messages")
        entry: dict[str, Any] = {"step": step, "task_id": record["task_id"], "status": record["status"],
                                 "messages": n, "prompt": "missing", "reply": None}
        report["steps"].append(entry)
        if not isinstance(n, int) or not 0 < n <= len(messages):
            report["errors"].append(f"step {step}: the call's prompt had {n} messages, the trajectory has "
                                    f"{len(messages)}")
            continue
        if n <= previous:
            report["errors"].append(f"step {step}: {n} messages after a call with {previous}: calls out of order")
        previous = n
        rebuilt = prompt_sha256(messages[:n], step)
        if rebuilt == record["used"].get("prompt_sha256"):
            entry["prompt"] = "match"
        else:
            entry["prompt"] = "differs"
            entry["rebuilt_sha256"] = rebuilt
            report["errors"].append(
                f"step {step}: the first {n} messages of the trajectory do not hash to the recorded prompt; a "
                "message was changed after this call without keeping what the model saw (agent.replay.rewrite), "
                "or the trajectory is not the run's")
        if record["status"] == "failed":  # e.g. the context-full 400: no reply came back
            continue
        reply = messages[n] if n < len(messages) else None
        replies.add(n)
        if reply is None or reply.get("role") != "assistant":
            entry["reply"] = "missing"
            report["errors"].append(f"step {step}: no reply follows its prompt in the trajectory")
        elif sha256_hex(str(first_content(reply) or "").encode("utf-8")) != record["generated"].get("response_sha256"):
            entry["reply"] = "differs"
            report["errors"].append(f"step {step}: the reply in the trajectory is not the recorded response")
        else:
            entry["reply"] = "match"
    unlogged = [i for i, m in enumerate(messages) if m.get("role") == "assistant" and i not in replies]
    report["errors"] += [f"trajectory message {i}: a model reply no call record names" for i in unlogged]


def _check_outputs(run: RunDir, messages: list[dict[str, Any]], tools: list[dict[str, Any]], cap: int,
                   report: dict[str, Any]) -> None:
    observations = {}
    for m in messages:
        extra = m.get("extra") or {}
        if extra.get("kind") == "observation" and "step_id" in extra:
            observations[extra["step_id"]] = m
    for record in tools:
        step, generated = record["step_id"], record["generated"]
        path = run.root / str(generated.get("output_file"))
        if not path.is_file():
            report["errors"].append(f"step {step}: {generated.get('output_file')} is missing")
            continue
        data = path.read_bytes()
        problems = []
        if sha256_hex(data) != generated.get("output_sha256"):
            problems.append(f"step {step}: {generated['output_file']} does not hash to the recorded output")
        seen = observations.get(step)
        if seen is None:
            problems.append(f"step {step}: the trajectory has no observation for the command")
        elif data[:cap].decode("utf-8", errors="replace") not in str(first_content(seen)):
            problems.append(f"step {step}: the observation does not show the start of {generated['output_file']}")
        report["errors"] += problems
        report["outputs_ok"] += not problems
    report["errors"] += [f"step {s}: an observation no command record names" for s in sorted(
        set(observations) - {r["step_id"] for r in tools})]


def replay_run(run_dir: Path) -> dict[str, Any]:
    """Rebuild and check the run's conversation; write and return replay.json's content."""
    run = RunDir(Path(run_dir))
    report: dict[str, Any] = {"schema_version": 1, "run_id": run.run_id, "replayed_at": utc_now(),
                              "trajectory_sha256": None, "calls": 0, "matched": 0, "commands": 0, "outputs_ok": 0,
                              "skipped": {}, "steps": [], "errors": []}
    chain = verify(run.events, run.claims)
    report["errors"] += [f"chain: {e}" for e in chain.errors]
    records = _records(run)
    calls = [r for r in records if r["subtype"] == "ai_model_invocation"]
    for r in calls:
        if not is_main(r):
            key = f"{r['agent_id']}/{(r.get('custom_metadata') or {}).get('origin')}"
            report["skipped"][key] = report["skipped"].get(key, 0) + 1
    main_calls = [r for r in calls if is_main(r)]
    tools = [r for r in records if r["subtype"] == "agent_tool" and is_main(r)]
    report["calls"], report["commands"] = len(main_calls), len(tools)
    trajectory = run.root / TRAJECTORY_FILE
    if not trajectory.is_file():
        report["errors"].append(f"no {TRAJECTORY_FILE}: nothing to replay")
    else:
        report["trajectory_sha256"] = file_sha256(trajectory)
        messages = json.loads(trajectory.read_text(encoding="utf-8")).get("messages", [])
        try:
            cap = int(run.load_config()["command_limits"]["output_cap_bytes"])
        except (OSError, ValueError, KeyError):
            cap = COMMAND_LIMITS["output_cap_bytes"]
        _check_calls(messages, main_calls, report)
        _check_outputs(run, messages, tools, cap, report)
    report["matched"] = sum(e["prompt"] == "match" and e["reply"] in ("match", None) for e in report["steps"])
    report["ok"] = not report["errors"] and report["matched"] == report["calls"]
    write_json(run.root / REPLAY_FILE, report)
    return report
