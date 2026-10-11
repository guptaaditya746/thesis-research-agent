"""Fact-quote pairs (row 1.12): runs/<id>/pairs.jsonl, the input of the quote-supports-fact judge.

One line per (answer fact, claim id it cites), in answer order. A fact without claims gets one line
with claim_id, quote and file null, so unsourced facts are counted too. `quote` is the exact text
the broker anchored in the corpus file (the selector's `exact`), `quote_submitted` what the agent
sent; `claim` is the claim's own s/p/o, which may differ from the fact's wording.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes
from .rundir import RunDir

PAIRS = "pairs.jsonl"


def claim_records(run: RunDir) -> dict[str, dict[str, Any]]:
    """Accepted claim records by claim id."""
    out = {}
    for raw in run.claims.read_bytes().splitlines():
        record = json.loads(raw)
        if record.get("status") == "accepted":
            out[record["generated"]["claim_id"]] = record
    return out


def pairs(run: RunDir) -> list[dict[str, Any]]:
    answer = json.loads(run.answer.read_bytes())
    claims = claim_records(run)
    out = []
    for row in answer["rows"]:
        for fact in row["facts"]:
            base = {"run_id": run.run_id, "row_id": row["id"], "fact_id": fact["id"], "s": fact["s"],
                    "p": fact["p"], "o": fact["o"], "origin": fact["origin"]}
            for claim_id in fact["claims"] or [None]:
                record = claims.get(claim_id) if claim_id else None
                anchor = record["used"]["anchor"] if record else None
                meta = record["custom_metadata"] if record else {}
                out.append(base | {
                    "claim_id": claim_id, "claim_found": record is not None if claim_id else None,
                    "file": anchor["file"] if anchor else None, "start": anchor["start"] if anchor else None,
                    "end": anchor["end"] if anchor else None, "quote": anchor["exact"] if anchor else None,
                    "quote_submitted": meta.get("quote"),
                    "claim": {k: meta[k] for k in ("s", "p", "o")} if record else None,
                    "step_id": record["step_id"] if record else None,
                })
    return out


def write_pairs(run: RunDir, path: Path | None = None) -> int:
    """Write pairs.jsonl (canonical JSON lines, LF, binary); return the number of lines."""
    lines = pairs(run)
    (path or run.root / PAIRS).write_bytes(b"".join(canonical_bytes(p) + b"\n" for p in lines))
    return len(lines)
