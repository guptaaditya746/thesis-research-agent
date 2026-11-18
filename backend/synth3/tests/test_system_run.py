"""synth3.system running: every confirmed plan on every folder, collected into the judge's shape."""
from pathlib import Path

import pytest

from evidence import planrun, stages
from evidence.plan import load_plan, with_answer, write_plan
from evidence.tests.conftest import provider_of
from synth3 import system
from synth3.answers import load_answers
from synth3.cli import main
from synth3.questions import load_questions
from synth3.sheetfacts import load_folder
from synth3.spec import load_spec
from synth3.system import MAX_WRITER_TRIES, auto_path, plan_path, run_folder, run_path
from synth3.tests.systemrun import OK_REPLY, system_model, write_demo_plans

FIX = Path(__file__).parent / "fixtures" / "questions"


@pytest.fixture(autouse=True)
def clean_registry():
    with stages.registered():
        yield


def counting_runner(calls, writer_reply=OK_REPLY):
    def runner(plan_file, corpus, out_dir, **kw):
        calls.append((plan_file, kw))
        kw = {k: v for k, v in kw.items() if k != "provider"}
        return planrun.run(plan_file, corpus, out_dir, selection="regex-only",
                           provider=provider_of(system_model(writer_reply)), **kw)
    return runner


def setup(folder, tmp_path, SPEC, confirmed="aditya"):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX)
    write_demo_plans(tmp_path / "plans", qs, SPEC, confirmed=confirmed)
    return f, qs


def test_one_folder_runs_every_plan_and_saves_records(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC); calls = []
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    assert sorted(out["ran"]) == ["d01", "d02", "d03"] and out["failed"] == {} and out["by_system"] == []
    assert {r.question_id for r in load_answers(tmp_path / "res", "demo")} == {"d01", "d02", "d03"}
    assert all(k["reason"] == "off" and k["links"] == "off" for _, k in calls)


def test_an_unconfirmed_plan_is_skipped_without_the_flag(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC, confirmed=None); calls = []
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    assert calls == [] and set(out["skipped"]) == {"d01", "d02", "d03"}
    assert "--confirm-as-system" in out["skipped"]["d01"] and "not confirmed by a person" in out["skipped"]["d01"]


def test_confirm_as_system_runs_a_copy_and_leaves_the_draft(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC, confirmed=None); calls = []
    draft = plan_path(tmp_path / "plans", "demo", "d01"); before = draft.read_bytes()
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", as_system=True, workers=1,
                     runner=counting_runner(calls))
    assert draft.read_bytes() == before and sorted(out["by_system"]) == ["d01", "d02", "d03"]
    auto = load_plan(auto_path(tmp_path / "plans", "demo", "d01"))
    assert auto.ready() and {d.confirmed_by for d in auto.decisions} == {"system"}
    recs = load_answers(tmp_path / "res", "demo")
    assert {r.plan_confirmed_by for r in recs} == {"system"}
    run_folder(f, qs, tmp_path / "plans", tmp_path / "res", as_system=True, workers=1, runner=counting_runner(calls))
    assert len(calls) == 3   # the copy is kept when the draft did not change, so the runs are kept


def test_the_system_copy_and_the_run_plan_are_written_atomically(folder, tmp_path, SPEC, monkeypatch):
    from synth3.tests.test_system_plan import atomic_writes
    f, qs = setup(folder, tmp_path, SPEC, confirmed=None)
    written = atomic_writes(monkeypatch)
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", as_system=True, workers=1,
                     runner=counting_runner([]))
    assert sorted(out["ran"]) == ["d01", "d02", "d03"]
    auto = auto_path(tmp_path / "plans", "demo", "d01")
    ran = run_path(tmp_path / "res", "demo", 1, "d01").with_suffix(".plan.json")
    assert auto in written and ran in written and len(written) == 6
    assert auto.read_text(encoding="utf-8") == load_plan(auto).model_dump_json(indent=2)


def test_a_second_run_keeps_complete_runs(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC); calls = []
    run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    assert out["ran"] == [] and sorted(out["kept"]) == ["d01", "d02", "d03"] and len(calls) == 3


def test_a_changed_plan_runs_again_and_the_old_run_is_kept_aside(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC); calls = []
    run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    path = plan_path(tmp_path / "plans", "demo", "d01"); p = load_plan(path)
    write_plan(p.model_copy(update={"decisions": [d.model_copy(update={"value": "0.02"}) if d.type == "threshold"
                                                  else d for d in p.decisions]}), path)
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    assert out["ran"] == ["d01"] and run_path(tmp_path / "res", "demo", 1, "d01").with_name("d01.old-1").is_dir()


def test_a_failed_writer_call_is_rerun_with_retry(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC); calls = []
    run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1,
               runner=counting_runner(calls, writer_reply=lambda p: RuntimeError("down")))
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    assert sorted(out["rerun"]) == ["d01", "d02", "d03"] and all(k["retry_errors"] for _, k in calls[3:])
    assert run_path(tmp_path / "res", "demo", 1, "d01").with_name("d01.redo-1").is_dir()
    assert out["failed"] == {}


