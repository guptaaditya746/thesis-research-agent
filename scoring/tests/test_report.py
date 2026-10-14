"""scoring/report.py: per-question means, paired differences, BCa intervals and the primary test,
against numbers computed by hand (and scipy called directly with the same seed); pending verdicts,
coverage, settings and inputs that must show in the report."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from scoring.cli import main as cli
from scoring.report import RESAMPLES, SEED, build, interval, wilcoxon_test, write

# Support shares per question and condition, two repeats each. Differences of the means:
# q01 .3, q02 .5, q03 .25, q04 .35, q05 .6, q06 .1 (all positive, no ties); q07 has no claim_off answer facts.
SHARES = {
    "q01": ([0.8, 0.6], [0.5, 0.3]), "q02": ([1.0, 0.8], [0.4, 0.4]), "q03": ([0.5, 0.5], [0.25, 0.25]),
    "q04": ([0.75, 0.25], [0.2, 0.1]), "q05": ([0.9, 0.7], [0.2, 0.2]), "q06": ([0.6, 0.6], [0.55, 0.45]),
    "q07": ([0.5, 0.5], [None, None]),
}
ON = np.array([0.7, 0.9, 0.5, 0.5, 0.8, 0.6])
OFF = np.array([0.4, 0.4, 0.25, 0.15, 0.2, 0.5])
SETTINGS = {"budget": {"steps": 60, "tokens": 2000000}, "temperature": 0.7, "prompt_version": "v2",
            "prompt_sha256": "p" * 64, "model": "Qwen/Qwen3.8-27B-FP8@017b9c7", "corpus_manifest_sha256": "m" * 64,
            "git_commit": "c" * 40}


def score(qid: str, condition: str, repeat: int, share: float | None, *, attempt: int = 1, exit_status: str = "submitted",
          provisional: bool = False, f1: float = 0.5, pending: int = 0, soft_pending: int = 0,
          verify_ok: bool | None = True, calibration: str = "passed", **settings: Any) -> dict[str, Any]:
    """A score.json as run_score writes it (the fields the report reads). claim_off's other partial mapping
    adds 0.1 to its share; claim_on's first-claim share is 0.2 lower. The two conditions' system prompts
    differ (the claim block), as in real runs."""
    on = condition == "claim_on"
    facts = 0 if share is None else 4
    known = share is not None and not pending
    kappa = {"passed": 0.72, "failed": 0.48, "none": None}[calibration]
    return {
        "schema_version": 3, "run_id": f"{qid}-{condition}-r{repeat}-a{attempt}", "qid": qid, "condition": condition,
        "repeat": repeat, "attempt": attempt, "seed": 1000 + repeat, "exit_status": exit_status,
        "answer_from": "final" if facts else "none", "provisional": provisional, "verify_ok": verify_ok,
        "key_reviewed": True, "key_complete": not provisional,
        "key_problems": [], "key_sha256": f"key-{qid}", "scorer": {"version": 3, "git_commit": "s" * 40},
        "rows": {"tp": 1, "fp": 1, "fn": 1, "precision": 0.5, "recall": 0.5, "f1": f1},
        "rows_by_level": {"normalised": {"f1": f1}},
        "facts": {level: {"precision": f1, "recall": f1, "f1": f1} for level in ("strict", "normalised", "soft")},
        "vital_recall": 1.0, "judged_precision": {"precision": None},
        "support": {"facts": facts, "pending": pending, "partial_counts_as": "no", "context": "calibrated",
                    "support_share": share if known else None,
                    "support_share_partial_no": share if known else None,
                    "support_share_partial_yes": (share if on else share + 0.1) if known else None,
                    "support_share_first_claim": (share - 0.2 if on else share) if known else None,
                    "claims_per_fact": (2.0 if on else 1.0) if facts else None,
                    "unsourced_share": 0.0 if on else 0.25,
                    "calibration": {"partial_counts_as": "no", "state": calibration, "kappa": kappa,
                                    "bar": 0.61 if kappa is not None else None}},
        "pending": {"support": pending, "same_fact": soft_pending, "same_row": 0},
        "judge": {"used": True, "identity": {"name": "gold.judge", "model": "judge-model", "prompts": {"support": "h"}},
                  "models": ["judge-model"], "prompt_sha256": ["h" * 64]},
        "run_settings": SETTINGS | {"prompt_sha256": ("p" if on else "q") * 64,
                                    "attach": None if on else {"budget_per_fact": {"steps": 6}}} | settings,
        "cost": {"tokens": 1000 if on else 1500, "tokens_without_attach": 1000 if on else 1200,
                 "seconds": 60.0 if on else 90.0, "seconds_without_attach": 60.0 if on else 70.0},
    }


def write_scores(root: Path, scores: list[dict[str, Any]]) -> Path:
    (root / "report").mkdir(parents=True, exist_ok=True)
    (root / "report" / "scores.jsonl").write_text("".join(json.dumps(s) + "\n" for s in scores), encoding="utf-8")
    return root


def sample() -> list[dict[str, Any]]:
    out = []
    for qid, (on, off) in SHARES.items():
        for r in (1, 2):
            out.append(score(qid, "claim_on", r, on[r - 1]))
            out.append(score(qid, "claim_off", r, off[r - 1], exit_status="budget" if (qid, r) == ("q02", 2) else "submitted"))
    # An earlier, cut attempt at q01 claim_on r1: the later attempt counts.
    out.append(score("q01", "claim_on", 1, 0.0, attempt=0))
    return out


def md_row(md: str, first: str) -> list[str]:
    """The cells of the Markdown table row that starts with `first`."""
    line = next(line for line in md.splitlines() if line.startswith(f"| {first} "))
    return [cell.strip() for cell in line.strip("|").split("|")]


def test_report_numbers_against_hand_computed(tmp_path: Path) -> None:
    report = build(write_scores(tmp_path, sample()))["report"]
    per_q = {(r["qid"], r["condition"]): r for r in report["per_question"]}
    assert per_q[("q04", "claim_on")]["support_share"] == pytest.approx(0.5) and per_q[("q04", "claim_on")]["runs"] == 2
    assert per_q[("q07", "claim_off")]["support_share"] is None  # no answer facts in either repeat
    assert (per_q[("q07", "claim_off")]["answered"], per_q[("q07", "claim_off")]["primary_runs"]) == (0, 0)
    assert [r["qid"] for r in report["paired"]] == [f"q0{n}" for n in range(1, 8)]
    q01 = next(r for r in report["paired"] if r["qid"] == "q01")["support_share"]
    assert (q01["claim_on"], q01["claim_off"], q01["difference"]) == pytest.approx((0.7, 0.4, 0.3))

    summary = report["summary"]["support_share"]
    assert summary["claim_on"]["mean"] == pytest.approx((ON.sum() + 0.5) / 7) and summary["claim_on"]["n"] == 7
    assert summary["claim_off"]["mean"] == pytest.approx(OFF.mean()) and summary["claim_off"]["n"] == 6
    assert (summary["claim_on"]["runs"], summary["claim_off"]["runs"], summary["claim_off"]["runs_without_value"]) == (
        14, 12, 2)
    assert summary["difference"]["mean"] == pytest.approx(0.35) and summary["difference"]["n"] == 6
    # BCa over questions, paired: the same numbers scipy gives for the same data and seed.
    direct = stats.bootstrap((ON, OFF), lambda a, b, axis: np.mean(a - b, axis=axis), paired=True,
                             n_resamples=RESAMPLES, method="BCa", rng=np.random.default_rng(SEED)).confidence_interval
    assert (summary["difference"]["low"], summary["difference"]["high"]) == pytest.approx((direct.low, direct.high))
    assert summary["difference"]["method"] == "BCa" and summary["difference"]["low"] > 0

    p = report["primary"]
    assert p["computed"] and (p["n_pairs"], p["n_nonzero"], p["excluded_questions"]) == (6, 6, ["q07"])
    assert (p["statistic"], p["p_value"], p["significant"]) == (0.0, 2 / 2 ** 6, True)  # exact: all six positive
    assert (p["t_plus"], p["t_minus"], p["rank_biserial"]) == (21.0, 0.0, 1.0)
    assert p["mean_difference"] == pytest.approx(0.35) and (p["ci_low"], p["ci_high"]) == pytest.approx((direct.low, direct.high))
    # Sensitivity: q07's claim_off runs had no facts; counted as 0 they pair q07 with difference 0.5.
    s = p["sensitivity_empty_as_zero"]
    assert s["n_pairs"] == 7 and s["mean_difference"] == pytest.approx((2.1 + 0.5) / 7)
    # The other partial mapping adds 0.1 to claim_off; the first claim alone takes 0.2 off claim_on.
    assert p["sensitivity_other_mapping"]["mean_difference"] == pytest.approx(0.25)
    assert p["sensitivity_first_claim"]["mean_difference"] == pytest.approx(0.15)
    assert p["sensitivity_first_claim"]["computed"] and p["sensitivity_first_claim"]["n_pairs"] == 6

    tokens = report["summary"]["tokens"]["difference"]
    assert (tokens["mean"], tokens["low"], tokens["high"], tokens["method"]) == (-500.0, -500.0, -500.0,
                                                                                 "degenerate (all equal)")
    assert report["summary"]["tokens_without_attach"]["difference"]["mean"] == -200.0
    assert report["summary"]["seconds_without_attach"]["claim_off"]["mean"] == 70.0
    assert report["summary"]["claims_per_fact"]["difference"]["mean"] == 1.0
    assert report["runs"]["scored"] == 28  # the earlier attempt is dropped
    assert report["runs"]["by_exit_status"] == {"claim_off": {"budget": 1, "submitted": 13}, "claim_on": {"submitted": 14}}
    assert report["runs"]["by_answer_from"] == {"claim_off": {"final": 12, "none": 2}, "claim_on": {"final": 14}}
    assert report["coverage"]["claim_off"] == {"scored": 14, "answered": 12, "answered_share": 12 / 14, "not_scored": 0}
    assert report["provisional"] is False and report["secondary"][0] == "fact_precision"
    # The conditions' prompts differ by design: no false alarm.
    assert report["complete"] is True and report["completeness"]["settings_differ"] == {}
    assert report["judge"] == {"state": "passed", "validated": True, "kappa": [0.72], "bar": 0.61}
    assert p["judge_validated"] is True and report["duplicates"] == []
    inputs = report["inputs"]
    assert len(inputs["scores_sha256"]) == 64 and inputs["batch_sha256"] is None
    assert inputs["keys"]["q01"] == ["key-q01"] and inputs["scorer_commits"] == ["s" * 40]
    assert inputs["judge"]["models"] == ["judge-model"] and inputs["judge"]["prompt_sha256"] == ["h" * 64]


def test_pending_verdicts_block_the_primary_test_and_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A run whose verdicts are pending is never averaged away silently."""
    scores = sample()
    scores[2] = score("q01", "claim_on", 2, 0.6, pending=2)  # q01 claim_on r2: judge failed on two quotes
    root = write_scores(tmp_path, scores)
    report = build(root)["report"]
    per_q = {(r["qid"], r["condition"]): r for r in report["per_question"]}
    q01 = per_q[("q01", "claim_on")]
    assert (q01["runs"], q01["primary_runs"], q01["pending_runs"], q01["support_share"]) == (2, 1, 1, 0.8)
    p = report["primary"]
    assert not p["computed"] and p["p_value"] is None and "1 scored run has pending judge verdicts" in p["reason"]
    assert "q01-claim_on-r2-a1" in p["reason"]
    assert not p["sensitivity_empty_as_zero"]["computed"] and not p["sensitivity_first_claim"]["computed"]
    assert report["complete"] is False and report["completeness"]["pending_support_runs"] == ["q01-claim_on-r2-a1"]
    assert cli(["report", str(root)]) == 0
    out = capsys.readouterr().out
    assert "primary: not computed (1 scored run has pending judge verdicts" in out and "INCOMPLETE" in out
    md = (root / "report" / "report.md").read_text(encoding="utf-8")
    assert "**INCOMPLETE: 1 runs have pending judge verdicts (q01-claim_on-r2-a1)" in md
    assert md_row(md, "q01")[1:3] == ["2/2", "1/2"]  # runs, and runs in the primary


