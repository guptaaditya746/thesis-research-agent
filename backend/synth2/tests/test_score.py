import pytest
from synth2.corpus import Settings, build_base
from synth2.family import make_family
from synth2.score import reference_answers, score_family, summarise


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    r = tmp_path_factory.mktemp("score")
    build_base(r / "base", Settings("rag", 11, 20, "opposed", "table", exact=True))
    make_family(r / "base")
    return r


def test_the_oracle_scores_perfectly(root):
    got = score_family(root, reference_answers(root, "pooled"))
    assert got["recovers_law"] == {"hits": 5, "of": 5}
    assert got["follows_evidence"] == {"hits": 1, "of": 1}
    assert got["resists_overclaiming"] == {"hits": 1, "of": 1}
    assert got["stays_steady"] == {"hits": 2, "of": 2}
    assert got["fell_for_lumping"]["hits"] == 0 and got["invalid"] == []
    assert all(got["by_kind"].values())


def test_vote_counting_never_recovers_a_dependence(root):
    got = score_family(root, reference_answers(root, "vote"))
    assert got["recovers_law"]["hits"] < 5
    assert got["fell_for_lumping"]["hits"] == 0


def test_lumping_is_caught_as_lumping(root):
    got = score_family(root, reference_answers(root, "lumped"))
    assert got["fell_for_lumping"]["hits"] == got["fell_for_lumping"]["of"] > 0


def test_missing_and_malformed_answers_count_as_wrong(root):
    answers = reference_answers(root, "pooled")
    first, second = sorted(answers)[:2]
    del answers[first]
    answers[second] = {"verdict": "probably"}
    got = score_family(root, answers)
    assert sorted(got["invalid"]) == sorted([first, second])
    assert got["recovers_law"] == {"hits": 3, "of": 5}


def test_summarise_mean_and_spread():
    reports = [{"recovers_law": {"hits": h, "of": 6}, "follows_evidence": {"hits": 1, "of": 1},
                "resists_overclaiming": {"hits": 1, "of": 1}, "stays_steady": {"hits": 2, "of": 2},
                "fell_for_lumping": {"hits": 0, "of": 0}}
               for h in (6, 3)]
    got = summarise(reports)
    assert got["recovers_law"] == {"mean": 0.75, "stderr": pytest.approx(0.25), "n": 2}
    assert got["follows_evidence"] == {"mean": 1.0, "stderr": 0.0, "n": 2}
    assert got["fell_for_lumping"] == {"mean": 0.0, "stderr": 0.0, "n": 0}


def test_a_spun_copy_with_nothing_spun_is_not_counted(tmp_path):
    from synth2.recipe import load_recipe
    from synth2.world import draw_law
    seed = next(s for s in range(50) if not draw_law(load_recipe("rag"), s, "uniform").mirrored)
    build_base(tmp_path / "base", Settings("rag", seed, 20, "uniform", "table", exact=True))
    make_family(tmp_path / "base")
    got = score_family(tmp_path, reference_answers(tmp_path, "pooled"))
    assert got["resists_overclaiming"] == {"hits": 0, "of": 0}
    assert got["stays_steady"] == {"hits": 2, "of": 2}
