"""The generality check (W6, Task 6.6). Two numbers over the 12 off-template questions: the share answered with a fresh
query (the plan's line has `template` None) and the off-template match rate (the plan's query answers as the reference
query does on the answer key).

`load_questions` reads questions.yaml: each question's `.gold` is the GroundTruth of the corpus's ground_truth.json,
the shape `evidence.kg.truthgraph.truth_store` reads. `gold_rows` runs the reference query on `truth_store`; both it and
`check` import the query runner (evidence.kg.query, workstream W4) when called, so this module loads without it.

`check(run, q)`: `run` has `.plan` (an evidence.plan.Plan) and optionally `.store` (the run's records graph, a
pyoxigraph Store). The line is the plan's line asking the question's text, else its first line. The plan's query runs
on the answer key (planning alone: the generality number) and on the run's records (end to end).

Commit-time rule: `committed_at(paths)` gives the time the files were first committed (None when not in git), so a
report can show the questions were fixed before the planner ran.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import repo_paths
from typing import Any

import yaml

from evaluation.truth import GroundTruth

HERE = Path(__file__).resolve().parent
QUESTIONS = HERE / "questions.yaml"
REFERENCE = HERE / "reference"
ROOT = repo_paths.REPO   # questions.yaml `corpus:` is relative to the repo
FLOAT_PLACES = 6


@dataclass(frozen=True)
class OffTemplateQuestion:
    id: str
    question: str
    reference: Path
    gold: GroundTruth          # the answer key (read by truth_store)

    @property
    def sparql(self) -> str:
        return self.reference.read_text(encoding="utf-8")


def load_questions(path: Path = QUESTIONS, root: Path = ROOT) -> list[OffTemplateQuestion]:
    spec = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    truth = GroundTruth.load(Path(root) / spec["corpus"] / "ground_truth.json")
    return [OffTemplateQuestion(q["id"], q["question"], REFERENCE / q["reference"], truth) for q in spec["questions"]]


def _cell(v: Any) -> Any:
    """A value as compared: floats to six places, names by `names.clean` (a graph key "lawfactqa" is "LawFactQA")."""
    from evidence.names import clean
    return round(v, FLOAT_PLACES) if isinstance(v, float) else clean(v) if isinstance(v, str) else v


def _count(rows: list[dict[str, Any]], name: str) -> bool:
    """A gold column of whole-number counts only (how many papers or metrics a row has)."""
    return all(isinstance(r.get(name), int) and not isinstance(r.get(name), bool) for r in rows)


def _column(rows: list[dict[str, Any]], name: str) -> list[str]:
    return sorted(repr(_cell(r.get(name))) for r in rows)


def same_rows(plan: list[dict[str, Any]], gold: list[dict[str, Any]]) -> bool:
    """The plan's answer holds the gold rows: compared on VALUES, not on variable names. Each gold column is matched
    to a plan column holding the same values (as a multiset); the rows, projected onto those columns, must then be
    the same multiset. A plan column that matches no gold column (an extra count, say) is ignored, see
    `extra_columns`; so is a gold count column no plan column holds (q04: the right papers, no `metrics` count), as
    long as another gold column is matched. Floats compare to six places, names by `names.clean`."""
    if not plan or not gold:
        return not plan and not gold
    if len(plan) != len(gold):
        return False
    plan_cols = list(dict.fromkeys(k for r in plan for k in r))
    picked: list[str] = []
    gold_cols: list[str] = []
    for name in dict.fromkeys(k for r in gold for k in r):
        want = _column(gold, name)
        hit = next((c for c in plan_cols if c not in picked and _column(plan, c) == want), None)
        if hit is None and _count(gold, name):
            continue
        if hit is None:
            return False
        picked.append(hit)
        gold_cols.append(name)
    if not gold_cols:
        return False
    project = lambda rows, cols: sorted(tuple(repr(_cell(r.get(c))) for c in cols) for r in rows)   # noqa: E731
    return project(plan, picked) == project(gold, gold_cols)


def extra_columns(plan: list[dict[str, Any]], gold: list[dict[str, Any]]) -> list[str]:
    """Plan columns whose values equal no gold column (reported, never a failure)."""
    gold_cols = [_column(gold, k) for k in dict.fromkeys(k for r in gold for k in r)]
    return [c for c in dict.fromkeys(k for r in plan for k in r) if _column(plan, c) not in gold_cols]


def gold_rows(q: OffTemplateQuestion) -> list[dict[str, Any]]:
    """The reference query run on the answer key's records."""
    from evidence.kg.query import run_query
    from evidence.kg.truthgraph import truth_store
    return run_query(truth_store(q), q.sparql, {}).rows


