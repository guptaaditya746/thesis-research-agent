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
error", "plan error: <why>", "not available: <why>" or "key split failed: <reason>"; the markdown lists it per question.

Headline per kind: rank top1, list f1, compare direction_agreement, claims recall; a part that is None counts 0.
A "fresh" question: the plan's line asking the question's text (else its first line) has no saved template; the same
rule as the off-template check. The headline and the answer-key split read one line, `wholerun.scored_line` (a ranking:
its first rank/best line), and judge a ranking by top-1 alike; a failed scored line is a "plan error".
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path

import repo_paths
from typing import Any

from evidence.plan import Plan, load_plan
from evidence.rundir import ANSWER_FILE, PLAN_FILE, RECORDS_FILE, RUN_FILE, RunDir

from . import report as rep
from . import stats
from .wholerun import (Answer, RealQuestion, answer_column, from_run, question_papers, sample, score,
                       scored_line, tune_papers)
from .planbatch import CONFIRMATIONS, REASONING, SYSTEM, pool, run_dir   # the layout scripts/plan-runs.py writes

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
    settings = RunDir(root).settings
    if settings is None:
        raise ValueError(f"{root}: no {RUN_FILE}; cannot tell which papers and model the engine run used")
    check_same_papers(q.corpus_dir, Path(settings.corpus))
    model = settings.model or DEFAULT_MODEL
    if rag_model is not None and model != rag_model:
        raise ValueError(f"{root}: the engine run used model {model!r} but the RAG baseline uses {rag_model!r}; "
                         "both must use one model")


def main_line(plan: Plan, q: RealQuestion) -> Any:
    """The plan's line that asks the question (else its first line)."""
    return next((x for x in plan.lines if x.question == q.question), plan.lines[0])


def is_fresh(plan: Plan, q: RealQuestion) -> bool:
    line = main_line(plan, q)
    return line.template is None and bool(line.query.strip())   # an unplanned line is not a fresh query


def plan_metrics(records: list[dict[str, Any]], plan: Plan) -> list[dict[str, Any]]:
    """The key records with each metric renamed to the plan measure it names (the measure id, or one of its word-list
    names, by `names.clean`): the plan's queries filter on measure ids ("f1"), the release spells "F1". A metric no
    measure names keeps its name. Values, papers and things are untouched."""
    from evidence.names import clean
    names = {clean(n): m for m in plan.measures for n in (m, *plan.words.things.get(m, []))}
    return [{**r, "metric": names.get(clean(str(r["metric"])), r["metric"])} for r in records]


