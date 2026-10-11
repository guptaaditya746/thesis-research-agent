"""The final answer step (row 1.8): the agent's json block -> answer.json in the 1.3 format.

The agent writes only {"rows": [...], "notes": "..."}; the harness adds the concept hash and the
answer kind, fills each fact's `claims` (default: none) and `origin` (research), and checks the
result with validate_answer and against the run's accepted claim ids.
"""
from __future__ import annotations

import json
from typing import Any

from .concept import concept_sha256, validate_answer
from .rundir import RunDir


def accepted_claim_ids(run: RunDir) -> set[str]:
    ids = set()
    for raw in run.claims.read_bytes().splitlines():
        record = json.loads(raw)
        if record.get("status") == "accepted":
            ids.add(record["generated"]["claim_id"])
    return ids


def build_answer(text: str, concept: dict[str, Any], known_claims: set[str] | None = None
                 ) -> tuple[dict[str, Any] | None, list[str]]:
    """Complete and check the agent's answer. Returns (answer, []) or (None, problems)."""
    try:
        given = json.loads(text)
    except ValueError as exc:
        return None, [f"the json block is not valid JSON: {exc}"]
    if not isinstance(given, dict):
        return None, ['the json block must be one object {"rows": [...], "notes": "..."}']
    # concept_sha256 and kind are the harness's to set; anything else is a mistake worth reporting.
    problems = [f"unexpected key {k!r} (only rows and notes)" for k in sorted(given)
                if k not in ("rows", "notes", "concept_sha256", "kind")]
    rows = given.get("rows")
    if not isinstance(rows, list):
        return None, problems + ['"rows" must be a list']
    for row in rows:
        for fact in (row.get("facts") if isinstance(row, dict) else None) or []:
            if isinstance(fact, dict):
                fact.setdefault("claims", [])
                fact.setdefault("origin", "research")
    answer: dict[str, Any] = {"concept_sha256": concept_sha256(concept), "kind": concept["answer_shape"]["kind"],
                              "rows": rows}
    if "notes" in given:
        answer["notes"] = given["notes"]
    problems += validate_answer(answer, concept)
    if not problems and known_claims is not None:
        cited = sorted({c for r in rows for f in r["facts"] for c in f["claims"]})
        problems += [f"{c} is not an accepted claim of this run" for c in cited if c not in known_claims]
    return (None if problems else answer), problems


def empty_answer(concept: dict[str, Any], reason: str) -> dict[str, Any]:
    """What a run without a valid final answer leaves: no rows, and why in notes."""
    return {"concept_sha256": concept_sha256(concept), "kind": concept["answer_shape"]["kind"], "rows": [],
            "notes": f"harness: no valid final answer ({reason})"}
