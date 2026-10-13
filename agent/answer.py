"""The final answer step (row 1.8): the agent's json block -> answer.json in the 1.3 format.

The agent writes only {"rows": [...], "notes": "..."}; the harness adds the concept hash and the
answer kind, fills each fact's `claims` (default: none) and `origin` (research), and checks the
result with validate_answer and against the run's accepted claim ids. `reply_schema` is that
reply object as a JSON Schema, for decoding the conclude replies under it (row 1.13).
"""
from __future__ import annotations

import copy
import json
from typing import Any

from .concept import answer_schema_for, concept_sha256, validate_answer
from .rundir import RunDir

# Dropped from the decoding schema: annotations, and keywords grammar backends ignore or reject.
NOT_FOR_GRAMMAR = ("$schema", "$id", "title", "description", "uniqueItems")


def reply_schema(concept: dict[str, Any]) -> dict[str, Any]:
    """JSON Schema of the agent's reply {rows, notes} for this concept (conclude under structured outputs).

    answer_schema_for(concept) without what the harness sets (concept_sha256, kind, each fact's
    origin). A fact's `claims` stays optional, as in the reply format (build_answer fills []), so
    the schema is the same for claim_on and claim_off; `notes` is required, so a forced answer
    can still say what was not checked. The fact `$ref` is inlined, `oneOf` (graph edge types,
    disjoint by their consts) becomes `anyOf`, and NOT_FOR_GRAMMAR keys are dropped, which keeps
    the schema within what xgrammar and llguidance accept. Nothing is lost: build_answer checks
    the reply against the full schema afterwards.
    """
    full = answer_schema_for(concept)
    fact = copy.deepcopy(full["$defs"]["fact"])
    del fact["properties"]["origin"]
    fact["required"] = [k for k in fact["required"] if k not in ("origin", "claims")]

    def grammar(node: Any) -> Any:
        if isinstance(node, list):
            return [grammar(n) for n in node]
        if not isinstance(node, dict):
            return node
        if node.get("$ref") == "#/$defs/fact":
            return grammar(fact)
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key == "properties":  # names, not keywords: a column may be called "title"
                out[key] = {name: grammar(sub) for name, sub in value.items()}
            elif key not in NOT_FOR_GRAMMAR:
                out["anyOf" if key == "oneOf" else key] = grammar(value)
        return out

    return grammar({"type": "object", "additionalProperties": False, "required": ["rows", "notes"],
                    "properties": {"rows": full["properties"]["rows"], "notes": {"type": "string"}}})


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
