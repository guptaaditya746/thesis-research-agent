"""Ground truth: seeded, effects and answers from evidence/rules.py, the effect mix as asked."""
from __future__ import annotations

import pytest

from evidence import rules
from synth import truth

SPEC = truth.default_spec()


def test_same_seed_same_studies_other_seed_other_studies() -> None:
    assert truth.generate(7, 12) == truth.generate(7, 12)
    assert truth.generate(7, 12) != truth.generate(8, 12)


def test_the_protocol_defines_the_truth() -> None:
    """Another protocol (a wider neutral band) gives other studies with the same seed; one that leaves
    no neutral band above the decoy gap is refused."""
    wide = SPEC.model_copy(update={"min_effect": 0.02})
    studies = truth.generate(5, 10, {"neutral": 1}, wide)
    assert all(s.effect.direction == "neutral" and abs(s.effect.delta) < 0.02 for s in studies)
    assert any(abs(s.effect.delta) >= 0.01 for s in studies)
    with pytest.raises(ValueError, match="neutral band"):
        truth.generate(5, 2, {"neutral": 1}, SPEC.model_copy(update={"min_effect": 0.008}))


@pytest.mark.parametrize("seed", range(1, 21))
def test_effect_is_rules_effect_on_main_pair(seed: int) -> None:
    for s in truth.generate(seed, 10):
        q = s.primary
        assert q.canonical in SPEC.metric_names and q.higher_is_better == SPEC.higher_is_better(q.canonical)
        base = s.measurement(s.condition("baseline").id, q.id, s.datasets[0])
        rag = s.measurement(s.condition("rag").id, q.id, s.datasets[0])
        assert (s.effect.treatment, s.effect.control, s.effect.metric) == (rag.id, base.id, q.id)
        assert (s.effect.direction, s.effect.delta) == rules.effect(rag.value, base.value, q.higher_is_better,
                                                                    SPEC.min_effect)
        # the second dataset shows the same direction, so either pair gives the same answer
        b2 = s.measurement(s.condition("baseline").id, q.id, s.datasets[1])
        r2 = s.measurement(s.condition("rag").id, q.id, s.datasets[1])
        assert rules.effect(r2.value, b2.value, q.higher_is_better, SPEC.min_effect)[0] == s.effect.direction
        assert rules.claim_agrees(s.claim, s.effect.direction, SPEC.claim_map)
        assert not rules.claim_agrees(s.false_claim, s.effect.direction, SPEC.claim_map)


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
    counts = {k: len(answer[k]) for k in ("supporting", "contradicting", "neutral")}
    assert answer["label"] == rules.label(counts, SPEC.table) == label
    assert sorted(answer["supporting"] + answer["contradicting"] + answer["neutral"]) == [s.study_id for s in studies]


@pytest.mark.parametrize("seed", range(1, 21))
def test_decoy_is_far_from_every_true_value_and_fits_the_false_claim(seed: int) -> None:
    """Taking a decoy for a measurement must never score as correct (evaluation tolerance 0.005)."""
    for s in truth.generate(seed, 20):
        if s.decoy is None:
            continue
        assert all(abs(s.decoy - m.value) > truth.DECOY_GAP for m in s.measurements), (s.study_id, s.decoy)
        base = s.value_of(s.effect.control)
        assert rules.claim_agrees(s.false_claim, rules.effect(s.decoy, base, s.primary.higher_is_better,
                                                             SPEC.min_effect)[0], SPEC.claim_map)


@pytest.mark.parametrize("seed", range(1, 41))
def test_true_values_of_a_study_are_more_than_the_gap_apart(seed: int) -> None:
    """A value read from the wrong cell can never match another fact by value alone (tolerance 0.005)."""
    for s in truth.generate(seed, 20):
        values = sorted(m.value for m in s.measurements)
        gaps = [b - a for a, b in zip(values, values[1:])]
        assert min(gaps) > truth.DECOY_GAP, (s.study_id, values)

