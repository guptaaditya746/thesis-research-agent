"""`score report <runs_root>`: the milestone 4 results from report/scores.jsonl (docs/e2e-build-plan.md).

Aggregation (the labelling repo's docs/EVALUATION.md, section 5): repeats are averaged per question and
condition first (they are not independent samples); summaries average the per-question means, so each
question counts once; claim_on and claim_off are compared on the same questions as paired per-question
differences claim_on - claim_off. Intervals: 95 % BCa bootstrap over questions (scipy.stats.bootstrap,
2,000 resamples, fixed seed; the paired form resamples questions with both conditions together). BCa
needs two questions and some spread: with all values equal the interval is that value ("degenerate");
when BCa cannot be computed the percentile interval is used, and `method` says which.

Primary outcome (pre-registered, docs/STATE.md Framing): support share, the share of a run's answer
facts whose quote supports them (judge), claim_on vs claim_off after the attach step. Per question the
mean over repeats; a run without answer facts has no support share and is left out of that mean; a
question needs a mean in both conditions to be paired. Test: Wilcoxon signed-rank on the paired
per-question means, two-sided, alpha 0.05 (scipy.stats.wilcoxon, zero_method "wilcox": zero differences,
after rounding to 12 decimals, are dropped; method "auto": the exact null distribution up to 50 pairs),
with the BCa interval of the mean difference and the matched-pairs rank-biserial correlation as effect
size. With fewer than 6 paired questions the test is not computed: even if every difference had the same
sign, the smallest two-sided p would be 2/2^5 = 0.0625 > alpha. A sensitivity analysis counts runs
without answer facts as support share 0.

Secondary outcomes, with intervals and no test: fact precision, recall and F1 (soft; F1 also strict
and normalised), row F1, vital recall, judged precision, unsourced share, tokens and time with and
without the attach step. Runs are counted by condition and exit status, and keys the batch could not
score by their state. Any score against a draft key makes the whole report provisional.

Writes report/report.json, report/report.md (tables to paste into the thesis) and report/*.csv.
"""
from __future__ import annotations

import json
import math
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from agent.canonical import write_json
from agent.rundir import utc_now

from .batch import BATCH_FILE, REPORT_DIR, SCORES_FILE

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
    "row_f1": ("Row F1", ("rows", "f1")),
    "vital_recall": ("Vital recall (soft)", ("vital_recall",)),
    "judged_precision": ("Judged precision", ("judged_precision", "precision")),
    "unsourced_share": ("Unsourced share", ("support", "unsourced_share")),
    "tokens": ("Tokens", ("cost", "tokens")),
    "tokens_without_attach": ("Tokens without attach", ("cost", "tokens_without_attach")),
    "seconds": ("Time (s)", ("cost", "seconds")),
    "seconds_without_attach": ("Time without attach (s)", ("cost", "seconds_without_attach")),
}
SECONDARY = [k for k in OUTCOMES if k != PRIMARY]
COUNTS = ("tokens", "tokens_without_attach")
TIMES = ("seconds", "seconds_without_attach")


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


def wilcoxon_test(diffs: np.ndarray, *, alpha: float = ALPHA, min_pairs: int = MIN_PAIRS) -> dict[str, Any]:
    """The pre-registered test on paired per-question differences (claim_on - claim_off)."""
    d = np.round(np.asarray(diffs, dtype=float), DECIMALS)
    nonzero = d[d != 0]
    out: dict[str, Any] = {"test": "wilcoxon signed-rank", "alternative": "two-sided", "zero_method": "wilcox",
                           "alpha": alpha, "n_pairs": int(len(d)), "n_nonzero": int(len(nonzero)),
                           "computed": False, "reason": None, "statistic": None, "p_value": None,
                           "significant": None, "t_plus": None, "t_minus": None, "rank_biserial": None}
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


def per_run(scores: list[dict[str, Any]]) -> pd.DataFrame:
    """One row per scored run; of several finished attempts at one repeat, the latest counts."""
    rows = []
    for s in scores:
        facts = (s.get("support") or {}).get("facts")
        row = {"run_id": s["run_id"], "qid": s.get("qid"), "condition": s["condition"], "repeat": s.get("repeat"),
               "attempt": s.get("attempt"), "exit_status": s.get("exit_status"), "provisional": bool(s.get("provisional")),
               "facts": facts} | {k: get(s, path) for k, (_, path) in OUTCOMES.items()}
        # Sensitivity analysis: an answer with no facts has support share 0 instead of none.
        row["support_share_empty_as_zero"] = 0.0 if facts == 0 else row["support_share"]
        rows.append(row)
    df = pd.DataFrame(rows, columns=["run_id", "qid", "condition", "repeat", "attempt", "exit_status", "provisional",
                                     "facts", *OUTCOMES, "support_share_empty_as_zero"])
    if df.empty:
        return df
    df["slot"] = [f"r{r:g}" if pd.notna(r) else run for r, run in zip(df["repeat"], df["run_id"])]
    df = df.sort_values(["qid", "condition", "slot", "attempt"], na_position="first")
    return df.drop_duplicates(["qid", "condition", "slot"], keep="last").drop(columns="slot").reset_index(drop=True)


def per_question(runs: pd.DataFrame) -> pd.DataFrame:
    """Means over repeats per question and condition (a run's missing value is left out of its mean)."""
    cols = [*OUTCOMES, "support_share_empty_as_zero"]
    if runs.empty:
        return pd.DataFrame(columns=["qid", "condition", "runs", *cols])
    grouped = runs.groupby(["qid", "condition"], sort=True)
    means = grouped[cols].mean()
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


