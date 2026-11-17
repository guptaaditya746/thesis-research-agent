from synth3.spec import load_spec
from synth3.world import MIN_PER_PAIR


def test_medicine_spec_loads_and_fits_forty_studies():
    spec = load_spec("medicine")
    assert len(spec.pairs) * MIN_PER_PAIR <= 40 * (1 - spec.head_to_head_rate)
    assert {m.kind for m in spec.measures} == {"count", "value"}
    assert any(not m.higher_is_better for m in spec.measures) and any(c.from_setting for c in spec.conditions)


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
