"""`score report <runs_root>`: the milestone 4 results from report/scores.jsonl (docs/e2e-build-plan.md).

Aggregation (the labelling repo's docs/EVALUATION.md, section 5): repeats are averaged per question and
condition first (they are not independent samples); summaries average the per-question means, so each
question counts once; claim_on and claim_off are compared on the same questions as paired per-question
differences claim_on - claim_off. Intervals: 95 % BCa bootstrap over questions (scipy.stats.bootstrap,
2,000 resamples, fixed seed; the paired form resamples questions with both conditions together). BCa
needs two questions and some spread: with all values equal the interval is that value ("degenerate");
when BCa cannot be computed the percentile interval is used, and `method` says which.

Primary outcome (pre-registered, docs/STATE.md Framing): support share, the share of a run's answer
facts whose quote supports them (judge; `partial` as the judge's calibration says), claim_on vs
claim_off after the attach step. Per question the mean over repeats; a run without answer facts has no
support share and is left out of that mean (coverage, the share of scored runs with answer facts, is
reported per condition beside it); a question needs a mean in both conditions to be paired. Test:
Wilcoxon signed-rank on the paired per-question means, two-sided, alpha 0.05 (scipy.stats.wilcoxon,
zero_method "wilcox": zero differences, after rounding to 12 decimals, are dropped; method "auto": the
exact null distribution up to 50 pairs), with the BCa interval of the mean difference and the
matched-pairs rank-biserial correlation as effect size. With fewer than 6 paired questions the test is
not computed: even if every difference had the same sign, the smallest two-sided p would be 2/2^5 =
0.0625 > alpha. Sensitivity analyses: runs without answer facts as support share 0; `partial` under
the other mapping; each fact judged by its first cited claim only (claim_on facts may cite several).

Nothing is dropped silently. A run whose support verdicts are pending (judge unreachable) has no
support share; while any scored run is in that state the primary test and its sensitivity tests are
not computed, and the runs are listed. A soft-level number with judge decisions pending is a lower
bound: such a run's soft outcomes are left out of the means, and each condition's summary says how
many runs fed it. The report also says which runs are unverified (no corpus at scoring) or failed
`agent verify`, whose key did not validate, whether the runs' settings (budget, temperature, prompt,
model, corpus, git commit) differ, and what produced the numbers (scorer commits, judge models and
prompt hashes, key hashes, the sha256 of scores.jsonl and batch.json).

Secondary outcomes, with intervals and no test: fact precision, recall and F1 (soft; F1 also strict
and normalised), row F1 (soft and normalised), vital recall, judged precision, unsourced share, claims
per sourced fact, tokens and time with and without the attach step. Runs are counted by condition,
exit status and answer source, and keys the batch could not score by their state. Any score against
a draft key makes the whole report provisional.

Writes report/report.json, report/report.md (tables to paste into the thesis) and report/*.csv.
"""
from __future__ import annotations

import json
import math
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from agent.canonical import canonical, file_sha256, write_json
from agent.rundir import utc_now

from .batch import BATCH_FILE, REPORT_DIR, SCORES_FILE
from .run_score import scorer

CONDITIONS = ("claim_on", "claim_off")
PRIMARY = "support_share"
MIN_PAIRS = 6
ALPHA = 0.05
CONFIDENCE = 0.95
RESAMPLES = 2000
SEED = 20261013
DECIMALS = 12  # differences are rounded before the test, so equal means give a zero difference

