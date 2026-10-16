"""Replay (docs/earlier-work.md, build row 2.13, test C6): rebuild a run's conversation and show that the log is complete.

`agent replay <run>` rebuilds the main agent's conversation from trajectory.json (mini-swe-agent's
copy of the messages, rewritten after every step) and out/ (each command's full output), and holds
it against the hash chain in events.jsonl:

- each `ai_model_invocation` of the main research loop (agent `main`, origin `research`): the prompt
  was the first `used.messages` messages of the conversation, each as the model saw it in that call
  (below). Prepared as OrchestratorModel.query prepares them (mini's `_prepare_messages_for_api`:
  the `extra` field dropped) and hashed in canonical JSON, they must give the recorded
  `prompt_sha256`. For a call that returned, the next message is the reply and hashes to
  `response_sha256`; every reply in the trajectory is a recorded call;
- each command of the main loop (`agent_tool`): out/<file> hashes to the recorded `output_sha256`,
  and the observation the model saw for that step shows the first `output_cap_bytes` of it.

What the model saw in each call. The loop (agent/loop.py, rows 1.15 and C8) changes some messages
after the model has seen them, for good, and keeps the text first shown in the message's
`extra.original_content` (never sent: mini drops `extra`):
- observation masking and the context-full stubs turn command outputs into one-line stubs, always
  the oldest outputs first and never back. Each call record says how many outputs of its prompt
  were stubs (`custom_metadata.masked_observations`), so in that call the first that many outputs
  show their stub and the later ones the text first shown;
- after the second context-full 400 the loop shortens its earlier replies; the calls up to that
  failed call saw them whole, the later ones shortened.
A loop that overwrites a message without keeping `original_content` (the M1 loop's context-full
stubs did) leaves the calls that saw the earlier text unrebuildable, and the replay names them.

When every call matches, the log names every message the model saw, in order and byte for byte,
so the run can be shown again exactly as it happened (the trace viewer and the claim walk rely on
that). The result goes to <run>/replay.json.

The attach step of a claim_off run (row 2.5) keeps each fact's conversation in
attach-trajectory.json (agent/attach.py); its calls and commands are checked the same way, per fact
(scope `research+attach`). Calls outside both (subagents; the attach calls of a run attached before
that file existed) are counted under `skipped` and `unchecked_calls`, and `complete` is false, so such
a run replays only partly (the CLI says PARTIAL, not PASS).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes, file_sha256, sha256_hex, write_json
from .chain import verify
from .rundir import COMMAND_LIMITS, RunDir, utc_now

TRAJECTORY_FILE = "trajectory.json"
ATTACH_TRAJECTORY = "attach-trajectory.json"  # agent/attach.py ATTACH_TRAJECTORY (not imported: attach imports the loop)
REPLAY_FILE = "replay.json"
ORIGINAL = "original_content"  # extra key holding the text first shown (agent/loop.py, ResearchAgent._stub)
CONTEXT_FULL = "context_window_exceeded"  # generated.error of a call refused as too long (C8)
SHORTENED_AFTER = 2  # context-full 400s after which the loop shortens its earlier replies (ResearchAgent._overflow)


# --- what the model saw --------------------------------------------------------------------------------

@dataclass(frozen=True)
class View:
    """What one call's prompt showed of the messages the loop changed later."""
    masked: int = 0  # the oldest `masked` command outputs were stubs
    shortened: bool = False  # the earlier replies were shortened (after the second context-full 400)


def first_content(message: dict[str, Any]) -> Any:
    """The content the model saw first in this message."""
    extra = message.get("extra") or {}
    return extra[ORIGINAL] if ORIGINAL in extra else message.get("content")


def prepared(messages: list[dict[str, Any]], view: View = View()) -> list[dict[str, Any]]:
    """The messages as they went to the model in a call with this view, without `extra`."""
    out, outputs = [], 0
    for m in messages:
        extra = m.get("extra") or {}
        content = m.get("content")
        if extra.get("kind") == "observation":
            outputs += 1
            if outputs > view.masked:
                content = extra.get(ORIGINAL, content)
        elif m.get("role") == "assistant" and not view.shortened:
            content = extra.get(ORIGINAL, content)
        out.append({k: (content if k == "content" else v) for k, v in m.items() if k != "extra"})
    return out


def prompt_sha256(messages: list[dict[str, Any]], view: View = View()) -> str:
    """What OrchestratorModel.query records as prompt_sha256 for these messages in a call with this view."""
    return sha256_hex(canonical_bytes(prepared(messages, view)))


# --- the check ----------------------------------------------------------------------------------------

def is_main(record: dict[str, Any]) -> bool:
    """A record of the main research loop (not the attach step, a subagent, the batch runner)."""
    return record["agent_id"] == "main" and (record.get("custom_metadata") or {}).get("origin") == "research"


