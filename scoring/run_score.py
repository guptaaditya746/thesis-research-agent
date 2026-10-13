"""`score run <run> --key <key.json>`: one finished run against its answer key -> <run>/score.json.

score.json (docs/e2e-build-plan.md, Scores; scoring/README.md lists every field):
{run_id, qid, condition, seed, repeat, attempt, exit_status, verify_ok, key_version, key_reviewed,
 key_sha256, provisional, rows: {tp, fp, fn, precision, recall, f1} (soft level), rows_by_level,
 facts: {strict, normalised, soft: {tp, fp, fn, precision, recall, f1, vital, vital_tp, vital_recall}},
 vital_recall (soft), judged_precision, support: {facts, with_claims, supports, partial, no, unsourced,
 pending, support_share, unsourced_share}, cost: {steps, model_calls, tokens, tokens_without_attach,
 seconds, seconds_without_attach, claim_steps, claim_step_tokens}, judge, detail, scored_at}.

- The key must be for the run's concept (same concept_sha256); its rows are checked against the
  concept's answer schema once the gold-only fact fields are stripped, and problems are recorded.
- A key that is not reviewed (key.draft.json, `reviewed: false`) makes the score provisional: it tests
  the pipeline and is never reported as a result (as the labelling repo's draft keys).
- exit_status comes from the run's records: a cut by the batch runner, a run error, the loop's reason
  for ending without an answer, or "submitted"; trajectory.json's info.exit_status is the fallback.
- verify_ok is `agent verify` (needs the corpus); without a corpus it is null. Cost is computed from
  events.jsonl as agent/verify.py does, with and without the attach step.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from agent import schema
from agent.batch import CUT_REASONS
from agent.canonical import file_sha256, write_json
from agent.concept import answer_schema_for, concept_sha256
from agent.rundir import RunDir, utc_now
from agent.verify import stats

from . import judge as judges
from .judge import Judge
from .match import GOLD_FIELDS, match
from .support import judge_support

SCORE_FILE = "score.json"
SCHEMA_VERSION = 1
RUN_KEY = re.compile(r"^(?P<qid>.+)-(?P<condition>claim_on|claim_off)-r(?P<repeat>\d+)(?:-a(?P<attempt>\d+))?$")
COST = ("steps", "model_calls", "tokens", "seconds", "claim_steps", "claim_step_tokens")


class ScoreError(ValueError):
    pass


def load_key(path: Path) -> dict[str, Any]:
    key = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(key, dict) or not isinstance(key.get("rows"), list):
        raise ScoreError(f"{path}: not an answer key (no rows)")
    return key


def provisional(key: dict[str, Any]) -> bool:
    """True for a draft key: not reviewed, or a version ending in -draft."""
    return key.get("reviewed") is not True or str(key.get("version", "")).endswith("-draft")


def key_problems(key: dict[str, Any], concept: dict[str, Any]) -> list[str]:
    """The key's rows against the concept's answer schema, gold-only fact fields stripped."""
    rows = copy.deepcopy(key["rows"])
    for row in rows:
        for fact in row.get("facts") or []:
            for name in GOLD_FIELDS:
                fact.pop(name, None)
            fact.setdefault("claims", [])
            fact.setdefault("origin", "research")
    answer = {"concept_sha256": concept_sha256(concept), "kind": concept["answer_shape"]["kind"], "rows": rows}
    problems = schema.errors(answer_schema_for(concept), answer)
    if key.get("kind") not in (None, concept["answer_shape"]["kind"]):
        problems.append(f"kind {key.get('kind')!r} is not the concept's {concept['answer_shape']['kind']!r}")
    return problems


def records(run: RunDir) -> list[dict[str, Any]]:
    out = []
    for raw in run.events.read_bytes().splitlines() if run.events.is_file() else []:
        try:
            out.append(json.loads(raw))
        except ValueError:
            break  # a torn last line; `agent verify` reports it
    return out


def exit_status(run: RunDir, recs: list[dict[str, Any]]) -> str:
    """How the research run ended: cut, error, submitted, or the loop's reason (budget, context_full, ...)."""
    coverage = [r for r in recs if r.get("subtype") == "coverage" and (r.get("custom_metadata") or {}).get("origin")
                != "attach"]
    reasons = [(r.get("generated") or {}).get("reason") for r in coverage]
    if any(r in CUT_REASONS for r in reasons):
        return "cut"
    if "run_error" in reasons:
        return "error"
    for r in coverage:
        if (r.get("generated") or {}).get("reason") == "no_final_answer":
            return str(((r["generated"].get("detail") or {}).get("exit_status")) or "no_answer")
    if any((r.get("custom_metadata") or {}).get("final_answer") for r in recs
           if r.get("subtype") == "ai_model_invocation"):
        return "submitted"
    try:
        info = json.loads((run.root / "trajectory.json").read_text(encoding="utf-8"))["info"]
        return str(info.get("exit_status") or "unknown")
    except (OSError, ValueError, KeyError, TypeError):
        return "unknown"