def summarise(questions: pd.DataFrame, outcome: str, **kw: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"label": OUTCOMES.get(outcome, (outcome,))[0]}
    for c in CONDITIONS:
        values = questions.loc[questions["condition"] == c, outcome].dropna().to_numpy(dtype=float)
        out[c] = interval(values, **kw)
    pairs = paired(questions, outcome)
    out["difference"] = interval(pairs["claim_on"].to_numpy(float), paired_with=pairs["claim_off"].to_numpy(float), **kw)
    return out


def primary(questions: pd.DataFrame, outcome: str = PRIMARY, **kw: Any) -> dict[str, Any]:
    pairs = paired(questions, outcome)
    asked = sorted(set(questions["qid"])) if not questions.empty else []
    test = wilcoxon_test(pairs["difference"].to_numpy(float))
    ci = interval(pairs["claim_on"].to_numpy(float), paired_with=pairs["claim_off"].to_numpy(float), **kw)
    return {"outcome": outcome, **test, "mean_difference": ci["mean"], "ci_low": ci["low"], "ci_high": ci["high"],
            "ci_method": ci["method"], "questions": list(pairs["qid"]),
            "excluded_questions": [q for q in asked if q not in set(pairs["qid"])]}


def exit_counts(runs: pd.DataFrame) -> pd.DataFrame:
    if runs.empty:
        return pd.DataFrame(columns=["condition"])
    table = pd.crosstab(runs["condition"], runs["exit_status"].fillna("unknown"))
    return table.reset_index().rename_axis(columns=None)


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


# --- the report ------------------------------------------------------------------------------------------

def build(runs_root: Path, *, seed: int = SEED, resamples: int = RESAMPLES) -> dict[str, Any]:
    """Compute everything; returns {"report": report.json content, "tables": {name: DataFrame}}."""
    scores = load_scores(runs_root)
    runs = per_run(scores)
    questions = per_question(runs)
    kw = {"seed": seed, "resamples": resamples}
    summary = {k: summarise(questions, k, **kw) for k in OUTCOMES}
    test = primary(questions, **kw)
    test["sensitivity_empty_as_zero"] = primary(questions, "support_share_empty_as_zero", **kw)
    provisional_runs = runs.loc[runs["provisional"]] if not runs.empty else runs
    exits = exit_counts(runs)
    report = {
        "schema_version": 1, "generated_at": utc_now(), "runs_root": str(runs_root),
        "provisional": bool(len(provisional_runs)), "provisional_runs": int(len(provisional_runs)),
        "provisional_questions": sorted(set(provisional_runs["qid"].dropna())) if len(provisional_runs) else [],
        "settings": {"interval": "BCa bootstrap over questions", "confidence": CONFIDENCE, "resamples": resamples,
                     "seed": seed, "alpha": ALPHA, "min_pairs": MIN_PAIRS,
                     "test": "scipy.stats.wilcoxon(zero_method='wilcox', alternative='two-sided', method='auto')",
                     "aggregation": "mean over repeats per question and condition, then over questions"},
        "runs": {"scored": int(len(runs)),
                 "by_condition": {c: int((runs["condition"] == c).sum()) for c in CONDITIONS} if not runs.empty else {},
                 "by_exit_status": {r["condition"]: {k: int(v) for k, v in r.items() if k != "condition" and v}
                                    for r in exits.to_dict("records")},
                 "batch": batch_states(runs_root)},
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
            for k in ("mean", "low", "high", "method", "n"):
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


def markdown(report: dict[str, Any], tables: dict[str, pd.DataFrame]) -> str:
    p = report["primary"]
    lines = ["# Results: recording quotes while researching (claim_on) vs attaching them afterwards (claim_off)", ""]
    if report["provisional"]:
        n = report["provisional_runs"]
        lines += [f"**PROVISIONAL: {n} run{'s were' if n != 1 else ' was'} scored against draft answer keys "
                  f"({', '.join(report['provisional_questions'])}). These numbers test the pipeline; do not "
                  "report them.**", ""]
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
    s = p["sensitivity_empty_as_zero"]
    lines += ["", f"Sensitivity (answers without facts count as 0): mean difference {fmt(s['mean_difference'])}, "
              + (f"p = {s['p_value']:.4g}." if s["computed"] else f"test not computed ({s['reason']})."), ""]
    rows = [{"Outcome": sm["label"], "claim_on": with_ci(sm["claim_on"], k), "claim_off": with_ci(sm["claim_off"], k),
             "Difference (on − off)": with_ci(sm["difference"], k), "Paired questions": sm["difference"]["n"]}
            for k, sm in report["summary"].items()]
    lines += ["## Outcomes by condition", "", table(rows), "",
              "Secondary outcomes are reported with intervals and without tests.", ""]
    lines += ["## Per question", "", per_question_markdown(tables["per_question"]), ""]
    exits = tables["exit_status"]
    if not exits.empty:
        lines += ["## Runs by exit status", "", exits.to_markdown(index=False), ""]
    batch = report["runs"]["batch"]
    if batch and batch["not_scored"]:
        rows = [{"condition": c, "state": st, "runs": n} for c, by in batch["not_scored"].items() for st, n in by.items()]
        lines += ["## Planned runs not scored", "", table(rows), ""]
    lines += ["Files: report.json (everything above, machine-readable), per_run.csv, per_question.csv, paired.csv, "
              "summary.csv, exit_status.csv.", ""]
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
        row: dict[str, Any] = {"Question": qid, "Runs on/off": f"{on.get('runs', 0)}/{off.get('runs', 0)}"}
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
