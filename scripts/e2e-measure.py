#!/usr/bin/env python3
"""The measurement table of the Slurm e2e session (docs/slurm-e2e-runbook.md, step 8), read from files.

    uv run python scripts/e2e-measure.py runs <run dir> [<run dir> ...]   # one line per run
    uv run python scripts/e2e-measure.py gold <gold dir> <qid> [<qid> ...]  # one line per gold D

Prints a Markdown table (for tests/RESULTS.md and the report) and, with `--json FILE`, writes one JSON
object per run or question as well. It only reads: events.jsonl through the same rules scoring uses
(`scoring.run_score.records`, `exit_status`, `answer_from`; `agent.verify.stats` for the cost), the
answer, attach.json, config.json; for gold doc.json, triage.jsonl, pool.jsonl and key.draft.json. A file
that is missing gives an empty cell, never an error: the session records what a failed step left.

What the run columns answer (the plan's open questions on the real model, docs/STATE.md "Later"):
- `answer`: final (the conclude reply), draft (scratch/answer-draft.json taken by the harness) or none;
- `guided`: whether the reply that became the answer was decoded under the reply schema
  (`used.decoding` of the call marked `final_answer`), and how many calls were guided at all;
- `refused` / `timeouts` / `cut`: guided calls the server refused (`guided_decoding_rejected`), conclude
  replies past the proxy timeout (`model_timeout`), guided replies cut at max_tokens (finish_reason length);
- `max prompt` and `max masked`: the largest prompt in tokens and the most outputs shown as stubs (1.15);
- coverage reasons and failed-call errors in full, so nothing the loop recorded is left out.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:  # run as a file: make the repository's packages importable
    sys.path.insert(0, str(REPO))

from agent.rundir import RunDir  # noqa: E402
from agent.verify import is_attach, stats  # noqa: E402
from scoring.run_score import answer_from, exit_status, records  # noqa: E402


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _jsonl(path: Path) -> list[dict[str, Any]]:
    out = []
    try:
        lines = path.read_bytes().splitlines()
    except OSError:
        return out
    for raw in lines:
        try:
            out.append(json.loads(raw))
        except ValueError:
            break  # a cut last line
    return out


def measure_run(root: Path) -> dict[str, Any]:
    run = RunDir(root)
    recs = records(run)
    config = _json(run.config) or {}
    research = [r for r in recs if not is_attach(r)]
    calls = [r for r in research if r.get("subtype") == "ai_model_invocation"]
    answered = [c for c in calls if c.get("status") != "failed"]
    guided = [c for c in answered if (c.get("used") or {}).get("decoding", "free") != "free"]
    final = [c for c in answered if (c.get("custom_metadata") or {}).get("final_answer")]
    tools = [r for r in research if r.get("subtype") == "agent_tool"]
    coverage = Counter((r.get("generated") or {}).get("reason") for r in research if r.get("subtype") == "coverage")
    failed = Counter((c.get("generated") or {}).get("error") for c in calls if c.get("status") == "failed")
    usage = [(c.get("generated") or {}).get("usage") or {} for c in answered]
    s = stats(recs) if recs else {}
    answer = _json(run.answer) or {}
    facts = [f for row in answer.get("rows") or [] for f in row.get("facts") or []]
    attach = _json(root / "attach.json")
    out: dict[str, Any] = {
        "run_id": root.name, "condition": config.get("condition"),
        "prompt_version": (config.get("prompt") or {}).get("version"), "budget": config.get("budget"),
        "spawn": bool((config.get("spawn") or {}).get("enabled")),
        "exit_status": exit_status(run, recs) if recs else None, "answer_from": answer_from(recs) if recs else None,
        "steps": (s.get("without_attach") or s).get("steps"), "model_calls": len(calls),
        "commands": len(tools), "tokens": (s.get("without_attach") or s).get("tokens"),
        "seconds": (s.get("without_attach") or s).get("seconds"),
        "rows": len(answer.get("rows") or []), "facts": len(facts),
        "facts_with_claims": sum(bool(f.get("claims")) for f in facts),
        "claims_accepted": s.get("claims_accepted", 0), "claims_rejected": s.get("claims_rejected", 0),
        "rejected_by_reason": dict(Counter((r.get("custom_metadata") or {}).get("reason") for r in recs
                                           if r.get("subtype") == "claim" and r.get("status") == "rejected")),
        "max_prompt_tokens": max((u.get("prompt_tokens", 0) for u in usage), default=0),
        "max_masked": max(((c.get("custom_metadata") or {}).get("masked_observations") or 0 for c in calls), default=0),
        "guided_calls": len(guided),
        "answer_guided": bool(final) and (final[-1].get("used") or {}).get("decoding", "free") != "free",
        "guided_cut": sum((c.get("generated") or {}).get("finish_reason") == "length" for c in guided),
        "longest_guided_s": max(((c.get("custom_metadata") or {}).get("seconds") or 0 for c in guided), default=0),
        "guided_refused": coverage.get("guided_decoding_rejected", 0), "model_timeouts": coverage.get("model_timeout", 0),
        "unparsed": coverage.get("unparsed", 0), "command_timeouts": sum(t.get("status") == "timeout" for t in tools),
        "max_repeat": max(((t.get("custom_metadata") or {}).get("repeat") or 0 for t in tools), default=0),
        "coverage": dict(coverage), "failed_calls": dict(failed),
        "subagents": s.get("subagents", 0),
    }
    if attach is not None or "attach" in s:
        a = attach or {}
        per_fact = a.get("facts") or []
        out["attach"] = {
            "facts": len(per_fact), "attached": a.get("attached"), "from_claim": a.get("attached_from_claim"),
            "no_source": a.get("no_source"), "tokens": (s.get("attach") or {}).get("tokens"),
            "seconds": (s.get("attach") or {}).get("seconds"),
            "max_fact_tokens": max((f.get("tokens", 0) for f in per_fact), default=0),
            "max_fact_steps": max((len(f.get("steps") or []) for f in per_fact), default=0),
            "gave_up": dict(Counter(f.get("reason") for f in per_fact
                                    if f.get("status") == "no_source" and f.get("reason") in ("budget", "context_full"))),
        }
    return out


def measure_gold(gold: Path, qid: str) -> dict[str, Any]:
    q = gold / qid
    doc = _json(q / "doc.json") or {}
    counts = doc.get("counts") or {}
    cost = counts.get("cost") or {}
    triage: dict[str, str] = {}
    for line in _jsonl(q / "triage.jsonl"):  # the last line per id wins
        triage[line.get("id")] = line.get("label")
    key = _json(q / "key.draft.json") or {}
    candidates = counts.get("candidates") or 0
    return {
        "qid": qid, "gold": str(gold), "partial": (doc.get("coverage") or {}).get("partial"),
        "coverage": doc.get("coverage"),
        "chunks": counts.get("chunks"), "chunks_relevant": counts.get("chunks_relevant"),
        "candidates": candidates, "anchored": counts.get("anchored"),
        "anchor_ok_share": round(counts["anchored"] / candidates, 3) if candidates else None,
        "anchor_rejected": counts.get("rejected"), "fixed_by_retry": counts.get("fixed_by_retry"),
        "rows": counts.get("rows"), "too_long": counts.get("too_long"), "split_chunks": counts.get("split_chunks"),
        "triage": dict(Counter(triage.values())), "pool": len(_jsonl(q / "pool.jsonl")),
        "draft_rows": len(key.get("rows") or []),
        "draft_facts": sum(len(r.get("facts") or []) for r in key.get("rows") or []),
        "calls_made": cost.get("calls_made"), "input_tokens": cost.get("input_tokens"),
        "output_tokens": cost.get("output_tokens"), "seconds": cost.get("seconds"),
        "model_calls": counts.get("model_calls"),
        "served": ((doc.get("built") or {}).get("models") or {}).get("served"),
    }


RUN_COLUMNS = [("run", "run_id"), ("cond", "condition"), ("exit", "exit_status"), ("answer", "answer_from"),
               ("steps", "steps"), ("calls", "model_calls"), ("tokens", "tokens"), ("s", "seconds"),
               ("rows", "rows"), ("facts", "facts"), ("claims acc/rej", None), ("max prompt", "max_prompt_tokens"),
               ("max masked", "max_masked"), ("guided answer", "answer_guided"), ("guided calls", "guided_calls"),
               ("refused", "guided_refused"), ("timeouts", "model_timeouts"), ("cut", "guided_cut"),
               ("longest guided s", "longest_guided_s"), ("unparsed", "unparsed"), ("subagents", "subagents"),
               ("attach", None)]
GOLD_COLUMNS = [("qid", "qid"), ("papers", None), ("relevant", None), ("chunks", "chunks"),
                ("relevant chunks", "chunks_relevant"), ("candidates", "candidates"), ("anchor ok", "anchor_ok_share"),
                ("rows", "rows"), ("triage a/c/i", None), ("pool", "pool"), ("draft facts", "draft_facts"),
                ("calls", "calls_made"), ("in tokens", "input_tokens"), ("s", "seconds")]


def _cell(m: dict[str, Any], label: str, key: str | None) -> str:
    if key is not None:
        value = m.get(key)
        return "" if value is None else ("yes" if value is True else "no" if value is False else str(value))
    if label == "claims acc/rej":
        return f"{m['claims_accepted']}/{m['claims_rejected']}"
    if label == "attach":
        a = m.get("attach")
        return "" if not a else (f"{a['facts']} facts, {a['attached']} attached ({a['from_claim']} from claim), "
                                 f"{a['no_source']} none, {a['tokens']} tok, {a['seconds']} s")
    cov = m.get("coverage") or {}
    if label == "papers":
        return str(cov.get("papers", ""))
    if label == "relevant":
        return str(cov.get("relevant", ""))
    t = m.get("triage") or {}
    return f"{t.get('answers', 0)}/{t.get('context', 0)}/{t.get('irrelevant', 0)}"


def table(rows: list[dict[str, Any]], columns: list[tuple[str, str | None]]) -> str:
    lines = ["| " + " | ".join(label for label, _ in columns) + " |", "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(_cell(m, label, key) for label, key in columns) + " |" for m in rows]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="what", required=True)
    r = sub.add_parser("runs", help="one line per run directory")
    r.add_argument("run_dirs", nargs="+", type=Path)
    g = sub.add_parser("gold", help="one line per question of a gold directory")
    g.add_argument("gold", type=Path)
    g.add_argument("qids", nargs="+")
    for p in (r, g):
        p.add_argument("--json", type=Path, help="also write one JSON object per line to this file")
    args = parser.parse_args(argv)
    if args.what == "runs":
        found = [d for d in args.run_dirs if (d / "config.json").is_file()]
        for d in args.run_dirs:
            if d not in found:
                print(f"WARN {d} has no config.json: not a run directory", file=sys.stderr)
        measured, columns = [measure_run(d) for d in found], RUN_COLUMNS
    else:
        measured, columns = [measure_gold(args.gold, q) for q in args.qids], GOLD_COLUMNS
    print(table(measured, columns))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with args.json.open("w", encoding="utf-8") as out:
            for m in measured:
                out.write(json.dumps(m, sort_keys=True) + "\n")
        print(f"wrote {len(measured)} lines to {args.json}")
    return 0 if measured else 1


if __name__ == "__main__":
    sys.exit(main())