def cost(recs: list[dict[str, Any]]) -> dict[str, Any]:
    """The plan's cost fields from agent.verify.stats: whole run, and without the attach step."""
    s = stats(recs)
    without = s.get("without_attach", s)
    return {**{k: s[k] for k in COST}, "tokens_without_attach": without["tokens"],
            "seconds_without_attach": without["seconds"],
            "attach_tokens": s["attach"]["tokens"] if "attach" in s else 0,
            "attach_seconds": s["attach"]["seconds"] if "attach" in s else 0.0}


def verify(run: RunDir, corpus: Path | None, manifest: Path | None) -> tuple[bool | None, list[str]]:
    if corpus is None:
        return None, []
    from agent.verify import verify_run

    report = verify_run(run, Path(corpus), Path(manifest or Path(corpus) / "manifest.json"))
    return report.ok, report.errors[:20]


def run_identity(run: RunDir, config: dict[str, Any]) -> dict[str, Any]:
    m = RUN_KEY.match(run.run_id)
    return {"run_id": run.run_id, "condition": config["condition"], "seed": config["sampling"]["seed"],
            "temperature": config["sampling"]["temperature"],
            "repeat": int(m.group("repeat")) if m else None,
            "attempt": int(m.group("attempt")) if m and m.group("attempt") else None}


def score_run(run_dir: Path | str, key_path: Path | str, *, judge: Judge | None = None, corpus: Path | None = None,
              manifest: Path | None = None, workers: int = 1, write: bool = True) -> dict[str, Any]:
    """Score one run; writes <run>/score.json unless write=False. Raises ScoreError when it cannot."""
    run = RunDir(Path(run_dir))
    if not run.answer.is_file():
        raise ScoreError(f"{run.root}: no answer.json; the run has not finished")
    config, concept = run.load_config(), run.load_concept()
    answer = json.loads(run.answer.read_text(encoding="utf-8"))
    key = load_key(Path(key_path))
    if key.get("concept_sha256") != config["hashes"]["concept_sha256"]:
        raise ScoreError(f"{key_path} is for concept {str(key.get('concept_sha256'))[:12]}, the run used "
                         f"{config['hashes']['concept_sha256'][:12]}")
    recs = records(run)
    verify_ok, verify_errors = verify(run, corpus, manifest)
    matched = match(answer, key, concept, judge, workers)
    support = judge_support(run, judge, corpus=corpus, workers=workers)
    rows, facts = matched["rows"], matched["facts"]
    score = {
        "schema_version": SCHEMA_VERSION, **run_identity(run, config), "qid": key.get("qid"),
        "kind": concept["answer_shape"]["kind"], "exit_status": exit_status(run, recs), "verify_ok": verify_ok,
        "verify_errors": verify_errors,
        "key_version": key.get("version"), "key_reviewed": key.get("reviewed") is True,
        "key_sha256": file_sha256(key_path), "key_path": str(key_path), "provisional": provisional(key),
        "key_problems": key_problems(key, concept)[:20],
        "rows": rows["levels"]["soft"], "rows_by_level": rows["levels"],
        "facts": facts["levels"], "vital_recall": facts["levels"]["soft"]["vital_recall"],
        "judged_precision": facts["judged_precision"],
        "support": {k: v for k, v in support.items() if k != "detail"},
        "cost": cost(recs),
        "judge": judges.summary(judge),
        "detail": {"rows": {k: rows[k] for k in ("pairs", "missed", "extra", "duplicates")},
                   "facts": {k: facts[k] for k in ("pairs", "missed", "extra", "duplicates")},
                   "support": support["detail"]},
        "scored_at": utc_now(),
    }
    if write:
        write_json(run.root / SCORE_FILE, score)
    return score


def read_score(run: RunDir) -> dict[str, Any] | None:
    try:
        return json.loads((run.root / SCORE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def line(score: dict[str, Any]) -> str:
    """One summary line for the terminal."""
    def f(x: Any) -> str:
        return "-" if x is None else f"{x:.3f}"
    s, facts = score["support"], score["facts"]
    return (f"{score['run_id']}: {score['condition']} exit={score['exit_status']} rows f1={f(score['rows']['f1'])} "
            f"facts f1 strict/normalised/soft={f(facts['strict']['f1'])}/{f(facts['normalised']['f1'])}/"
            f"{f(facts['soft']['f1'])} vital={f(score['vital_recall'])} support={s['supports']}/{s['facts']} "
            f"share={f(s['support_share'])} unsourced={s['unsourced']} pending={s['pending']} "
            f"tokens={score['cost']['tokens']}" + (" PROVISIONAL" if score["provisional"] else ""))
