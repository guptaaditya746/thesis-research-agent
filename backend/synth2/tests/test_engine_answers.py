import json

import pytest

from synth2.cli import main
from synth2.engine_answers import collect, to_answer
from synth2.score import Answer


@pytest.mark.parametrize("label, verdict", [("supported", "helps"), ("refuted", "hurts"),
    ("no_effect", "no_effect"), ("mixed", "mixed"), ("insufficient", "insufficient")])
def test_engine_labels_map_onto_synth2_verdicts(label, verdict):
    answer = to_answer(label)
    assert Answer.parse(answer).verdict == verdict
    assert answer["condition"] is None and answer["sides"] == {} and answer["untested"] == []


def test_an_unknown_label_is_refused():
    with pytest.raises(ValueError):
        to_answer("maybe")


def _fake_run(runs, name, corpus_id, label):
    """The shape the engine writes: run.json with `corpus_id`, answer.json of an effect run with `label`."""
    folder = runs / name
    folder.mkdir(parents=True)
    (folder / "run.json").write_text(json.dumps({"corpus_id": corpus_id, "extractors": []}), encoding="utf-8")
    (folder / "answer.json").write_text(json.dumps({"system": "evidence", "label": label, "counts": {}}), encoding="utf-8")


def test_two_runs_of_one_corpus_are_refused(tmp_path, capsys):
    runs = tmp_path / "runs"
    _fake_run(runs, "a", "c1", "mixed")
    _fake_run(runs, "b", "c1", "supported")
    with pytest.raises(ValueError):
        collect(runs)
    assert main(["engine-answers", "--runs", str(runs), "--out", str(tmp_path / "x.json")]) == 2
    assert "c1" in capsys.readouterr().err
    assert not (tmp_path / "x.json").exists()


def test_no_run_is_refused(tmp_path):
    (tmp_path / "runs").mkdir()
    assert main(["engine-answers", "--runs", str(tmp_path / "runs"), "--out", str(tmp_path / "x.json")]) == 2


def test_collected_answers_score_with_synth2_score(tmp_path):
    root = tmp_path / "grid"
    assert main(["build", "--out", str(root), "--seeds", "1", "--laws", "opposed", "--texts", "table"]) == 0
    runs = tmp_path / "runs"
    for p in sorted(root.glob("*/s*/*/ground_truth.json")):
        truth = json.loads(p.read_text(encoding="utf-8"))
        _fake_run(runs, p.parent.name, truth["corpus_id"], "mixed")
    answers = tmp_path / "answers.json"
    assert main(["engine-answers", "--runs", str(runs), "--out", str(answers)]) == 0
    assert main(["score", "--root", str(root), "--answers", str(answers), "--out", str(tmp_path / "report.json")]) == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["all"]["recovers_law"]["mean"] == 0.0
