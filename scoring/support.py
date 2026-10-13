"""Does each answer fact's quote support it? The primary outcome's input (docs/e2e-build-plan.md).

Input: pairs.jsonl (agent/pairs.py, row 1.12), one line per (answer fact, claim id it cites), with the
exact text the broker anchored in the corpus; a run without the file gets it computed the same way.
Each accepted claim's quote is judged against the fact's own s, p and o with gold.judge.support()
(scoring/judge.py): supports, partial or no. A fact takes the best verdict over its claims, so one
supporting quote is enough.

A fact is unsourced when it cites no accepted claim. For a claim_off run after the attach step (row 2.5)
the attach claims are its claims, and a fact the step answered "no source found" for (claims []) is
unsourced. A claim_off run whose attach step never ran has only unsourced facts.

support_share = facts with a supporting quote / all answer facts (unsourced and partial count as not
supported); null when the answer has no facts, or while any verdict is pending (judge unavailable).
The judge is told which paper the quote is from (and its title when the corpus is at hand), since a
quote rarely names its own paper.
"""
from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from typing import Any

from agent.pairs import PAIRS, pairs
from agent.rundir import RunDir

from .judge import Judge, run_all

RANK = {"no": 0, "partial": 1, "supports": 2}


def load_pairs(run: RunDir) -> list[dict[str, Any]]:
    path = run.root / PAIRS
    if path.is_file():
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return pairs(run)


def paper_title(corpus: Path | None, file: str) -> str | None:
    """The first Markdown heading of a corpus file (the paper's title in the Docling conversion)."""
    if corpus is None:
        return None
    try:
        with open(Path(corpus) / file, encoding="utf-8") as fh:
            for _, line in zip(range(200), fh):
                if line.startswith("#"):
                    return line.lstrip("#").strip() or None
    except OSError:
        return None
    return None


def quote_context(file: str | None, corpus: Path | None = None) -> str | None:
    if not file:
        return None
    title = paper_title(corpus, file)
    paper = file[:-3] if file.endswith(".md") else file
    return f"The quote is from the corpus paper {paper} (file {file})" + (f', titled "{title}"' if title else "") + "."


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
                  workers: int = 1) -> dict[str, Any]:
    """Support counts and share for one run, with each fact's verdicts in `detail`."""
    facts: dict[tuple[str, str], dict[str, Any]] = {}
    for line in load_pairs(run):
        fact = facts.setdefault((line["row_id"], line["fact_id"]), {
            "row_id": line["row_id"], "fact_id": line["fact_id"], "origin": line.get("origin"),
            "spo": {k: line[k] for k in ("s", "p", "o")}, "claims": []})
        if line.get("claim_id") and line.get("claim_found") and line.get("quote"):
            fact["claims"].append({"claim_id": line["claim_id"], "file": line.get("file"), "quote": line["quote"]})
    jobs = [(fact, claim) for fact in facts.values() for claim in fact["claims"]]
    contexts = {c["file"]: quote_context(c["file"], corpus) for _, c in jobs}
    verdicts = (run_all([partial(judge.support, f["spo"], c["quote"], context=contexts[c["file"]]) for f, c in jobs],
                        workers) if judge is not None else [None] * len(jobs))
    for (fact, claim), verdict in zip(jobs, verdicts):
        claim["verdict"] = verdict
    detail = []
    for fact in facts.values():
        label = fact_label([c["verdict"] for c in fact["claims"]])
        detail.append({"row_id": fact["row_id"], "fact_id": fact["fact_id"], "origin": fact["origin"], "label": label,
                       "claims": [{"claim_id": c["claim_id"], "file": c["file"],
                                   "label": c["verdict"]["label"] if c["verdict"] else None,
                                   "rationale": (c["verdict"] or {}).get("rationale"),
                                   "model": (c["verdict"] or {}).get("model")} for c in fact["claims"]]})
    return summarise(detail) | {"detail": detail}


def summarise(detail: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [d["label"] for d in detail]
    n = len(labels)
    count = {k: labels.count(k) for k in ("supports", "partial", "no", "unsourced", "pending")}
    return {"facts": n, "with_claims": n - count["unsourced"], **count,
            "support_share": count["supports"] / n if n and not count["pending"] else None,
            "unsourced_share": count["unsourced"] / n if n else None}
