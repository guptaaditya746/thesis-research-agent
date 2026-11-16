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


CONCLUSION = {"verdict": "depends", "condition": "fact_rarity", "sides": {"rare": "supports", "common": "contradicts"},
              "untested": [], "delta": 0.01, "conditions": []}


def test_a_depends_conclusion_keeps_its_condition_and_sides():
    from synth2.engine_answers import answer_form
    form = answer_form({"label": "mixed", "conclusion": CONCLUSION})
    assert form == {"verdict": "depends", "condition": "fact_rarity", "sides": {"rare": "helps", "common": "hurts"},
                    "untested": []}
    assert Answer.parse(form).verdict == "depends"
    assert answer_form({"synthesis": {"label": "mixed", "conclusion": CONCLUSION}}) == form   # a plan run


@pytest.mark.parametrize("verdict, word", [("supported", "helps"), ("refuted", "hurts"), ("no_effect", "no_effect"),
                                           ("insufficient", "insufficient")])
def test_a_conclusion_with_one_direction_beats_the_label_and_keeps_untested(verdict, word):
    from synth2.engine_answers import answer_form
    answer = {"label": "mixed", "conclusion": {**CONCLUSION, "verdict": verdict, "condition": None, "sides": {},
                                               "untested": ["model_size.large"]}}
    assert answer_form(answer) == {"verdict": word, "condition": None, "sides": {}, "untested": ["model_size.large"]}


def test_an_answer_without_a_conclusion_maps_its_label_and_a_broken_conclusion_is_refused():
    from synth2.engine_answers import answer_form
    assert answer_form({"label": "mixed"}) == to_answer("mixed")
    for broken in ({"verdict": "depends"}, {"verdict": "perhaps"}, "depends",
                   {**CONCLUSION, "sides": {"rare": "maybe"}}):
        with pytest.raises(ValueError):
            answer_form({"label": "mixed", "conclusion": broken})


def test_the_oracles_answers_recover_the_law_of_a_whole_family(tmp_path):
    from evaluation import oracle
    from repo_paths import DATA
    root = tmp_path / "grid"
    assert main(["build", "--out", str(root), "--seeds", "1", "--laws", "opposed", "--texts", "table"]) == 0
    runs = tmp_path / "runs"
    members = sorted(p.parent for p in root.glob("*/s*/*/ground_truth.json"))
    assert len(members) == 5
    for corpus in members:
        oracle.run(DATA / "domains/rag/protocols/rag-factuality-subsets.yaml", corpus, runs / corpus.name)
    answers = tmp_path / "answers.json"
    assert main(["engine-answers", "--runs", str(runs), "--out", str(answers)]) == 0
    assert main(["score", "--root", str(root), "--answers", str(answers), "--out", str(tmp_path / "report.json")]) == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["all"]["recovers_law"]["mean"] == 1.0 and report["all"]["follows_evidence"]["mean"] == 1.0
    keys = [json.loads((c / "ground_truth.json").read_text(encoding="utf-8"))["key"]["verdict"] for c in members]
    assert "depends" in keys
