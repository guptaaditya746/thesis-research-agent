"""`evqa compare` shows the scorer's bootstrap intervals (thesis_scorer.bootstrap; its own tests are in
services/thesis-scorer)."""
from __future__ import annotations

from pathlib import Path

from evqa import compare
from evqa.tests.test_compare import _q, make_run


def test_compare_prints_the_paired_interval_and_says_when_it_holds_zero(tmp_path: Path) -> None:
    qids = [f"Q{i}" for i in range(1, 9)]
    base = [0.0, 0.5, 1.0, 0.0, 0.5, 1.0, 0.0, 0.5]
    noisy = [1.0, 0.0, 1.0, 1.0, 0.0, 0.5, 0.0, 0.5]
    steady = [min(1.0, x + 0.5) for x in base]
    runs = [make_run(tmp_path, name, "practice", 0.5, {q: _q(q, "lookup", s, 1.0) for q, s in zip(qids, sc)})
            for name, sc in (("practice-qwen", base), ("practice-noisy", noisy), ("practice-steady", steady))]
    text = compare.report(runs)
    noise = text.split("## Is the l3 difference more than noise?")[1]
    lines = [x for x in noise.splitlines() if x.startswith("- ")]
    assert "`practice-noisy-abc` minus `practice-qwen-abc`: l3 +0.0625" in lines[0]
    assert "8 questions in both" in lines[0] and "contains 0, so this difference may be noise" in lines[0]
    assert "l3 +0.3750" in lines[1] and "does not contain 0" in lines[1]
    assert "| l3 95% interval | n/a | n/a | n/a |" in text            # these eval.json files predate intervals
