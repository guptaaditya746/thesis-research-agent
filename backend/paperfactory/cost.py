"""What a run cost (#13): paperfactory's calls.jsonl plus PaperOrchestra's call logs (work/<paper>[.redo-N].log.jsonl).

Per role, per paper, total, and a straight-line projection for N papers. Rules:
  * A call whose cost is unknown makes every sum it is part of "unknown" (the known part is given next to it).
  * A cached PaperOrchestra call cost nothing in this run; what it cost when it was made is reported as
    "usd_cached_original" (what a fresh run would pay again).
  * A failed PaperOrchestra attempt (timeout, no JSON) has no cost in the log: it is counted, not priced.
  * A step is charged to a paper when its name has the paper id as a part (tag:P, verify:P, qa:P:t, repair:P,
    worldcheck:P); everything else (world, judge validation, verifier test, leak test) is shared.
Logs renamed *.stale-N (outputs made under old settings, meta.py) are left out.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _rows(p: Path) -> list[dict[str, Any]]:
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue           # a line cut off by a stopped run
    return out


class Sum:
    def __init__(self) -> None:
        self.known, self.calls, self.unknown = 0.0, 0, 0

    def add(self, usd: float | None) -> None:
        self.calls += 1
        if usd is None:
            self.unknown += 1
        else:
            self.known += usd

    def out(self) -> dict[str, Any]:
        return {"usd": round(self.known, 4) if not self.unknown else "unknown", "usd_known": round(self.known, 4),
                "calls": self.calls, "calls_unknown_cost": self.unknown}


def writer_calls(work: Path, pid: str) -> list[dict[str, Any]]:
    """PaperOrchestra's call records for one paper (first write and redos), from its own logs."""
    logs = [work / f"{pid}.log.jsonl"] + sorted(work.glob(f"{pid}.redo-*.log.jsonl"))
    return [r for p in logs for r in _rows(p) if r.get("event") in ("call", "call_error")]


def paper_of(step: str, pids: set[str]) -> str | None:
    parts = step.split(":")
    return next((p for p in parts[1:] if p in pids), None)


def report(out_dir: Path, pids: list[str], project: list[int]) -> dict[str, Any]:
    pidset = set(pids)
    by_role: dict[str, Sum] = {}
    by_paper: dict[str, dict[str, Sum]] = {p: {} for p in pids}
    shared, total = Sum(), Sum()
    cached_original, failed_attempts = 0.0, 0

    def add(role: str, pid: str | None, usd: float | None) -> None:
        by_role.setdefault(role, Sum()).add(usd)
        total.add(usd)
        if pid is None:
            shared.add(usd)
        else:
            by_paper[pid].setdefault(role, Sum()).add(usd)
    for r in _rows(out_dir / "calls.jsonl"):
        add(r.get("role", "?"), paper_of(r.get("step", ""), pidset), r.get("cost_usd"))
    for pid in pids:
        for r in writer_calls(out_dir / "work", pid):
            if r["event"] == "call_error":
                failed_attempts += 1
            elif r.get("cached"):
                cached_original += r.get("original_cost_usd") or 0.0
            else:
                add("writer", pid, r.get("cost_usd"))
    papers = {}
    for pid, roles in by_paper.items():
        s = Sum()
        for x in roles.values():
            s.known += x.known
            s.calls += x.calls
            s.unknown += x.unknown
        papers[pid] = s.out() | {"by_role": {k: v.out() for k, v in sorted(roles.items())}}
    t = total.out()
    n = len(pids)

    def proj(k: int) -> Any:
        if not n:
            return "unknown"
        per = sum(p["usd_known"] for p in papers.values()) / n
        if t["usd"] == "unknown":
            return "unknown"
        return round(per * k + shared.known * max(1.0, k / n), 2)
    return {"usd": t["usd"], "usd_known": t["usd_known"], "calls": t["calls"],
            "calls_unknown_cost": t["calls_unknown_cost"],
            "by_role": {k: v.out() for k, v in sorted(by_role.items())},
            "per_paper": papers, "shared": shared.out(),
            "mean_per_paper_usd": round(sum(p["usd_known"] for p in papers.values()) / n, 4) if n else "unknown",
            "writer_failed_attempts_unpriced": failed_attempts,
            "usd_cached_original": round(cached_original, 4),
            "projection": {"rule": "per-paper mean x N, shared part scaled by N / papers in this run (straight line)",
                           **{str(k): proj(k) for k in project}}}