def is_attach(record: dict[str, Any]) -> bool:
    """A record of the attach step (agent/attach.py: agent main, origin attach, the fact id)."""
    return record["agent_id"] == "main" and (record.get("custom_metadata") or {}).get("origin") == "attach"


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
    previous, previous_failed, overflows = 0, False, 0
    for record in calls:
        step, n = record["step_id"], record["used"].get("messages")
        entry: dict[str, Any] = {"step": step, "task_id": record["task_id"], "status": record["status"],
                                 "messages": n, "prompt": "missing", "reply": None}
        report["steps"].append(entry)
        failed = record["status"] == "failed"
        view = View(masked=int((record.get("custom_metadata") or {}).get("masked_observations") or 0),
                    shortened=overflows >= SHORTENED_AFTER)
        if failed and (record.get("generated") or {}).get("error") == CONTEXT_FULL:
            overflows += 1  # the calls after this one saw what the loop stubbed after it
        if not isinstance(n, int) or not 0 < n <= len(messages):
            report["errors"].append(f"step {step}: the call's prompt had {n} messages, the trajectory has "
                                    f"{len(messages)}")
            continue
        # A call after one that got no reply may send the same messages again (a refused reply schema).
        if n < previous or (n == previous and not previous_failed):
            report["errors"].append(f"step {step}: {n} messages after a call with {previous}: calls out of order")
        previous, previous_failed = n, failed
        rebuilt = prompt_sha256(messages[:n], view)
        if rebuilt == record["used"].get("prompt_sha256"):
            entry["prompt"] = "match"
        else:
            entry["prompt"] = "differs"
            entry["rebuilt_sha256"] = rebuilt
            report["errors"].append(
                f"step {step}: the first {n} messages of the trajectory do not hash to the recorded prompt; a "
                f"message was changed after this call without keeping what the model saw (extra.{ORIGINAL}), "
                "or the trajectory is not the run's")
        if failed:  # e.g. the context-full 400: no reply came back
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


def _fact_of(record: dict[str, Any]) -> str:
    return str((record.get("custom_metadata") or {}).get("fact_id"))


def _check_attach(run: RunDir, path: Path, calls: list[dict[str, Any]], tools: list[dict[str, Any]], cap: int,
                  report: dict[str, Any]) -> None:
    """The attach step's calls and commands against each fact's conversation in attach-trajectory.json."""
    try:
        facts = {str(f["fact_id"]): f.get("messages") or [] for f in json.loads(path.read_text(encoding="utf-8"))["facts"]}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report["errors"].append(f"{ATTACH_TRAJECTORY}: cannot be read ({exc})")
        return
    for fact_id in dict.fromkeys(_fact_of(r) for r in [*calls, *tools]):
        messages = facts.get(fact_id)
        if messages is None:
            report["errors"].append(f"attach fact {fact_id}: no conversation in {ATTACH_TRAJECTORY}")
            continue
        _check_calls(messages, [r for r in calls if _fact_of(r) == fact_id], report)
        _check_outputs(run, messages, [r for r in tools if _fact_of(r) == fact_id], cap, report)


def replay_run(run_dir: Path) -> dict[str, Any]:
    """Rebuild and check the run's conversation; write and return replay.json's content."""
    run = RunDir(Path(run_dir))
    report: dict[str, Any] = {"schema_version": 1, "run_id": run.run_id, "replayed_at": utc_now(),
                              "scope": "research", "trajectory_sha256": None, "calls": 0, "matched": 0,
                              "commands": 0, "outputs_ok": 0, "masked": 0, "skipped": {}, "unchecked_calls": 0,
                              "steps": [], "errors": []}
    chain = verify(run.events, run.claims)
    report["errors"] += [f"chain: {e}" for e in chain.errors]
    records = _records(run)
    calls = [r for r in records if r["subtype"] == "ai_model_invocation"]
    attach_file = run.root / ATTACH_TRAJECTORY
    attached = attach_file.is_file()
    checked = (lambda r: is_main(r) or is_attach(r)) if attached else is_main
    for r in calls:
        if not checked(r):
            key = f"{r['agent_id']}/{(r.get('custom_metadata') or {}).get('origin')}"
            report["skipped"][key] = report["skipped"].get(key, 0) + 1
    report["unchecked_calls"] = sum(report["skipped"].values())
    main_calls = [r for r in calls if is_main(r)]
    attach_calls = [r for r in calls if is_attach(r)] if attached else []
    tools = [r for r in records if r["subtype"] == "agent_tool" and is_main(r)]
    attach_tools = [r for r in records if r["subtype"] == "agent_tool" and is_attach(r)] if attached else []
    report["calls"] = len(main_calls) + len(attach_calls)
    report["commands"] = len(tools) + len(attach_tools)
    try:
        cap = int(run.load_config()["command_limits"]["output_cap_bytes"])
    except (OSError, ValueError, KeyError):
        cap = COMMAND_LIMITS["output_cap_bytes"]
    trajectory = run.root / TRAJECTORY_FILE
    if not trajectory.is_file():
        report["errors"].append(f"no {TRAJECTORY_FILE}: nothing to replay")
    else:
        report["trajectory_sha256"] = file_sha256(trajectory)
        messages = json.loads(trajectory.read_text(encoding="utf-8")).get("messages", [])
        report["masked"] = sum(bool((m.get("extra") or {}).get("masked")) for m in messages)  # stubs at the end
        _check_calls(messages, main_calls, report)
        _check_outputs(run, messages, tools, cap, report)
    if attached:
        report["scope"] = "research+attach"
        report["attach_trajectory_sha256"] = file_sha256(attach_file)
        _check_attach(run, attach_file, attach_calls, attach_tools, cap, report)
    report["matched"] = sum(e["prompt"] == "match" and e["reply"] in ("match", None) for e in report["steps"])
    report["ok"] = not report["errors"] and report["matched"] == report["calls"]
    report["complete"] = report["ok"] and not report["unchecked_calls"]  # every model call of the run checked
    write_json(run.root / REPLAY_FILE, report)
    return report
