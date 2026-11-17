from pathlib import Path

import pytest
import yaml

from synth3.questions import (Question, answer_by_of, asked_sha256, load_questions, question_sha256,
                              sheet_question_sha256, spec_names, target_of)

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


def test_a_crlf_file_has_the_same_hash_as_its_lf_copy(tmp_path, SPEC):
    text = (FIX / "demo.yaml").read_bytes().replace(b"\r\n", b"\n")
    for name, data in (("lf", text), ("crlf", text.replace(b"\n", b"\r\n"))):
        (tmp_path / name).mkdir()
        (tmp_path / name / "demo.yaml").write_bytes(data)
    lf, crlf = (load_questions("demo", SPEC, tmp_path / n) for n in ("lf", "crlf"))
    assert lf.sha256 == crlf.sha256 and lf.questions == crlf.questions
    assert spec_names(SPEC) == SPEC.names()


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


def test_the_asked_hash_covers_kind_and_target():
    q = Question(id="x", question="Q?", sub_questions=["s?"])
    assert asked_sha256(q) == asked_sha256(q.model_copy(update={"notes": "n"}))
    assert asked_sha256(q) != asked_sha256(q.model_copy(update={"kind": "best"}))
    inv = q.model_copy(update={"kind": "inventory"})
    assert asked_sha256(inv) != asked_sha256(inv.model_copy(update={"target": "metric"}))
    assert asked_sha256(inv) == asked_sha256(inv.model_copy(update={"target": "condition"}))
    assert question_sha256(q) == question_sha256(q.model_copy(update={"kind": "best"}))


def test_target_only_with_inventory(tmp_path, SPEC):
    d = yaml.safe_load((FIX / "demo.yaml").read_text(encoding="utf-8"))
    d["questions"][0].update(target="metric")
    with pytest.raises(ValueError, match="d01: target is only for kind inventory"):
        load_questions("demo", SPEC, write_q(tmp_path, d))


def test_how_the_system_answers_each_kind():
    assert answer_by_of(Question(id="x", question="Q?")) == "written"
    inv = Question(id="x", question="Q?", kind="inventory")
    assert answer_by_of(inv) == "inventory" and target_of(inv) == "condition"
    assert target_of(inv.model_copy(update={"target": "metric"})) == "metric"
    assert target_of(Question(id="x", question="Q?", kind="effect")) is None