def test_a_complete_run_without_its_written_answer_is_redone_with_retry(folder, tmp_path, SPEC):
    """m24: a sealed complete written run that lost written-answer.json is set aside and run again."""
    f, qs = setup(folder, tmp_path, SPEC); calls = []
    run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    (run_path(tmp_path / "res", "demo", 1, "d01") / "written-answer.json").unlink()
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    assert out["rerun"] == ["d01"] and calls[3][1]["retry_errors"] is True and len(calls) == 4
    assert run_path(tmp_path / "res", "demo", 1, "d01").with_name("d01.redo-1").is_dir()


def test_a_fixed_kind_run_with_unchecked_items_is_redone(folder, tmp_path, SPEC):
    """m24: an effect run whose stage report notes an unchecked item is run again with retry."""
    import json
    f, qs = setup(folder, tmp_path, SPEC); calls = []
    effect = qs.model_copy(update={"questions": [qs.get("d01").model_copy(update={"kind": "effect"})]})
    path = plan_path(tmp_path / "plans", "demo", "d01")
    write_plan(with_answer(load_plan(path), "effect", None), path)
    first = run_folder(f, effect, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    assert first["ran"] == ["d01"]
    run = run_path(tmp_path / "res", "demo", 1, "d01")
    (run / "stage_report.json").write_text(json.dumps({"claims": {"S001": ["unchecked: claim 0-10: down"]}}),
                                           encoding="utf-8")
    out = run_folder(f, effect, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls))
    assert out["rerun"] == ["d01"] and calls[1][1]["retry_errors"] is True
    assert run.with_name("d01.redo-1").is_dir()


def test_a_written_answer_that_failed_its_checks_is_asked_again_with_a_fresh_key(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC); calls = []; bad = lambda p: {"sentences": []}
    first = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls, bad))
    assert sorted(first["empty"]) == ["d01", "d02", "d03"]
    run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls, bad))
    assert load_plan(calls[3][0]).writer_try == 1
    run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls, bad))
    last = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner(calls, bad))
    assert sorted(last["kept"]) == ["d01", "d02", "d03"] and len(calls) == 3 * MAX_WRITER_TRIES


def test_a_damaged_run_is_listed_as_failed_and_the_loop_goes_on(folder, tmp_path, SPEC):
    import json
    f, qs = setup(folder, tmp_path, SPEC); calls = []
    inner = counting_runner(calls)

    def damaging(plan_file, corpus, out_dir, **kw):
        root = inner(plan_file, corpus, out_dir, **kw)
        if kw["run_id"] == "d01":   # a written run whose answer lost its `cut`
            path = root / "written-answer.json"
            written = json.loads(path.read_text(encoding="utf-8"))
            path.write_text(json.dumps({k: v for k, v in written.items() if k != "cut"}), encoding="utf-8")
        return root
    out = run_folder(f, qs, tmp_path / "plans", tmp_path / "res", workers=1, runner=damaging)
    assert set(out["failed"]) == {"d01"} and "cut" in out["failed"]["d01"]
    assert {r.question_id for r in load_answers(tmp_path / "res", "demo")} == {"d02", "d03"}


def test_missing_stale_and_rekinded_plans_are_skipped_with_reasons(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC)
    plan_path(tmp_path / "plans", "demo", "d02").unlink()
    edited = qs.model_copy(update={"questions": [qs.get("d01").model_copy(update={"kind": "effect"}),
                                                 qs.get("d02"),
                                                 qs.get("d03").model_copy(update={"question": "Changed?"})]})
    out = run_folder(f, edited, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner([]))
    assert out["skipped"]["d02"] == "no plan; run synth3 system-plan first"
    assert out["skipped"]["d03"] == "the question changed after planning"
    assert out["skipped"]["d01"].startswith("the plan answers by written, the question asks for effect")


def test_a_plan_for_another_inventory_target_is_skipped_naming_both(folder, tmp_path, SPEC):
    f, qs = setup(folder, tmp_path, SPEC)
    d01 = qs.get("d01")
    path = plan_path(tmp_path / "plans", "demo", "d01")
    write_plan(with_answer(load_plan(path), "inventory", "condition"), path)
    edited = qs.model_copy(update={"questions": [d01.model_copy(update={"kind": "inventory", "target": "metric"})]})
    out = run_folder(f, edited, tmp_path / "plans", tmp_path / "res", workers=1, runner=counting_runner([]))
    assert out["skipped"]["d01"] == ("the plan answers by inventory/condition, the question asks for "
                                     "inventory/metric; run synth3 system-plan")


def test_system_run_by_command(folder, tmp_path, spec_dir, monkeypatch, capsys):
    f, qs = setup(folder, tmp_path, load_spec("demo", spec_dir))
    monkeypatch.setattr(system, "planrun_run", counting_runner([]))   # the default runner, looked up at call time
    assert main(["system-run", "--domain", "demo", "--seeds", "1", "--workers", "1", "--folders", str(folder.parent),
                 "--plans", str(tmp_path / "plans"), "--questions-root", str(FIX), "--spec-root", str(spec_dir),
                 "--results", str(tmp_path / "res")]) == 0
    assert "s1: ran 3, rerun 0, kept 0, skipped 0, failed 0, empty 0, plans confirmed by system 0" in capsys.readouterr().out