# outcome -> (label, path in score.json)
OUTCOMES: dict[str, tuple[str, tuple[str, ...]]] = {
    "support_share": ("Support share (judge)", ("support", "support_share")),
    "fact_precision": ("Fact precision (soft)", ("facts", "soft", "precision")),
    "fact_recall": ("Fact recall (soft)", ("facts", "soft", "recall")),
    "fact_f1": ("Fact F1 (soft)", ("facts", "soft", "f1")),
    "fact_f1_normalised": ("Fact F1 (normalised)", ("facts", "normalised", "f1")),
    "fact_f1_strict": ("Fact F1 (strict)", ("facts", "strict", "f1")),
    "row_f1": ("Row F1 (soft)", ("rows", "f1")),
    "row_f1_normalised": ("Row F1 (normalised)", ("rows_by_level", "normalised", "f1")),
    "vital_recall": ("Vital recall (soft)", ("vital_recall",)),
    "judged_precision": ("Judged precision", ("judged_precision", "precision")),
    "unsourced_share": ("Unsourced share", ("support", "unsourced_share")),
    "claims_per_fact": ("Claims per sourced fact", ("support", "claims_per_fact")),
    "tokens": ("Tokens", ("cost", "tokens")),
    "tokens_without_attach": ("Tokens without attach", ("cost", "tokens_without_attach")),
    "seconds": ("Time (s, active)", ("cost", "seconds")),
    "seconds_without_attach": ("Time without attach (s)", ("cost", "seconds_without_attach")),
}
SECONDARY = [k for k in OUTCOMES if k != PRIMARY]
SOFT_FACTS = ("fact_precision", "fact_recall", "fact_f1", "vital_recall", "judged_precision")
SOFT_ROWS = ("row_f1",)
# The pre-registered sensitivity analyses of the primary outcome: column -> label.
SENSITIVITY = {
    "support_share_empty_as_zero": "answers without facts count as support share 0",
    "support_share_other_mapping": "`partial` under the other mapping than the calibrated one",
    "support_share_first_claim": "each fact judged by its first cited claim only",
}
COUNTS = ("tokens", "tokens_without_attach")
TIMES = ("seconds", "seconds_without_attach")
SETTINGS = ("budget", "temperature", "prompt_version", "prompt_sha256", "model", "corpus_manifest_sha256",
            "git_commit")


class ReportError(ValueError):
    pass


# --- numbers ---------------------------------------------------------------------------------------------

