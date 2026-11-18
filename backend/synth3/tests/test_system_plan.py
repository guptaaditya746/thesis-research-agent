"""synth3.system planning: one plan per question, drafted with its sub-questions, kept on a second run."""
from pathlib import Path

import pytest

from evidence import steps
from evidence.plan import load_plan, with_answer
from evidence.tests.test_planner_subq import flags, line, lm, script, words  # noqa: F401  (lm is a fixture)
from modelcall import ModelCallError
from synth3 import system
from synth3.cli import main
from synth3.questions import Question, answer_by_of, load_questions, target_of
from synth3.spec import load_spec
from synth3.system import draft_plan, plan_domain, plan_path
from synth3.tests.systemrun import demo_plan

FIX = Path(__file__).parent / "fixtures" / "questions"


def use_fake_draft(monkeypatch, SPEC, fail=()):
    calls: list[tuple] = []

    def fake_draft(q, lm, templates):
        calls.append((q.id, lm))
        if q.id in fail:
            raise ModelCallError("down", None, [])
        return with_answer(demo_plan(SPEC, q, confirmed=None), answer_by_of(q), target_of(q))

    monkeypatch.setattr(system, "draft_plan", fake_draft)
    return calls


def test_draft_plan_passes_the_sub_questions_and_the_kind(lm, monkeypatch):  # noqa: F811
    replies, seen = lm
    monkeypatch.setattr(system, "write_words", lambda text, things, lm=None: words(text, things))
    script(replies, [line()]); replies.append(flags("d1"))
    qq = Question(id="d01", question="Does Targeted therapy raise the Response rate?", kind="inventory",
                  sub_questions=["Which papers measured it?"])
    plan = draft_plan(qq, steps.current(), {})
    assert plan.sub_questions == ["Which papers measured it?"] and plan.answer_by == "inventory"
    assert plan.target == "condition" and any("Which papers measured it?" in p for p in seen)
    assert not plan.ready()


def test_a_second_run_keeps_plans_and_a_changed_question_is_replanned(tmp_path, SPEC, monkeypatch):
    qs = load_questions("demo", SPEC, FIX); calls = use_fake_draft(monkeypatch, SPEC)
    assert sorted(plan_domain("demo", qs, tmp_path, "lm", {})["drafted"]) == ["d01", "d02", "d03"]
    assert len(plan_domain("demo", qs, tmp_path, "lm", {})["kept"]) == 3 and len(calls) == 3
    edited = qs.model_copy(update={"questions": [qs.get("d01").model_copy(update={"question": "Changed?"}),
                                                 *qs.questions[1:]]})
    out = plan_domain("demo", edited, tmp_path, "lm", {})
    assert out["drafted"] == ["d01"] and (tmp_path / "demo" / "d01.stale-1.json").is_file()


def test_redo_drafts_with_a_fresh_model(tmp_path, SPEC, monkeypatch):
    qs = load_questions("demo", SPEC, FIX); calls = use_fake_draft(monkeypatch, SPEC)
    plan_domain("demo", qs, tmp_path, "lm", {})
    out = plan_domain("demo", qs, tmp_path, "lm", {}, redo={"d02"}, redo_lm="fresh-lm")
    assert out["drafted"] == ["d02"] and calls[-1] == ("d02", "fresh-lm")
    assert (tmp_path / "demo" / "d02.stale-1.json").is_file()


def test_a_changed_kind_is_set_in_place(tmp_path, SPEC, monkeypatch):
    qs = load_questions("demo", SPEC, FIX); calls = use_fake_draft(monkeypatch, SPEC)
    plan_domain("demo", qs, tmp_path, "lm", {})
    edited = qs.model_copy(update={"questions": [qs.get("d01").model_copy(update={"kind": "effect"}),
                                                 *qs.questions[1:]]})
    out = plan_domain("demo", edited, tmp_path, "lm", {})
    assert out["rekinded"] == ["d01"] and len(calls) == 3
    assert load_plan(plan_path(tmp_path, "demo", "d01")).answer_by == "effect"


def test_a_redo_whose_model_fails_leaves_the_confirmed_plan_in_place(tmp_path, SPEC, monkeypatch):
    qs = load_questions("demo", SPEC, FIX)
    path = plan_path(tmp_path, "demo", "d02")
    path.parent.mkdir(parents=True)
    path.write_text(demo_plan(SPEC, qs.get("d02")).model_dump_json(indent=2), encoding="utf-8")   # confirmed
    before = path.read_bytes()
    use_fake_draft(monkeypatch, SPEC, fail={"d02"})
    out = plan_domain("demo", qs, tmp_path, "lm", {}, redo={"d02"}, redo_lm="fresh-lm")
    assert list(out["failed"]) == ["d02"] and path.read_bytes() == before
    assert not list(path.parent.glob("d02.stale-*.json")) and load_plan(path).ready()


