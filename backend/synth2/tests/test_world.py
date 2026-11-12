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


def test_two_subset_papers_split_on_any_condition_not_only_the_true_one():
    two, on_true, total = 0, 0, 0
    for seed in range(30):
        law = draw_law(R, seed, "opposed")
        for s in draw_studies(R, law, seed, 20):
            total += 1
            if len(s.cells) == 2:
                differs = [c for c in s.cells[0].levels if s.cells[0].levels[c] != s.cells[1].levels[c]]
                assert len(differs) == 1
                two += 1
                on_true += differs[0] == law.condition
    assert 0.4 < two / total < 0.6
    assert 0.2 < on_true / two < 0.5


def test_two_subsets_on_the_same_side_have_their_own_noise():
    law = draw_law(R, 3, "opposed")
    same_side = [s for seed in range(5) for s in draw_studies(R, law, seed, 20)
                 if len(s.cells) == 2 and s.cells[0].levels[law.condition] == s.cells[1].levels[law.condition]]
    assert same_side and all((s.cells[0].k_t, s.cells[0].k_c) != (s.cells[1].k_t, s.cells[1].k_c) for s in same_side)


def _cross_study_clashes(studies):
    """Pairs of different studies with a cell of the same treatment and control rates (3 decimals). The two
    subsets of one study may match: a split on a condition with no effect is meant to show no difference."""
    seen, clashes = {}, []
    for s in studies:
        keys = {(round(c.k_t / c.n_t, 3), round(c.k_c / c.n_c, 3)) for c in s.cells}
        clashes += [(seen[k], s.id) for k in keys if k in seen]
        seen.update({k: s.id for k in keys if k not in seen})
    return clashes


@pytest.mark.parametrize("exact", [True, False])
def test_no_two_studies_share_both_rates(exact):
    # the engine takes two results with the same treatment and control rates (3 decimals) as one study
    # published twice (evidence/rules.duplicates), so distinct studies must never share them
    for kind in LAW_KINDS:
        for seed in range(60):
            for count in (6, 20):
                studies = draw_studies(R, draw_law(R, seed, kind), seed, count, exact=exact)
                assert _cross_study_clashes(studies) == [], (kind, seed, count)


def test_seed_17_no_longer_has_lookalike_studies():
    # seed 17 drew S002 and S005 with the same rates, so the engine took S005 for a copy of S002
    assert _cross_study_clashes(draw_studies(R, draw_law(R, 17, "opposed"), 17, 6, exact=True)) == []
