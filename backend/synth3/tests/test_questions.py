from pathlib import Path

import pytest
import yaml

from synth3.questions import Question, load_questions, question_sha256, sheet_question_sha256

FIX = Path(__file__).parent / "fixtures" / "questions"


def write_q(dir, d):
    dir.mkdir(parents=True, exist_ok=True)
    (dir / "demo.yaml").write_text(yaml.safe_dump(d, sort_keys=False), encoding="utf-8")
    return dir


def test_example_questions_load(SPEC):
    qs = load_questions("demo", SPEC, FIX)
    assert [q.id for q in qs.questions] == ["d01", "d02", "d03"]
    assert len(qs.get("d02").sub_questions) == 2 and qs.get("d01").kind == "open"


@pytest.mark.parametrize("change, words", [
    (lambda d: d["questions"].append(dict(d["questions"][0], question="Other?")), "used twice"),
    (lambda d: d["questions"].append(dict(id="d09", question="  does targeted THERAPY improve the response "
                                                            "rate compared with standard care?")), "same question"),
    (lambda d: d["questions"][0].update(question=" "), "d01: question is empty"),
    (lambda d: d["questions"][1].update(sub_questions=[""]), "d02: sub_questions holds an empty entry"),
    (lambda d: d["questions"][2].update(about=["Aspirin"]), "Aspirin"),
    (lambda d: d.update(domain="law"), "domain 'law'"),
    (lambda d: d["questions"][0].update(id="Q 1"), "id 'Q 1'"),
    (lambda d: d["questions"][0].update(answer="yes"), "answer"),
    (lambda d: d["questions"][0].update(kind="chaining"), "d01: kind 'chaining'"),
])
def test_refuses_bad_question_files(tmp_path, SPEC, change, words):
    d = yaml.safe_load((FIX / "demo.yaml").read_text(encoding="utf-8")); change(d)
    with pytest.raises(ValueError, match=words):
        load_questions("demo", SPEC, write_q(tmp_path, d))


def test_missing_file_says_who_writes_it(tmp_path, SPEC):
    with pytest.raises(ValueError, match="no questions file.*Aditya"):
        load_questions("demo", SPEC, tmp_path / "none")


def test_the_hash_ignores_notes_and_kind():
    """The answer records' hash keeps the sub-questions: plan 4's system plans with them."""
    q = Question(id="x", question="Q?", sub_questions=["s?"])
    assert question_sha256(q) == question_sha256(q.model_copy(update={"notes": "n", "kind": "best"}))
    assert question_sha256(q) != question_sha256(q.model_copy(update={"sub_questions": ["t?"]}))


def test_the_sheet_hash_ignores_sub_questions():
    """Sub-questions are never scored and set no scope, so a sheet does not depend on them."""
    q = Question(id="x", question="Q?", sub_questions=["s?"], about=["Targeted therapy"])
    same = q.model_copy(update={"sub_questions": ["t?", "u?"], "notes": "n", "kind": "best"})
    assert sheet_question_sha256(q) == sheet_question_sha256(same)
    assert sheet_question_sha256(q) != sheet_question_sha256(q.model_copy(update={"question": "Other?"}))
    assert sheet_question_sha256(q) != sheet_question_sha256(q.model_copy(update={"about": []}))


def test_a_yaml_typo_is_a_value_error_naming_the_file(tmp_path, SPEC):
    (tmp_path / "q").mkdir()
    (tmp_path / "q" / "demo.yaml").write_text("domain: demo\nquestions: [unclosed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="demo.yaml: not valid YAML"):
        load_questions("demo", SPEC, tmp_path / "q")
