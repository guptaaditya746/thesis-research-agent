"""The bodies of the whole-run evaluation commands (`evaluate wholerun | leak | offtemplate | links`, Task 8.3).

`wholerun` scores the plan runs of one real set (nothing here starts a run or calls a model; the RAG baseline is
passed in as `rag_answer`). The runbook writes each plan run into `--runs` as
<runs>/<auto-confirmed|hand-confirmed>/<on|off>/<question id>/ (answer.json, plan.json, run.json, evidence.jsonl).
The auto-confirmed row covers every question of sample.json; the hand-confirmed row is the FIRST 5 questions of
sample.json, so a person must confirm exactly those 5. Rows are named "<confirmation>/<reasoning>"; the RAG rows
"rag/global" and "rag/per_paper" (Task 6.5: same questions, same papers, same model).

Rules for what is scored:
- A question with no run folder is a "missing run": it counts as a loss for the engine (headline 0) in the row, the
  summary and the pairing, and is listed under `missing`.
- A run folder without plan.json is a "missing plan": treated as a missing run (headline 0, a loss in the pairing, in n)
  and listed under `missing_plan`; never scored. A plan not confirmed as its row says is refused. A row whose every
  question is missing is kept (mean 0).
- With the RAG baseline, every engine run's run.json must name the same papers (corpus manifest) and the same model
  as the baseline (`rag_model`); a mismatch (or no run.json) is refused (ValueError).
- Questions whose papers are in tune_split.json are dropped before sampling (`held_out_for_tuning`).

Report (wholerun.json and wholerun.md): `rows` (per-question scores, each with `headline`; a question that cannot be
scored has `headline` 0 and counts in `n_unscored`), `summary` (per row: n, n_missing_run, n_unscored, mean headline
with a bootstrap interval; rank rows also the mean Kendall tau), `comparison` (every engine row against every RAG
row over the SAME questions: n, n_missing_run, wins, losses, ties, the engine mean, the RAG mean and the paired mean
difference with its interval, evaluation/stats.py; no row assumes the engine wins; row means over different question
sets are not comparable, only these paired means are), `generality` (per confirmation: questions answered with a
fresh query vs a saved template), `left_out`, `held_out_for_tuning`, `missing`, `missing_plan`, `sample`.
Every row with an answer-key (set with key records) carries `error_split`: "right", "synthesis error", "extraction
error", "not available: <why>" or "key split failed: <reason>"; the markdown lists it per question.

Headline per kind: rank top1, list f1, compare direction_agreement, claims recall; a part that is None counts 0.
A "fresh" question: the plan's line asking the question's text (else its first line) has no saved template; the same
rule as the off-template check. The answer-key split runs on that same (main) line.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from evidence.plan import Plan, load_plan
from evidence.rundir import PLAN_FILE, RUN_FILE

from . import report as rep
from . import stats
from .wholerun import (Answer, RealQuestion, from_run, key_store, question_papers, sample, score, tune_papers)

CONFIRMATIONS = ("auto-confirmed", "hand-confirmed")
SYSTEM = "system"                  # who confirm_all(plan, who="system") stamps on an auto-confirmed plan
HAND_N = 5                         # hand-confirmed questions per set
RAG_MODES = ("global", "per_paper")
HEADLINE = {"rank": "top1", "list": "f1", "compare": "direction_agreement", "claims": "recall"}
DEFAULT_MODEL = "orch-model"       # what a run without an explicit model uses (extractors.llm.DEFAULTS)
RagAnswer = Callable[[RealQuestion, str], Answer]


def headline(result: dict[str, Any]) -> float:
    value = result.get(HEADLINE[result["kind"]])
    return float(value) if value is not None else 0.0


def _plan(root: Path) -> Plan | None:
    path = root / PLAN_FILE
    return load_plan(path) if path.is_file() else None


def _check_confirmed(plan: Plan, confirmation: str, where: Path) -> None:
    """An auto-confirmed run's plan is confirmed by "system" only (confirm_all); a hand-confirmed one by a person."""
    who = {d.confirmed_by for d in plan.decisions}
    bad = (who != {SYSTEM}) if confirmation == "auto-confirmed" else (not who - {SYSTEM} or SYSTEM in who)
    if bad:
        raise ValueError(f"{where}: the plan's decisions are confirmed by {sorted(map(str, who))}, which is not "
                         f"{confirmation}")


