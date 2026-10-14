"""Does each answer fact's quote support it? The primary outcome's input (docs/e2e-build-plan.md).

Input: pairs.jsonl (agent/pairs.py, row 1.12), one line per (answer fact, claim id it cites), with the
exact text the broker anchored in the corpus and its offsets; a run without the file gets it computed
the same way. Each accepted claim's quote is judged against the fact's own s, p and o: supports,
partial or no. With the corpus at hand the judge gets each line through gold.judge's support_pair, so
its input is the one it was calibrated on (the paper id and the text around the quote,
gold.judge.context_for); without a corpus, or with a judge that has no support_pair, it sees the fact
and the quote alone. Which of the two is recorded (`context`).

A fact takes the best verdict over its claims, so one supporting quote is enough (pre-registered,
docs/STATE.md). claim_on facts may cite several claims; claim_off facts after the attach step cite at
most one, so `claims_per_fact` is recorded and `support_share_first_claim` (each fact judged by its
first cited claim alone) is the sensitivity analysis for that difference.

A fact is unsourced when it cites no accepted claim. For a claim_off run after the attach step (row 2.5)
the attach claims are its claims, and a fact the step answered "no source found" for (claims []) is
unsourced. A claim_off run whose attach step never ran has only unsourced facts.

support_share = facts with a supporting quote / all answer facts. A `partial` verdict counts as
supporting when the judge's calibration against people says so (`$GOLD/judge-report.json`,
calibration.partial_counts_as, picked on the first half of the calibration sample), else not; the
share under the other mapping is kept beside it. Unsourced facts never count. The shares are null when
the answer has no facts, or while any verdict is pending (judge unavailable).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.canonical import file_sha256
from agent.pairs import PAIRS, pairs
from agent.rundir import RunDir

from .judge import Judge

RANK = {"no": 0, "partial": 1, "supports": 2}
JUDGE_REPORT = "judge-report.json"
MAPPINGS = ("no", "yes")


def load_pairs(run: RunDir) -> list[dict[str, Any]]:
    path = run.root / PAIRS
    if path.is_file():
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return pairs(run)


def calibration(gold: Path | None) -> dict[str, Any]:
    """How `partial` counts, from $GOLD/judge-report.json; "no" (and source null) before calibration."""
    path = Path(gold) / JUDGE_REPORT if gold else None
    try:
        report = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else None
    except (OSError, ValueError):
        report = None
    found = ((report or {}).get("calibration") or {}).get("partial_counts_as")
    if found not in MAPPINGS:
        return {"partial_counts_as": "no", "source": None, "sha256": None}
    return {"partial_counts_as": found, "source": str(path), "sha256": file_sha256(path)}


def fact_label(verdicts: list[dict[str, Any] | None]) -> str:
    """The fact's label from its claims' verdicts: unsourced, pending, or the best of the verdicts."""
    if not verdicts:
        return "unsourced"
    known = [v["label"] for v in verdicts if v is not None]
    best = max(known, key=RANK.__getitem__, default=None)
    if best == "supports" or (best is not None and len(known) == len(verdicts)):
        return best
    return "pending"


def judge_support(run: RunDir, judge: Judge | None, *, corpus: Path | None = None,
                  partial_counts_as: str = "no") -> dict[str, Any]:
    """Support counts and shares for one run, with each fact's verdicts in `detail`."""
    facts: dict[tuple[str, str], dict[str, Any]] = {}
    for line in load_pairs(run):
        fact = facts.setdefault((line["row_id"], line["fact_id"]), {
            "row_id": line["row_id"], "fact_id": line["fact_id"], "origin": line.get("origin"), "claims": []})
        if line.get("claim_id") and line.get("claim_found") and line.get("quote"):
            fact["claims"].append({"claim_id": line["claim_id"], "file": line.get("file"), "line": line})
    jobs = [claim for fact in facts.values() for claim in fact["claims"]]
    verdicts = judge.supports([c["line"] for c in jobs], corpus) if judge is not None else [None] * len(jobs)
    for claim, verdict in zip(jobs, verdicts):
        claim["verdict"] = verdict
    detail = []
    for fact in facts.values():
        claims = fact["claims"]
        detail.append({"row_id": fact["row_id"], "fact_id": fact["fact_id"], "origin": fact["origin"],
                       "label": fact_label([c["verdict"] for c in claims]),
                       "first_claim_label": fact_label([claims[0]["verdict"]] if claims else []),
                       "claims": [{"claim_id": c["claim_id"], "file": c["file"]}
                                  | {k: (c["verdict"] or {}).get(k)
                                     for k in ("label", "rationale", "model", "prompt_sha256", "cached")}
                                  for c in claims]})
    context = judge.context_mode(corpus) if judge is not None else None
    return summarise(detail, partial_counts_as) | {"context": context, "detail": detail}


def share(labels: list[str], yes: tuple[str, ...]) -> float | None:
    if not labels or "pending" in labels:
        return None
    return sum(label in yes for label in labels) / len(labels)


def summarise(detail: list[dict[str, Any]], partial_counts_as: str = "no") -> dict[str, Any]:
    labels = [d["label"] for d in detail]
    n = len(labels)
    count = {k: labels.count(k) for k in ("supports", "partial", "no", "unsourced", "pending")}
    strict, lenient = ("supports",), ("supports", "partial")
    yes = lenient if partial_counts_as == "yes" else strict
    sourced = [len(d["claims"]) for d in detail if d["claims"]]
    return {"facts": n, "with_claims": n - count["unsourced"], **count, "partial_counts_as": partial_counts_as,
            "support_share": share(labels, yes),
            "support_share_partial_no": share(labels, strict), "support_share_partial_yes": share(labels, lenient),
            "support_share_first_claim": share([d["first_claim_label"] for d in detail], yes),
            "claims_per_fact": sum(sourced) / len(sourced) if sourced else None,
            "unsourced_share": count["unsourced"] / n if n else None}
