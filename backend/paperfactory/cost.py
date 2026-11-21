"""What a run cost (#13): paperfactory's calls.jsonl plus PaperOrchestra's call logs (work/<paper>[.redo-N].log.jsonl).

Per role, per paper, total, and a straight-line projection for N papers. Rules:
  * A call whose cost is unknown makes every sum it is part of "unknown" (the known part is given next to it).
  * A cached PaperOrchestra call cost nothing in this run; what it cost when it was made is reported as
    "usd_cached_original" (what a fresh run would pay again).
  * A failed PaperOrchestra attempt (timeout, no JSON) has no cost in the log: it is counted, not priced.
  * A step is charged to a paper when its name has the paper id as a part (tag:P, verify:P, qa:P:t, repair:P,
    worldcheck:P); everything else (world, judge validation, verifier test, leak test) is shared.
Logs renamed *.stale-N (outputs made under old settings, meta.py) are left out.

Two views (review finding 4):
  spent     every logged paid call of every run in this folder: the money really spent.
  one_pass  each distinct call (cache key) once, at what it cost when it was made: what one clean run of the
            current outputs costs. Per paper, per role and the projection use this view. Rows without a key (logs
            from before) count as distinct calls.
A failed writer attempt (review finding 5) has no cost in PaperOrchestra's log: it is unknown, unless the writer is
a local model (cost 0).
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


def report(out_dir: Path, pids: list[str], project: list[int], writer_local: bool = False) -> dict[str, Any]:
    pidset = set(pids)
    rows: list[tuple[str, str | None, str | None, float | None]] = []      # (role, paper, key, cost)
    cached_original, failed_attempts = 0.0, 0
    for r in _rows(out_dir / "calls.jsonl"):
        rows.append((r.get("role", "?"), paper_of(r.get("step", ""), pidset), r.get("key"), r.get("cost_usd")))
    for pid in pids:
        for r in writer_calls(out_dir / "work", pid):
            if r["event"] == "call_error":
                failed_attempts += 1
                rows.append(("writer", pid, None, 0.0 if writer_local else None))
            elif r.get("cached"):
                cached_original += r.get("original_cost_usd") or 0.0
                # not spent in this run; in one_pass it stands for the call that made the cached answer
                rows.append(("writer-cached", pid, "po:" + r["key"] if r.get("key") else None,
                             r.get("original_cost_usd")))
            else:
                rows.append(("writer", pid, "po:" + str(r.get("key")) if r.get("key") else None, r.get("cost_usd")))

    def view(rs: list[tuple[str, str | None, str | None, float | None]]) -> dict[str, Any]:
        by_role: dict[str, Sum] = {}
        by_paper: dict[str, dict[str, Sum]] = {p: {} for p in pids}
        shared, total = Sum(), Sum()
        for role, pid, _, usd in rs:
            by_role.setdefault(role, Sum()).add(usd)
            total.add(usd)
            (shared if pid is None else by_paper[pid].setdefault(role, Sum())).add(usd)
        papers = {}
        for pid, roles in by_paper.items():
            s_ = Sum()
            for x in roles.values():
                s_.known, s_.calls, s_.unknown = s_.known + x.known, s_.calls + x.calls, s_.unknown + x.unknown
            papers[pid] = s_.out() | {"by_role": {k: v.out() for k, v in sorted(roles.items())}}
        return {"total": total.out(), "by_role": {k: v.out() for k, v in sorted(by_role.items())},
                "per_paper": papers, "shared": shared.out()}

    spent = view([r for r in rows if r[0] != "writer-cached"])
    seen: dict[str, tuple] = {}
    distinct = []
    for r in rows:
        role = "writer" if r[0] == "writer-cached" else r[0]
        if r[2] is None:
            distinct.append((role, *r[1:]))
        elif r[2] not in seen or (seen[r[2]][3] is None and r[3] is not None):
            seen[r[2]] = (role, *r[1:])
    one = view(distinct + list(seen.values()))
    n = len(pids)
    known_pp = [p["usd_known"] for p in one["per_paper"].values()]
    unknown = one["total"]["usd"] == "unknown"

    def proj(k: int) -> Any:
        if not n or unknown:
            return "unknown"
        return round(sum(known_pp) / n * k + one["shared"]["usd_known"] * max(1.0, k / n), 2)
    t = spent["total"]
    return {"usd": t["usd"], "usd_known": t["usd_known"], "calls": t["calls"],
            "calls_unknown_cost": t["calls_unknown_cost"], "spent": spent, "one_pass": one,
            "by_role": one["by_role"], "per_paper": one["per_paper"], "shared": one["shared"],
            "mean_per_paper_usd": round(sum(known_pp) / n, 4) if n and not unknown else "unknown",
            "writer_failed_attempts": failed_attempts, "usd_cached_original": round(cached_original, 4),
            "projection": {"rule": "one_pass: per-paper mean x N, shared part scaled by N / papers in this run "
                                   "(straight line)", **{str(k): proj(k) for k in project}}}
