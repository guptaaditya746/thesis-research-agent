"""synth3.system: a plan run's folder becomes the judge's AnswerRecord, and `collect` reads plan runs."""
import json

import pytest
import yaml

from evidence import stages
from synth3.answers import answer_path, pulled_facts
from synth3.cli import main
from synth3.questions import asked_sha256, question_sha256
from synth3.sheetfacts import load_folder
from synth3.system import from_system_run
from synth3.tests.conftest import q
from synth3.tests.systemrun import FACT_REPLY, demo_plan, make_system_run

QQ = dict(text="Does Targeted therapy raise the Response rate?", sub_questions=["Which papers say Secret-sub?"])


@pytest.fixture(autouse=True)
def clean_registry():
    with stages.registered():
        yield


@pytest.fixture
def written(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q(QQ["text"], sub_questions=QQ["sub_questions"])
    plan = demo_plan(SPEC, qq)
    return f, qq, plan, make_system_run(tmp_path / "runs", f, qq, plan)


def banned_in(text, plan):
    banned = ["Secret-sub", "evidence-engine", "plan-", "orch-model", "system", *(l.question for l in plan.lines)]
    return [b for b in banned if b in text]


def test_a_written_run_becomes_a_record(written):
    f, qq, plan, run = written
    rec = from_system_run(run, f, qq)
    out = json.loads((run / "written-answer.json").read_text(encoding="utf-8"))
    assert rec.system == "system" and rec.question_sha256 == question_sha256(qq)
    assert rec.asked_sha256 == asked_sha256(qq) and rec.plan_confirmed_by == "person"
    assert rec.text == out["answer_text"] and rec.facts == pulled_facts(run, f)
    assert rec.facts_left_out == sum(out["cut"]["left_out"].values())


def test_the_demo_folder_gives_pulled_facts(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q(QQ["text"])
    run = make_system_run(tmp_path / "runs", f, qq, demo_plan(SPEC, qq), writer_reply=FACT_REPLY)
    rec = from_system_run(run, f, qq)
    assert rec.facts and rec.text.startswith("A paper measured it (S") and rec.cited


def test_the_record_holds_no_sub_question_and_no_system_name(written):
    f, qq, plan, run = written
    assert banned_in(from_system_run(run, f, qq).text, plan) == []


def test_a_finding_with_paper_ids_holds_no_banned_word(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q(QQ["text"], sub_questions=QQ["sub_questions"])
    plan = demo_plan(SPEC, qq)
    run = make_system_run(tmp_path / "runs", f, qq, plan, writer_reply=FACT_REPLY)
    rec = from_system_run(run, f, qq)
    assert rec.cited and banned_in(rec.text, plan) == []


@pytest.mark.parametrize("change, words", [
    (lambda qq: qq.model_copy(update={"question": "Other?"}), "planned for another version of the question"),
    (lambda qq: qq.model_copy(update={"sub_questions": []}), "planned for another version of the question"),
    (lambda qq: qq.model_copy(update={"kind": "effect"}), "answers by written, the question asks for effect"),
])
def test_a_run_for_another_question_is_refused(written, change, words):
    f, qq, plan, run = written
    with pytest.raises(ValueError, match=words):
        from_system_run(run, f, change(qq))


def test_a_failed_writer_call_asks_for_a_rerun(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q(QQ["text"])
    run = make_system_run(tmp_path / "runs", f, qq, demo_plan(SPEC, qq), writer_reply=lambda p: RuntimeError("down"))
    with pytest.raises(ValueError, match="model call failed.*run it again with retry"):
        from_system_run(run, f, qq)


def test_a_failed_written_answer_is_an_empty_answer(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q(QQ["text"])
    run = make_system_run(tmp_path / "runs", f, qq, demo_plan(SPEC, qq), writer_reply=lambda p: {"sentences": []})
    rec = from_system_run(run, f, qq)
    assert rec.text == "" and rec.cited == [] and not rec.text_cut


def test_an_effect_run_is_judged_as_kind_lines(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q(QQ["text"], kind="effect")
    plan = demo_plan(SPEC, qq, answer_by="effect")
    run = make_system_run(tmp_path / "runs", f, qq, plan)
    rec = from_system_run(run, f, qq)
    assert rec.text.startswith("Targeted therapy against Standard care on Response rate: ")
    assert not rec.text.lstrip().startswith("{")
    assert banned_in(rec.text, plan) == [] and rec.facts_left_out is None


@pytest.mark.xfail(strict=True, reason="the engine's undetermined reasons name the thing id (evidence/synthesis.py "
                                       "REASONS: 'no targeted condition found'); kindtext does not map it to the name")
def test_an_effect_run_names_no_thing_id(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q(QQ["text"], kind="effect")
    run = make_system_run(tmp_path / "runs", f, qq, demo_plan(SPEC, qq, answer_by="effect"))
    assert "targeted" not in from_system_run(run, f, qq).text.replace("Targeted", "")


def test_a_system_confirmed_plan_is_recorded_as_such(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q(QQ["text"])
    run = make_system_run(tmp_path / "runs", f, qq, demo_plan(SPEC, qq, confirmed="system"))
    assert from_system_run(run, f, qq).plan_confirmed_by == "system"


def test_an_unsealed_run_is_refused(written):
    f, qq, plan, run = written
    (run / "run.json").unlink()
    with pytest.raises(ValueError, match="the run is not complete"):
        from_system_run(run, f, qq)


def test_collect_reads_a_plan_run(written, tmp_path, spec_dir):
    f, qq, plan, run = written
    (tmp_path / "qs").mkdir()
    (tmp_path / "qs" / "demo.yaml").write_text(yaml.safe_dump({"domain": "demo", "questions": [
        {"id": qq.id, "question": qq.question, "sub_questions": qq.sub_questions}]}), encoding="utf-8")
    assert main(["collect", "--domain", "demo", "--seed", "1", "--question", qq.id, "--run", str(run),
                 "--folders", str(f.path.parent), "--questions-root", str(tmp_path / "qs"),
                 "--spec-root", str(spec_dir), "--results", str(tmp_path / "res")]) == 0
    assert answer_path(tmp_path / "res", "demo", 1, "system", qq.id).is_file()
