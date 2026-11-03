"""DSPy tuning command: refuses overlap, writes the tuned file (tiny fake optimizer and fake model, no network)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence import steps
from evidence.cli import main
from evidence.steps import tune as T
from modelcall.dspy_lm import RecordedLM


def corpus(root: Path, cid: str, labels: dict[str, list[str]]) -> Path:
    d = root / cid
    d.mkdir(parents=True)
    conds = [{"id": f"S1.c{i}", "role": role, "label": names[0], "aliases": names[1:]}
             for i, (role, names) in enumerate(labels.items())]
    (d / "ground_truth.json").write_text(json.dumps({"question": "Does A beat B?", "studies": [
        {"study_id": "S1", "paper": "S1", "conditions": conds, "metrics": [], "measurements": []}],
        "placements": []}), encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps({"corpus_id": cid, "papers": []}), encoding="utf-8")
    return d


class FakeOptimizer:
    """Stands in for GEPA: returns the student with new instructions, makes no model call."""
    def __init__(self, *a):
        pass

    def compile(self, student, trainset=None, **kw):
        student.predict.signature = student.predict.signature.with_instructions("TUNED INSTRUCTIONS")
        return student


@pytest.fixture
def lm():
    return RecordedLM("fake", lambda text, **kw: json.dumps({"names": ["alpha", "beta"]}), with_call=True)


@pytest.fixture
def two(tmp_path):
    tr = corpus(tmp_path, "c-train", {"baseline": ["alpha", "alpha one", "alpha two"]})
    te = corpus(tmp_path, "c-test", {"baseline": ["alpha", "beta", "gamma"]})
    return tr, te


def test_refuses_overlap(two, lm, tmp_path):
    tr, _ = two
    with pytest.raises(T.TuneError, match="disjoint"):
        T.tune("write_words", [tr], [tr], lm=lm, make_optimizer=FakeOptimizer, tuned_dir=tmp_path / "t")
    assert not (tmp_path / "t").exists()


def test_writes_tuned_file(two, lm, tmp_path, monkeypatch):
    tr, te = two
    out = tmp_path / "tuned"
    report = T.tune("write_words", [tr], [te], lm=lm, make_optimizer=FakeOptimizer, tuned_dir=out)
    data = json.loads((out / "write_words.json").read_text(encoding="utf-8"))
    assert data["instructions"] == "TUNED INSTRUCTIONS"
    assert data["max_metric_calls"] == 500 and data["optimizer"] == "gepa" and data["model_calls"] >= 2
    assert data["scores"]["before"]["test"] == 0.5          # unseen names beta, gamma; the fake finds beta
    assert report == data
    monkeypatch.setattr(steps, "TUNED_DIR", out)            # Step still reads its `instructions` key
    assert steps.Step(T.SPECS["write_words"].signature(), "write_words").instructions() == "TUNED INSTRUCTIONS"


def test_real_step_uses_held_out_slice(tmp_path, lm):
    d = tmp_path / "real"
    d.mkdir()
    rows = [{"step": "claims.read_claim", "paper": p, "inputs": {"sentence": "A is faster."},
             "gold": {"is_claim": True, "direction": "improves"}} for p in ("p1", "p2", "p3")]
    (d / "tune_examples.json").write_text(json.dumps({"examples": rows}), encoding="utf-8")
    (d / "tune_split.json").write_text(json.dumps({"papers": ["p1"], "rest": ["p2", "p3"]}), encoding="utf-8")
    train, test = T.sources("claims.read_claim", [d], "train"), T.sources("claims.read_claim", [d], "test")
    assert len(T.examples_of(T.SPECS["claims.read_claim"], train)) == 1
    assert len(T.examples_of(T.SPECS["claims.read_claim"], test)) == 2
    T.check_disjoint(train, test)                           # same set, disjoint papers: fine
    (d / "tune_split.json").write_text(json.dumps({"papers": ["p1", "p2"], "rest": ["p2", "p3"]}), encoding="utf-8")
    with pytest.raises(T.TuneError, match="papers"):
        T.check_disjoint(T.sources("claims.read_claim", [d], "train"), T.sources("claims.read_claim", [d], "test"))


def test_unknown_step_refused(two, lm):
    with pytest.raises(T.TuneError, match="no tuning metric"):
        T.tune("planner_rule", [two[0]], [two[1]], lm=lm)


def test_cli_refuses_overlap(two, capsys):
    tr, _ = two
    assert main(["tune", "write_words", "--train", str(tr), "--test", str(tr)]) == 2
    assert "disjoint" in capsys.readouterr().err