def error_split(q: RealQuestion, root: Path, plan: Plan, headline_: float) -> str:
    """truthgraph.split on the scored line (`scored_line`, the line the headline reads; a ranking judged by top-1 as
    the headline is): "right", "synthesis error" or "extraction error"; "plan error: <why>" when that line failed in
    the run (the plan could not run it, so neither the extraction nor the synthesis was tried); "not available:
    <why>" (no key records, kind not covered); "key split failed: <reason>" when the code raised. The key records'
    metrics are named as the plan's measures (`plan_metrics`); the line runs on them as the run answered its lines
    (`PlanLines.of_run`: the run's plan version)."""
    if q.records is None:
        return "not available: no answer-key records for this set"
    expected = q.gold.get("ranking") if q.kind == "rank" else q.gold.get("items") if q.kind == "list" else None
    if expected is None:
        return f"not available: no split for kind {q.kind}"
    try:
        from evidence.kg import query as kq
        from evidence.kg.truthgraph import split
        from evidence.planlines import PlanLines

        from .realpapers.keystore import store
        spec = scored_line(plan, q)
        doc = json.loads((root / "answer.json").read_text(encoding="utf-8"))
        line = next((x for x in doc.get("lines") or [] if x.get("id") == spec.id), None)
        if line is not None and line.get("status") == "failed":
            return f"plan error: line {spec.id} failed: {str(line.get('text') or '')[:160]}"
        rows = list(line["rows"]) if line and line.get("status") == "done" else []
        gold = PlanLines.of_run(root, store(plan_metrics(q.records, plan)), plan=plan).query(spec.query)
        return split(kq.Answer(rows=rows, empty=not rows), gold, list(expected), answer_column(q, spec.query),
                     top1=q.kind == "rank")
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
             left_out: str, reasoning: Iterable[str] = REASONING, confirm: Iterable[str] = CONFIRMATIONS,
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
        for how in reasoning:
            key = f"{conf}/{how}"
            if "engine" not in systems:
                continue
            rows[key], missing[key], missing_plan[key] = [], [], []
            for q in pool(chosen, conf):
                root = run_dir(runs, conf, how, q.id)
                if not RunDir(root).file(ANSWER_FILE).is_file():   # a failed run's empty answer is scored (0)
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
    from evidence.planlines import PlanLines, load_records

    from .offtemplate import check as ot
    results, per = [], {}
    questions = ot.load_questions()
    for q in questions:
        path = Path(runs) / q.id / PLAN_FILE
        if not path.is_file():   # no plan (planning or the run failed): counted, neither fresh nor a match
            found = {"fresh": False, "match_on_key": False, "match_on_run": None, "extra_columns": [],
                     "failed": "missing plan"}
            results.append(found)
            per[q.id] = found
            continue
        try:
            found = ot.check(PlanLines.of_run(path.parent, load_records(path.parent)), q)   # as the run answered
        except Exception as exc:   # noqa: BLE001 - one bad question is a "no match", never a dead report
            try:
                fresh = ot.is_fresh(ot.plan_line(load_plan(path), q))    # known without running the query
            except Exception:   # noqa: BLE001 - an unreadable plan has no line to look at
                fresh = False
            has_records = RunDir(path.parent).file(RECORDS_FILE).is_file()   # a run with records: no match end to end
            found = {"fresh": fresh, "match_on_key": False, "match_on_run": False if has_records else None,
                     "extra_columns": [], "failed": f"failed: {type(exc).__name__}: {exc}"}
        results.append(found)
        per[q.id] = found
    committed = ot.committed_at([ot.QUESTIONS, *sorted(ot.REFERENCE.glob("*.rq"))])
    report = {"summary": ot.summary(results), "questions": per,
              "not_run": sum(r.get("failed") == "missing plan" for r in results),
              "committed_at": committed.isoformat() if committed else None}
    text = [f"# Off-template check", "",
            f"Questions checked: {report['summary']['questions']} (not run: {report['not_run']}).",
            f"Answered with a fresh query: {_cell(report['summary']['fresh_share'])}.",
            f"Off-template match rate (answer key): {_cell(report['summary']['match_rate'])}.",
            f"Match rate on the run's own records: {_cell(report['summary']['match_on_run_rate'])}.",
            *[f"- {i}: {r['failed']}" for i, r in per.items() if r.get("failed")],
            f"Questions first committed: {report['committed_at'] or 'not in git'}.", ""]
    rep.write_pair(report, chr(10).join(text), out, "offtemplate")
    return report


# --- leak ---------------------------------------------------------------------------------------------------------

TUNED_WORD_STEPS = ("write_words", "write_more_words")     # the tuned steps that write the word list
CORPORA_ROOT = repo_paths.EV2_CORPORA


def _condition_names(truth: Any, *, aliases: bool) -> set[str]:
    """The cleaned names of a truth's conditions. With `aliases=True` what the tuning gold holds (`tune._names_by_role`:
    every role but `other`, label and aliases); with `aliases=False` what the leak split marks (every condition's
    label)."""
    from evidence.names import clean
    names = set()
    for fact in truth.facts.values():
        if fact.type == "condition" and (not aliases or fact.data.get("role") != "other"):
            names |= {clean(n) for n in [fact.data.get("label"), *(fact.data.get("aliases") or [] if aliases else [])]
                      if isinstance(n, str)}
    return names - {""}


