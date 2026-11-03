"""Run the plan's evidence lines, each in its own try block (for W4's `after_run`): one line that crashes (a model
error, a bad query) does not stop the others. The crashed line reports "failed: <reason>" and the answer says
"missing: <line>"; a line with no rows says "No evidence found", which is a valid result.

Each line runs with the parameters its decisions give (`decision_params`: the plan's current values), so a changed
decision changes what runs. The main-answer rule (one of RULES) is applied here, in code, to the lines' results.

`run_query(query, params) -> list[dict]` is W4's SPARQL runner (it fills the `$placeholders` from `params`),
injected."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from evidence.plan import Plan

from .plan import OVERSELL_ID, RULES, decision_params

NO_EVIDENCE = "No evidence found"


def apply_rule(rule: str, found: list[bool]) -> bool:
    """The main answer from the rule and one found/not-found flag per counted line."""
    if rule not in RULES:
        raise ValueError(f"unknown main-answer rule {rule!r}; one of {sorted(RULES)}")
    if not found:
        return False
    if rule == "any_line":
        return any(found)
    if rule == "all_lines":
        return all(found)
    return sum(found) * 2 > len(found)


def run_lines(plan: Plan, run_query: Callable[[str, dict[str, Any]], list[dict[str, Any]]]) -> dict[str, Any]:
    lines: list[dict[str, Any]] = []
    for line in plan.lines:
        try:
            if not line.query.strip():
                raise ValueError("the line could not be planned (no query)")
            rows = run_query(line.query, decision_params(plan, line.query))
        except Exception as exc:  # noqa: BLE001 - any failure of one line stays with that line
            lines.append({"id": line.id, "question": line.question, "status": "failed", "rows": [],
                          "text": f"failed: {str(exc) or type(exc).__name__}"})
            continue
        lines.append({"id": line.id, "question": line.question, "status": "done", "rows": rows,
                      "text": f"{len(rows)} found" if rows else NO_EVIDENCE})
    missing = [f"missing: {x['question']}" for x in lines if x["status"] == "failed"]
    counted = [x for x in lines if x["id"] != OVERSELL_ID]  # the oversell line is a caveat, not evidence for the answer
    flags = [bool(x["rows"]) for x in counted if x["status"] == "done"]
    met = apply_rule(plan.main_rule, flags) if any(x["rows"] for x in counted) else False
    if not any(x["rows"] for x in lines):
        text = NO_EVIDENCE
    else:
        text = f"{'Yes' if met else 'No'}: {RULES[plan.main_rule]} ({sum(flags)} of {len(counted)} lines found evidence)"
    if missing:
        text += "; " + "; ".join(missing)
    return {"lines": lines, "answer": {"main_rule": plan.main_rule, "rule_met": met,
                                       "found": [x["id"] for x in lines if x["rows"]], "missing": missing,
                                       "text": text}}
