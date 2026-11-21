"""`evqa compare <run_dir>...`: one Markdown report that puts finished runs side by side (no LLM).

    uv run python -m evqa.compare runs/evqa/a runs/evqa/b [--out runs/evqa/compare-2026-11-21.md]

Part 1, every run: the eval.json totals per layer and per question type, plus LLM requests / real calls / cache
hits / tokens / seconds per question (from events.jsonl: the "end" event of each step carries
`seconds` and `llm = {requests, calls, cache_hits}`, see run.py `_do`). Tokens are not recorded anywhere yet
(lm.py keeps only the reply text, the LLM cache stores no usage), so they print as "n/a".

Part 2, the per-question differences: practice runs only. A run whose config.yaml split is not "practice", or
whose name (config name or folder name) starts with bench- or holdout-, is left out of part 2, and none of its
per-question data is read: from eval.json only "totals" is used, from events.jsonl only sums over all questions.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from evqa.paths import REPO

LAYERS = ["questions", "answerable", "facts", "l0", "l1", "l2_recall", "l2_precision", "l2_name_ok", "l3",
          "l3_exact", "advisor"]
NOT_REPORTED = ["accuracy", "hallucination", "near_miss_trap"]
TYPE_KEYS = ["questions", "l3", "exact", "advisor"]
PER_Q = [("l3", ("l3", "score")), ("l2 recall", ("l2", "recall")), ("l2 precision", ("l2", "precision")),
         ("advisor", ("advisor", "score"))]
LOCKED_PREFIXES = ("bench-", "holdout-")
NA = "n/a"


class Run:
    def __init__(self, path: Path) -> None:
        self.path = path
        conf = path / "config.yaml"
        self.config: dict[str, Any] = (yaml.safe_load(conf.read_text(encoding="utf-8")) or {}) if conf.is_file() else {}
        self.name = str(self.config.get("name") or path.name)
        self.label = path.name

    def per_question_allowed(self) -> tuple[bool, str]:
        """Practice runs only. No config.yaml = unknown split = not allowed."""
        for n in (self.name, self.path.name):
            if n.startswith(LOCKED_PREFIXES):
                return False, f"name {n!r} is a test/hold-out run"
        split = self.config.get("split")
        if split != "practice":
            return False, f"split is {split!r}, not 'practice'"
        return True, ""

    def totals(self) -> dict[str, Any]:
        f = self.path / "eval.json"
        if not f.is_file():
            return {}
        return json.loads(f.read_text(encoding="utf-8")).get("totals") or {}

    def questions(self) -> dict[str, Any]:
        """Per-question scores; only called after per_question_allowed()."""
        ok, why = self.per_question_allowed()
        if not ok:
            raise PermissionError(f"{self.path}: per-question data refused ({why})")
        f = self.path / "eval.json"
        return (json.loads(f.read_text(encoding="utf-8")).get("questions") or {}) if f.is_file() else {}

    def cost(self) -> dict[str, Any]:
        """Sums over every step "end" event (all resumes included) and the run wall time, per question."""
        f = self.path / "events.jsonl"
        sums: dict[str, float] = defaultdict(float)
        qids: set[str] = set()
        wall = 0.0
        if f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                e = json.loads(line)
                if e.get("kind") != "end":
                    continue
                d = e.get("data") or {}
                if e.get("step") == "run":
                    wall += float(d.get("seconds") or 0)
                    continue
                if e.get("qid"):
                    qids.add(e["qid"])
                sums["seconds"] += float(d.get("seconds") or 0)
                for k in ("requests", "calls", "cache_hits"):
                    sums[k] += float((d.get("llm") or {}).get(k) or 0)
                if "tokens" in (d.get("llm") or {}):    # not recorded yet (see module doc); used once lm.py counts them
                    sums["tokens"] += float(d["llm"]["tokens"] or 0)
        n = self.totals().get("questions") or len(qids)
        out: dict[str, Any] = {"n": n}
        for k in ("requests", "calls", "cache_hits", "seconds", "tokens"):
            out[k] = (sums[k] / n) if n and k in sums else None
        out["wall"] = wall / n if n and wall else None
        return out


def _fmt(v: Any) -> str:
    if v is None:
        return NA
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, float):
        return f"{v:.4f}".rstrip("0").rstrip(".")
    return str(v)


def _dig(d: Any, path: tuple[str, ...]) -> Any:
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


def totals_table(runs: list[Run]) -> list[str]:
    tots = [r.totals() for r in runs]
    costs = [r.cost() for r in runs]
    rows: list[list[str]] = [["config", *[r.name for r in runs]], ["split", *[_fmt(r.config.get("split")) for r in runs]]]
    rows += [[k, *[_fmt(t.get(k)) for t in tots]] for k in LAYERS]
    rows += [[f"not_reported {k}", *[_fmt(_dig(t, ("not_reported", k))) for t in tots]] for k in NOT_REPORTED]
    types = list(dict.fromkeys(ty for t in tots for ty in (t.get("per_type") or {})))
    for ty in types:
        rows += [[f"{ty} {k}", *[_fmt(_dig(t, ("per_type", ty, k))) for t in tots]] for k in TYPE_KEYS]
    for key, label in [("requests", "LLM requests / q"), ("calls", "LLM real calls / q"),
                       ("cache_hits", "LLM cache hits / q"), ("tokens", "tokens / q"),
                       ("seconds", "step seconds / q"), ("wall", "wall seconds / q")]:
        rows.append([label, *[_fmt(round(c[key], 2) if c[key] is not None else None) for c in costs]])
    return _table(["", *[r.label for r in runs]], rows)


def diff_table(runs: list[Run]) -> list[str]:
    """Rows (question, measure) whose value is not the same in every run."""
    allowed, skipped = [], []
    for r in runs:
        ok, why = r.per_question_allowed()
        (allowed if ok else skipped).append((r, why))
    out = [f"- left out (not a practice run, per-question data not opened): `{r.label}`: {why}" for r, why in skipped]
    if len(allowed) < 2:
        return [*out, "", "Per-question differences need at least two practice runs."]
    qs = [r.questions() for r, _ in allowed]
    rows = []
    for qid in sorted({q for d in qs for q in d}, key=lambda s: (len(s), s)):
        qtype = next((d[qid].get("type") for d in qs if qid in d), "")
        for label, path in PER_Q:
            vals = [_fmt(_dig(d.get(qid), path)) if qid in d else "missing" for d in qs]
            if len(set(vals)) > 1:
                rows.append([qid, qtype or "", label, *vals])
    if not rows:
        return [*out, "", "No per-question differences."]
    return [*out, "", *_table(["question", "type", "measure", *[r.label for r, _ in allowed]], rows)]


def report(run_dirs: list[Path]) -> str:
    runs = [Run(p) for p in run_dirs]
    lines = [f"# evqa compare ({dt.date.today().isoformat()})", "",
             "Runs: " + ", ".join(f"`{p}`" for p in run_dirs), "",
             "## Totals per layer and per question type", "",
             *totals_table(runs), "",
             "Tokens: n/a = not recorded (lm.py keeps only the reply text).", "",
             "## Per-question differences (practice runs only)", "",
             *diff_table(runs), ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="evqa compare", description=__doc__.splitlines()[0])
    p.add_argument("run_dirs", type=Path, nargs="+")
    p.add_argument("--out", type=Path, default=None, help="default runs/evqa/compare-<YYYY-MM-DD>.md")
    return run_cli(p.parse_args(argv))


def run_cli(a: argparse.Namespace) -> int:
    missing = [d for d in a.run_dirs if not d.is_dir()]
    if missing:
        print(f"not a run folder: {', '.join(map(str, missing))}", file=sys.stderr)
        return 2
    text = report(a.run_dirs)
    out = a.out or REPO / "runs" / "evqa" / f"compare-{dt.date.today().isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