def test_soft_outcomes_with_pending_decisions_are_left_out(tmp_path: Path) -> None:
    scores = sample()
    scores[0] = score("q01", "claim_on", 1, 0.8, f1=0.9, soft_pending=3)  # unjudged soft level: a lower bound
    report = build(write_scores(tmp_path, scores))["report"]
    per_q = {(r["qid"], r["condition"]): r for r in report["per_question"]}
    assert per_q[("q01", "claim_on")]["fact_f1"] == 0.5  # only r2's complete number
    assert per_q[("q01", "claim_on")]["fact_f1_normalised"] == pytest.approx(0.7)  # needs no judge
    assert report["summary"]["fact_f1"]["claim_on"]["runs"] == 13
    assert report["summary"]["fact_f1"]["claim_on"]["runs_without_value"] == 1
    assert report["primary"]["computed"]  # the support share is complete
    assert report["completeness"]["pending_soft_runs"] == ["q01-claim_on-r1-a1"] and report["complete"] is False


def test_unverified_runs_key_problems_and_differing_settings_are_flagged(tmp_path: Path) -> None:
    scores = sample()
    scores[0] = score("q01", "claim_on", 1, 0.8, verify_ok=None, budget={"steps": 150, "tokens": 400000})
    scores[1]["key_problems"] = ["rows/0: 'facts' is a required property"]
    scores[3]["verify_ok"] = False
    root = write_scores(tmp_path, scores)
    report = write(root)
    c = report["completeness"]
    assert (c["unverified_runs"], c["verify_failed_runs"], c["key_problem_runs"]) == (
        ["q01-claim_on-r1-a1"], ["q01-claim_off-r2-a1"], ["q01-claim_off-r1-a1"])
    assert list(c["settings_differ"]) == ["budget"] and sum(c["settings_differ"]["budget"].values()) == 28
    md = (root / "report" / "report.md").read_text(encoding="utf-8")
    assert "**UNVERIFIED: 1 runs were scored without `agent verify` (no corpus) and 1 failed it.**" in md
    assert "**KEY PROBLEMS: 1 runs" in md and "**SETTINGS DIFFER between runs: budget**" in md


