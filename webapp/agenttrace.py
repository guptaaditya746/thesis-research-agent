"""The research agent's records as the viewer shows an agent's trace (the agentic extractor's calls, the agent
baseline): one Step per (agent, step id) and the claims, read from the files the agent writes (agent/rundir.py
layout). A command's output file is read only inside the agent's run directory."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.rundir import RunDir
from agent.timeline import HEAD_LINES

from .files import NotFound, inside
from .models import Anchor, Claim, ClaimRef, ModelCall, Step

HEAD_BYTES = 4096


def paper_of(file: str | None) -> str | None:
    if not file:
        return None
    name = Path(str(file).replace("\\", "/")).name
    return name[:-3] if name.endswith(".md") else name


def claim_of(record: dict[str, Any]) -> Claim:
    meta, used = record.get("custom_metadata") or {}, record.get("used") or {}
    accepted = record.get("status") == "accepted"
    anchor = used.get("anchor") if accepted else None
    file = anchor["file"] if anchor else used.get("file")
    return Claim(claim_id=(record.get("generated") or {}).get("claim_id"), task_id=record["task_id"],
                 status="accepted" if accepted else "rejected", reason=meta.get("reason"),
                 s=meta.get("s"), p=meta.get("p"), o=meta.get("o"), file=file, paper_id=paper_of(file),
                 quote=anchor["exact"] if anchor else (meta.get("quote") or used.get("quote")),
                 quote_submitted=meta.get("quote"), step=record["step_id"], agent_id=record["agent_id"],
                 origin=meta.get("origin", "research"),
                 anchor=Anchor(start=anchor["start"], end=anchor["end"]) if anchor else None)


def output_head(run: RunDir, name: str | None) -> str | None:
    """The first HEAD_LINES lines (at most HEAD_BYTES) of a command's output file."""
    if not name:
        return None
    try:
        with open(inside(run.root, name), "rb") as fh:
            data = fh.read(HEAD_BYTES)
    except (OSError, NotFound):
        return None
    return "\n".join(data.decode("utf-8", errors="replace").splitlines()[:HEAD_LINES])


def steps_of(run: RunDir, records: list[dict[str, Any]]) -> list[Step]:
    """One Step per (agent, step id), in chain order: its model call, command, claims, coverage, spawns."""
    steps: dict[tuple[str, int], dict[str, Any]] = {}
    for r in records:
        key = (r.get("agent_id") or "main", int(r.get("step_id", 0)))
        meta, used, gen = r.get("custom_metadata") or {}, r.get("used") or {}, r.get("generated") or {}
        step = steps.setdefault(key, {"step": key[1], "agent_id": key[0], "origin": meta.get("origin", "research"),
                                      "claims": [], "coverage": [], "spawned": [], "times": []})
        step["times"] += [t for t in (r.get("started_at"), r.get("ended_at")) if t]
        if meta.get("fact_id"):
            step["fact_id"] = meta["fact_id"]
        kind = r.get("subtype")
        if kind == "ai_model_invocation":
            usage = gen.get("usage") or {}
            step["phase"] = meta.get("phase")
            step["model_call"] = ModelCall(
                task_id=r["task_id"], status=r.get("status", "finished"), tokens=usage.get("total_tokens"),
                prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
                seconds=meta.get("seconds"), parse=gen.get("parse"), reply=gen.get("reply"),
                finish_reason=gen.get("finish_reason"), final_answer=bool(meta.get("final_answer")),
                error=gen.get("error"))
        elif kind == "agent_tool":
            step.update(command=used.get("command"), exit_code=gen.get("exit_code"),
                        timed_out=bool(gen.get("timed_out")), output_bytes=gen.get("output_bytes"),
                        output_file=gen.get("output_file"), output_head=output_head(run, gen.get("output_file")),
                        repeat=meta.get("repeat"))
            step.setdefault("phase", meta.get("phase"))
        elif kind == "claim":
            step["claims"].append(ClaimRef(claim_id=gen.get("claim_id"), status="accepted" if r.get("status") == "accepted"
                                           else "rejected", reason=meta.get("reason"), s=meta.get("s"),
                                           p=meta.get("p"), o=meta.get("o")))
        elif kind == "coverage":
            step["coverage"].append(str(gen.get("reason")))
        elif kind == "spawn" and isinstance(gen.get("agent_id"), str):
            step["spawned"].append(gen["agent_id"])
    out = []
    for step in steps.values():
        times = step.pop("times")
        out.append(Step(**step, started_at=min(times, default=None), ended_at=max(times, default=None)))
    return out
