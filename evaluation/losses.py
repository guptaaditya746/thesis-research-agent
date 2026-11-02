"""Cost per system and the losses-first table (spec 6.16, D41).

`system_cost` reads the model calls and tokens a system recorded: the engine's run.json `cost`, a baseline
answer's `model_call` and `mapping_call`, the agent baseline's `agent` block. `evaluate score` puts it on every
`synthesis` entry as `cost`.

`losses` turns score reports (report.json of `evaluate score`, each tagged with its folder by `read_reports`) into
one table per domain: per question each system's headline score and cost, whether the engine lost and the first
cause of its loss (CAUSES, in order):

- missed: the extraction (A) missed a fact of the scored types;
- wrongly linked: a B accuracy of the report (`association_accuracy` over all levels, `kind_accuracy`,
  `claim_accuracy`) is below 1; a kind whose B has no accuracy (chaining, limitations, builds_on, inventory)
  skips this step (preflight F33);
- names not grouped: the run left names unresolved (run.json `unresolved_names`), or the inventory B split or
  merged a name;
- wrong rule: none of these, so the evidence was there and the answer rule went wrong.

The engine loses when its headline is below the best baseline's (the oracle diagnostics are not baselines), or
its label (effect) or winner (best) is wrong. Losses come first, then by question id.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from evidence.protocol import DEFAULT_PACK

from .report import table, write_pair
from .truth import ENGINE

CAUSES = ("missed", "wrongly linked", "names not grouped", "wrong rule")
CAUSE_TEXT = {"missed": "the extraction did not find facts the answer needs",
              "wrongly linked": "values were found but tied to the wrong condition, metric or claim",
              "names not grouped": "names of one thing were left apart, or names of two things put together",
              "wrong rule": "the evidence was found and linked; the answer rule gave the wrong result"}
TIM_SENTENCE = "We should not assume that the evidence-level approach will necessarily perform better"
REF = "_report_ref"   # the report's `<group>~<name>` under the scores root, set by read_reports
REF_SEP = "~"         # as the web app's score ids (webapp RUN_SEP)
COST_KEYS = ("model_calls", "input_tokens", "output_tokens", "tokens")
HEADLINE = {"effect": "direction_accuracy", "inventory": "f1", "best": "per_study_accuracy",
            "consistency": "per_study_accuracy"}   # other kinds: the `headline` their scorer writes
B_ACCURACY = ("association_accuracy", "kind_accuracy", "claim_accuracy")
ALL = "all"


# --- cost -----------------------------------------------------------------------------------------------------

def _sum(values: list[Any]) -> int | None:
    """The sum, or None when any value is unknown."""
    return None if any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in values) else sum(values)


def _cost(model_calls: int | None, input_tokens: int | None, output_tokens: int | None,
          tokens: int | None = None) -> dict[str, int | None]:
    if tokens is None and input_tokens is not None and output_tokens is not None:
        tokens = input_tokens + output_tokens
    return {"model_calls": model_calls, "input_tokens": input_tokens, "output_tokens": output_tokens,
            "tokens": tokens}


def system_cost(answer: dict[str, Any], run: dict[str, Any] | None) -> dict[str, int | None]:
    """Model calls and tokens of one system on a question; a count the system did not record is None.

    The engine (`run` its run.json): run.json `cost`. A baseline (`run` None): its answering call (`model_call`) and
    its mapping call (`mapping_call`, None when the answer was empty), or the agent baseline's `agent` block (calls
    and tokens, in and out not split) plus its mapping call. `tokens` is input + output when both are known."""
    if run is not None:
        c = run.get("cost") or {}
        return _cost(c.get("model_calls"), c.get("input_tokens"), c.get("output_tokens"))
    mapping = answer.get("mapping_call")
    calls = [m for m in (answer.get("model_call"), mapping) if isinstance(m, dict)]
    agent = answer.get("agent")
    if isinstance(agent, dict):
        mapped = _sum([m.get("input_tokens") for m in calls] + [m.get("output_tokens") for m in calls])
        return _cost(_sum([agent.get("model_calls"), len(calls)]), None, None,
                     _sum([agent.get("tokens"), mapped]))
    if "model_call" not in answer:   # an answer that records no call (an oracle, an old answer): not known
        return _cost(None, None, None)
    return _cost(len(calls), _sum([m.get("input_tokens") for m in calls]),
                 _sum([m.get("output_tokens") for m in calls]))


# --- headline and cause ---------------------------------------------------------------------------------------

def headline(kind: str, system: dict[str, Any]) -> float | None:
    """One system's headline score (a `synthesis` entry of a report): the `level == "all"` row where the entry has
    rows (effect), else the entry; effect direction accuracy, inventory F1, best and consistency per-study
    accuracy, the other kinds the `headline` their scorer writes (KeyError naming the kind without one)."""
    rows = system.get("rows")
    row = next((r for r in rows or [] if r.get("level") == ALL), None) if rows is not None else system
    if kind in HEADLINE:
        return None if row is None else row.get(HEADLINE[kind])
    if row is None or "headline" not in row:
        raise KeyError(f"question kind {kind!r}: the score has no `headline` (plan 2's scorer writes one)")
    return row["headline"]


def _b_accuracies(integration: dict[str, Any] | None) -> list[float]:
    """The report's B accuracies: the `all` row's association accuracy and the kind's own accuracy (B_ACCURACY)."""
    if not integration:
        return []
    rows = [r for r in integration.get("rows") or [] if r.get("level") == ALL]
    return [v for source in (integration, *rows) for k in B_ACCURACY
            if isinstance(v := source.get(k), (int, float))]