def _corpus_index(roots: Iterable[Path]) -> dict[str, Path]:
    """{corpus id: folder} for every folder under `roots` that holds a ground_truth.json. The id is the manifest's
    `corpus_id` (what tune.py writes into a tuned file, `tune._corpus_id`), else the folder name; the folder name
    also finds it."""
    index: dict[str, Path] = {}
    for root in roots:
        for folder in sorted(p for p in Path(root).iterdir() if (p / "ground_truth.json").is_file()) if Path(root).is_dir() else []:
            manifest = folder / "manifest.json"
            ident = str(json.loads(manifest.read_text(encoding="utf-8")).get("corpus_id") or folder.name)                 if manifest.is_file() else folder.name
            index.setdefault(ident, folder)
            index.setdefault(folder.name, folder)
    return index


def check_tuned_words(truth: Any, tuned_dir: Path | None = None, corpora: Iterable[Path] = ()) -> None:
    """Refuse (ValueError) when a tuned word-writing step was tuned on corpora whose condition names (cleaned, not
    hashed) overlap the leak corpus's: the tuned instructions may then hold the names the split calls "unseen".
    `tuned_dir` holds the tuned files (default evidence/steps/tuned); no file, no refusal. The corpora a file lists
    are looked up by id in `corpora` (default tests/EV2/corpora); one that cannot be read is refused too."""
    from .truth import GroundTruth
    if tuned_dir is None:
        from evidence.steps import TUNED_DIR
        tuned_dir = TUNED_DIR
    roots = [Path(c) for c in corpora] or [CORPORA_ROOT]
    index = _corpus_index(roots)
    mine = _condition_names(truth, aliases=False)
    for step in TUNED_WORD_STEPS:
        path = Path(tuned_dir) / f"{step}.json"
        if not path.is_file():
            continue
        tuned = json.loads(path.read_text(encoding="utf-8"))
        for side in ("train_corpora", "test_corpora"):
            for corpus_id in tuned.get(side) or []:
                found = index.get(corpus_id)
                if found is None:
                    raise ValueError(f"tuned {step} ({path}) lists {side[:-8]} corpus {corpus_id!r}, which cannot be "
                                     f"read from {[str(r) for r in roots]}: cannot tell whether its names overlap; "
                                     "pass --corpora")
                shared = mine & _condition_names(GroundTruth.load(found / "ground_truth.json"), aliases=True)
                if shared:
                    raise ValueError(f"tuned {step} ({path}) was tuned with {side[:-8]} corpus {corpus_id!r}, which "
                                     f"share {len(shared)} condition names with {truth.corpus_id!r} (for example "
                                     f"{sorted(shared)[:3]}): the leak split would measure names the writer was tuned "
                                     "on; tune on other corpora or move the tuned file aside")


def leak(run: Path, corpus: Path, out: Path, *, tuned_dir: Path | None = None,
         corpora: Iterable[Path] = ()) -> dict[str, Any]:
    """The leak split of a run's extraction recall: facts whose name is "on the list" vs "unseen". The word list is
    the one in the run's plan.json; ValueError for a corpus that is not Claude-written, or when the tuned word writer
    was tuned on corpora sharing the corpus's condition names (`check_tuned_words`)."""
    from . import leak as lk
    from .score import score_extraction_only
    from .truth import GroundTruth
    plan = load_plan(Path(run) / PLAN_FILE)
    truth = GroundTruth.load(Path(corpus) / "ground_truth.json")
    check_tuned_words(truth, tuned_dir, corpora)
    result = {"extraction": score_extraction_only(Path(run), Path(corpus))}
    marks = lk.mark(truth, plan.words, result["extraction"].get("scored_types"))
    split = lk.split_scores(result, marks)
    nl = chr(10)
    lines = ["# Leak split (extraction recall)", "",
             "Named facts are matched by name (conditions without their role, metrics without the plan's measure id), "
             "so these recalls are not comparable with the extraction scores of `evaluate score`.", "", "| names | facts | matched | recall |", "|---|---|---|---|"]
    lines += [f"| {k} | {v['facts']} | {v['matched']} | {_cell(v['recall'])} |" for k, v in split.items()]
    rep.write_pair(split, nl.join(lines) + nl, out, "leak")
    return split