def atomic_writes(monkeypatch) -> list[Path]:
    """Every plan file system.py writes, through jsonio.write_text_atomic; write_plan (not atomic) refuses."""
    from jsonio import write_text_atomic
    written: list[Path] = []

    def record(path, text):
        written.append(Path(path))
        write_text_atomic(path, text)

    def refuse(plan, path):
        raise AssertionError(f"write_plan is not atomic: {path}")
    monkeypatch.setattr(system, "write_text_atomic", record, raising=False)
    monkeypatch.setattr(system, "write_plan", refuse, raising=False)
    return written


def test_drafted_and_rekinded_plans_are_written_atomically(tmp_path, SPEC, monkeypatch):
    qs = load_questions("demo", SPEC, FIX); use_fake_draft(monkeypatch, SPEC)
    written = atomic_writes(monkeypatch)
    plan_domain("demo", qs, tmp_path, "lm", {})
    edited = qs.model_copy(update={"questions": [qs.get("d01").model_copy(update={"kind": "effect"}),
                                                 *qs.questions[1:]]})
    assert plan_domain("demo", edited, tmp_path, "lm", {})["rekinded"] == ["d01"]
    d01 = plan_path(tmp_path, "demo", "d01")
    assert written.count(d01) == 2 and len(written) == 4
    assert d01.read_text(encoding="utf-8") == load_plan(d01).model_dump_json(indent=2)   # the bytes evplan writes


def test_a_rekinded_plan_keeps_its_confirmations(tmp_path, SPEC, monkeypatch):
    """m19: a kind edit sets the kind in place; the person's confirmations stay."""
    qs = load_questions("demo", SPEC, FIX); use_fake_draft(monkeypatch, SPEC)
    path = plan_path(tmp_path, "demo", "d01")
    path.parent.mkdir(parents=True)
    path.write_text(demo_plan(SPEC, qs.get("d01")).model_dump_json(indent=2), encoding="utf-8")   # confirmed
    edited = qs.model_copy(update={"questions": [qs.get("d01").model_copy(update={"kind": "effect"})]})
    assert plan_domain("demo", edited, tmp_path, "lm", {})["rekinded"] == ["d01"]
    plan = load_plan(path)
    assert plan.answer_by == "effect" and plan.ready() and {d.confirmed_by for d in plan.decisions} == {"aditya"}


def test_system_plan_prints_each_problem(tmp_path, spec_dir, monkeypatch, capsys):
    """m19: a drafted plan whose answer kind cannot run is listed with its problem, and the command says so."""
    import yaml
    SPEC = load_spec("demo", spec_dir)

    def fake_draft(q, lm, templates):
        return with_answer(demo_plan(SPEC, q, confirmed=None).model_copy(update={"measures": []}), "best", None)
    monkeypatch.setattr(system, "draft_plan", fake_draft)
    monkeypatch.setattr(system, "orch_lm", lambda path: f"lm:{path.name}")
    (tmp_path / "qs").mkdir()
    (tmp_path / "qs" / "demo.yaml").write_text(yaml.safe_dump({"domain": "demo", "questions": [
        {"id": "d01", "question": "Which treatment is best for Response rate?", "kind": "best"}]}), encoding="utf-8")
    code = main(["system-plan", "--domain", "demo", "--plans", str(tmp_path / "p"), "--questions-root",
                 str(tmp_path / "qs"), "--spec-root", str(spec_dir), "--results", str(tmp_path / "r")])
    assert code == 1 and "  problem d01: a best answer needs a measure" in capsys.readouterr().out


def test_a_failing_draft_is_listed_and_the_rest_go_on(tmp_path, SPEC, monkeypatch):
    use_fake_draft(monkeypatch, SPEC, fail={"d02"})
    out = plan_domain("demo", load_questions("demo", SPEC, FIX), tmp_path, "lm", {})
    assert list(out["failed"]) == ["d02"] and "down" in out["failed"]["d02"]
    assert sorted(out["drafted"]) == ["d01", "d03"]


def test_system_plan_by_command(tmp_path, spec_dir, monkeypatch, capsys):
    use_fake_draft(monkeypatch, SPEC := load_spec("demo", spec_dir))
    monkeypatch.setattr(system, "orch_lm", lambda path: f"lm:{path.name}")
    args = ["system-plan", "--domain", "demo", "--plans", str(tmp_path / "p"), "--questions-root", str(FIX),
            "--spec-root", str(spec_dir), "--results", str(tmp_path / "r")]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "drafted 3, kept 0, rekinded 0, failed 0" in out and "--confirm-as-system" in out
    assert main([*args, "--redo", "zz"]) == 2
