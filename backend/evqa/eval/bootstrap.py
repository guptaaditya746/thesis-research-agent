"""Percentile bootstrap intervals over questions: how far a score could move if the run had drawn other questions.

With 22 or 78 questions a difference of 0.01-0.05 can be chance. Each interval resamples the questions with
replacement (RESAMPLES times, fixed SEED, so the same scores give the same interval), takes the mean of each
resample, and keeps the middle 95% of those means. Pure Python (random), no numpy.

    mean_interval([0.5, 1.0, 0.0])          -> [lo, hi] for the mean score
    paired_interval(a, b)                   -> [lo, hi] for mean(b - a) over the same questions
"""
from __future__ import annotations

import math
import random

RESAMPLES = 2000
SEED = 0
LEVEL = 0.95
METHOD = f"percentile bootstrap over questions, {RESAMPLES} resamples, seed {SEED}, {LEVEL:.0%} interval"


def mean_interval(values: list[float | None], resamples: int = RESAMPLES, seed: int = SEED,
                  level: float = LEVEL) -> list[float] | None:
    """Interval for the mean of the values that apply (None = n/a is left out, as in prism._mean); None when
    none applies."""
    xs = [float(x) for x in values if x is not None]
    if not xs:
        return None
    rng, n = random.Random(seed), len(xs)
    means = sorted(sum(rng.choices(xs, k=n)) / n for _ in range(resamples))
    tail = (1 - level) / 2
    lo = means[max(0, math.floor(tail * resamples))]
    hi = means[min(resamples - 1, math.ceil((1 - tail) * resamples) - 1)]
    return [round(lo, 4), round(hi, 4)]


def paired_interval(a: list[float], b: list[float], resamples: int = RESAMPLES, seed: int = SEED,
                    level: float = LEVEL) -> list[float] | None:
    """Interval for mean(b) - mean(a) when a[i] and b[i] are the same question in two runs: resampling the
    per-question differences keeps each question's two scores together (paired bootstrap)."""
    if len(a) != len(b):
        raise ValueError("paired scores need the same questions in the same order")
    return mean_interval([y - x for x, y in zip(a, b, strict=True)], resamples, seed, level)


def contains_zero(iv: list[float] | None) -> bool:
    return iv is not None and iv[0] <= 0 <= iv[1]