def _check_engine(root: Path, q: RealQuestion, rag_model: str | None) -> None:
    """The engine run read the baseline's papers and used the baseline's model (run.json settings)."""
    from .baselines.real import check_same_papers
    path = root / RUN_FILE
    if not path.is_file():
        raise ValueError(f"{root}: no {RUN_FILE}; cannot tell which papers and model the engine run used")
    settings = json.loads(path.read_text(encoding="utf-8")).get("settings") or {}
    check_same_papers(q.corpus_dir, Path(settings.get("corpus") or ""))
    model = settings.get("model") or DEFAULT_MODEL
    if rag_model is not None and model != rag_model:
        raise ValueError(f"{root}: the engine run used model {model!r} but the RAG baseline uses {rag_model!r}; "
                         "both must use one model")


def main_line(plan: Plan, q: RealQuestion) -> Any:
    """The plan's line that asks the question (else its first line)."""
    return next((x for x in plan.lines if x.question == q.question), plan.lines[0])


def is_fresh(plan: Plan, q: RealQuestion) -> bool:
    return main_line(plan, q).template is None


def error_split(q: RealQuestion, root: Path, plan: Plan, headline_: float) -> str:
    """truthgraph.split on the main line: "right", "synthesis error" or "extraction error"; "not available: <why>"
    (no key records, kind not covered); "key split failed: <reason>" when the code raised."""
    if q.records is None:
        return "not available: no answer-key records for this set"
    expected = q.gold.get("ranking") if q.kind == "rank" else q.gold.get("items") if q.kind == "list" else None
    if expected is None:
        return f"not available: no split for kind {q.kind}"
    try:
        from evidence.kg import query as kq
        from evidence.kg.truthgraph import split
        from evidence.planrun import line_params
        spec = main_line(plan, q)
        doc = json.loads((root / "answer.json").read_text(encoding="utf-8"))
        line = next((x for x in doc.get("lines") or [] if x.get("id") == spec.id), None)
        rows = list(line["rows"]) if line and line.get("status") == "done" else []
        gold = kq.run_query(key_store(q), spec.query, line_params(plan, spec.query))
        return split(kq.Answer(rows=rows, empty=not rows), gold, list(expected))
    except Exception as exc:   # noqa: BLE001 - a diagnosis only; says what failed, never stops a report
        return f"key split failed: {type(exc).__name__}: {exc}"


