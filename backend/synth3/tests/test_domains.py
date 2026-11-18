import pytest

from synth3.realspec import load_real_spec
from synth3.spec import SPECS, load_spec
from synth3.world import MIN_PER_PAIR


def test_medicine_spec_loads_and_fits_forty_studies():
    spec = load_spec("medicine")
    assert len(spec.pairs) * MIN_PER_PAIR <= 40 * (1 - spec.head_to_head_rate)
    assert {m.kind for m in spec.measures} == {"count", "value"}
    assert any(not m.higher_is_better for m in spec.measures) and any(c.from_setting for c in spec.conditions)


@pytest.mark.parametrize("domain", ["law", "materials", "rag"])
def test_domain_specs_load_and_fit_forty_studies(domain):
    live = (SPECS / f"{domain}.yaml").exists()      # true once Aditya approves and moves the draft
    spec = load_spec(domain, SPECS if live else SPECS / "drafts")
    assert len(spec.pairs) * MIN_PER_PAIR <= 40 * (1 - spec.head_to_head_rate)
    assert {m.kind for m in spec.measures} == {"count", "value"} and len(spec.measures) >= 3
    assert any(not m.higher_is_better for m in spec.measures) and any(c.from_setting for c in spec.conditions)
    assert load_real_spec(domain).domain == domain


def test_no_two_comparisons_in_a_medicine_folder_share_the_engines_duplicate_key():
    from evidence.rules import duplicates
    from synth3.reference import draw_supported_studies
    from synth3.world import load_world
    from repo_paths import DATA
    spec = load_spec("medicine")
    for seed in range(1, 6):
        world = load_world(DATA / "synth3" / "worlds" / "medicine" / f"s{seed}.json", spec)
        studies, _ = draw_supported_studies(spec, world, seed, 40)
        rows = []
        for s in studies:
            pairs = [(t, spec.control.id) for t in s.arms[1:]] if s.arms[0] == spec.control.id else [s.arms[:2]]
            for c in s.cells:
                for arm, against in pairs:
                    a, b = ({r.arm: r for r in c.results}[x] for x in (arm, against))
                    v = (lambda r: r.k / r.n if r.mean is None else r.mean)
                    rows.append((f"{s.id}c{c.index}{arm}", c.measure, v(a), v(b)))
        assert duplicates(rows) == {}, f"seed {seed}"


@pytest.mark.parametrize("domain, phrases", [
    ("medicine", ["a sham procedure", "Renal Denervation vs Sham", "sham-controlled trials", "standard of care",
                  "the standard-of-care arm", "on top of SoC alone", "HOC: -15.7 vs. PLB: -4.3 mmHg",
                  "PBO group", "vehicle-treated rats", "the comparator group", "an active-control trial",
                  "a double blind, active control, 3-parallel group", "versus no intervention",
                  "followed by no intervention"]),
    ("materials", ["the as-cast samples", "as cast alloy", "as-received plates", "untreated specimens",
                   "the reference samples"]),
    ("rag", ["a closed-book setting", "the no-retrieval baseline", "zero-shot prompting", "without retrieval",
             "the vanilla LLM"]),
])
def test_every_real_config_bans_its_real_control_phrases(domain, phrases):
    live = (SPECS / f"{domain}.yaml").exists()
    spec = load_spec(domain, SPECS if live else SPECS / "drafts")
    pat = load_real_spec(domain).banned(spec)
    for real in phrases:
        assert pat.search(real), (domain, real)


def test_the_medicine_control_words_skip_look_alikes():
    pat = load_real_spec("medicine").banned(load_spec("medicine"))
    for fine in ("events by SOC and preferred term", "no treatment-related deaths", "no treatment- or dose-related",
                 "with no intervention benefits", "social support"):
        assert not pat.search(fine), fine


@pytest.mark.parametrize("domain", ["medicine", "law", "materials", "rag"])
def test_every_real_config_builds_its_name_pattern_and_never_renames_a_keep_word(domain):
    # rag listed "dpr" and "fid" (lower_names refuses 3 letters) and "bm25", which the keep word BM25 must win
    from synth3.rename import lower_names
    rs = load_real_spec(domain)
    pat = lower_names(rs)
    assert [w for w in rs.keep if pat.fullmatch(w)] == []
    generic = {"retriever", "embedding", "rerank", "reranker", "realm", "atlas", "retro", "bm25"}
    assert not generic & set(rs.name_words), "ordinary field words are not names"
