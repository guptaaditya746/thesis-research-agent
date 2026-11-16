import pytest

from synth3.world import KINDS, PairLaw, World, describe, draw_world, load_world, save_world


def test_same_seed_same_world(SPEC):
    assert draw_world(SPEC, 3).json() == draw_world(SPEC, 3).json()


def test_one_law_per_pair_and_never_approved_when_drawn(SPEC):
    w = draw_world(SPEC, 1)
    assert [(l.treatment, l.measure) for l in w.laws] == SPEC.pairs and w.approved is False


def test_every_world_has_a_law_that_depends(SPEC):
    assert all(any(l.kind in ("one_sided", "opposed") for l in draw_world(SPEC, s).laws) for s in range(1, 30))


def test_kinds_and_setting_conditions_occur_across_seeds(SPEC):
    laws = [l for s in range(1, 11) for l in draw_world(SPEC, s).laws]
    assert {l.kind for l in laws} == set(KINDS) and any(l.condition == "site" for l in laws)


def test_uncovered_pairs_occur_and_never_the_only_depends_law(SPEC):
    worlds = [draw_world(SPEC, s) for s in range(1, 21)]
    assert any(w.uncovered for w in worlds)
    for w in worlds:
        covered = [l for l in w.laws if (l.treatment, l.measure) not in w.uncovered]
        assert any(l.kind in ("one_sided", "opposed") for l in covered)


def test_law_answer_for_none_is_no_effect(SPEC):
    assert PairLaw("a", "m1", "none", None, {}).answer(0.01) == ("no_effect", None, {})


def test_round_trip_and_edits_are_checked(SPEC, tmp_path):
    w = draw_world(SPEC, 4)
    save_world(tmp_path / "w.json", w)
    assert load_world(tmp_path / "w.json", SPEC) == w
    bad = w.json(); bad["laws"][0] = {**bad["laws"][0], "kind": "none", "effects": {"young": 0.1}}
    with pytest.raises(ValueError, match="kind"):
        World.parse(bad, SPEC)


def test_describe_names_every_pair_in_words(SPEC):
    text = describe(draw_world(SPEC, 2), SPEC)
    assert all(SPEC.measure(m).name in text for _, m in SPEC.pairs) and "ctrl" not in text


def test_answers_match_kinds_across_seeds(SPEC):
    for s in range(1, 21):
        for l in draw_world(SPEC, s).laws:
            word, cond, sides = l.answer(SPEC.measure(l.measure).min_effect)
            assert (word == "depends") == (l.kind in ("one_sided", "opposed"))
            assert (cond, sides == {}) == ((None, True) if word != "depends" else (l.condition, False))
            assert (word == "no_effect") == (l.kind == "none")


def test_parse_refuses_named_problems(SPEC):
    good = draw_world(SPEC, 4).json()

    def edited(**kw):
        return {**good, **kw}

    with pytest.raises(ValueError, match="spec_sha256"):
        World.parse(edited(spec_sha256="x"), SPEC)
    with pytest.raises(ValueError, match="missing"):
        World.parse(edited(laws=good["laws"][1:]), SPEC)
    with pytest.raises(ValueError, match="doubled"):
        World.parse(edited(laws=good["laws"] + good["laws"][:1]), SPEC)
    with pytest.raises(ValueError, match="not a pair"):
        World.parse(edited(uncovered=[["ctrl", "m1"]]), SPEC)
    law = next(l for l in good["laws"] if l["kind"] != "none")
    with pytest.raises(ValueError, match="condition"):
        World.parse(edited(laws=[{**law, "condition": "nope"} if l is law else l for l in good["laws"]]), SPEC)
    with pytest.raises(ValueError, match="level"):
        World.parse(edited(laws=[{**law, "effects": {"zzz": 0.1}} if l is law else l for l in good["laws"]]), SPEC)
