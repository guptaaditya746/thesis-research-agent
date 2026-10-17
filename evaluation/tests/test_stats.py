"""The bootstrap intervals (evaluation/stats.py): degenerate samples never raise, bounds are sane and
deterministic, the paired difference has the right sign."""
from __future__ import annotations

import warnings

import pytest

from evaluation import stats


@pytest.mark.parametrize("rows", [[], [(1,)], [(1,), (1,), (1,)], [(0,), (0,)], [(0.5,)]])
def test_degenerate_means_give_the_point_with_null_bounds(rows: list[tuple[float, ...]]) -> None:
    out = stats.bootstrap_mean(v for (v,) in rows)
    if not rows:
        assert out == {"point": None, "low": None, "high": None}
    else:
        assert out["point"] == pytest.approx(sum(v for (v,) in rows) / len(rows))
        assert out["low"] is None and out["high"] is None


def test_f1_one_on_every_paper_has_no_spread() -> None:
    rows = [(9, 9, 9), (6, 6, 6), (3, 3, 3)]  # rows differ, every resample's F1 is 1
    out = stats.bootstrap_f1(rows)
    assert out == {"point": 1.0, "low": None, "high": None}


def test_f1_with_an_imperfect_paper_has_bounds_around_the_point() -> None:
    rows = [(9, 9, 9), (6, 6, 6), (3, 6, 6), (2, 4, 4), (5, 5, 5)]
    out = stats.bootstrap_f1(rows)
    assert out["point"] == pytest.approx(stats.micro_f1(*map(lambda i: [r[i] for r in rows], (0, 1, 2))))
    assert out["low"] is not None and out["high"] is not None
    assert 0.0 <= out["low"] <= out["point"] <= out["high"] <= 1.0


def test_accuracy_bounds_are_within_unit_interval_and_deterministic() -> None:
    values = [1, 1, 1, 0, 1, 0, 1, 1, 0, 1]
    a, b = stats.bootstrap_mean(values), stats.bootstrap_mean(values)
    assert a == b and a["point"] == 0.7
    assert 0.0 <= a["low"] < 0.7 < a["high"] <= 1.0


def test_paired_difference_has_the_right_sign() -> None:
    engine = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    baseline = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
    diffs = [e - b for e, b in zip(engine, baseline)]
    out = stats.bootstrap_mean(diffs)
    assert out["point"] == 0.5 and out["low"] > 0.0 and out["high"] <= 1.0
    reverse = stats.bootstrap_mean([-d for d in diffs])
    assert reverse["point"] == -0.5 and reverse["high"] < 0.0


def test_a_bootstrap_never_warns_or_raises() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        stats.bootstrap_mean([0, 0, 0, 1])              # a near-constant jackknife (BCa falls back)
        stats.bootstrap_ratio([(0, 0), (0, 0), (1, 0)])  # zero denominators
        stats.bootstrap_f1([(0, 0, 0), (0, 0, 3)])       # nothing found anywhere
    assert stats.bootstrap_ratio([(1, 2), (2, 4), (0, 1)])["point"] == pytest.approx(3 / 7)


def test_interval_text_format() -> None:
    assert stats.interval_text(0.8123, 0.7449, 0.8801) == "0.812 [0.74, 0.88]"
    assert stats.interval_text(1.0, None, None) == "1.000 [n/a]"
    assert stats.interval_text(None, None, None) == "-"
    assert stats.interval_row({"point": 0.5, "low": 0.1, "high": 0.9}, system="x") == {
        "system": "x", "point": 0.5, "low": 0.1, "high": 0.9}
