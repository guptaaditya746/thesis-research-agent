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
RANK_TEMPLATES = ("rank", "best")


def _number(x: Any) -> str:
    return f"{x:g}" if isinstance(x, (int, float)) else str(x)


def best_text(template: str | None, rows: list[dict[str, Any]]) -> str | None:
    """What a rank or best line found, named: "Best: <thing> in <paper> (score <s>)" (every thing tied on the top
    score; rank.rq's score is in the metric's own direction), "Best: <thing> (<n> wins)" for best.rq; else None."""
    if template not in RANK_TEMPLATES or not rows or "thing" not in rows[0]:
        return None
    first = rows[0]
    if "score" in first:
        top = [r for r in rows if r.get("score") == first["score"]]
        names = ", ".join(f"{r['thing']} in {r['paper']}" if r.get("paper") else str(r["thing"]) for r in top)
        return f"Best: {names} (score {_number(first['score'])})"
    if "count" in first:
        top = [r for r in rows if r.get("kind") == first.get("kind") and r.get("count") == first["count"]]
        return f"Best: {', '.join(str(r['thing']) for r in top)} ({_number(first['count'])} wins)"
    return None


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


def run_lines(plan: Plan, run_query: Callable[[str, dict[str, Any]], list[dict[str, Any]]], *,
              name_best: bool = False) -> dict[str, Any]:
    """`name_best` (a v2 plan run): the answer text first names a rank line's best thing (`best_text`)."""
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
        templates = {x.id: x.template for x in plan.lines}
        first = next((x for x in counted if x["rows"] and templates.get(x["id"]) in RANK_TEMPLATES), None) if name_best else None
        named = best_text(templates[first["id"]], first["rows"]) if first is not None else None   # a ranking: who is best
        text = f"{named}; {text}" if named else text
    if missing:
        text += "; " + "; ".join(missing)
    return {"lines": lines, "answer": {"main_rule": plan.main_rule, "rule_met": met,
                                       "found": [x["id"] for x in lines if x["rows"]], "missing": missing,
                                       "text": text}}
