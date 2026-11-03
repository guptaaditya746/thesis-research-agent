"""Run the plan's evidence lines, each in its own try block (for W4's `after_run`): one line that crashes (a model
error, a bad query) does not stop the others. The crashed line reports "failed: <reason>" and the answer says
"missing: <line>"; a line with no rows says "No evidence found", which is a valid result.

`run_query(query) -> list[dict]` is W4's SPARQL runner, injected."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from evidence.plan import Plan

NO_EVIDENCE = "No evidence found"


def run_lines(plan: Plan, run_query: Callable[[str], list[dict[str, Any]]]) -> dict[str, Any]:
    lines: list[dict[str, Any]] = []
    for line in plan.lines:
        try:
            if not line.query.strip():
                raise ValueError("the line could not be planned (no query)")
            rows = run_query(line.query)
        except Exception as exc:  # noqa: BLE001 - any failure of one line stays with that line
            lines.append({"id": line.id, "question": line.question, "status": "failed", "rows": [],
                          "text": f"failed: {exc}"})
            continue
        lines.append({"id": line.id, "question": line.question, "status": "done", "rows": rows,
                      "text": f"{len(rows)} found" if rows else NO_EVIDENCE})
    missing = [f"missing: {x['question']}" for x in lines if x["status"] == "failed"]
    found = [x for x in lines if x["rows"]]
    text = f"{len(found)} of {len(lines)} lines found evidence" if found else NO_EVIDENCE
    if missing:
        text += "; " + "; ".join(missing)
    return {"lines": lines, "answer": {"main_rule": plan.main_rule, "found": [x["id"] for x in found],
                                       "missing": missing, "text": text}}
