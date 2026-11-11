import pytest
from synth2.conclude import Answer, lumped, pooled, vote
from synth2.recipe import load_recipe
from synth2.world import Cell, Study

R = load_recipe("rag")


def study(i, rarity, size, length, k_t, k_c, dup=None):
    cell = Cell({"fact_rarity": rarity, "model_size": size, "question_length": length}, 500, k_t, 500, k_c)
    return Study(f"S{i:03d}", f"A{i} et al. (2024)", "FactProbe", (cell,), "helps", False, dup)


FOUR = [study(1, "rare", "small", "short", 400, 300), study(2, "rare", "large", "long", 400, 300),
        study(3, "common", "small", "long", 300, 350), study(4, "common", "large", "short", 300, 350)]


def test_pooled_finds_the_condition_that_matters():
    assert pooled(FOUR, R) == Answer("depends", "fact_rarity", {"rare": "helps", "common": "hurts"}, ())


def test_lumping_and_voting_miss_it():
    assert lumped(FOUR, R) == Answer("helps", None, {}, ())
    assert vote(FOUR, R) == Answer("mixed", None, {}, ())


def test_untested_side_is_reported_not_guessed():
    assert pooled(FOUR[:2], R) == Answer("helps", None, {}, ("fact_rarity.common",))


def test_no_studies_is_insufficient_with_every_level_untested():
    got = pooled([], R)
    assert got.verdict == "insufficient" and len(got.untested) == 6
    assert vote([], R).verdict == "insufficient"


def test_a_small_gap_is_not_a_dependence():
    near = [study(1, "rare", "small", "short", 330, 320), study(2, "common", "large", "long", 320, 330)]
    assert pooled(near, R).verdict == "no_effect"


def test_duplicates_are_not_counted_twice():
    assert pooled(FOUR + [study(5, "rare", "small", "short", 400, 300, dup="S001")], R) == pooled(FOUR, R)
    assert vote(FOUR + [study(5, "rare", "small", "short", 400, 300, dup="S001")], R) == vote(FOUR, R)


def test_answer_round_trip_and_refusals():
    a = pooled(FOUR, R)
    assert Answer.parse(a.json()) == a
    for bad in ({"verdict": "maybe", "condition": None, "sides": {}, "untested": []},
                {"verdict": "depends", "condition": None, "sides": {}, "untested": []},
                {"verdict": "helps", "condition": None, "sides": {"rare": "great"}, "untested": []},
                {"verdict": "helps"}, "helps", None):
        with pytest.raises(ValueError):
            Answer.parse(bad)
