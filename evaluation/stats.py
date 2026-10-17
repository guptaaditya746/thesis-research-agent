"""Bootstrap confidence intervals for the report (docs/evidence-system.md F4, intervals).

Our addition (the supervisor's design names no statistics; STATE.md §7 "Statistics"). Rules:

1. An interval is a 95 % BCa bootstrap interval (scipy.stats.bootstrap, method "BCa", RESAMPLES resamples,
   a numpy generator seeded with `seed`, 0 by default), so the same rows give the same bounds every time.
2. Resampling is paired over rows: a row is one paper (extraction) or one study (synthesis) with every
   number the statistic needs (matched, items, facts; correct; engine correct minus baseline correct), and
   one resample draws whole rows, so a ratio's numerator and denominator always come from the same papers.
3. The point value is the statistic over the whole sample, never the mean of the bootstrap distribution.
4. Degenerate input gives the point value with null bounds: fewer than two rows, every row equal, or a
   bootstrap distribution with no spread (every resample gives the same statistic, e.g. F1 = 1 on every
   paper).
5. When BCa cannot be computed (scipy warns and returns nan, e.g. a constant jackknife), the percentile
   method is used instead; when that gives no finite bounds either, the bounds are null. A bootstrap never
   raises and never lets a scipy warning through to the caller.
"""
from __future__ import annotations

import warnings
from typing import Any, Callable, Iterable, Sequence

import numpy as np
from scipy import stats

RESAMPLES = 2000
CONFIDENCE = 0.95
METHODS = ("BCa", "percentile")

Interval = dict[str, float | None]
Statistic = Callable[..., float]


def _bounds(stat: Statistic, columns: list[np.ndarray], method: str, seed: int, n: int) -> tuple[float, float] | None:
    rng = np.random.default_rng(seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            result = stats.bootstrap(columns, stat, paired=True, vectorized=False, n_resamples=n,
                                     confidence_level=CONFIDENCE, method=method, random_state=rng)
        except Exception:  # noqa: BLE001 - an interval is never worth failing a report
            return None
    dist = np.asarray(result.bootstrap_distribution, dtype=float)
    if dist.size and np.nanmax(dist) == np.nanmin(dist):
        return None  # rule 4: no spread
    low, high = float(result.confidence_interval.low), float(result.confidence_interval.high)
    if not (np.isfinite(low) and np.isfinite(high)):
        return None
    return low, high


def bootstrap(stat: Statistic, rows: Iterable[Sequence[float]], *, seed: int = 0, n: int = RESAMPLES) -> Interval:
    """{point, low, high} of `stat(*columns)` over the rows, resampling rows (rules 1-5)."""
    rows = [tuple(float(v) for v in r) for r in rows]
    if not rows:
        return {"point": None, "low": None, "high": None}
    columns = [np.asarray(c, dtype=float) for c in zip(*rows)]
    point = float(stat(*columns))
    if len(rows) < 2 or all(r == rows[0] for r in rows):
        return {"point": point, "low": None, "high": None}
    for method in METHODS:
        bounds = _bounds(stat, columns, method, seed, n)
        if bounds is not None:
            return {"point": point, "low": bounds[0], "high": bounds[1]}
    return {"point": point, "low": None, "high": None}


def mean(values: np.ndarray) -> float:
    return float(np.mean(values))


def ratio(numerators: np.ndarray, denominators: np.ndarray) -> float:
    total = float(np.sum(denominators))
    return float(np.sum(numerators)) / total if total else 0.0


def micro_f1(matched: np.ndarray, items: np.ndarray, facts: np.ndarray) -> float:
    m, i, f = float(np.sum(matched)), float(np.sum(items)), float(np.sum(facts))
    precision, recall = (m / i if i else 0.0), (m / f if f else 0.0)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def bootstrap_mean(values: Iterable[float], *, seed: int = 0, n: int = RESAMPLES) -> Interval:
    """Interval of the mean (an accuracy from 0/1 rows, a paired difference from -1/0/1 rows)."""
    return bootstrap(mean, [(v,) for v in values], seed=seed, n=n)


def bootstrap_ratio(pairs: Iterable[tuple[float, float]], *, seed: int = 0, n: int = RESAMPLES) -> Interval:
    """Interval of sum(numerators) / sum(denominators), rows (numerator, denominator)."""
    return bootstrap(ratio, pairs, seed=seed, n=n)


def bootstrap_f1(rows: Iterable[tuple[int, int, int]], *, seed: int = 0, n: int = RESAMPLES) -> Interval:
    """Interval of the micro F1 of rows (matched, items, facts), one row per paper."""
    return bootstrap(micro_f1, rows, seed=seed, n=n)


def interval_row(interval: Interval, **keys: Any) -> dict[str, Any]:
    return {**keys, "point": interval["point"], "low": interval["low"], "high": interval["high"]}


def interval_text(point: float | None, low: float | None, high: float | None) -> str:
    """`0.812 [0.74, 0.88]` for the Markdown tables; `0.812 [n/a]` when the bounds are null (rule 4)."""
    if point is None:
        return "-"
    if low is None or high is None:
        return f"{point:.3f} [n/a]"
    return f"{point:.3f} [{low:.2f}, {high:.2f}]"
