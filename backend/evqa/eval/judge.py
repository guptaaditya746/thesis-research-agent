"""Label judge (plan v2 step 5): does the settings label the user sees describe the seed context of its values?

    out = judge_run(run_dir, lm=None)        # adds "label_judge" to run_dir/eval.json; `evqa eval --judge`

Reported apart from the provenance scores (prism.py never reads labels). Per answer table item whose rows come from
facts of exactly one seed context (prism.Provenance), one blind LLM call (JudgeLabel) gets only the label (the item's
cells other than subject) and the context description: no run verdicts, no ids, no scores. Code checks the verdict is
on the list; an unreadable reply is retried once, then counted "unreadable". Items without one provenance context are
counted, not judged.

Population judge (judge_population, `evqa eval --judge-population`): Prism marks a value-matched row's population
"unverified" when its own label names the patients in other words than the seed context (prism.population_check).
The same blind JudgeLabel call gets that label and the seed context only. "matches" -> pass, "does not match" ->
fail, "unclear"/unreadable -> stays unverified. l2_complete_judged = per question, facts complete by code or pending
with only the population left and judged "matches", / gold facts; mean over questions (as prism l2_complete).
Written to run_dir/population_judge.json; eval.json is not changed. Use a judge model other than the run's Extract
model (docs/prompt-writing.md); the file records both.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import dspy
from pydantic import BaseModel

from evqa.contracts import Answer, Row, RunConfig, read_jsonl
from evqa.eval import prism

VERDICTS = ("matches", "does not match", "unclear")


class LabelVerdict(BaseModel):
    verdict: Literal["matches", "does not match", "unclear"] = "unclear"
    reason: str = ""


class JudgeLabel(dspy.Signature):
    """Decide whether a table label describes the given study conditions.

    Input: label is the text a reader sees next to a value (setting values joined by " · ", or "not stated");
    conditions is the true description of the conditions the value was measured under.
    Output: verdict "matches" (the label names these conditions, possibly in other words or shorter), "does not
    match" (the label names other or narrower/broader conditions), or "unclear" (the label is empty, "not stated",
    or too vague to tell); reason is one short sentence.
    Examples: label "asthmatic adults", conditions "adults with asthma" -> matches. Label "annealed", conditions
    "as-cast specimens" -> does not match. Label "not stated", conditions "zero-shot prompting" -> unclear.
    """
    label: str = dspy.InputField()
    conditions: str = dspy.InputField()
    judgement: LabelVerdict = dspy.OutputField()


def label_of(cells: dict[str, str]) -> str:
    vals = [v for k, v in cells.items() if k != "subject" and v and v != "not stated"]
    return " · ".join(vals) or "not stated"


def ask(label: str, conditions: str, lm: dspy.BaseLM) -> LabelVerdict | None:
    for attempt in range(2):
        try:
            with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
                out = dspy.Predict(JudgeLabel)(label=label, conditions=conditions,
                                               config={"attempt": attempt} if attempt else {})
            got = out.judgement if isinstance(out.judgement, LabelVerdict) else LabelVerdict.model_validate(out.judgement)
            if got.verdict in VERDICTS:
                return got
        except Exception:   # noqa: BLE001 - an unreadable reply is retried once, then counted
            continue
    return None


def judge_run(run_dir: Path, lm: dspy.BaseLM | None = None) -> dict[str, Any]:
    run_dir = Path(run_dir)
    cfg = RunConfig.load(run_dir / "config.yaml")
    if lm is None:
        from evqa.lm import make_lm
        lm = make_lm(cfg.llm_for("judge"))
    eval_path = run_dir / "eval.json"
    ev = json.loads(eval_path.read_text(encoding="utf-8")) if eval_path.is_file() else prism.score_run(run_dir)
    items: list[dict[str, Any]] = []
    skipped = 0
    seen: dict[tuple[str, str], LabelVerdict | None] = {}
    for qid in ev.get("questions", {}):
        qdir = run_dir / qid
        if not (qdir / "answer.json").is_file():
            continue
        ans = Answer.model_validate_json((qdir / "answer.json").read_text(encoding="utf-8"))
        rows: list[Row] = read_jsonl(qdir / "rows.jsonl", Row)
        prov = prism.Provenance(rows, cfg.domain)
        for item in ans.table:
            context = prov.value("patient_group", item.rows)
            if context == "?" or not context:
                skipped += 1
                continue
            label = label_of(item.cells)
            if (label, context) not in seen:
                seen[(label, context)] = ask(label, context, lm)
            got = seen[(label, context)]
            items.append({"qid": qid, "label": label, "conditions": context,
                          "verdict": got.verdict if got else "unreadable", "reason": got.reason if got else ""})
    counts = {v: sum(i["verdict"] == v for i in items) for v in (*VERDICTS, "unreadable")}
    out = {"items": len(items), "not_judged_no_single_context": skipped, "counts": counts,
           "match_rate": round(counts["matches"] / len(items), 4) if items else None, "calls": len(seen),
           "details": items}
    ev["label_judge"] = out
    eval_path.write_text(json.dumps(ev, indent=2) + "\n", encoding="utf-8")
    return out


def judge_population(run_dir: Path, lm: dspy.BaseLM | None = None, judge_model: str | None = None,
                     write: bool = True) -> dict[str, Any]:
    """Settle Prism's unverified populations with the blind label judge (module doc)."""
    run_dir = Path(run_dir)
    cfg = RunConfig.load(run_dir / "config.yaml")
    if lm is None:
        from evqa.lm import make_lm
        step = cfg.llm_for("judge")
        lm = make_lm(step)
        judge_model = judge_model or f"{step.backend}:{step.model}"
    ev = prism.score_run(run_dir, domain=cfg.domain, write=False)     # current scorer, saved eval.json untouched
    facts_all = prism.seed_facts(cfg.domain)
    seen: dict[tuple[str, str], LabelVerdict | None] = {}
    items: list[dict[str, Any]] = []
    per_q: list[float] = []
    for qid, q in ev["questions"].items():
        if not q["facts"]:
            continue
        rows: list[Row] = read_jsonl(run_dir / qid / "rows.jsonl", Row) if q["facts"] else []
        good = 0
        for f in q["facts"]:
            if f["complete"] == "complete":
                good += 1
                continue
            checks = f["complete_checks"]
            if f["complete"] != "pending" or [k for k, v in checks.items() if v == "unverified"] != ["population"]:
                continue
            row = rows[f["complete_row"]]
            label = row.patient_group or row.patient_group_raw or "not stated"
            context = facts_all[f["id"]]["context"]
            if (label, context) not in seen:
                seen[(label, context)] = ask(label, context, lm)
            got = seen[(label, context)]
            verdict = got.verdict if got else "unreadable"
            good += verdict == "matches"
            items.append({"qid": qid, "fact": f["id"], "row": f["complete_row"], "label": label,
                          "conditions": context, "verdict": verdict, "reason": got.reason if got else ""})
        per_q.append(good / len(q["facts"]))
    counts = {v: sum(i["verdict"] == v for i in items) for v in (*VERDICTS, "unreadable")}
    out = {"run_id": ev["run_id"], "scorer": ev["scorer"], "judge_model": judge_model,
           "extract_model": f"{cfg.llm_for('extract').backend}:{cfg.llm_for('extract').model}",
           "items": len(items), "calls": len(seen), "counts": counts,
           "l2_complete": ev["totals"]["l2_complete"], "l2_complete_upper": ev["totals"]["l2_complete_upper"],
           "l2_complete_judged": round(sum(per_q) / len(per_q), 4) if per_q else None, "details": items}
    if write:
        (run_dir / "population_judge.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out