# --- links --------------------------------------------------------------------------------------------------------

def _work(ref: Any) -> str:
    """An OpenAlex work id by its last path segment, upper case ("https://openalex.org/w1" is "W1")."""
    return re.sub(r".*/", "", str(ref).strip()).upper()


def _doi_of(text: Any) -> str | None:
    """The bare lower-case DOI in `text` (a DOI, its doi.org URL or "doi:..."), else None (a cited title, an arXiv id)."""
    found = re.search(r"10[.][0-9]+/[^ ]+", str(text or ""))
    return found.group(0).rstrip(".,;)").lower() if found else None


def _reference(entry: Any) -> tuple[str | None, str | None]:
    """(work id, DOI) of one reference: {"work": ..., "doi": ...} (what `build_references` writes) or a bare string, a
    work id or a DOI."""
    if isinstance(entry, dict):
        return (_work(entry["work"]) if entry.get("work") else None), _doi_of(entry.get("doi"))
    return (None, _doi_of(entry)) if _doi_of(entry) else (_work(entry), None)


def _same_work(a: tuple[str | None, str | None], b: tuple[str | None, str | None]) -> bool:
    return (a[0] is not None and a[0] == b[0]) or (a[1] is not None and a[1] == b[1])


def builds_on_recall(links: list[dict[str, Any]], references: dict[str, list[Any]]) -> dict[str, Any]:
    """Builds-on links against OpenAlex `references` ({paper id: [reference, ...]}, `build_references`): recall of each
    paper's referenced works among the run's links, and precision of the links. A link names a work by its `work` (the
    OpenAlex id the run resolved, "W..." or its URL); a DOI equal to the link's `ref` counts too (the fallback for a
    link with no `work`). None when a side is empty."""
    found: dict[str, dict[tuple[str | None, str | None], None]] = {}
    unresolved = in_set = 0
    for link in links:
        if link.get("resolve_failed") or "resolve_failed" in str(link.get("text", "")):
            unresolved += 1          # OpenAlex did not answer: neither a hit nor a miss, left out
            continue
        if link.get("in_set") and not link.get("work") and not _doi_of(link.get("ref")):
            in_set += 1              # a corpus paper found without OpenAlex: no work id or DOI to compare, left out
            continue
        if link.get("paper") in references:
            key = (_work(link["work"]) if link.get("work") else None, _doi_of(link.get("ref")))
            found.setdefault(link["paper"], {})[key] = None
    per: dict[str, dict[str, int]] = {}
    for paper, refs in references.items():
        want, got = [_reference(r) for r in refs], list(found.get(paper, {}))
        per[paper] = {"expected": len(want), "found": sum(any(_same_work(w, g) for g in got) for w in want),
                      "links": len(got), "links_right": sum(any(_same_work(w, g) for w in want) for g in got)}
    total_want, total_links = sum(p["expected"] for p in per.values()), sum(p["links"] for p in per.values())
    return {"recall": sum(p["found"] for p in per.values()) / total_want if total_want else None,
            "precision": sum(p["links_right"] for p in per.values()) / total_links if total_links else None,
            "n_expected": total_want, "n_links": total_links, "n_unresolved": unresolved,
            "n_in_set": in_set, "per_paper": per}