def plan_line(plan: Any, q: OffTemplateQuestion) -> Any:
    return next((line for line in plan.lines if line.question == q.question), plan.lines[0])


def is_fresh(line: Any) -> bool:
    """A fresh query: no saved template, and a query at all (an unplanned line is neither fresh nor a template)."""
    return line.template is None and bool(line.query.strip())


def key_sides(plan: Any, truth: GroundTruth) -> list[str]:
    """The plan's compared sides as the answer key names them: the key's conditions carry the pack's roles
    (baseline, rag, other), the plan's queries its own thing ids; each side becomes the role most of the key's
    conditions named like the thing (its id or word-list names, `names.clean`) have, else stays as it is."""
    from collections import Counter

    from evidence.names import clean
    from evidence.planrun import compare_sides
    conditions = [f.data for f in truth.facts.values() if f.type == "condition"]
    out = []
    for side in compare_sides(plan):
        names = {clean(n) for n in (side, *plan.words.things.get(side, []))}
        roles = Counter(c["role"] for c in conditions
                        if {clean(str(x)) for x in (c.get("label"), *(c.get("aliases") or [])) if x} & names)
        out.append(roles.most_common(1)[0][0] if roles else side)
    return out


def check(run: Any, q: OffTemplateQuestion) -> dict[str, Any]:
    """{"fresh": the plan's line is a fresh query, "match_on_key": its answer on the answer key's records equals the
    gold answer (planning alone: THE generality number), "match_on_run": the same on the run's extracted records
    (end to end; None when the run has no `store`), "extra_columns": plan columns beyond the gold's}."""
    from evidence.kg.query import run_query
    from evidence.kg.truthgraph import truth_store
    from evidence.planrun import line_params
    line = plan_line(run.plan, q)
    gold = gold_rows(q)
    params = line_params(run.plan, line.query)      # the planner keeps $choices: fill them as the run does
    on_key = run_query(truth_store(q), line.query, {**params, "sides": key_sides(run.plan, q.gold)}).rows
    store = getattr(run, "store", None)
    on_run = run_query(store, line.query, params).rows if store is not None else None
    return {"fresh": is_fresh(line), "match_on_key": same_rows(on_key, gold),
            "match_on_run": None if on_run is None else same_rows(on_run, gold),
            "extra_columns": extra_columns(on_key, gold)}


def summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """The two numbers of the generality claim over the questions (a question with no plan is a row too: neither
    fresh nor a match): the share answered with a fresh query and
    the match rate on the answer key (`match_rate`); the end-to-end rate beside them (`match_on_run_rate`)."""
    n = len(results)
    results = [{"fresh": False, "match_on_key": False, "match_on_run": None, **r} for r in results]   # failed: no match
    runs = [r["match_on_run"] for r in results if r.get("match_on_run") is not None]
    return {"questions": n, "fresh_share": sum(r["fresh"] for r in results) / n if n else None,
            "match_rate": sum(r["match_on_key"] for r in results) / n if n else None,
            "match_on_run_rate": sum(runs) / len(runs) if runs else None}


def committed_at(paths: list[Path], cwd: Path = ROOT) -> datetime | None:
    """When the earliest of `paths` was first committed (git), None when none is committed."""
    times = []
    for path in paths:
        out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%cI", "--", str(path)], cwd=cwd,
                             capture_output=True, text=True, check=False).stdout.split()
        if out:
            times.append(datetime.fromisoformat(out[-1]))
    return min(times) if times else None
