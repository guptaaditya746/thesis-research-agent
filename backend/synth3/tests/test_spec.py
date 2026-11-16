import pytest

from synth3.spec import load_spec

from .conftest import good, write


def test_loads_and_lists_pairs(tmp_path):
    spec = load_spec("demo", write(tmp_path, good()))
    assert spec.control.id == "ctrl" and [a.id for a in spec.treatments] == ["a", "b"]
    assert spec.pairs == [(t, m) for t in ("a", "b") for m in ("m1", "m2", "m3")]
    assert spec.measure("m3").kind == "value"


@pytest.mark.parametrize("change, words", [
    (lambda d: d["arms"][0].update(control=False), "exactly one control"),
    (lambda d: d["arms"].pop(), "at least 3 arms"),
    (lambda d: d["measures"].pop(), "at least 3 measures"),
    (lambda d: d["measures"][0].update(base_rate=[0.2, 0.95]), "base_rate"),
    (lambda d: d["measures"][2].pop("base_value"), "base_value"),
    (lambda d: d["measures"][0].update(min_gap=0.5), "min_gap"),
    (lambda d: d["arms"][2].update(label=d["arms"][1]["label"] + " retard"), "inside"),
    (lambda d: d["measures"][0].update(outcome="reached grade 2"), "digit"),
    (lambda d: d["settings"][0]["levels"].clear(), "setting"),
    (lambda d: d["authors"].__delitem__(slice(10, None)), "authors"),
])
def test_refuses_bad_specs(tmp_path, change, words):
    d = good(); change(d)
    with pytest.raises(ValueError, match=words):
        load_spec("demo", write(tmp_path, d))


def test_crlf_and_lf_hash_the_same(tmp_path):
    assert load_spec("demo", write(tmp_path / "lf", good())).sha256 == \
           load_spec("demo", write(tmp_path / "crlf", good(), newline="\r\n")).sha256
