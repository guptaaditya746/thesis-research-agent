"""Bootstrap intervals: deterministic, sensible on small inputs, written into eval.json, shown by `evqa compare`."""
from __future__ import annotations

from pathlib import Path

from evqa import compare
from evqa.eval import bootstrap, prism
from evqa.tests.test_compare import _q, make_run


def test_mean_interval_is_deterministic_and_holds_the_mean() -> None:
    xs = [0.0, 1.0, 1.0, 0.5, 0.0, 1.0, 0.25, 0.75]
    iv = bootstrap.mean_interval(xs)
    assert iv == bootstrap.mean_interval(xs)                     # fixed seed: same interval every time
    assert 0.0 <= iv[0] < sum(xs) / len(xs) < iv[1] <= 1.0
    assert bootstrap.mean_interval([0.4, 0.4, None]) == [0.4, 0.4]   # no spread, n/a left out
    assert bootstrap.mean_interval([None]) is None and bootstrap.mean_interval([]) is None
    assert bootstrap.mean_interval(xs * 10)[1] - bootstrap.mean_interval(xs * 10)[0] < iv[1] - iv[0]   # more questions, narrower


def test_paired_interval_sees_a_steady_gain_and_a_noisy_one() -> None:
    a = [0.0, 0.5, 1.0, 0.0, 0.5, 1.0, 0.0, 0.5]
    steady = [x + 0.1 for x in a]                                   # every question up by 0.1
    assert bootstrap.paired_interval(a, steady) == [0.1, 0.1] and not bootstrap.contains_zero([0.1, 0.1])
    noisy = [1.0, 0.0, 1.0, 1.0, 0.0, 0.5, 0.0, 0.5]                # up on some, down on others
    assert bootstrap.contains_zero(bootstrap.paired_interval(a, noisy))


def test_run_intervals_cover_the_headline_totals() -> None:
    def q(l3: float, answerable: bool = True, hall: bool = False) -> dict:
        return {"answerable": answerable, "l0": 1.0 if answerable else None, "l1": 0.5 if answerable else None,
                "l2": {"recall": 0.5, "precision": 1.0, "name_ok": 1.0} if answerable else
                      {"recall": None, "precision": None, "name_ok": None},
                "l3": {"score": l3, "hallucination": hall}, "advisor": {"score": 1.0}}
    iv = prism.run_intervals([q(1.0), q(0.0), q(1.0), q(0.0, False, True), q(1.0, False)])
    assert iv["method"] == bootstrap.METHOD
    assert iv["l1"] == [0.5, 0.5] and iv["advisor"] == [1.0, 1.0]
    assert iv["l3"][0] < 2 / 3 < iv["l3"][1]                         # answerable questions only
    assert iv["not_reported_accuracy"][0] <= 0.5 <= iv["not_reported_accuracy"][1]
    assert set(iv) == {"method", "l0", "l1", "l2_recall", "l2_precision", "l2_name_ok", "l3", "advisor",
                       "not_reported_accuracy", "not_reported_hallucination", "l1_paper", "l2_complete",
                       "l2_complete_upper"}


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
