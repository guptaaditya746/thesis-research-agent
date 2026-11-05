"""`score run <run> [--key <key.json>]`: one finished run against its answer key -> <run>/score.json.

score.json (docs/earlier-work.md, "Gold files, answer key, judge, scores" and Scoring):
{schema_version, run_id, qid, condition, seed, temperature, repeat, attempt, kind, exit_status, answer_from,
 verify_ok, key_version, key_reviewed, key_sha256, provisional, key_problems, rows: {tp, fp, fn, precision,
 recall, f1, asked, pending} (soft level), rows_by_level, facts: {strict, normalised, soft: {tp, fp, fn,
 precision, recall, f1, vital, vital_tp, vital_recall (+ asked, pending at soft)}}, vital_recall (soft),
 judged_precision, support: {facts, with_claims, supports, partial, no, unsourced, pending, support_share,
 ..., context, partial_counts_as, calibration}, pending: {support, same_fact, same_row}, cost: {steps,
 model_calls, tokens, tokens_without_attach, seconds, seconds_without_attach, wall_seconds, claim_steps,
 claim_step_tokens, attach_tokens, attach_seconds}, run_settings, judge, scorer, detail, scored_at}.

- The key must be for the run's concept (same concept_sha256); its rows are checked against the
  concept's answer schema once the gold-only fact fields are stripped, and problems are recorded.
- A key that is not reviewed (key.draft.json, `reviewed: false`) makes the score provisional: it tests
  the pipeline and is never reported as a result (as the labelling repo's draft keys). So does a
  key.json whose review is not finished (`review.complete` false, `key_complete` in score.json):
  `gold export` writes one after every pull, and what nobody has decided yet is missing from it.
- exit_status comes from the run's records: a cut by the batch runner, a run error, the loop's reason
  for ending without a final answer, or "submitted"; trajectory.json's info.exit_status is the fallback.
  answer_from says where answer.json came from: the final reply (`final`), the agent's draft file after
  the run ended without one (`draft`, coverage record answer_from_draft), or nowhere (`none`, an answer
  with no rows); null for runs older than these records.
- verify_ok is `agent verify` (needs the corpus); without a corpus it is null. Cost is computed from
  events.jsonl as agent/verify.py does, with and without the attach step. `seconds` is the active time:
  the research span plus the attach step's span, so a queue wait between the job that ran the research
  and a later job that ran the attach step (agent/batch.py) is not counted; `wall_seconds` is the whole
  span from the first record to the last.
- Judged precision takes the facts reviewers rejected as wrong from the review export beside the key
  (export.json decisions answered `incorrect`, gold/export.py), with their s/p/o from candidates.jsonl
  or pool.jsonl; without an export it is null.
- `pending` counts the judge decisions this run is still missing; `judge` is this run's own calls (a
  fork of the batch's judge), with the judge's identity (model and prompt hashes), and `scorer` the
  scoring code's version and git commit, so `score batch` can tell when a score is out of date.
"""
from __future__ import annotations

import copy
import functools
import json
import re
from pathlib import Path
from typing import Any

from agent import schema
from agent.batch import CUT_REASONS
from jsonio import file_sha256, write_json
from agent.concept import answer_schema_for, concept_sha256
from agent.rundir import RunDir, git_head, utc_now
from agent.verify import stats

from . import judge as judges
from .judge import Judge
from .match import GOLD_FIELDS, match
from .support import calibration, judge_support

SCORE_FILE = "score.json"
SCHEMA_VERSION = 3  # the scoring rules' version: a score.json of another version is always rescored
RUN_KEY = re.compile(r"^(?P<qid>.+)-(?P<condition>claim_on|claim_off)-r(?P<repeat>\d+)(?:-a(?P<attempt>\d+))?$")
COST = ("steps", "model_calls", "tokens", "claim_steps", "claim_step_tokens")
EXPORT_FILE = "export.json"
FACT_FILES = ("candidates.jsonl", "pool.jsonl")


class ScoreError(ValueError):
    pass


def load_key(path: Path) -> dict[str, Any]:
    key = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(key, dict) or not isinstance(key.get("rows"), list):
        raise ScoreError(f"{path}: not an answer key (no rows)")
    return key


def key_complete(key: dict[str, Any]) -> bool | None:
    """Whether the review behind the key is finished: gold/export.py's `review.complete` (every pool
    record decided, overlap disagreements resolved, the missing-facts record done, the screening
    sample checked); None for a key without that record (a draft, or one written by hand)."""
    review = key.get("review")
    return review.get("complete") is True if isinstance(review, dict) else None


def provisional(key: dict[str, Any]) -> bool:
    """True for a draft key (not reviewed, or a version ending in -draft) and for a reviewed key whose
    review is not finished: `gold export` writes key.json (v1, reviewed) after every pull, also half
    way through the review, and the records nobody has decided yet are simply missing from it."""
    return (key.get("reviewed") is not True or str(key.get("version", "")).endswith("-draft")
            or key_complete(key) is False)


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


