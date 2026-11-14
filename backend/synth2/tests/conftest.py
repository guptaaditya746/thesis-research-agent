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


STUDY_INPUT = {
    "label": "Lee et al. (2021)", "treatment": "augmented", "control": "baseline",
    "system_names": {"treatment": "FindSys", "control": "PlainSys"}, "benchmark": "TrivBench", "metric": "accuracy",
    "claim_sentence": "The augmented system is better.",
    "cells": [{"levels": [{"name": "Low Noise"}], "treatment_correct": 70, "treatment_total": 100,
               "control_correct": 50, "control_total": 100}],
}
SOURCE_PAPER = (
    "# Reading With FiD\n\nWe study FiD and FiD-RAG on the NaturalQuestions benchmark. Karpukhin et al. (2020) and "
    "Smith and Jones (2019) built earlier readers, see https://github.com/someone/tool for code. Roberts et al. "
    "(2021) also used FiD. Our RAG model uses Wikipedia.\n\n## Results\n\nFiD-RAG answers more questions than the "
    "rest, as Karpukhin et al. (2020) report.\n"
)


@pytest.fixture
def edit_base(tmp_path):
    """A prepared real-edit folder with one study (S001): inputs, a renamed source and its map."""
    from synth2 import realedit
    src = tmp_path / "source.md"
    src.write_text(SOURCE_PAPER, encoding="utf-8")
    inputs = tmp_path / "v10"
    inputs.mkdir()
    (inputs / "S001.json").write_text(json.dumps({**STUDY_INPUT, "skeleton_source": str(src)}), encoding="utf-8")
    base = tmp_path / "v11"
    realedit.prepare(inputs, base)
    return base
