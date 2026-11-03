"""The generality check (W6, Task 6.6). Two numbers over the 12 off-template questions: the share answered with a fresh
query (the plan's line has `template` None) and the off-template match rate (the plan's query answers as the reference
query does on the answer key).

`load_questions` reads questions.yaml: each question's `.gold` is the GroundTruth of the corpus's ground_truth.json,
the shape `evidence.kg.truthgraph.truth_store` reads. `gold_rows` runs the reference query on `truth_store`; both it and
`check` import the query runner (evidence.kg.query, workstream W4) when called, so this module loads without it.

`check(run, q)`: `run` has `.plan` (an evidence.plan.Plan) and `.store` (the run's records graph, a pyoxigraph Store).
The line is the plan's line asking the question's text, else its first line.

Commit-time rule: `committed_at(paths)` gives the time the files were first committed (None when not in git), so a
report can show the questions were fixed before the planner ran.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from evaluation.truth import GroundTruth

HERE = Path(__file__).resolve().parent
QUESTIONS = HERE / "questions.yaml"
REFERENCE = HERE / "reference"
ROOT = HERE.parents[1]
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


def _key(row: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted((k, round(v, FLOAT_PLACES) if isinstance(v, float) else v) for k, v in row.items()))


def same_rows(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> bool:
    """The two answers hold the same rows (order ignored, floats to six places)."""
    return sorted(map(_key, a), key=repr) == sorted(map(_key, b), key=repr)


def gold_rows(q: OffTemplateQuestion) -> list[dict[str, Any]]:
    """The reference query run on the answer key's records."""
    from evidence.kg.query import run_query
    from evidence.kg.truthgraph import truth_store
    return run_query(truth_store(q), q.sparql, {}).rows


def plan_line(plan: Any, q: OffTemplateQuestion) -> Any:
    return next((line for line in plan.lines if line.question == q.question), plan.lines[0])


def check(run: Any, q: OffTemplateQuestion) -> dict[str, bool]:
    """{"fresh": the plan's line is a fresh query, "match": its answer equals the gold answer}."""
    from evidence.kg.query import run_query
    line = plan_line(run.plan, q)
    answer = run_query(run.store, line.query, {})
    return {"fresh": line.template is None, "match": same_rows(answer.rows, gold_rows(q))}


def summary(results: list[dict[str, bool]]) -> dict[str, Any]:
    """The two numbers of the generality claim over the checked questions."""
    n = len(results)
    return {"questions": n, "fresh_share": sum(r["fresh"] for r in results) / n if n else None,
            "match_rate": sum(r["match"] for r in results) / n if n else None}


def committed_at(paths: list[Path], cwd: Path = ROOT) -> datetime | None:
    """When the earliest of `paths` was first committed (git), None when none is committed."""
    times = []
    for path in paths:
        out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%cI", "--", str(path)], cwd=cwd,
                             capture_output=True, text=True, check=False).stdout.split()
        if out:
            times.append(datetime.fromisoformat(out[-1]))
    return min(times) if times else None
