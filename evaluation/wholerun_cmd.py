"""The bodies of the whole-run evaluation commands (`evaluate wholerun | leak | offtemplate | links`, Task 8.3).

`wholerun` scores the plan runs of one real set (nothing here starts a run or calls a model; the RAG baseline is
passed in as `rag_answer`). Layout of `--runs`:  <runs>/<auto-confirmed|hand-confirmed>/<on|off>/<question id>/  each
a plan run folder (answer.json, plan.json, evidence.jsonl). A question with no run folder is listed under `missing`,
never scored as an empty answer. Rows are named "<confirmation>/<reasoning>"; the RAG rows "rag/global" and
"rag/per_paper" (Task 6.5: same questions, same papers, same model).

Report (wholerun.json and wholerun.md): `rows` (the per-question scores, each with its `headline`), `summary` (mean
headline with a bootstrap interval per row), `comparison` (every engine row against every RAG row: wins, losses,
ties and the paired interval of the headline differences, evaluation/stats.py; no row assumes the engine wins),
`generality` (per confirmation: questions answered with a fresh query vs a saved template), `left_out` (the open-full-
text line), `held_out_for_tuning` (questions left out because their papers are in tune_split.json), `missing`,
`sample` (the fixed sample, also saved as sample.json).

Headline per kind: rank top1, list f1, compare direction_agreement, claims recall; a part that is None counts 0.
A "fresh" question: the plan's line asking the question's text (else its first line) has no saved template; the same
rule as the off-template check.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from evidence.plan import Plan, load_plan
from evidence.rundir import PLAN_FILE

from . import report as rep
from . import stats
from .wholerun import (Answer, RealQuestion, from_run, key_store, question_papers, sample, score, tune_papers)

CONFIRMATIONS = ("auto-confirmed", "hand-confirmed")
SYSTEM = "system"                  # who confirm_all(plan, who="system") stamps on an auto-confirmed plan
HAND_N = 5                         # hand-confirmed questions per set
RAG_MODES = ("global", "per_paper")
HEADLINE = {"rank": "top1", "list": "f1", "compare": "direction_agreement", "claims": "recall"}
RagAnswer = Callable[[RealQuestion, str], Answer]


def headline(result: dict[str, Any]) -> float:
    value = result.get(HEADLINE[result["kind"]])
    return float(value) if value is not None else 0.0


def _plan(root: Path) -> Plan | None:
    path = root / PLAN_FILE
    return load_plan(path) if path.is_file() else None


def _check_confirmed(plan: Plan | None, confirmation: str, where: Path) -> None:
    """An auto-confirmed run's plan is confirmed by "system" only (confirm_all); a hand-confirmed one by a person."""
    if plan is None:
        return
    who = {d.confirmed_by for d in plan.decisions}
    bad = (who != {SYSTEM}) if confirmation == "auto-confirmed" else (not who - {SYSTEM} or SYSTEM in who)
    if bad:
        raise ValueError(f"{where}: the plan's decisions are confirmed by {sorted(map(str, who))}, which is not "
                         f"{confirmation}")


def is_fresh(plan: Plan, q: RealQuestion) -> bool:
    line = next((x for x in plan.lines if x.question == q.question), plan.lines[0])
    return line.template is None


def _error_split(q: RealQuestion, root: Path, plan: Plan | None, answer: Answer) -> str | None:
    """Right / synthesis error / extraction error (truthgraph.split) for a question whose set has answer-key records
    and whose answer is a ranking or a list; None when it cannot be told."""
    expected = q.gold.get("ranking") if q.kind == "rank" else q.gold.get("items") if q.kind == "list" else None
    store = key_store(q)
    if plan is None or store is None or expected is None:
        return None
    try:
        from evidence.kg import query as kq
        from evidence.kg.truthgraph import split
        from evidence.planrun import line_params
        doc = json.loads((root / "answer.json").read_text(encoding="utf-8"))
        line = next(x for x in doc["lines"] if x.get("status") == "done" and x.get("rows"))
        spec = next(x for x in plan.lines if x.id == line["id"])
        ours = kq.Answer(rows=line["rows"], empty=False)
        gold = kq.run_query(store, spec.query, line_params(plan, spec.query))
        return split(ours, gold, list(expected))
    except Exception:   # noqa: BLE001 - a diagnosis only; never stops a report
        return None