def test_settings_are_compared_within_each_condition(tmp_path: Path) -> None:
    """Another system prompt or attach budget inside one condition is flagged; the two conditions'
    prompts differing is the design. So are the loop's settings across all runs (another Slurm job)."""
    scores = sample()
    scores[1] = score("q01", "claim_off", 1, 0.5, prompt_sha256="x" * 64, attach={"budget_per_fact": {"steps": 9}})
    scores[0] = score("q01", "claim_on", 1, 0.8, loop={"conclude_decoding": "free"})
    c = write(write_scores(tmp_path, scores))["completeness"]
    assert set(c["settings_differ"]) == {"prompt_sha256", "attach", "loop"}
    prompts = c["settings_differ"]["prompt_sha256"]
    assert sum(n for k, n in prompts.items() if k.startswith("claim_off")) == 14
    assert [k for k in prompts if k.startswith("claim_on")] == [f'claim_on: "{"p" * 64}"']  # one prompt: fine


def test_a_judge_that_failed_calibration_is_not_the_result(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Below the kappa bar the support share is an unvalidated secondary number and the soft scores are
    reported without the judge (docs/STATE.md, Judge): the report says so first, the primary test is
    marked unvalidated, and the soft outcomes are left out while strict and normalised stand."""
    root = write_scores(tmp_path, [score(q, c, r, share, calibration="failed") for q, (on, off) in SHARES.items()
                                   for r in (1, 2) for c, share in (("claim_on", on[r - 1]), ("claim_off", off[r - 1]))])
    report = write(root)
    assert report["judge"]["state"] == "failed" and report["judge"]["kappa"] == [0.48]
    assert report["primary"]["computed"] and report["primary"]["judge_validated"] is False
    assert report["summary"]["fact_f1"]["claim_on"]["n"] == 0  # soft: left out
    assert report["summary"]["fact_f1_normalised"]["claim_on"]["n"] == 7  # needs no judge
    md = (root / "report" / "report.md").read_text(encoding="utf-8")
    assert "**JUDGE FAILED CALIBRATION (kappa 0.48 below 0.61)" in md and "**Unvalidated: the judge failed" in md
    assert cli(["report", str(root)]) == 0 and "JUDGE FAILED CALIBRATION" in capsys.readouterr().out
    none = write(write_scores(tmp_path / "none", [score("q01", "claim_on", 1, 0.5, calibration="none")]))
    assert none["judge"]["state"] == "none" and not none["judge"]["validated"]
    assert "**JUDGE NOT CALIBRATED" in (tmp_path / "none" / "report" / "report.md").read_text(encoding="utf-8")


def test_scores_of_one_run_twice_are_listed_not_mixed(tmp_path: Path) -> None:
    """Two batch roots scored together (e2e-smoke and m4-72 both have q01-claim_on-r1-a1): one is kept,
    the other listed and warned about, never averaged in silently."""
    scores = sample() + [score("q01", "claim_on", 1, 0.0)]  # the smoke run of the same name
    report = write(write_scores(tmp_path, scores))
    assert [d["run_id"] for d in report["duplicates"]] == ["q01-claim_on-r1-a1"] and report["runs"]["scored"] == 28
    assert "**DUPLICATE RUNS: 1 score left out" in (tmp_path / "report" / "report.md").read_text(encoding="utf-8")


def test_incomplete_keys_are_named_in_the_provisional_warning(tmp_path: Path) -> None:
    scores = sample()
    scores[0] |= {"provisional": True, "key_complete": False}  # key.json of a review still going on
    scores[1] |= {"provisional": True, "key_reviewed": False, "key_complete": None}  # key.draft.json
    report = write(write_scores(tmp_path, scores))
    assert report["completeness"]["key_states"] == {"draft": 1, "incomplete": 1, "reviewed": 26}
    md = (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    assert "(1 against draft keys and 1 against keys whose review is not finished; q01)" in md


def test_wilcoxon_on_a_known_example() -> None:
    # scipy.stats.wilcoxon's documented example (Cushny and Peebles via Fisher): W = 24, exact p = 0.0413.
    d = np.array([6, 8, 14, 16, 23, 24, 28, 29, 41, -48, 49, 56, 60, -67, 75]) / 100
    result = wilcoxon_test(d)
    assert (result["statistic"], result["p_value"]) == (24.0, pytest.approx(0.041259765625))
    assert (result["t_minus"], result["t_plus"]) == (24.0, 96.0) and result["rank_biserial"] == pytest.approx(0.6)
    zeros = wilcoxon_test(np.zeros(7))
    assert zeros["computed"] and zeros["p_value"] == 1.0 and zeros["n_nonzero"] == 0
    # Equal means computed in another order differ by rounding error only: still a zero difference.
    assert wilcoxon_test(np.array([1e-17, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]))["n_nonzero"] == 6
    blocked = wilcoxon_test(d, blocked="verdicts pending")
    assert not blocked["computed"] and blocked["reason"] == "verdicts pending" and blocked["n_pairs"] == 15


def test_fewer_than_six_pairs_is_not_computed(tmp_path: Path) -> None:
    scores = [s for s in sample() if s["qid"] in ("q01", "q02", "q03")]
    report = build(write_scores(tmp_path, scores))["report"]
    p = report["primary"]
    assert not p["computed"] and p["p_value"] is None and p["n_pairs"] == 3
    assert p["reason"].startswith("fewer than 6 paired questions (n = 3)")
    assert p["mean_difference"] == pytest.approx((0.3 + 0.5 + 0.25) / 3) and p["ci_method"] == "BCa"


def test_intervals_at_the_edges() -> None:
    assert interval(np.array([])) == {"n": 0, "mean": None, "low": None, "high": None, "method": None}
    one = interval(np.array([0.4]))
    assert (one["mean"], one["low"], one["method"]) == (0.4, None, "none (fewer than 2 questions)")
    same = interval(np.array([0.5, 0.5, 0.5]))
    assert (same["low"], same["high"], same["method"]) == (0.5, 0.5, "degenerate (all equal)")


def test_provisional_report_and_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scores = sample()
    scores[0]["provisional"] = True  # q01 scored against its draft key
    root = write_scores(tmp_path, scores)
    items = [{"key": f"q0{n}-claim_on-r1", "condition": "claim_on", "state": "finished", "scored": True} for n in (1, 2)]
    items.append({"key": "q08-claim_off-r3", "condition": "claim_off", "state": "cut", "scored": False})
    (root / "report" / "batch.json").write_text(json.dumps({"items": items}), encoding="utf-8")
    assert cli(["report", str(root)]) == 0
    out = capsys.readouterr().out
    assert "primary: support share claim_on - claim_off = 0.350 over 6 questions, Wilcoxon p = 0.03125" in out
    assert "PROVISIONAL" in out and "INCOMPLETE" not in out
    report = json.loads((root / "report" / "report.json").read_text(encoding="utf-8"))
    assert report["provisional"] is True and report["provisional_questions"] == ["q01"]
    assert len(report["inputs"]["batch_sha256"]) == 64
    md = (root / "report" / "report.md").read_text(encoding="utf-8")
    assert md.splitlines()[2].startswith("**PROVISIONAL") and "## Primary outcome (pre-registered)" in md
    assert "| Support share (judge) " in md and "0.350 [" in md and "p = 0.03125 (significant" in md
    assert md_row(md, "q04")[:6] == ["q04", "2/2", "2/2", "0.500", "0.150", "0.350"]  # per question, formatted
    assert "Coverage (scored runs with answer facts, the runs the primary rests on): claim_on 14/14 (100%); " \
           "claim_off 12/14 (86%), 1 planned runs not scored." in md
    assert "- `partial` under the other mapping than the calibrated one: mean difference 0.250" in md
    assert report["runs"]["batch"] == {"items": 3, "scored": 2, "not_scored": {"claim_off": {"cut": 1}}}
    assert "## Planned runs not scored" in md
    for name in ("per_run", "per_question", "paired", "summary", "exit_status"):
        assert (root / "report" / f"{name}.csv").is_file()
    per_q = pd.read_csv(root / "report" / "per_question.csv")
    assert len(per_q) == 14 and set(per_q["condition"]) == {"claim_on", "claim_off"}
    summary = pd.read_csv(root / "report" / "summary.csv").set_index("outcome")
    assert summary.loc["support_share", "difference_mean"] == pytest.approx(0.35)


def test_missing_scores(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli(["report", str(tmp_path)]) == 1
    assert "run `score batch" in capsys.readouterr().out
    report = write(write_scores(tmp_path, []))
    assert report["runs"]["scored"] == 0 and not report["primary"]["computed"] and report["complete"] is True
