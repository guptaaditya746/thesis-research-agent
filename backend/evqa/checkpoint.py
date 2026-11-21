"""Settings checkpoint report (Q1): one Markdown file from a run folder's spec.json, rows.jsonl and settings.jsonl.

    uv run python -m evqa.checkpoint runs/evqa/<run_id> docs/design/checkpoint-settings.md

No LLM. Counts, by code only:
  candidate quotes   every setting the model returned in any attempt (spec dimensions and extras), value not
                     "not stated": pass = anchor.spans finds its quote in the paper (line breaks, dash types and
                     curly quotes tolerated, as for row quotes); "exact" = a verbatim substring. This is the Q1 gate (>= 90%).
  final quotes       the same over the last attempt per paper only (what the repair produced).
  question copies    final settings whose value appears in the question text but whose quote is not in the paper or
                     does not contain the value (the "copied from the question" check; 0 expected).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from evqa import corpus
from evqa.extract import anchor


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.is_file() else []


def _candidates(attempt: dict) -> list[dict]:
    return [s for d in attempt.get("drafts") or [] for s in [*d.get("settings", []), *d.get("extra_settings", [])]
            if s.get("value", "not stated") != "not stated"]


def report(run_dir: Path) -> tuple[str, dict]:
    cfg = json.loads(json.dumps(__import__("yaml").safe_load((run_dir / "config.yaml").read_text())))
    texts = corpus.papers(cfg["domain"])
    totals = {"candidates": 0, "candidates_ok": 0, "candidates_exact": 0, "recovered_checks": 0, "final": 0, "final_ok": 0, "question_copies": 0,
              "attempts": 0, "rejected_attempts": 0, "unassigned_rows": 0, "rows": 0, "missing_audit": []}
    body: list[str] = []
    for qdir in sorted((d for d in run_dir.iterdir() if d.is_dir()), key=lambda d: int(d.name.rsplit("p", 1)[-1])
                       if d.name.rsplit("p", 1)[-1].isdigit() else 0):
        spec = json.loads((qdir / "spec.json").read_text()) if (qdir / "spec.json").is_file() else {}
        question = spec.get("question", "")
        audit = _jsonl(qdir / "settings.jsonl")
        rows = [r for r in _jsonl(qdir / "rows.jsonl") if not r.get("dropped")]
        body += [f"## {qdir.name}", "", question, ""]
        dims = "; ".join(f"{d['key']} = {d.get('fixed_value') or 'open'}" for d in spec.get("dimensions", []))
        body += [f"Dimensions: {dims or 'none'}", ""]
        if rows and not audit:
            totals["missing_audit"].append(qdir.name)
        if not audit:
            body += ["- No extracted rows." if not rows else "- Rows but no settings audit.", ""]
            continue
        for paper in audit:
            text = texts.get(paper["paper"], "")
            attempts = paper.get("attempts", [])
            body.append(f"### {paper['paper']}")
            for a in attempts:
                totals["attempts"] += 1
                totals["rejected_attempts"] += not a.get("accepted")
                cands = _candidates(a)
                ok = [s for s in cands if s.get("quote") and anchor.spans(text, s["quote"])]
                totals["candidates_exact"] += sum(1 for s in cands if s.get("quote") and s["quote"] in text)
                # checks that failed only because of exact matching (quote found now, value still in quote)
                totals["recovered_checks"] += sum(1 for s in ok if s["quote"] not in text and s["value"] in s["quote"])
                totals["candidates"] += len(cands)
                totals["candidates_ok"] += len(ok)
                state = "accepted" if a.get("accepted") else "rejected"
                body.append(f"- attempt {a['attempt'] + 1} ({state}): {len(cands)} candidate settings in "
                            f"{len(a.get('drafts') or [])} sets, {len(ok)} quotes found in the paper")
                for s in cands:
                    mark = "ok" if s in ok else "QUOTE NOT IN PAPER"
                    tag = " (extra)" if s in [x for d in a.get("drafts") or [] for x in d.get("extra_settings", [])] else ""
                    body.append(f"  - {s['dimension']}{tag}: {s['value']}; quote: \"{s.get('quote', '')}\" [{mark}]")
                fails = [*a.get("check_failures", []), *a.get("verifier_failures", [])] + ([a["error"]] if a.get("error") else [])
                for f in fails:
                    body.append(f"  - failed check: {f}")
            if attempts:
                last = _candidates(attempts[-1])
                totals["final"] += len(last)
                totals["final_ok"] += sum(1 for s in last if s.get("quote") and anchor.spans(text, s["quote"]))
            for group in paper.get("final_sets", []):
                for s in group["settings"]:
                    v = s.get("value", "not stated")
                    if v != "not stated" and v.lower() in question.lower() and (not anchor.spans(text, s["quote"]) or v not in s["quote"]):
                        totals["question_copies"] += 1
                body.append(f"- final {group['id']}: {group.get('label') or 'not stated'}"
                            + (f"; extras kept: {', '.join(paper['extras_kept'])}" if paper.get("extras_kept") else ""))
            for r in paper.get("rows", []):
                totals["rows"] += 1
                if not r.get("settings"):
                    totals["unassigned_rows"] += 1
                    body.append(f"- row not assigned: \"{r['quote'][:120]}\"")
            body.append("")
    pct = lambda a, b: f"{100 * a / b:.1f}%" if b else "n/a"   # noqa: E731
    head = [
        "# Q1 practice checkpoint (settings)", "",
        f"Run: `{run_dir.name}`. Generated by `uv run python -m evqa.checkpoint` (code only, no LLM).", "",
        f"- Candidate setting quotes (every attempt): {totals['candidates_ok']}/{totals['candidates']} found in the "
        f"paper = {pct(totals['candidates_ok'], totals['candidates'])} (gate: >= 90%)",
        f"- Exact substring only (old check): {totals['candidates_exact']}/{totals['candidates']}; failed checks "
        f"recovered by tolerant matching: {totals['recovered_checks']}",
        f"- Final attempt only: {totals['final_ok']}/{totals['final']} = {pct(totals['final_ok'], totals['final'])}",
        f"- Attempts: {totals['attempts']}, rejected: {totals['rejected_attempts']}",
        f"- Values copied from the question without paper support: {totals['question_copies']}",
        f"- Rows without a setting set: {totals['unassigned_rows']}/{totals['rows']}",
        f"- Questions with rows but no audit: {', '.join(totals['missing_audit']) or 'none'}", "",
        "Only practice questions were inspected. The verifier runs on the same Qwen weights as the generator, so its "
        "agreement is correlated evidence.", ""]
    return "\n".join(head + body) + "\n", totals


def main(argv: list[str]) -> int:
    text, totals = report(Path(argv[0]))
    Path(argv[1]).write_text(text, encoding="utf-8")
    print(json.dumps(totals))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