def plain(x: Any) -> Any:
    """JSON-safe: numpy scalars to Python, NaN to None, recursively."""
    if isinstance(x, dict):
        return {str(k): plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [plain(v) for v in x]
    if isinstance(x, np.generic):
        x = x.item()
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def get(score: dict[str, Any], path: tuple[str, ...]) -> float:
    value: Any = score
    for part in path:
        value = value.get(part) if isinstance(value, dict) else None
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else math.nan


def interval(values: np.ndarray, *, paired_with: np.ndarray | None = None, seed: int = SEED,
             resamples: int = RESAMPLES, confidence: float = CONFIDENCE) -> dict[str, Any]:
    """Mean and BCa bootstrap interval over questions; with paired_with, of the paired mean difference."""
    data = (values, paired_with) if paired_with is not None else (values,)
    diffs = values - paired_with if paired_with is not None else values
    n = len(diffs)
    out: dict[str, Any] = {"n": n, "mean": float(np.mean(diffs)) if n else None, "low": None, "high": None,
                           "method": None}
    if n < 2:
        return out | {"method": "none (fewer than 2 questions)" if n else None}
    if np.all(diffs == diffs[0]):
        return out | {"low": out["mean"], "high": out["mean"], "method": "degenerate (all equal)"}

    def statistic(*samples: np.ndarray, axis: int = -1) -> np.ndarray:
        return np.mean(samples[0] - samples[1] if len(samples) == 2 else samples[0], axis=axis)

    for method in ("BCa", "percentile"):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ci = stats.bootstrap(data, statistic, paired=paired_with is not None, n_resamples=resamples,
                                 confidence_level=confidence, method=method,
                                 rng=np.random.default_rng(seed)).confidence_interval
        if math.isfinite(ci.low) and math.isfinite(ci.high):
            return out | {"low": float(ci.low), "high": float(ci.high), "method": method}
    return out | {"method": "failed"}


def wilcoxon_test(diffs: np.ndarray, *, alpha: float = ALPHA, min_pairs: int = MIN_PAIRS,
                  blocked: str | None = None) -> dict[str, Any]:
    """The pre-registered test on paired per-question differences (claim_on - claim_off).

    `blocked`: a reason not to compute it although there are enough pairs (verdicts still pending)."""
    d = np.round(np.asarray(diffs, dtype=float), DECIMALS)
    nonzero = d[d != 0]
    out: dict[str, Any] = {"test": "wilcoxon signed-rank", "alternative": "two-sided", "zero_method": "wilcox",
                           "alpha": alpha, "n_pairs": int(len(d)), "n_nonzero": int(len(nonzero)),
                           "computed": False, "reason": None, "statistic": None, "p_value": None,
                           "significant": None, "t_plus": None, "t_minus": None, "rank_biserial": None}
    if blocked:
        return out | {"reason": blocked}
    if len(d) < min_pairs:
        return out | {"reason": f"fewer than {min_pairs} paired questions (n = {len(d)}): with n < {min_pairs} "
                                f"the smallest two-sided p is 2/2^n > {alpha}"}
    ranks = stats.rankdata(np.abs(nonzero))
    t_plus, t_minus = float(ranks[nonzero > 0].sum()), float(ranks[nonzero < 0].sum())
    out |= {"computed": True, "t_plus": t_plus, "t_minus": t_minus,
            "rank_biserial": (t_plus - t_minus) / (t_plus + t_minus) if len(nonzero) else 0.0}
    if not len(nonzero):
        return out | {"statistic": 0.0, "p_value": 1.0, "significant": False, "reason": "every difference is zero"}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = stats.wilcoxon(d, zero_method="wilcox", alternative="two-sided", method="auto")
    p = float(res.pvalue)
    return out | {"statistic": float(res.statistic), "p_value": p, "significant": p < alpha}


# --- tables ----------------------------------------------------------------------------------------------

def load_scores(runs_root: Path) -> list[dict[str, Any]]:
    path = Path(runs_root) / REPORT_DIR / SCORES_FILE
    if not path.is_file():
        raise ReportError(f"{path} is missing; run `score batch {runs_root}` first")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def per_run(scores: list[dict[str, Any]]) -> pd.DataFrame:
    """One row per scored run; of several finished attempts at one repeat, the latest counts."""
    rows = []
    for s in scores:
        support = s.get("support") or {}
        pending = s.get("pending") or {}
        facts = support.get("facts")
        row = {"run_id": s["run_id"], "qid": s.get("qid"), "condition": s["condition"], "repeat": s.get("repeat"),
               "attempt": s.get("attempt"), "exit_status": s.get("exit_status"), "answer_from": s.get("answer_from"),
               "provisional": bool(s.get("provisional")), "facts": facts,
               "answered": bool(facts), "judged": bool((s.get("judge") or {}).get("used")),
               "pending_support": _int(pending.get("support", support.get("pending"))),
               "pending_same_fact": _int(pending.get("same_fact")), "pending_same_row": _int(pending.get("same_row")),
               "verify_ok": s.get("verify_ok"), "key_problems": len(s.get("key_problems") or []),
               "support_context": support.get("context"), "partial_counts_as": support.get("partial_counts_as")
               } | {k: get(s, path) for k, (_, path) in OUTCOMES.items()}
        # Soft numbers with judge decisions pending are lower bounds: left out, never averaged with the rest.
        for outcome in SOFT_FACTS if row["pending_same_fact"] else ():
            row[outcome] = math.nan
        for outcome in SOFT_ROWS if row["pending_same_row"] else ():
            row[outcome] = math.nan
        row["support_share_empty_as_zero"] = 0.0 if facts == 0 else row["support_share"]
        other = "support_share_partial_no" if support.get("partial_counts_as") == "yes" else "support_share_partial_yes"
        row["support_share_other_mapping"] = get(s, ("support", other))
        row["support_share_first_claim"] = get(s, ("support", "support_share_first_claim"))
        row |= {f"setting_{k}": canonical((s.get("run_settings") or {}).get(k)) for k in SETTINGS}
        rows.append(row)
    columns = ["run_id", "qid", "condition", "repeat", "attempt", "exit_status", "answer_from", "provisional", "facts",
               "answered", "judged", "pending_support", "pending_same_fact", "pending_same_row", "verify_ok",
               "key_problems", "support_context", "partial_counts_as", *OUTCOMES, *SENSITIVITY,
               *(f"setting_{k}" for k in SETTINGS)]
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df
    df["slot"] = [f"r{r:g}" if pd.notna(r) else run for r, run in zip(df["repeat"], df["run_id"])]
    df = df.sort_values(["qid", "condition", "slot", "attempt"], na_position="first")
    return df.drop_duplicates(["qid", "condition", "slot"], keep="last").drop(columns="slot").reset_index(drop=True)


def per_question(runs: pd.DataFrame) -> pd.DataFrame:
    """Means over repeats per question and condition (a run's missing value is left out of its mean),
    with how many runs there were, how many had answer facts, fed the primary or had verdicts pending."""
    cols = [*OUTCOMES, *SENSITIVITY]
    counts = ["runs", "answered", "primary_runs", "pending_runs"]
    if runs.empty:
        return pd.DataFrame(columns=["qid", "condition", *counts, *cols])
    grouped = runs.groupby(["qid", "condition"], sort=True)
    means = grouped[cols].mean()
    means.insert(0, "pending_runs", grouped["pending_support"].apply(lambda s: int((s > 0).sum())))
    means.insert(0, "primary_runs", grouped[PRIMARY].count())
    means.insert(0, "answered", grouped["answered"].sum().astype(int))
    means.insert(0, "runs", grouped.size())
    return means.reset_index()


def paired(questions: pd.DataFrame, outcome: str) -> pd.DataFrame:
    """Per question: claim_on, claim_off and their difference, for the questions with both."""
    cols = ["qid", *CONDITIONS, "difference"]
    if questions.empty:
        return pd.DataFrame(columns=cols)
    wide = questions.pivot(index="qid", columns="condition", values=outcome)
    wide = wide.reindex(columns=list(CONDITIONS)).dropna()
    wide["difference"] = wide["claim_on"] - wide["claim_off"]
    return wide.reset_index().rename_axis(columns=None)[cols]


def summarise(questions: pd.DataFrame, outcome: str, runs: pd.DataFrame | None = None, **kw: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"label": OUTCOMES.get(outcome, (outcome,))[0]}
    for c in CONDITIONS:
        values = questions.loc[questions["condition"] == c, outcome].dropna().to_numpy(dtype=float)
        out[c] = interval(values, **kw)
        if runs is not None:  # how many runs fed the means (soft numbers with pending decisions do not)
            mine = runs.loc[runs["condition"] == c, outcome] if not runs.empty else pd.Series(dtype=float)
            out[c] |= {"runs": int(mine.notna().sum()), "runs_without_value": int(mine.isna().sum())}
    pairs = paired(questions, outcome)
    out["difference"] = interval(pairs["claim_on"].to_numpy(float), paired_with=pairs["claim_off"].to_numpy(float), **kw)
    return out


def primary(questions: pd.DataFrame, outcome: str = PRIMARY, *, blocked: str | None = None, **kw: Any) -> dict[str, Any]:
    pairs = paired(questions, outcome)
    asked = sorted(set(questions["qid"])) if not questions.empty else []
    test = wilcoxon_test(pairs["difference"].to_numpy(float), blocked=blocked)
    ci = interval(pairs["claim_on"].to_numpy(float), paired_with=pairs["claim_off"].to_numpy(float), **kw)
    return {"outcome": outcome, **test, "mean_difference": ci["mean"], "ci_low": ci["low"], "ci_high": ci["high"],
            "ci_method": ci["method"], "questions": list(pairs["qid"]),
            "excluded_questions": [q for q in asked if q not in set(pairs["qid"])]}


def exit_counts(runs: pd.DataFrame, column: str = "exit_status") -> pd.DataFrame:
    if runs.empty:
        return pd.DataFrame(columns=["condition"])
    table = pd.crosstab(runs["condition"], runs[column].fillna("unknown"))
    return table.reset_index().rename_axis(columns=None)


def by_condition(table: pd.DataFrame) -> dict[str, dict[str, int]]:
    return {r["condition"]: {k: int(v) for k, v in r.items() if k != "condition" and v} for r in table.to_dict("records")}


def batch_states(runs_root: Path) -> dict[str, Any] | None:
    path = Path(runs_root) / REPORT_DIR / BATCH_FILE
    try:
        items = json.loads(path.read_text(encoding="utf-8"))["items"]
    except (OSError, ValueError, KeyError):
        return None
    out: dict[str, dict[str, int]] = {}
    for item in items:
        if not item.get("scored"):
            by = out.setdefault(item.get("condition") or "unknown", {})
            by[item["state"]] = by.get(item["state"], 0) + 1
    return {"items": len(items), "scored": sum(bool(i.get("scored")) for i in items), "not_scored": out}


def coverage(runs: pd.DataFrame, batch: dict[str, Any] | None) -> dict[str, Any]:
    """Per condition: scored runs, those with answer facts (the primary's runs) and the share, and the
    planned runs the batch could not score (cut, failed, not started, ...)."""
    out = {}
    for c in CONDITIONS:
        mine = runs.loc[runs["condition"] == c] if not runs.empty else runs
        n, answered = int(len(mine)), int(mine["answered"].sum()) if len(mine) else 0
        out[c] = {"scored": n, "answered": answered, "answered_share": answered / n if n else None,
                  "not_scored": sum(((batch or {}).get("not_scored") or {}).get(c, {}).values())}
    return out


def completeness(runs: pd.DataFrame) -> dict[str, Any]:
    """What the numbers rest on: pending verdicts, unjudged and unverified runs, invalid keys, differing settings."""
    if runs.empty:
        return {"complete": True, "pending_support_runs": [], "pending_soft_runs": [], "unjudged_runs": [],
                "unverified_runs": [], "verify_failed_runs": [], "key_problem_runs": [], "support_context": {},
                "partial_counts_as": {}, "settings_differ": {}}

    def ids(mask: pd.Series) -> list[str]:
        return sorted(runs.loc[mask, "run_id"])

    differ = {}
    for k in SETTINGS:
        values = Counter(runs[f"setting_{k}"])
        if len(values) > 1:
            differ[k] = {v: int(n) for v, n in sorted(values.items())}
    pending = ids(runs["pending_support"] > 0)
    return {"complete": not pending and not (runs["pending_same_fact"] + runs["pending_same_row"]).any(),
            "pending_support_runs": pending,
            "pending_soft_runs": ids((runs["pending_same_fact"] + runs["pending_same_row"]) > 0),
            "unjudged_runs": ids(~runs["judged"]),
            "unverified_runs": ids(runs["verify_ok"].isna()),
            "verify_failed_runs": ids(runs["verify_ok"].eq(False)),
            "key_problem_runs": ids(runs["key_problems"] > 0),
            "support_context": {str(k): int(v) for k, v in Counter(runs["support_context"].fillna("none")).items()},
            "partial_counts_as": {str(k): int(v) for k, v in Counter(runs["partial_counts_as"].fillna("?")).items()},
            "settings_differ": differ}


def inputs(runs_root: Path, scores: list[dict[str, Any]]) -> dict[str, Any]:
    """What produced the numbers: input file hashes, scoring code, keys and judge."""
    folder = Path(runs_root) / REPORT_DIR
    keys: dict[str, set[str]] = {}
    for s in scores:
        keys.setdefault(str(s.get("qid")), set()).add(str(s.get("key_sha256")))
    judge = [s.get("judge") or {} for s in scores]
    identities = {canonical(j.get("identity")) for j in judge if j.get("used")}
    return {"scores_sha256": file_sha256(folder / SCORES_FILE),
            "batch_sha256": file_sha256(folder / BATCH_FILE) if (folder / BATCH_FILE).is_file() else None,
            "report_git_commit": scorer()["git_commit"],
            "scorer_commits": sorted({str((s.get("scorer") or {}).get("git_commit")) for s in scores}),
            "scorer_versions": sorted({str(s.get("schema_version")) for s in scores}),
            "keys": {q: sorted(v) for q, v in sorted(keys.items())},
            "judge": {"models": sorted({m for j in judge for m in j.get("models") or []}),
                      "prompt_sha256": sorted({p for j in judge for p in j.get("prompt_sha256") or []}),
                      "identities": [json.loads(i) for i in sorted(identities)]}}


# --- the report ------------------------------------------------------------------------------------------

def build(runs_root: Path, *, seed: int = SEED, resamples: int = RESAMPLES) -> dict[str, Any]:
    """Compute everything; returns {"report": report.json content, "tables": {name: DataFrame}}."""
    scores = load_scores(runs_root)
    runs = per_run(scores)
    questions = per_question(runs)
    kw = {"seed": seed, "resamples": resamples}
    state = completeness(runs)
    pending = state["pending_support_runs"]
    blocked = (f"{len(pending)} scored run{'s have' if len(pending) != 1 else ' has'} pending judge verdicts "
               f"({', '.join(pending[:10])}{', ...' if len(pending) > 10 else ''}); run `score batch` with the judge "
               "until none is pending") if pending else None
    summary = {k: summarise(questions, k, runs, **kw) for k in OUTCOMES}
    test = primary(questions, blocked=blocked, **kw)
    for column, label in SENSITIVITY.items():
        test[column.replace("support_share_", "sensitivity_")] = primary(questions, column, blocked=blocked, **kw) | {
            "label": label}
    provisional_runs = runs.loc[runs["provisional"]] if not runs.empty else runs
    batch = batch_states(runs_root)
    exits, sources = exit_counts(runs), exit_counts(runs, "answer_from")
    report = {
        "schema_version": 2, "generated_at": utc_now(), "runs_root": str(runs_root),
        "provisional": bool(len(provisional_runs)), "provisional_runs": int(len(provisional_runs)),
        "provisional_questions": sorted(set(provisional_runs["qid"].dropna())) if len(provisional_runs) else [],
        "complete": state["complete"], "completeness": state,
        "settings": {"interval": "BCa bootstrap over questions", "confidence": CONFIDENCE, "resamples": resamples,
                     "seed": seed, "alpha": ALPHA, "min_pairs": MIN_PAIRS,
                     "test": "scipy.stats.wilcoxon(zero_method='wilcox', alternative='two-sided', method='auto')",
                     "aggregation": "mean over repeats per question and condition, then over questions",
                     "soft_pending": "runs with soft-level judge decisions pending are left out of soft outcomes"},
        "inputs": inputs(runs_root, scores),
        "runs": {"scored": int(len(runs)),
                 "by_condition": {c: int((runs["condition"] == c).sum()) for c in CONDITIONS} if not runs.empty else {},
                 "by_exit_status": by_condition(exits), "by_answer_from": by_condition(sources),
                 "batch": batch},
        "coverage": coverage(runs, batch),
        "questions": sorted(set(runs["qid"].dropna())) if not runs.empty else [],
        "per_question": questions.to_dict("records"),
        "paired": paired_records(questions),
        "summary": summary, "primary": test, "secondary": SECONDARY,
    }
    tables = {"per_run": runs, "per_question": questions, "paired": paired_table(questions),
              "summary": summary_table(summary), "exit_status": exits}
    return {"report": plain(report), "tables": tables}


def paired_records(questions: pd.DataFrame) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for outcome in OUTCOMES:
        for row in paired(questions, outcome).to_dict("records"):
            out.setdefault(row["qid"], {"qid": row["qid"]})[outcome] = {
                "claim_on": row["claim_on"], "claim_off": row["claim_off"], "difference": row["difference"]}
    return [out[q] for q in sorted(out)]


def paired_table(questions: pd.DataFrame) -> pd.DataFrame:
    parts = [paired(questions, o).set_index("qid").add_prefix(f"{o}_") for o in OUTCOMES]
    return pd.concat(parts, axis=1).reset_index() if parts else pd.DataFrame()


def summary_table(summary: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for outcome, s in summary.items():
        row: dict[str, Any] = {"outcome": outcome, "label": s["label"]}
        for part in (*CONDITIONS, "difference"):
            for k in ("mean", "low", "high", "method", "n", "runs"):
                if k in s[part]:
                    row[f"{part}_{k}"] = s[part][k]
        rows.append(row)
    return pd.DataFrame(rows)


# --- report.md -------------------------------------------------------------------------------------------

def fmt(x: Any, outcome: str = "") -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "–"
    if outcome in COUNTS:
        return f"{x:,.0f}"
    if outcome in TIMES:
        return f"{x:,.1f}"
    return f"{x:.3f}"


def with_ci(s: dict[str, Any], outcome: str) -> str:
    if s["mean"] is None:
        return "–"
    if s["low"] is None:
        return fmt(s["mean"], outcome)
    return f"{fmt(s['mean'], outcome)} [{fmt(s['low'], outcome)}, {fmt(s['high'], outcome)}]"


def warnings_md(report: dict[str, Any]) -> list[str]:
    """The report's state in bold, first: what keeps these numbers from being results."""
    c, out = report["completeness"], []
    if report["provisional"]:
        n = report["provisional_runs"]
        out.append(f"**PROVISIONAL: {n} run{'s were' if n != 1 else ' was'} scored against draft answer keys "
                   f"({', '.join(report['provisional_questions'])}). These numbers test the pipeline; do not "
                   "report them.**")
    if c["pending_support_runs"]:
        out.append(f"**INCOMPLETE: {len(c['pending_support_runs'])} runs have pending judge verdicts "
                   f"({', '.join(c['pending_support_runs'][:10])}); the primary test is not computed until "
                   "`score batch` has run with the judge.**")
    if c["pending_soft_runs"]:
        out.append(f"**Soft level pending for {len(c['pending_soft_runs'])} runs** (no judge, or failed calls): "
                   "their soft outcomes are left out of the means below.")
    if c["unverified_runs"] or c["verify_failed_runs"]:
        out.append(f"**UNVERIFIED: {len(c['unverified_runs'])} runs were scored without `agent verify` (no corpus) "
                   f"and {len(c['verify_failed_runs'])} failed it.**")
    if c["key_problem_runs"]:
        out.append(f"**KEY PROBLEMS: {len(c['key_problem_runs'])} runs were scored against keys whose rows do not "
                   "validate against the concept's answer schema (see score.json key_problems).**")
    if c["settings_differ"]:
        out.append(f"**SETTINGS DIFFER between runs: {', '.join(c['settings_differ'])}** (report.json "
                   "completeness.settings_differ).")
    if len(c["partial_counts_as"]) > 1 or len(c["support_context"]) > 1:
        out.append("**Mixed judge settings across runs** (partial mapping or judge context; report.json "
                   "completeness).")
    return [line for w in out for line in (w, "")]


def markdown(report: dict[str, Any], tables: dict[str, pd.DataFrame]) -> str:
    p = report["primary"]
    lines = ["# Results: recording quotes while researching (claim_on) vs attaching them afterwards (claim_off)", ""]
    lines += warnings_md(report)
    lines += [f"{report['runs']['scored']} scored runs on {len(report['questions'])} questions, generated "
              f"{report['generated_at']}. Means over repeats per question first, then over questions; intervals "
              f"are 95 % BCa bootstrap intervals over questions ({report['settings']['resamples']:,} resamples, "
              f"seed {report['settings']['seed']}).", "", "## Primary outcome (pre-registered)", "",
              "Share of answer facts whose quote supports them (LLM judge), claim_on − claim_off, paired over "
              "questions; Wilcoxon signed-rank test, two-sided, α = 0.05.", ""]
    if p["computed"]:
        verdict = "significant" if p["significant"] else "not significant"
        lines.append(f"n = {p['n_pairs']} questions ({p['n_nonzero']} non-zero differences): W = min(T+, T−) = "
                     f"{p['statistic']:g}, p = {p['p_value']:.4g} ({verdict} at α = {p['alpha']}); mean "
                     f"difference {fmt(p['mean_difference'])}, 95 % CI [{fmt(p['ci_low'])}, {fmt(p['ci_high'])}] "
                     f"({p['ci_method']}); rank-biserial r = {fmt(p['rank_biserial'])}.")
    else:
        lines.append(f"Not computed: {p['reason']}. Mean difference {fmt(p['mean_difference'])} over "
                     f"{p['n_pairs']} paired questions.")
    if p["excluded_questions"]:
        lines.append(f"Not paired (no support share in one condition): {', '.join(p['excluded_questions'])}.")
    cov = report["coverage"]
    lines += ["", "Coverage (scored runs with answer facts, the runs the primary rests on): "
              + "; ".join(f"{c} {v['answered']}/{v['scored']}" + (f" ({v['answered_share']:.0%})"
                                                                   if v["answered_share"] is not None else "")
                          + (f", {v['not_scored']} planned runs not scored" if v["not_scored"] else "")
                          for c, v in cov.items()) + ".", ""]
    lines += ["Sensitivity analyses:", ""]
    for column in SENSITIVITY:
        s = p[column.replace("support_share_", "sensitivity_")]
        lines.append(f"- {s['label']}: mean difference {fmt(s['mean_difference'])} over {s['n_pairs']} questions, "
                     + (f"p = {s['p_value']:.4g}." if s["computed"] else f"test not computed ({s['reason']})."))
    lines.append("")
    rows = [{"Outcome": sm["label"], "claim_on": with_ci(sm["claim_on"], k), "claim_off": with_ci(sm["claim_off"], k),
             "Difference (on − off)": with_ci(sm["difference"], k), "Paired questions": sm["difference"]["n"],
             "Runs on/off": f"{sm['claim_on'].get('runs', '–')}/{sm['claim_off'].get('runs', '–')}"}
            for k, sm in report["summary"].items()]
    lines += ["## Outcomes by condition", "", table(rows), "",
              "Secondary outcomes are reported with intervals and without tests. Runs on/off: the runs with a "
              "value (soft outcomes leave out runs with judge decisions pending).", ""]
    lines += ["## Per question", "", per_question_markdown(tables["per_question"]), ""]
    exits = tables["exit_status"]
    if not exits.empty:
        lines += ["## Runs by exit status", "", exits.to_markdown(index=False), ""]
    sources = report["runs"]["by_answer_from"]
    if sources:
        lines += ["Answer source (final reply, the agent's draft file, none): "
                  + "; ".join(f"{c}: " + ", ".join(f"{k} {n}" for k, n in sorted(v.items()))
                              for c, v in sorted(sources.items())) + ".", ""]
    batch = report["runs"]["batch"]
    if batch and batch["not_scored"]:
        rows = [{"condition": c, "state": st, "runs": n} for c, by in batch["not_scored"].items() for st, n in by.items()]
        lines += ["## Planned runs not scored", "", table(rows), ""]
    lines += ["Files: report.json (everything above, machine-readable, with the inputs' hashes), per_run.csv, "
              "per_question.csv, paired.csv, summary.csv, exit_status.csv.", ""]
    return "\n".join(lines)


def table(rows: list[dict[str, Any]]) -> str:
    """A Markdown table of already formatted cells (tabulate would reformat numbers)."""
    return pd.DataFrame(rows).to_markdown(index=False, disable_numparse=True)


def per_question_markdown(questions: pd.DataFrame) -> str:
    """One row per question: runs and the main outcomes in each condition (on / off)."""
    show = {"support_share": "Support", "fact_f1": "Fact F1", "row_f1": "Row F1", "unsourced_share": "Unsourced",
            "tokens": "Tokens"}
    cell = {(r["qid"], r["condition"]): r for r in questions.to_dict("records")}
    rows = []
    for qid in sorted({q for q, _ in cell}):
        on, off = cell.get((qid, "claim_on"), {}), cell.get((qid, "claim_off"), {})
        row: dict[str, Any] = {"Question": qid, "Runs on/off": f"{on.get('runs', 0)}/{off.get('runs', 0)}",
                               "In primary on/off": f"{on.get('primary_runs', 0)}/{off.get('primary_runs', 0)}"}
        for outcome, name in show.items():
            row[f"{name} on"] = fmt(on.get(outcome), outcome)
            row[f"{name} off"] = fmt(off.get(outcome), outcome)
            if outcome == PRIMARY:
                a, b = on.get(outcome), off.get(outcome)
                row["Support Δ"] = fmt(a - b if a is not None and b is not None else None)
        rows.append(row)
    return table(rows) if rows else "No scored runs."


def write(runs_root: Path, *, seed: int = SEED, resamples: int = RESAMPLES) -> dict[str, Any]:
    """Build the report and write report.json, report.md and the CSV tables; returns report.json."""
    built = build(runs_root, seed=seed, resamples=resamples)
    out = Path(runs_root) / REPORT_DIR
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "report.json", built["report"])
    (out / "report.md").write_text(markdown(built["report"], built["tables"]), encoding="utf-8", newline="\n")
    for name, table in built["tables"].items():
        table.to_csv(out / f"{name}.csv", index=False, lineterminator="\n")
    return built["report"]
