"""Python steps for what SPARQL cannot say (W4 task 4.2): a template names one in its header comment (`# after: <name>`)
and the query runner calls `<name>(rows, params)` on the rows it got.

- `effect`: the old synthesis, per paper: the question metrics are tried in order, within one the treatment and
  control values are paired on the same context (`synthesis._pair`'s rule, over rows), `rules.effect` gives the
  direction, and `rules.duplicates` flags a later paper that repeats an earlier one's numbers.
- `chaining_path`: labels the paths from A over B to C "indirect" (they agree) or "conflicting" (they differ by more
  than `$threshold`)."""
from __future__ import annotations

from typing import Any

from evidence import rules

INDIRECT, CONFLICTING = "indirect", "conflicting"
DEFAULT_PREFER = ("table_cell", "document_order")


def _best(rows: list[dict[str, Any]], prefer: tuple[str, ...]) -> dict[str, Any]:
    keys = {"table_cell": lambda r: not r["inTable"], "document_order": lambda r: r["position"]}
    return min(rows, key=lambda r: (*(keys[p](r) for p in prefer), r["value"]))


def _pair(treatment: list[dict[str, Any]], control: list[dict[str, Any]],
          prefer: tuple[str, ...]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    order: list[Any] = []
    for r in sorted(treatment + control, key=lambda r: (r["position"], r["value"])):
        if r.get("context") not in order:
            order.append(r.get("context"))
    for ctx in order:
        t = [r for r in treatment if r.get("context") == ctx]
        c = [r for r in control if r.get("context") == ctx]
        if t and c:
            return _best(t, prefer), _best(c, prefer)
    for ctx in order:
        t = [r for r in treatment if r.get("context") in (ctx, None)]
        c = [r for r in control if r.get("context") in (ctx, None)]
        if t and c and (ctx is None or any(r.get("context") is None for r in t + c)):
            return _best(t, prefer), _best(c, prefer)
    return None


def effect(rows: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per paper (in `params["order"]` when given, else by id): direction supports / contradicts / neutral, or
    undetermined, with delta, metric and the two values; `duplicate_of` set on a later repeat of an earlier paper."""
    sides = params["sides"]
    treatment_side, control_side = sides[0], sides[1]
    prefer = tuple(params.get("prefer") or DEFAULT_PREFER)
    higher = params["higher_is_better"]
    papers = list(params.get("order") or sorted({r["paper"] for r in rows}))
    out: list[dict[str, Any]] = []
    for paper in papers:
        mine = [r for r in rows if r["paper"] == paper]
        entry: dict[str, Any] = {"paper": paper, "direction": "undetermined", "delta": None, "metric": None,
                                 "treatment_value": None, "control_value": None, "duplicate_of": None}
        fields = list(params.get("must_match") or [])
        for wanted in params["metrics"]:
            on = [r for r in mine if r["metric"] == wanted]
            keys = list(dict.fromkeys(tuple(r.get(f"mm{n}") for n in range(len(fields))) for r in on))
            pair = None
            for key in keys:   # the values of a pair come from experiments with equal must-match settings
                same = [r for r in on if tuple(r.get(f"mm{n}") for n in range(len(fields))) == key]
                pair = _pair([r for r in same if r["side"] == treatment_side],
                             [r for r in same if r["side"] == control_side], prefer)
                if pair is not None:
                    break
            if pair is not None:
                t, c = pair
                direction, delta = rules.effect(t["number"], c["number"], higher[wanted], params["min_effect"])
                entry.update(direction=direction, delta=delta, metric=wanted, treatment_value=t["number"],
                             control_value=c["number"])
                break
        out.append(entry)
    determined = [e for e in out if e["direction"] != "undetermined"]
    for later, first in rules.duplicates((e["paper"], e["metric"], e["treatment_value"], e["control_value"])
                                         for e in determined).items():
        next(e for e in out if e["paper"] == later)["duplicate_of"] = first
    return out


def counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    """The effect rows as the counts of answer.json: supporting / contradicting / neutral (duplicates left out),
    duplicates and undetermined."""
    keys = {"supports": "supporting", "contradicts": "contradicting", "neutral": "neutral",
            "undetermined": "undetermined"}
    out = {"contradicting": 0, "duplicates": 0, "neutral": 0, "supporting": 0, "undetermined": 0}
    for r in rows:
        out["duplicates" if r["duplicate_of"] is not None else keys[r["direction"]]] += 1
    return out


def chaining_path(rows: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, Any]]:
    """Each row is a path A - B - C with `estimate`, A over C by the difference of differences. All paths get one
    label: conflicting when two estimates differ by more than `threshold`, else indirect."""
    estimates = [r["estimate"] for r in rows]
    threshold = float(params.get("threshold", 0))
    spread = max(estimates) - min(estimates) if estimates else 0
    label = CONFLICTING if spread > threshold and len(estimates) > 1 else INDIRECT
    return [{**r, "label": label} for r in rows]