# --- --hard (Tim M2 section 6-7): more experiments and an ablation per study --------------------------------

PLAIN_DIGEST = "b2ee323b93c0345ee0cd1daabf808143dd674e28e8b059f6aa3f0e41122deb18"   # repr(generate(1, 20)) on main


def test_without_hard_the_set_is_byte_identical_to_main() -> None:
    import hashlib
    assert hashlib.sha256(repr(truth.generate(1, 20)).encode()).hexdigest() == PLAIN_DIGEST
    assert truth.generate(1, 20, hard=False) == truth.generate(1, 20)


def test_hard_studies_have_more_experiments_and_ablations() -> None:
    plain, hard = truth.generate(1, 30), truth.generate(1, 30, hard=True)
    multi = [s for s in hard if len(s.experiments) >= 2]
    ablations = [c for s in hard for c in s.conditions if c not in s.main_conditions]
    assert len(multi) >= 5 and len(ablations) >= 3
    assert all(1 <= len(s.experiments) <= 3 for s in hard)
    for p, s in zip(plain, hard):
        # the main experiment is the plain study, unchanged; the effect is computed from it alone
        assert [(m.id, m.condition, m.metric, m.dataset, m.value) for m in s.measurements[:len(p.measurements)]] == \
            [(m.id, m.condition, m.metric, m.dataset, m.value) for m in p.measurements]
        assert (s.effect, s.claim, s.decoy) == (p.effect, p.claim, p.decoy)
        main = s.experiments[0]
        assert s.main_experiment == main.id == f"{s.study_id}.e1"
        assert {m.experiment for m in s.measurements[:len(p.measurements)]} == {main.id}
        assert s.find(s.condition("rag").id, s.primary.id, s.datasets[0]).id == s.effect.treatment
        extra = [c for c in s.conditions if c not in s.main_conditions]
        assert len(extra) <= 1
        for c in extra:
            assert c.role == "other" and c.label.startswith(s.condition("rag").label + " without ")
        for e in s.experiments[1:]:
            assert e.datasets == (s.datasets[0],)
            for cid in e.conditions:
                for k in s.metrics:
                    assert s.find(cid, k.id, s.datasets[0], e.id) is not None
        values = sorted([m.value for m in s.measurements] + ([s.decoy] if s.decoy is not None else []))
        assert min(b - a for a, b in zip(values, values[1:])) > truth.DECOY_GAP, s.study_id
        rel = abs(round(s.value_of(s.effect.treatment) - s.value_of(s.effect.control), 3))
        assert all(abs(m.value - rel) > truth.DECOY_GAP for m in s.measurements[len(p.measurements):])


@pytest.mark.parametrize("seed, n, missing", [(1, 30, 3), (1, 100, 6), (2, 40, 6), (3, 40, 6)])
def test_hard_missing_never_leaves_a_complete_comparison_in_another_experiment(seed: int, n: int, missing: int) -> None:
    """An undetermined (missing) study states no comparison anywhere: --missing picks only studies without
    further experiments, so no subset or ablation pair can stand in for the main one (review I4: S021)."""
    studies = truth.generate(seed, n, hard=True, missing=missing)
    gaps = [s for s in studies if s.missing]
    assert len(gaps) == missing
    for s in gaps:
        assert not s.effect.determined and len(s.experiments) == 1, s.study_id
        assert {m.experiment for m in s.measurements} == {s.main_experiment}, s.study_id


def test_hard_with_every_knob() -> None:
    studies = truth.generate(1, 30, hard=True, duplicates=3, missing=3, outliers=2, irrelevant=2)
    for s in studies:
        if s.duplicate_of:
            original = next(o for o in studies if o.study_id == s.duplicate_of)
            assert [e.name for e in s.experiments] == [e.name for e in original.experiments]
            assert all(m.experiment.startswith(s.study_id + ".") for m in s.measurements)
        if s.missing:
            assert len(s.experiments) >= 1 and s.pair(s.datasets[0]) is None
        if not s.relevant:
            assert s.experiments == ()
