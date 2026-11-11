import json

import pytest

from synth2.corpus import Settings, build_base


@pytest.fixture
def tiny(tmp_path):
    """A 6-study table-text rag corpus (`<tmp>/base`) with at least one one-cell and one two-cell study."""
    for seed in range(50):
        out = tmp_path / "base"
        build_base(out, Settings("rag", seed, 6, "uniform", "table", exact=True))
        sizes = {len(s["cells"]) for s in json.loads((out / "ground_truth.json").read_text(encoding="utf-8"))["studies"]}
        if {1, 2} <= sizes:
            return out
        for p in sorted(out.rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
        out.rmdir()
    raise AssertionError("no seed in range(50) gives both a one-cell and a two-cell study")
