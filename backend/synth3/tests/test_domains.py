from synth3.spec import load_spec
from synth3.world import MIN_PER_PAIR


def test_medicine_spec_loads_and_fits_forty_studies():
    spec = load_spec("medicine")
    assert len(spec.pairs) * MIN_PER_PAIR <= 40 * (1 - spec.head_to_head_rate)
    assert {m.kind for m in spec.measures} == {"count", "value"}
    assert any(not m.higher_is_better for m in spec.measures) and any(c.from_setting for c in spec.conditions)
