import pytest
from synth2.recipe import load_recipe
from synth2.world import LAW_KINDS, Cell, Study, direction, draw_law, draw_studies, study_delta

R = load_recipe("rag")


def test_law_shape_for_each_kind():
    for kind, (first, second) in LAW_KINDS.items():
        law = draw_law(R, 7, kind)
        levels = [lv.id for c in R.conditions if c.id == law.condition for lv in c.levels]
        assert set(law.effects) == set(levels)
        got = sorted(direction(e, R.min_effect) for e in law.effects.values())
        want = sorted([first, second])
        if law.mirrored:
            want = sorted({"helps": "hurts", "hurts": "helps", "no_effect": "no_effect"}[d] for d in want)
        assert got == want
        assert all(e == 0.0 or 0.08 <= abs(e) <= 0.15 for e in law.effects.values())


def test_seeds_vary_the_true_condition_and_the_mirror():
    laws = [draw_law(R, s, "opposed") for s in range(40)]
    assert {l.condition for l in laws} == {"fact_rarity", "model_size", "question_length"}
    assert {l.mirrored for l in laws} == {True, False}


def test_studies_are_deterministic_and_in_range():
    law = draw_law(R, 3, "opposed")
    a = draw_studies(R, law, 3, 20)
    assert a == draw_studies(R, law, 3, 20)
    assert [s.id for s in a] == [f"S{i:03d}" for i in range(1, 21)]
    assert len({s.label for s in a}) == 20
    for s in a:
        assert 1 <= len(s.cells) <= 2
        for c in s.cells:
            assert set(c.levels) == {"fact_rarity", "model_size", "question_length"}
            assert 200 <= c.n_t <= 1000 and c.n_t % 50 == 0 and c.n_t == c.n_c
    assert {len(s.cells) for s in a} == {1, 2}


def test_exact_counts_follow_the_law():
    law = draw_law(R, 3, "opposed")
    for s in draw_studies(R, law, 3, 20, exact=True):
        for c in s.cells:
            effect = law.effects[c.levels[law.condition]]
            assert abs((c.k_t / c.n_t - c.k_c / c.n_c) - effect) < 0.006


def test_untested_level_has_no_cell():
    law = draw_law(R, 3, "opposed")
    gone = sorted(law.effects)[0]
    cells = [c for s in draw_studies(R, law, 3, 20, untested=gone) for c in s.cells]
    assert cells and all(c.levels[law.condition] != gone for c in cells)


def test_redraw_level_changes_only_that_side():
    law = draw_law(R, 3, "opposed")
    side = sorted(law.effects)[1]
    base, again = draw_studies(R, law, 3, 20), draw_studies(R, law, 3, 20, noise_seed=1, redraw_level=side)
    for b, a in zip(base, again):
        for cb, ca in zip(b.cells, a.cells):
            if cb.levels[law.condition] != side:
                assert cb == ca
    assert base != again


def test_base_claims_are_honest():
    law = draw_law(R, 3, "opposed")
    for s in draw_studies(R, law, 3, 20):
        assert s.claim == direction(study_delta(s), R.min_effect)
        assert s.overclaims is False


def test_cell_refuses_impossible_counts():
    levels = {"fact_rarity": "rare", "model_size": "small", "question_length": "short"}
    with pytest.raises(ValueError):
        Cell(levels, n_t=100, k_t=101, n_c=100, k_c=50)
    with pytest.raises(ValueError):
        Cell(levels, n_t=0, k_t=0, n_c=100, k_c=50)


def test_study_round_trip_and_bad_cell_names_the_study():
    s = draw_studies(R, draw_law(R, 3, "opposed"), 3, 1)[0]
    assert Study.parse(s.json()) == s
    bad = s.json()
    bad["cells"][0]["k_t"] = bad["cells"][0]["n_t"] + 1
    with pytest.raises(ValueError, match="S001"):
        Study.parse(bad)