def loss_cause(report: dict[str, Any]) -> str:
    """The first cause of CAUSES that holds for the report (module docstring)."""
    if (report.get("extraction") or {}).get("missed"):
        return "missed"
    integration = report.get("integration") or {}
    if any(v < 1 for v in _b_accuracies(integration)):
        return "wrongly linked"
    if (report.get("unresolved_names") or 0) > 0 or (integration.get("kind") == "inventory" and
                                                     (integration.get("split") or integration.get("merged"))):
        return "names not grouped"
    return "wrong rule"


def engine_lost(kind: str, systems: list[dict[str, Any]]) -> bool:
    """The engine's headline is below the best baseline's, or its label (effect) or winner (best) is wrong; a
    report without the engine has no loss."""
    from .score import COUNTERPARTS   # the oracle diagnostics; imported here (score imports this module)

    engine = next((s for s in systems if s.get("system") == ENGINE), None)
    if engine is None:
        return False
    if engine.get("label_correct") is False or engine.get("winner_correct") is False:
        return True
    mine = headline(kind, engine)
    best = max((v for s in systems if s.get("system") not in (ENGINE, *COUNTERPARTS)
                if (v := headline(kind, s)) is not None), default=None)
    return mine is not None and best is not None and mine < best


# --- the table ------------------------------------------------------------------------------------------------

def losses(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """{"domains": {domain: rows}}, one row per report (each tagged with REF, read_reports): question, kind, each
    system's headline and cost, whether the engine lost and the first cause; losses first, then by question id."""
    domains: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for report in reports:
        if REF not in report:
            raise KeyError(f"a report without {REF} (read the reports with read_reports): "
                           f"question {report.get('question_id')!r}, run {report.get('run_id')!r}")
        kind = report.get("kind", "effect")
        systems = report.get("synthesis") or []
        lost = engine_lost(kind, systems)
        domains[report.get("domain") or DEFAULT_PACK].append({
            "question_id": report.get("question_id"), "kind": kind,
            "systems": {s["system"]: headline(kind, s) for s in systems},
            "cost": {s["system"]: s["cost"] for s in systems if isinstance(s.get("cost"), dict)},
            "engine_loss": lost, "cause": loss_cause(report) if lost else None, "report": report[REF]})
    for rows in domains.values():
        rows.sort(key=lambda r: (not r["engine_loss"], str(r["question_id"]), r["report"]))
    return {"domains": dict(sorted(domains.items()))}


def read_reports(scores: Path) -> list[dict[str, Any]]:
    """Every report.json one or two folders under the scores root (`<group>/` or `<group>/<name>/`, as the web
    app lists them), tagged with REF `<group>` or `<group>~<name>`."""
    out = []
    for path in sorted(Path(scores).glob("*/report.json")) + sorted(Path(scores).glob("*/*/report.json")):
        parts = path.parent.relative_to(scores).parts
        out.append({**json.loads(path.read_text(encoding="utf-8")), REF: REF_SEP.join(parts)})
    return sorted(out, key=lambda r: r[REF])


def render(result: dict[str, Any]) -> str:
    """losses.md: the comparison opens with Tim's sentence (§7); per domain the losses-first table, one line per
    engine loss, and the model calls and tokens per system (D41)."""
    out = ["# Losses first", "", "## Comparison", "", f"{TIM_SENTENCE} (Tim, §7).", "",
           "Per domain, every question with each system's headline score, the engine's losses first. Each engine "
           "loss has one cause, the first that holds: " + "; ".join(f"{c}: {CAUSE_TEXT[c]}" for c in CAUSES) + ".",
           ""]
    for domain, rows in result["domains"].items():
        systems = sorted({s for r in rows for s in r["systems"]}, key=lambda s: (s != ENGINE, s))
        flat = [{"question": r["question_id"], "kind": r["kind"], **r["systems"],
                 "engine loss": "yes" if r["engine_loss"] else "no", "cause": r["cause"], "report": r["report"]}
                for r in rows]
        out += [f"## {domain}", "", table(flat, ["question", "kind", *systems, "engine loss", "cause", "report"]), ""]
        lost = [r for r in rows if r["engine_loss"]]
        if lost:
            out += ["Engine losses:", "", *[f"- {r['question_id']} ({r['report']}): {r['cause']}, "
                                            f"{CAUSE_TEXT[r['cause']]}." for r in lost], ""]
        costs = [{"question": r["question_id"], "system": s, **c} for r in rows for s, c in r["cost"].items()]
        if costs:
            out += ["Model calls and tokens per system:", "",
                    table(costs, ["question", "system", *COST_KEYS]), ""]
    return "\n".join(line.rstrip() for line in out)


def write_losses(result: dict[str, Any], out: Path) -> tuple[Path, Path]:
    """losses.json and losses.md in `out`."""
    return write_pair(result, render(result), out, "losses")
