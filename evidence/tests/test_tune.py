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
    def __init__(self, name, metric, lm, budget, reflection_lm=None):
        self.budget = budget

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
    assert data["max_metric_calls"] == min(data["light_budget"], 500) and data["optimizer"] == "gepa" and data["model_calls"] >= 2
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


def test_refuses_same_papers_under_other_ids(tmp_path, lm):
    a = corpus(tmp_path, "id-a", {"baseline": ["alpha", "x"]})
    b = corpus(tmp_path, "id-b", {"baseline": ["alpha", "y", "z"]})      # different ids and truth ...
    for d in (a, b):
        (d / "papers").mkdir()
        (d / "papers" / "P1.md").write_text("The same  paper text.", encoding="utf-8")   # ... same paper text
    with pytest.raises(T.TuneError, match="share 1 paper"):
        T.tune("write_words", [a], [b], lm=lm, make_optimizer=FakeOptimizer, tuned_dir=tmp_path / "t")


def test_refuses_same_truth_under_other_ids(tmp_path, lm):
    a = corpus(tmp_path, "id-a", {"baseline": ["alpha", "x"]})
    b = corpus(tmp_path, "id-b", {"baseline": ["alpha", "x"]})
    with pytest.raises(T.TuneError, match="ground truths"):
        T.check_disjoint(T.sources("write_words", [a], "train"), T.sources("write_words", [b], "test"))


def test_words_test_drops_examples_without_unseen_names(tmp_path, lm):
    tr = corpus(tmp_path, "c-train", {"baseline": ["alpha", "beta"], "rag": ["r1", "r2"]})
    te = corpus(tmp_path, "c-test", {"baseline": ["alpha"], "rag": ["r1", "r3"]})
    report = T.tune("write_words", [tr], [te], lm=lm, make_optimizer=FakeOptimizer, tuned_dir=tmp_path / "t")
    assert report["test_dropped_no_unseen_names"] == 1 and report["n_test"] == 1


def test_real_set_without_examples_file_refused(tmp_path, lm):
    d = tmp_path / "real"
    d.mkdir()
    (d / "tune_split.json").write_text(json.dumps({"papers": ["p1"], "rest": ["p2"]}), encoding="utf-8")
    with pytest.raises(T.TuneError, match="tune_examples.json"):
        T.sources("recheck", [d], "train")
    with pytest.raises(T.TuneError, match="neither"):
        T.sources("write_words", [tmp_path / "nothing"], "train")


def test_planner_query_not_tunable():
    assert "planner_query" not in T.SPECS


def test_claims_have_negatives_and_all_true_scores_below_one(tmp_path):
    d = tmp_path / "c"
    (d / "papers").mkdir(parents=True)
    text = "We study things. Method A shortens the delay. Baseline B had 12 ms of delay in the test."
    (d / "papers" / "S1.md").write_text(text, encoding="utf-8")
    c1 = text.index("Method A shortens the delay.")
    v = text.index("12 ms")
    (d / "ground_truth.json").write_text(json.dumps({"question": "q", "studies": [
        {"paper": "S1", "author_claim": {"id": "S1.a1", "direction": "improves"}}],
        "placements": [{"fact": "S1.a1", "role": "claim", "paper": "S1", "start": c1, "end": c1 + 28},
                       {"fact": "S1.m1", "role": "value", "paper": "S1", "start": v, "end": v + 5}]}), encoding="utf-8")
    ex = T.build_claims(d)
    assert [e["gold"]["is_claim"] for e in ex] == [True, False]
    class AllTrue:
        is_claim, direction = True, "improves"
    assert sum(T.metric_claims(e["gold"], AllTrue) for e in ex) / 2 == 0.5


def test_unparseable_replies_counted_and_refused(two, tmp_path):
    bad = RecordedLM("fake", lambda text, **kw: "not json at all", with_call=True)
    with pytest.raises(T.TuneError, match="failed to parse"):
        T.tune("write_words", list(two)[:1], list(two)[1:], lm=bad, make_optimizer=FakeOptimizer, tuned_dir=tmp_path / "t")
    assert not (tmp_path / "t" / "write_words.json").exists()


def test_real_step_refuses_synthetic_only_training(two, lm, tmp_path):
    with pytest.raises(T.TuneError, match="real-paper step"):
        T.tune("claims.read_claim", [two[0]], [two[1]], lm=lm, make_optimizer=FakeOptimizer, tuned_dir=tmp_path / "t")
    assert main(["tune", "recheck", "--train", str(two[0]), "--test", str(two[1])]) == 2


def test_calls_reported_apart(two, lm, tmp_path):
    r = T.tune("write_words", [two[0]], [two[1]], lm=lm, make_optimizer=FakeOptimizer, tuned_dir=tmp_path / "t")
    assert r["scoring_calls"]["before"] == r["n_train"] + r["n_test"] and r["optimizer_calls"] == 0
    assert r["reflection_calls"] == 0 and r["model_calls"] == r["scoring_calls"]["before"] + r["scoring_calls"]["after"]
