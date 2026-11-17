from collections import Counter

import pytest

from synth2.world import direction
from synth3.spec import load_spec
from synth3.world import MIN_PER_PAIR, ArmResult, Study, draw_studies, draw_world, pair_delta

from .conftest import good, write


def test_refuses_too_few_studies_and_names_a_pair(SPEC):
    with pytest.raises(ValueError, match=r"fewer than 3 studies: \w+\|\w+"):
        draw_studies(SPEC, draw_world(SPEC, 1), 1, count=5)


def control_pairs(studies):
    return Counter((t, m) for s in studies if s.arms[0] == "ctrl" for t in s.arms[1:] for m in s.measures)


def test_covered_pairs_get_three_studies_uncovered_get_none(SPEC):
    for seed in range(1, 11):
        w = draw_world(SPEC, seed); seen = control_pairs(draw_studies(SPEC, w, seed, 40))
        for p in SPEC.pairs:
            assert (seen[p] == 0) if p in w.uncovered else (seen[p] >= MIN_PER_PAIR)


def test_head_to_head_studies_exist_without_control(SPEC):
    studies = draw_studies(SPEC, draw_world(SPEC, 2), 2, 40)
    assert any("ctrl" not in s.arms and len(s.arms) == 2 for s in studies)


def test_lower_is_better_sign(SPEC):
    w = draw_world(SPEC, 3)
    for s in draw_studies(SPEC, w, 3, 40):
        for c in s.cells:
            if c.measure == "m2" and s.arms[0] == "ctrl":
                ctrl, a = c.results[0], c.results[1]
                raw = a.k / a.n - ctrl.k / ctrl.n
                assert pair_delta(SPEC, [c], s.arms[1], "ctrl") == pytest.approx(-raw)


def test_claims_honest_except_listed_overclaims(SPEC):
    studies = [s for seed in range(1, 6) for s in draw_studies(SPEC, draw_world(SPEC, seed), seed, 40)]
    assert any(s.overclaims for s in studies)
    for s in studies:
        for key, word in s.claims.items():
            arm, against, m = key.split("|")
            honest = direction(pair_delta(SPEC, [c for c in s.cells if c.measure == m], arm, against),
                               SPEC.measure(m).min_effect)
            assert (word == "helps" and honest != "helps") if key in s.overclaims else word == honest


def test_no_two_results_share_their_numbers_within_a_folder(SPEC):
    studies = draw_studies(SPEC, draw_world(SPEC, 4), 4, 40)
    keys = [tuple((r.k, r.n, r.mean) for r in c.results) for s in studies for c in s.cells]
    assert len(keys) == len(set(keys))


def test_attempt_changes_numbers_not_design(SPEC):
    w = draw_world(SPEC, 5)
    a, b = draw_studies(SPEC, w, 5, 40, 0), draw_studies(SPEC, w, 5, 40, 1)
    assert [(s.arms, s.measures, s.setting) for s in a] == [(s.arms, s.measures, s.setting) for s in b]
    assert [s.cells for s in a] != [s.cells for s in b]


def test_every_cell_has_every_condition_and_setting_level(SPEC):
    setting = {s.name: s.levels for s in SPEC.settings}
    for s in draw_studies(SPEC, draw_world(SPEC, 6), 6, 40):
        for c in s.cells:
            assert list(c.levels) == [cond.id for cond in SPEC.conditions]
            assert c.levels["site"] == setting[s.setting]["site"]
            assert [r.arm for r in c.results] == list(s.arms)


def test_arm_result_is_a_count_or_a_value_and_nothing_else():
    ArmResult("a", 10, k=3); ArmResult("a", 10, mean=4.2, sd=0.5)
    for bad in (dict(k=11), dict(k=-1), dict(k=3, mean=1.0, sd=0.1), dict(mean=1.0), dict(),
                dict(mean=float("nan"), sd=0.1)):
        with pytest.raises(ValueError):
            ArmResult("a", 10, **bad)


def test_cell_index_counts_from_zero_in_every_study(SPEC):
    for s in draw_studies(SPEC, draw_world(SPEC, 8), 8, 40):
        assert [c.index for c in s.cells] == list(range(len(s.cells)))


def test_numbers_that_can_only_repeat_are_refused_not_redrawn_forever(tmp_path):
    d = good()
    # every mean rounds to 1, so cells of the same n can only repeat each other
    d["measures"][2] = {**d["measures"][2], "base_value": [1.0, 1.0], "spread": 0.01, "decimals": 0}
    spec = load_spec("demo", write(tmp_path, d))
    with pytest.raises(ValueError, match=r"study S\d+, cell \d+, measure m3: 1000 redraws"):
        draw_studies(spec, draw_world(spec, 1), 1, 40)


def test_study_round_trip(SPEC):
    for s in draw_studies(SPEC, draw_world(SPEC, 7), 7, 40):
        assert Study.parse(s.json()) == s


def test_same_values_with_a_different_n_count_as_one_study_published_twice(tmp_path):
    from evidence.rules import duplicates
    d = good()
    # value measure with one decimal and a narrow range: many cells share both means whatever their n
    d["measures"][2] = {**d["measures"][2], "base_value": [10.0, 14.0], "spread": 0.1, "decimals": 1}
    spec = load_spec("demo", write(tmp_path, d))
    studies = draw_studies(spec, draw_world(spec, 1), 1, 40)
    rows = []
    for s in studies:
        pairs = [(t, "ctrl") for t in s.arms[1:]] if s.arms[0] == "ctrl" else [s.arms[:2]]
        for c in s.cells:
            if c.measure == "m3":
                by = {r.arm: r.mean for r in c.results}
                rows += [(f"{s.id}c{c.index}{a}", "m3", by[a], by[b]) for a, b in pairs]
    assert rows and duplicates(rows) == {}