def _summary(rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    taus = [r["kendall_tau"] for r in rows if r.get("kendall_tau") is not None]
    out = {"n": len(rows), "n_missing_run": sum(bool(r.get("missing_run")) for r in rows),
           "n_missing_plan": sum(bool(r.get("missing_plan")) for r in rows),
           "n_unscored": sum(bool(r.get("unscored")) for r in rows),
           **stats.interval_row(stats.bootstrap_mean([headline(r) if not r.get("missing_run") else 0.0 for r in rows],
                                                     seed=seed))}
    if taus:
        out["mean_kendall_tau"] = sum(taus) / len(taus)
    splits: dict[str, int] = {}
    for r in rows:
        if "error_split" in r:
            kind = r["error_split"].split(":")[0]
            splits[kind] = splits.get(kind, 0) + 1
    if splits:
        out["error_split"] = splits
    return out


def _compare(engine: list[dict[str, Any]], rag: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    """Engine and RAG over the same questions only (a question both have); a missing engine run is a loss (0)."""
    theirs = {r["id"]: headline(r) for r in rag}
    pairs = [(0.0 if r.get("missing_run") else headline(r), theirs[r["id"]], bool(r.get("missing_run")))
             for r in engine if r["id"] in theirs]
    diffs = [a - b for a, b, _ in pairs]
    n = len(pairs)
    return {"n": n, "n_missing_run": sum(m for _, _, m in pairs), "wins": sum(d > 0 for d in diffs),
            "losses": sum(d < 0 for d in diffs), "ties": sum(d == 0 for d in diffs),
            "engine_mean": sum(a for a, _, _ in pairs) / n if n else None,
            "rag_mean": sum(b for _, b, _ in pairs) / n if n else None,
            "paired": stats.interval_row(stats.bootstrap_mean(diffs, seed=seed)) if diffs else None}


def wholerun(questions: list[RealQuestion], runs: Path, out: Path, *, set_name: str, n: int = 10, seed: int = 0,
             left_out: str, reasoning: Iterable[str] = ("on", "off"), confirm: Iterable[str] = CONFIRMATIONS,
             systems: Iterable[str] = ("engine",), rag_answer: RagAnswer | None = None,
             rag_model: str | None = None, groups: Any = None) -> dict[str, Any]:
    """Score one real set (see the module docstring). Writes sample.json, wholerun.json and wholerun.md in `out`."""
    out, runs = Path(out), Path(runs)
    systems = tuple(systems)
    if "rag" in systems and (rag_answer is None or rag_model is None):
        raise ValueError("--system rag needs a RAG baseline (rag_answer) and its model (rag_model)")
    out.mkdir(parents=True, exist_ok=True)
    held = [q.id for q in questions if set(question_papers(q)) & tune_papers(q)]
    chosen = sample([q for q in questions if q.id not in held], n, seed, out / "sample.json")
    rows: dict[str, list[dict[str, Any]]] = {}
    missing: dict[str, list[str]] = {}
    missing_plan: dict[str, list[str]] = {}
    fresh: dict[str, dict[str, bool]] = {c: {} for c in confirm}
    for conf in confirm:
        pool = chosen if conf == "auto-confirmed" else chosen[:HAND_N]
        for how in reasoning:
            key = f"{conf}/{how}"
            if "engine" not in systems:
                continue
            rows[key], missing[key], missing_plan[key] = [], [], []
            for q in pool:
                root = runs / conf / how / q.id
                if not (root / "answer.json").is_file():
                    missing[key].append(q.id)
                    rows[key].append({"id": q.id, "kind": q.kind, "confirmation": conf, "missing_run": True,
                                      "headline": 0.0})
                    continue
                plan = _plan(root)
                if plan is None:
                    missing_plan[key].append(q.id)
                    rows[key].append({"id": q.id, "kind": q.kind, "confirmation": conf, "missing_run": True,
                                      "missing_plan": True, "headline": 0.0})
                    continue
                _check_confirmed(plan, conf, root)
                if "rag" in systems:
                    _check_engine(root, q, rag_model)
                answer = from_run(root, q)
                result = score(answer, q, confirmation=conf, groups=groups)   # type: ignore[arg-type]
                result["headline"] = headline(result)
                result["unscored"] = result.get(HEADLINE[q.kind]) is None
                result["error_split"] = error_split(q, root, plan, result["headline"])
                rows[key].append(result)
                fresh[conf].setdefault(q.id, is_fresh(plan, q))
    if "rag" in systems:
        for mode in RAG_MODES:
            rows[f"rag/{mode}"] = [(r := score(rag_answer(q, mode), q, groups=groups))   # type: ignore[misc]
                                   | {"headline": headline(r), "unscored": r.get(HEADLINE[q.kind]) is None}
                                   for q in chosen]
    comparison = [{"engine": e, "rag": r, **_compare(rows[e], rows[r], seed)}
                  for e in rows if not e.startswith("rag/") for r in rows if r.startswith("rag/")]
    generality = {c: {"questions": len(f), "fresh": sum(f.values()), "template": len(f) - sum(f.values()),
                      "fresh_share": sum(f.values()) / len(f) if f else None} for c, f in fresh.items() if f}
    report = {"set": set_name, "sample": json.loads((out / "sample.json").read_text(encoding="utf-8")),
              "left_out": left_out, "held_out_for_tuning": held, "rows": rows,
              "missing": {k: v for k, v in missing.items() if v},
              "missing_plan": {k: v for k, v in missing_plan.items() if v},
              "summary": {k: _summary(v, seed) for k, v in rows.items() if v}, "comparison": comparison,
              "generality": generality}
    rep.write_pair(report, render(report), out, "wholerun")
    return report


def _cell(value: Any) -> str:
    return "-" if value is None else (f"{value:.3f}" if isinstance(value, float) else str(value))


def render(report: dict[str, Any]) -> str:
    nl = chr(10)
    sample_ = report["sample"]
    out = [f"# Whole run: {report['set']}", "", f"{report['left_out']}",
           f"Sample: {len(sample_['ids'])} questions (n={sample_['n']}, seed={sample_['seed']}).",
           f"Held out for tuning: {len(report['held_out_for_tuning'])}.", "",
           "## Rows (mean headline per question)", "",
           "Rows cover different questions; compare rows only through the paired means below.", "",
           "| row | n | missing run | unscored | mean [95%] | mean tau | answer-key split |",
           "|---|---|---|---|---|---|---|"]
    for key, s in report["summary"].items():
        split = ", ".join(f"{k} {v}" for k, v in s.get("error_split", {}).items()) or "-"
        out.append(f"| {key} | {s['n']} | {s['n_missing_run']} | {s['n_unscored']} | "
                   f"{stats.interval_text(s['point'], s['low'], s['high'])} | {_cell(s.get('mean_kendall_tau'))} | {split} |")
    for title, table in (("Missing runs (count as a loss for the engine)", report["missing"]),
                         ("Missing plan (not scored)", report["missing_plan"])):
        if table:
            out += ["", f"## {title}", ""] + [f"- {key}: {', '.join(ids)}" for key, ids in table.items()]
    if report["comparison"]:
        out += ["", "## Engine against RAG (paired, same questions)", "",
                "| engine row | RAG row | n | missing run | wins | losses | ties | engine mean | RAG mean | "
                "mean difference [95%] |", "|---|---|---|---|---|---|---|---|---|---|"]
        for c in report["comparison"]:
            p = c["paired"]
            diff = stats.interval_text(p["point"], p["low"], p["high"]) if p else "-"
            out.append(f"| {c['engine']} | {c['rag']} | {c['n']} | {c['n_missing_run']} | {c['wins']} | {c['losses']} | "
                       f"{c['ties']} | {_cell(c['engine_mean'])} | {_cell(c['rag_mean'])} | {diff} |")
    shown = [(k, r) for k, rs in report["rows"].items() for r in rs if "error_split" in r]
    if shown:
        out += ["", "## Answer-key split per question", "", "| row | question | split |", "|---|---|---|"]
        out += [f"| {k} | {r['id']} | {r['error_split']} |" for k, r in shown]
    if report["generality"]:
        out += ["", "## Fresh query or saved template", ""]
        for conf, g in report["generality"].items():
            out.append(f"- {conf}: {g['fresh']} of {g['questions']} questions answered with a fresh query, "
                       f"{g['template']} with a saved template.")
    return nl.join(out) + nl


# --- off-template -------------------------------------------------------------------------------------------------

def offtemplate(runs: Path, out: Path) -> dict[str, Any]:
    """Check every off-template question that has `<runs>/<question id>/plan.json`: the two generality numbers."""
    from .offtemplate import check as ot
    results, per = [], {}
    questions = ot.load_questions()
    for q in questions:
        path = Path(runs) / q.id / PLAN_FILE
        if not path.is_file():
            continue
        found = ot.check(SimpleNamespace(plan=load_plan(path)), q)
        results.append(found)
        per[q.id] = found
    committed = ot.committed_at([ot.QUESTIONS, *sorted(ot.REFERENCE.glob("*.rq"))])
    report = {"summary": ot.summary(results), "questions": per, "not_run": len(questions) - len(results),
              "committed_at": committed.isoformat() if committed else None}
    text = [f"# Off-template check", "",
            f"Questions checked: {report['summary']['questions']} (not run: {report['not_run']}).",
            f"Answered with a fresh query: {_cell(report['summary']['fresh_share'])}.",
            f"Off-template match rate (answer key): {_cell(report['summary']['match_rate'])}.",
            f"Match rate on the run's own records: {_cell(report['summary']['match_on_run_rate'])}.",
            f"Questions first committed: {report['committed_at'] or 'not in git'}.", ""]
    rep.write_pair(report, chr(10).join(text), out, "offtemplate")
    return report


# --- leak ---------------------------------------------------------------------------------------------------------

def leak(run: Path, corpus: Path, out: Path) -> dict[str, Any]:
    """The leak split of a run's extraction recall: facts whose name is "on the list" vs "unseen". The word list is
    the one in the run's plan.json; ValueError for a corpus that is not Claude-written."""
    from . import leak as lk
    from .score import score as score_run
    from .truth import GroundTruth
    plan = load_plan(Path(run) / PLAN_FILE)
    truth = GroundTruth.load(Path(corpus) / "ground_truth.json")
    result = score_run(Path(run), Path(corpus), [], None, None, None)
    marks = lk.mark(truth, plan.words, result["extraction"].get("scored_types"))
    split = lk.split_scores(result, marks)
    nl = chr(10)
    lines = ["# Leak split (extraction recall)", "", "| names | facts | matched | recall |", "|---|---|---|---|"]
    lines += [f"| {k} | {v['facts']} | {v['matched']} | {_cell(v['recall'])} |" for k, v in split.items()]
    rep.write_pair(split, nl.join(lines) + nl, out, "leak")
    return split


# --- links --------------------------------------------------------------------------------------------------------

def _work(ref: str) -> str:
    return re.sub(r".*/", "", str(ref).strip())


def builds_on_recall(links: list[dict[str, Any]], references: dict[str, list[str]]) -> dict[str, Any]:
    """Builds-on links against OpenAlex `references` (evidence.openalex.references, saved per paper as
    {paper id: [work id, ...]}): recall of each paper's referenced works among the run's links, and precision of the
    links. Work ids compare by their last path segment ("https://openalex.org/W1" is "W1"). None when a side is empty."""
    found: dict[str, set[str]] = {}
    for link in links:
        if link.get("paper") in references:
            found.setdefault(link["paper"], set()).add(_work(link["ref"]))
    per, right, total_found, total_want = {}, 0, 0, 0
    for paper, refs in references.items():
        want, got = {_work(r) for r in refs}, found.get(paper, set())
        per[paper] = {"expected": len(want), "found": len(want & got)}
        right += len(want & got)
        total_found += len(got)
        total_want += len(want)
    return {"recall": right / total_want if total_want else None, "precision": right / total_found if total_found else None,
            "n_expected": total_want, "n_links": total_found, "per_paper": per}


def links(run: Path, out: Path, *, corpus: Path | None = None, question_id: str | None = None,
          references: Path | None = None) -> dict[str, Any]:
    """Chaining (with `question_id`): the existing scorer's result against the synthetic truth network
    (evaluation/score.py); builds-on (with `references`): `builds_on_recall` of the run's links."""
    result: dict[str, Any] = {}
    if question_id is not None:
        from .score import score as score_run
        if corpus is None:
            raise ValueError("chaining needs --corpus")
        result["chaining"] = score_run(Path(run), Path(corpus), [], None, None, question_id)
    if references is not None:
        answer = json.loads((Path(run) / "answer.json").read_text(encoding="utf-8"))
        result["builds_on"] = builds_on_recall(answer.get("links") or [],
                                               json.loads(Path(references).read_text(encoding="utf-8")))
    if not result:
        raise ValueError("give --question-id (chaining) and/or --references (builds-on)")
    nl = chr(10)
    text = ["# Links", ""]
    if "chaining" in result:
        text += [f"Chaining ({result['chaining'].get('question_id')}): see links.json."]
    if "builds_on" in result:
        b = result["builds_on"]
        text += [f"Builds-on recall of OpenAlex references: {_cell(b['recall'])} (precision {_cell(b['precision'])})."]
    rep.write_pair(result, nl.join(text) + nl, out, "links")
    return result