def wrong_facts(key_path: Path) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    """Facts reviewers rejected as wrong, from export.json in the key's directory, and where they came from.

    A decision counts when it drops the candidate as `incorrect`, also after adjudication ("adjudicated
    by NAME: incorrect"); `unsure` and unanswered records are not judgements. (None, None) without an
    export, which leaves judged precision open.
    """
    qdir = Path(key_path).parent
    export = qdir / EXPORT_FILE
    try:
        decisions = json.loads(export.read_text(encoding="utf-8")).get("decisions")
    except (OSError, ValueError, AttributeError):
        return None, None
    if not isinstance(decisions, list):
        return None, None
    ids = {str(d["candidate_id"]) for d in decisions if isinstance(d, dict) and d.get("candidate_id")
           and not d.get("keep") and str(d.get("reason") or "").rsplit(": ", 1)[-1] == "incorrect"}
    spo: dict[str, dict[str, Any]] = {}
    for name in FACT_FILES:
        path = qdir / name
        for raw in path.read_text(encoding="utf-8").splitlines() if ids and path.is_file() else []:
            try:
                item = json.loads(raw)
            except ValueError:
                continue
            if isinstance(item, dict) and item.get("id") in ids and item["id"] not in spo and all(k in item for k in "spo"):
                spo[item["id"]] = {k: item[k] for k in "spo"}
    wrong = [{**spo[i], "candidate_id": i, "verdict": "wrong"} for i in sorted(spo)]
    return wrong, {"file": str(export), "sha256": file_sha256(export), "rejected_as_wrong": len(ids),
                   "with_fact": len(spo)}


def records(run: RunDir) -> list[dict[str, Any]]:
    out = []
    for raw in run.events.read_bytes().splitlines() if run.events.is_file() else []:
        try:
            out.append(json.loads(raw))
        except ValueError:
            break  # a torn last line; `agent verify` reports it
    return out


def _research_coverage(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in recs if r.get("subtype") == "coverage"
            and (r.get("custom_metadata") or {}).get("origin") != "attach"]


def _detail_status(record: dict[str, Any]) -> str | None:
    detail = (record.get("generated") or {}).get("detail")
    return str(detail["exit_status"]) if isinstance(detail, dict) and detail.get("exit_status") else None


def exit_status(run: RunDir, recs: list[dict[str, Any]]) -> str:
    """How the research run ended: cut, error, submitted, or the loop's reason (budget, context_full, ...)."""
    coverage = _research_coverage(recs)
    reasons = [(r.get("generated") or {}).get("reason") for r in coverage]
    if any(r in CUT_REASONS for r in reasons):
        return "cut"
    if "run_error" in reasons:
        return "error"
    for r in coverage:
        reason = (r.get("generated") or {}).get("reason")
        if reason == "answer_from_draft":
            return _detail_status(r) or "unknown"
        if reason == "no_final_answer":
            return _detail_status(r) or "no_answer"
    if any((r.get("custom_metadata") or {}).get("final_answer") for r in recs
           if r.get("subtype") == "ai_model_invocation"):
        return "submitted"
    try:
        info = json.loads((run.root / "trajectory.json").read_text(encoding="utf-8"))["info"]
        return str(info.get("exit_status") or "unknown")
    except (OSError, ValueError, KeyError, TypeError):
        return "unknown"


def answer_from(recs: list[dict[str, Any]]) -> str | None:
    """final (the conclude reply), draft (the agent's draft file, e2e/agent-fix), none, or null (unknown)."""
    reasons = {(r.get("generated") or {}).get("reason") for r in _research_coverage(recs)}
    if "answer_from_draft" in reasons:
        return "draft"
    if any((r.get("custom_metadata") or {}).get("final_answer") for r in recs
           if r.get("subtype") == "ai_model_invocation"):
        return "final"
    if "no_final_answer" in reasons:
        return "none"
    return None


def cost(recs: list[dict[str, Any]]) -> dict[str, Any]:
    """The plan's cost fields from agent.verify.stats: whole run, and without the attach step."""
    s = stats(recs)
    without, attach = s.get("without_attach", s), s.get("attach")
    return {**{k: s[k] for k in COST}, "tokens_without_attach": without["tokens"],
            "seconds": round(without["seconds"] + attach["seconds"], 3) if attach else s["seconds"],
            "seconds_without_attach": without["seconds"], "wall_seconds": s["seconds"],
            "attach_tokens": attach["tokens"] if attach else 0, "attach_seconds": attach["seconds"] if attach else 0.0}


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


ATTACH_SETTINGS = ("prompt", "budget_per_fact", "conclude_replies", "conclude_decoding", "sandbox")


