import pytest

from synth3.reference import draw_supported_studies, reference_facts
from synth3.world import draw_world


def test_supported_studies_match_every_covered_law(SPEC):
    for seed in range(1, 6):
        w = draw_world(SPEC, seed)
        studies, _ = draw_supported_studies(SPEC, w, seed, 40)
        facts = reference_facts(SPEC, w, studies)
        assert all(p["matches_law"] for p in facts["pairs"] if not p["uncovered"])


def test_uncovered_pair_is_insufficient_and_marked(SPEC):
    seed = next(s for s in range(1, 50) if draw_world(SPEC, s).uncovered)
    w = draw_world(SPEC, seed); studies, _ = draw_supported_studies(SPEC, w, seed, 40)
    p = next(p for p in reference_facts(SPEC, w, studies)["pairs"] if p["uncovered"])
    assert p["answer"]["verdict"] == "insufficient"


def test_depends_gives_the_reason_in_words(SPEC):
    w = draw_world(SPEC, 1); studies, _ = draw_supported_studies(SPEC, w, 1, 40)
    for p in reference_facts(SPEC, w, studies)["pairs"]:
        if p["answer"]["verdict"] == "depends":
            assert p["reason"] == next(c.name for c in SPEC.conditions if c.id == p["answer"]["condition"])


def test_groups_partition_and_overclaims_are_listed(SPEC):
    w = draw_world(SPEC, 2); studies, _ = draw_supported_studies(SPEC, w, 2, 40)
    for p in reference_facts(SPEC, w, studies)["pairs"]:
        assert sorted(p["supporting"] + p["contradicting"] + p["neutral"]) == sorted(p["studies"])
        assert set(p["overclaimed_in"]) <= set(p["studies"])


def test_gate_refuses_when_noise_cannot_be_beaten(SPEC):
    tiny = SPEC.model_copy(update={"n_range": (50, 50), "n_step": 50})
    with pytest.raises(ValueError, match="never matched"):
        draw_supported_studies(tiny, draw_world(tiny, 1), 1, 40)
