"""Ground truth: seeded, effects and answers from evidence/rules.py, the effect mix as asked."""
from __future__ import annotations

import pytest

from evidence import rules
from synth import truth


def test_same_seed_same_studies_other_seed_other_studies() -> None:
    assert truth.generate(7, 12) == truth.generate(7, 12)
    assert truth.generate(7, 12) != truth.generate(8, 12)


@pytest.mark.parametrize("seed", range(1, 21))
def test_effect_is_rules_effect_on_main_pair(seed: int) -> None:
    for s in truth.generate(seed, 10):
        q = s.primary
        assert q.canonical in rules.METRICS and q.higher_is_better == rules.METRICS[q.canonical]
        base = s.measurement(s.condition("baseline").id, q.id, s.datasets[0])
        rag = s.measurement(s.condition("rag").id, q.id, s.datasets[0])
        assert (s.effect.rag, s.effect.baseline, s.effect.metric) == (rag.id, base.id, q.id)
        assert (s.effect.direction, s.effect.delta) == rules.effect(rag.value, base.value, q.higher_is_better)
        # the second dataset shows the same direction, so either pair gives the same answer
        b2 = s.measurement(s.condition("baseline").id, q.id, s.datasets[1])
        r2 = s.measurement(s.condition("rag").id, q.id, s.datasets[1])
        assert rules.effect(r2.value, b2.value, q.higher_is_better)[0] == s.effect.direction
        assert rules.claim_agrees(s.claim, s.effect.direction)
        assert not rules.claim_agrees(s.false_claim, s.effect.direction)


@pytest.mark.parametrize("seed", range(1, 21))
def test_study_shape_and_values(seed: int) -> None:
    for s in truth.generate(seed, 10):
        roles = [c.role for c in s.conditions]
        assert roles[:2] == ["baseline", "rag"] and set(roles[2:]) <= {"other"} and len(roles) <= 4
        assert [m.canonical for m in s.metrics][1:] and all(m.canonical == "other" for m in s.metrics[1:])
        assert len(s.datasets) == 2
        assert len(s.measurements) == len(s.conditions) * len(s.metrics) * 2
        values = [m.value for m in s.measurements]
        assert len(set(values)) == len(values), "values are distinct within a study"
        for m in s.measurements:
            unit = next(k.unit for k in s.metrics if k.id == m.metric)
            if unit == "fraction":
                assert 0.05 <= m.value <= 0.95 and round(m.value * 1000) % 10
        if s.decoy is not None:
            assert s.decoy not in values and s.index % 2


def test_effect_counts_largest_remainder() -> None:
    assert truth.effect_counts(6, {"supports": 0.6, "contradicts": 0.2, "neutral": 0.2}) == {
        "supports": 4, "contradicts": 1, "neutral": 1}
    assert truth.effect_counts(20, {"supports": 0.6, "contradicts": 0.2, "neutral": 0.2}) == {
        "supports": 12, "contradicts": 4, "neutral": 4}
    assert truth.effect_counts(5, {"contradicts": 1}) == {"supports": 0, "contradicts": 5, "neutral": 0}
    with pytest.raises(ValueError):
        truth.effect_counts(5, {"supports": 0})


@pytest.mark.parametrize(("mix", "label"), [
    ({"supports": 1}, "supported"), ({"contradicts": 1}, "refuted"), ({"neutral": 1}, "no_effect"),
    ({"supports": 0.5, "contradicts": 0.5}, "mixed"), ({"supports": 0.5, "neutral": 0.5}, "supported"),
])
def test_every_answer_label_can_be_made(mix: dict[str, float], label: str) -> None:
    studies = truth.generate(3, 8, mix)
    answer = truth.answer(studies)
    counts = [len(answer[k]) for k in ("supporting", "contradicting", "neutral")]
    assert answer["label"] == rules.label(*counts) == label
    assert sorted(answer["supporting"] + answer["contradicting"] + answer["neutral"]) == [s.study_id for s in studies]


@pytest.mark.parametrize("seed", range(1, 21))
def test_decoy_is_far_from_every_true_value_and_fits_the_false_claim(seed: int) -> None:
    """Taking a decoy for a measurement must never score as correct (evaluation tolerance 0.005)."""
    for s in truth.generate(seed, 20):
        if s.decoy is None:
            continue
        assert all(abs(s.decoy - m.value) > truth.DECOY_GAP for m in s.measurements), (s.study_id, s.decoy)
        base = s.value_of(s.effect.baseline)
        assert rules.claim_agrees(s.false_claim, rules.effect(s.decoy, base, s.primary.higher_is_better)[0])