def run_settings(config: dict[str, Any]) -> dict[str, Any]:
    """The settings the runs of one comparison must share (the report flags any that differ).

    `prompt_sha256` is the condition's own system prompt (claim_on and claim_off differ by the claim
    block) and `attach` exists for claim_off only, so the report compares those two within each
    condition; the rest across all runs: the loop (conclude decoding and reply limit, masking, ...;
    not the proxy URL), subagents, sandbox mode and command limits can differ between Slurm jobs.
    """
    orchestrator = (config.get("models") or {}).get("orchestrator") or {}
    prompt = config.get("prompt") or {}
    loop = config.get("loop")
    attach = config.get("attach")
    return {"budget": config.get("budget"), "temperature": (config.get("sampling") or {}).get("temperature"),
            "prompt_version": prompt.get("version"), "prompt_sha256": prompt.get("sha256"),
            "model": f"{orchestrator.get('name')}@{orchestrator.get('revision')}" if orchestrator else None,
            "corpus_manifest_sha256": (config.get("hashes") or {}).get("corpus_manifest_sha256"),
            "git_commit": config.get("git_commit"),
            "loop": {k: v for k, v in loop.items() if k != "base_url"} if isinstance(loop, dict) else None,
            "spawn": config.get("spawn"), "sandbox_mode": (config.get("sandbox") or {}).get("mode"),
            "command_limits": config.get("command_limits"),
            "attach": {k: attach.get(k) for k in ATTACH_SETTINGS} if isinstance(attach, dict) else None}


@functools.cache
def scorer() -> dict[str, Any]:
    """This scoring code: the rules' version and the repository's git commit (null outside a checkout)."""
    try:
        commit: str | None = git_head(Path(__file__).resolve().parent.parent)
    except Exception:  # no git, or not a checkout
        commit = None
    return {"version": SCHEMA_VERSION, "git_commit": commit}


def score_run(run_dir: Path | str, key_path: Path | str, *, judge: Judge | None = None, corpus: Path | None = None,
              manifest: Path | None = None, gold: Path | None = None, write: bool = True) -> dict[str, Any]:
    """Score one run; writes <run>/score.json unless write=False. Raises ScoreError when it cannot.

    `gold`: the gold directory whose judge-report.json says how `partial` counts (default: none, so no).
    """
    run = RunDir(Path(run_dir))
    if not run.answer.is_file():
        raise ScoreError(f"{run.root}: no answer.json; the run has not finished")
    config, concept = run.load_config(), run.load_concept()
    answer = json.loads(run.answer.read_text(encoding="utf-8"))
    key = load_key(Path(key_path))
    if key.get("concept_sha256") != config["hashes"]["concept_sha256"]:
        raise ScoreError(f"{key_path} is for concept {str(key.get('concept_sha256'))[:12]}, the run used "
                         f"{config['hashes']['concept_sha256'][:12]}")
    mine = judge.fork() if judge is not None else None  # this run's own counts
    recs = records(run)
    verify_ok, verify_errors = verify(run, corpus, manifest)
    wrong, wrong_source = wrong_facts(Path(key_path))
    matched = match(answer, key, concept, mine, wrong)
    calibrated = calibration(gold)
    support = judge_support(run, mine, corpus=corpus, partial_counts_as=calibrated["partial_counts_as"])
    rows, facts = matched["rows"], matched["facts"]
    score = {
        "schema_version": SCHEMA_VERSION, **run_identity(run, config), "qid": key.get("qid"),
        "kind": concept["answer_shape"]["kind"], "exit_status": exit_status(run, recs),
        "answer_from": answer_from(recs), "verify_ok": verify_ok, "verify_errors": verify_errors,
        "key_version": key.get("version"), "key_reviewed": key.get("reviewed") is True,
        "key_complete": key_complete(key),
        "key_sha256": file_sha256(key_path), "key_path": str(key_path), "provisional": provisional(key),
        "key_problems": key_problems(key, concept)[:20],
        "rows": rows["levels"]["soft"], "rows_by_level": rows["levels"],
        "facts": facts["levels"], "vital_recall": facts["levels"]["soft"]["vital_recall"],
        "judged_precision": facts["judged_precision"] | {"source": wrong_source},
        "support": {k: v for k, v in support.items() if k != "detail"} | {"calibration": calibrated},
        "pending": {"support": support["pending"], "same_fact": facts["levels"]["soft"]["pending"],
                    "same_row": rows["levels"]["soft"]["pending"]},
        "cost": cost(recs),
        "run_settings": run_settings(config),
        "judge": judges.summary(mine),
        "scorer": scorer(),
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
    s, facts, pending = score["support"], score["facts"], score["pending"]
    return (f"{score['run_id']}: {score['condition']} exit={score['exit_status']} rows f1={f(score['rows']['f1'])} "
            f"facts f1 strict/normalised/soft={f(facts['strict']['f1'])}/{f(facts['normalised']['f1'])}/"
            f"{f(facts['soft']['f1'])} vital={f(score['vital_recall'])} support={s['supports']}/{s['facts']} "
            f"share={f(s['support_share'])} unsourced={s['unsourced']} pending={pending['support']}"
            f"+{pending['same_fact']}+{pending['same_row']} tokens={score['cost']['tokens']}"
            + (" PROVISIONAL" if score["provisional"] else ""))