def build_references(run: Path, corpus: Path) -> dict[str, list[dict[str, Any]]]:
    """{paper id: [{"work": "W...", "doi": bare DOI or None}, ...]}: the `referenced_works` of every work the run
    recorded in openalex.jsonl (evidence.openalex), for the papers of `corpus` those works are (by DOI or title, as the
    run's links find them). Offline: it reads the record only. A paper whose own work the run never asked OpenAlex
    for (a paper no other paper cites) has no entry, and is not scored."""
    from evidence.openalex import RECORD_FILE, OpenAlex
    from modelcall.cache import JsonlCache
    path = Path(run) / RECORD_FILE
    if not path.is_file():
        raise ValueError(f"{path}: no recorded OpenAlex answers (the run made no builds-on links)")
    works: list[dict[str, Any]] = []
    for _key, value in JsonlCache(path).items():
        body = json.loads(value["output"])
        if isinstance(body, dict):
            works += [w for w in ([body] if "id" in body else body.get("results") or []) if isinstance(w, dict)]
    doi = {_work(w["id"]): _doi_of(w.get("doi")) for w in works if w.get("id")}
    manifest = json.loads((Path(corpus) / "manifest.json").read_text(encoding="utf-8"))
    texts = {p["id"]: (Path(corpus) / (p.get("file") or f"papers/{p['id']}.md")).read_text(encoding="utf-8")
             for p in manifest["papers"]}
    out: dict[str, dict[str, str | None]] = {}
    for work in works:
        referenced = work.get("referenced_works") or []
        paper = OpenAlex._run_doc(work, texts) if referenced else None
        if paper is not None:
            for ref in referenced:
                out.setdefault(paper, {}).setdefault(_work(ref), doi.get(_work(ref)))
    return {p: [{"work": w, "doi": d} for w, d in sorted(refs.items())] for p, refs in sorted(out.items())}


def builds_on_status(answer: dict[str, Any], references: dict[str, list[Any]]) -> str | None:
    """Why builds-on cannot be scored ("links not run: ..."), else None. A number is never made up: a run without the
    links list, without references to compare with, or whose links cannot be told from the references is not scored."""
    links = answer.get("links")
    if links is None:
        return "links not run: the run's answer.json has no links"
    if not any(references.values()):
        return "links not run: no paper has OpenAlex references to compare with"
    refs_have_doi = any(_reference(r)[1] for rs in references.values() for r in rs)
    if links and not any("work" in link for link in links) and not (
            refs_have_doi and any(_doi_of(link.get("ref")) for link in links)):
        return "links not run: the links carry no OpenAlex work id (rerun the plan run)"
    return None


def links(run: Path, out: Path, *, corpus: Path | None = None, question_id: str | None = None,
          references: Path | None = None, build: bool = False) -> dict[str, Any]:
    """Chaining (with `question_id`): the existing scorer's result against the synthetic truth network
    (evaluation/score.py); builds-on (with `references`, or `build` to make the references from the run's recorded
    OpenAlex answers into <out>/openalex-references.json): `builds_on_recall` of the run's links, or "links not run"."""
    result: dict[str, Any] = {}
    refs: dict[str, list[Any]] | None = None
    if build and references is not None:
        raise ValueError("--build-references and --references are two ways to get the references: give one")
    if question_id is not None:
        from .score import score as score_run
        if corpus is None:
            raise ValueError("chaining needs --corpus")
        result["chaining"] = score_run(Path(run), Path(corpus), [], None, None, question_id)
    if build:
        if corpus is None:
            raise ValueError("--build-references needs --corpus (the papers the recorded works are matched to)")
        refs = build_references(run, corpus)
        Path(out).mkdir(parents=True, exist_ok=True)
        Path(out, "openalex-references.json").write_text(json.dumps(refs, indent=1) + chr(10), encoding="utf-8",
                                                         newline=chr(10))
    elif references is not None:
        refs = json.loads(Path(references).read_text(encoding="utf-8"))
    if refs is not None:
        answer = RunDir(run).json(ANSWER_FILE)
        status = builds_on_status(answer, refs)
        scored = builds_on_recall(answer.get("links") or [], refs)
        result["builds_on"] = {**scored, "recall": None, "precision": None, "status": status} if status else scored
    if not result:
        raise ValueError("give --question-id (chaining) and/or --references or --build-references (builds-on)")
    nl = chr(10)
    text = ["# Links", ""]
    if "chaining" in result:
        text += [f"Chaining ({result['chaining'].get('question_id')}): see links.json."]
    if "builds_on" in result:
        b = result["builds_on"]
        text += [b["status"] if b.get("status") else
                 f"Builds-on recall of OpenAlex references: {_cell(b['recall'])} (precision {_cell(b['precision'])})."]
    rep.write_pair(result, nl.join(text) + nl, out, "links")
    return result