def _summary(rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    return {"questions": len(rows), **stats.interval_row(stats.bootstrap_mean([headline(r) for r in rows], seed=seed))}


def _compare(engine: list[dict[str, Any]], rag: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    theirs = {r["id"]: headline(r) for r in rag}
    diffs = [headline(r) - theirs[r["id"]] for r in engine if r["id"] in theirs]
    return {"n": len(diffs), "wins": sum(d > 0 for d in diffs), "losses": sum(d < 0 for d in diffs),
            "ties": sum(d == 0 for d in diffs),
            "paired": stats.interval_row(stats.bootstrap_mean(diffs, seed=seed)) if diffs else None}


def wholerun(questions: list[RealQuestion], runs: Path, out: Path, *, set_name: str, n: int = 10, seed: int = 0,
             left_out: str, reasoning: Iterable[str] = ("on", "off"), confirm: Iterable[str] = CONFIRMATIONS,
             systems: Iterable[str] = ("engine",), rag_answer: RagAnswer | None = None,
             groups: Any = None) -> dict[str, Any]:
    """Score one real set (see the module docstring). Writes sample.json, wholerun.json and wholerun.md in `out`."""
    out, runs = Path(out), Path(runs)
    out.mkdir(parents=True, exist_ok=True)
    held = [q.id for q in questions if set(question_papers(q)) & tune_papers(q)]
    chosen = sample([q for q in questions if q.id not in held], n, seed, out / "sample.json")
    systems = tuple(systems)
    rows: dict[str, list[dict[str, Any]]] = {}
    missing: dict[str, list[str]] = {}
    fresh: dict[str, dict[str, bool]] = {c: {} for c in confirm}
    for conf in confirm:
        pool = chosen if conf == "auto-confirmed" else chosen[:HAND_N]
        for how in reasoning:
            key = f"{conf}/{how}"
            if "engine" not in systems:
                continue
            rows[key], missing[key] = [], []
            for q in pool:
                root = runs / conf / how / q.id
                if not (root / "answer.json").is_file():
                    missing[key].append(q.id)
                    continue
                plan = _plan(root)
                _check_confirmed(plan, conf, root)
                answer = from_run(root, q)
                result = score(answer, q, confirmation=conf, groups=groups)   # type: ignore[arg-type]
                result["headline"] = headline(result)
                if result["headline"] < 1 and (split := _error_split(q, root, plan, answer)):
                    result["error_split"] = split
                rows[key].append(result)
                if plan is not None:
                    fresh[conf].setdefault(q.id, is_fresh(plan, q))
            if not rows[key]:
                del rows[key]    # no run at all for this row: only `missing` says so
    if "rag" in systems:
        if rag_answer is None:
            raise ValueError("--system rag needs a RAG baseline (rag_answer)")
        for mode in RAG_MODES:
            rows[f"rag/{mode}"] = [(r := score(rag_answer(q, mode), q, groups=groups)) | {"headline": headline(r)}
                                   for q in chosen]
    comparison = [{"engine": e, "rag": r, **_compare(rows[e], rows[r], seed)}
                  for e in rows if not e.startswith("rag/") for r in rows if r.startswith("rag/")]
    generality = {c: {"questions": len(f), "fresh": sum(f.values()), "template": len(f) - sum(f.values()),
                      "fresh_share": sum(f.values()) / len(f) if f else None} for c, f in fresh.items() if f}
    report = {"set": set_name, "sample": json.loads((out / "sample.json").read_text(encoding="utf-8")),
              "left_out": left_out, "held_out_for_tuning": held, "rows": rows, "missing": missing,
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
           f"Held out for tuning: {len(report['held_out_for_tuning'])}.", "", "## Rows (mean headline per question)", "",
           "| row | questions | mean | 95% interval |", "|---|---|---|---|"]
    for key, s in report["summary"].items():
        out.append(f"| {key} | {s['questions']} | {stats.interval_text(s['point'], s['low'], s['high'])} | |")
    for key, gone in report["missing"].items():
        if gone:
            out.append(f"| {key} | missing runs: {', '.join(gone)} | | |")
    if report["comparison"]:
        out += ["", "## Engine against RAG (paired, per question)", "",
                "| engine row | RAG row | wins | losses | ties | mean difference [95%] |", "|---|---|---|---|---|---|"]
        for c in report["comparison"]:
            p = c["paired"]
            diff = stats.interval_text(p["point"], p["low"], p["high"]) if p else "-"
            out.append(f"| {c['engine']} | {c['rag']} | {c['wins']} | {c['losses']} | {c['ties']} | {diff} |")
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
