"""scoring/report.py: per-question means, paired differences, BCa intervals and the primary test,
against numbers computed by hand (and scipy called directly with the same seed)."""
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


def score(qid: str, condition: str, repeat: int, share: float | None, *, attempt: int = 1, exit_status: str = "submitted",
          provisional: bool = False, f1: float = 0.5) -> dict[str, Any]:
    on = condition == "claim_on"
    facts = 0 if share is None else 4
    return {
        "run_id": f"{qid}-{condition}-r{repeat}-a{attempt}", "qid": qid, "condition": condition, "repeat": repeat,
        "attempt": attempt, "seed": 1000 + repeat, "exit_status": exit_status, "provisional": provisional,
        "rows": {"tp": 1, "fp": 1, "fn": 1, "precision": 0.5, "recall": 0.5, "f1": f1},
        "facts": {level: {"precision": f1, "recall": f1, "f1": f1} for level in ("strict", "normalised", "soft")},
        "vital_recall": 1.0, "judged_precision": {"precision": None},
        "support": {"facts": facts, "support_share": share, "unsourced_share": 0.0 if on else 0.25},
        "cost": {"tokens": 1000 if on else 1500, "tokens_without_attach": 1000 if on else 1200,
                 "seconds": 60.0 if on else 90.0, "seconds_without_attach": 60.0 if on else 70.0},
    }


def write_scores(root: Path, scores: list[dict[str, Any]]) -> Path:
    (root / "report").mkdir(parents=True, exist_ok=True)
    (root / "report" / "scores.jsonl").write_text("".join(json.dumps(s) + "\n" for s in scores), encoding="utf-8")
    return root


def sample(**changes: Any) -> list[dict[str, Any]]:
    out = []
    for qid, (on, off) in SHARES.items():
        for r in (1, 2):
            out.append(score(qid, "claim_on", r, on[r - 1]))
            out.append(score(qid, "claim_off", r, off[r - 1], exit_status="budget" if (qid, r) == ("q02", 2) else "submitted"))
    # An earlier, cut attempt at q01 claim_on r1: the later attempt counts.
    out.append(score("q01", "claim_on", 1, 0.0, attempt=0))
    return out


def test_report_numbers_against_hand_computed(tmp_path: Path) -> None:
    report = build(write_scores(tmp_path, sample()))["report"]
    per_q = {(r["qid"], r["condition"]): r for r in report["per_question"]}
    assert per_q[("q04", "claim_on")]["support_share"] == pytest.approx(0.5) and per_q[("q04", "claim_on")]["runs"] == 2
    assert per_q[("q07", "claim_off")]["support_share"] is None  # no answer facts in either repeat
    assert [r["qid"] for r in report["paired"]] == [f"q0{n}" for n in range(1, 8)]
    q01 = next(r for r in report["paired"] if r["qid"] == "q01")["support_share"]
    assert (q01["claim_on"], q01["claim_off"], q01["difference"]) == pytest.approx((0.7, 0.4, 0.3))

    summary = report["summary"]["support_share"]
    assert summary["claim_on"]["mean"] == pytest.approx((ON.sum() + 0.5) / 7) and summary["claim_on"]["n"] == 7
    assert summary["claim_off"]["mean"] == pytest.approx(OFF.mean()) and summary["claim_off"]["n"] == 6
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

    tokens = report["summary"]["tokens"]["difference"]
    assert (tokens["mean"], tokens["low"], tokens["high"], tokens["method"]) == (-500.0, -500.0, -500.0,
                                                                                 "degenerate (all equal)")
    assert report["summary"]["tokens_without_attach"]["difference"]["mean"] == -200.0
    assert report["summary"]["seconds_without_attach"]["claim_off"]["mean"] == 70.0
    assert report["runs"]["scored"] == 28  # the earlier attempt is dropped
    assert report["runs"]["by_exit_status"] == {"claim_off": {"budget": 1, "submitted": 13}, "claim_on": {"submitted": 14}}
    assert report["provisional"] is False and report["secondary"][0] == "fact_precision"


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
    assert "PROVISIONAL" in out
    report = json.loads((root / "report" / "report.json").read_text(encoding="utf-8"))
    assert report["provisional"] is True and report["provisional_questions"] == ["q01"]
    md = (root / "report" / "report.md").read_text(encoding="utf-8")
    assert "**PROVISIONAL" in md and "## Primary outcome (pre-registered)" in md
    assert "| Support share (judge) " in md and "0.350 [" in md and "p = 0.03125 (significant" in md
    assert "| q04        | 2/2           | 0.500        | 0.150         | 0.350" in md  # per question, formatted
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
    assert report["runs"]["scored"] == 0 and not report["primary"]["computed"]
