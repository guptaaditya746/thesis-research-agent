"""synth3.remeasure: one folder's kept system runs re-run N times with no cache and measured."""
import shutil
from pathlib import Path

import pytest

from evidence import replay as replay_module
from evidence import stages
from evidence.tests.conftest import provider_of
from jsonio import sha256_hex
from synth3 import remeasure
from synth3.answers import load_answers
from synth3.cli import main
from synth3.remeasure import measure_folder, reexec_root
from synth3.sheetfacts import load_folder
from synth3.spec import load_spec
from synth3.tests.conftest import q
from synth3.tests.systemrun import FACT_REPLY, demo_plan, make_system_run, system_model

FIX = Path(__file__).parent / "fixtures" / "questions"


@pytest.fixture(autouse=True)
def clean_registry():
    with stages.registered():
        yield


def original(folder, tmp_path, SPEC, qid="d01", answer_by="written"):
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?").model_copy(update={"id": qid})
    res = tmp_path / "res"
    return res, make_system_run(res / "demo" / "runs" / "s1", f, qq, demo_plan(SPEC, qq, answer_by),
                                writer_reply=FACT_REPLY, run_id=qid)


def fake(writer_reply=FACT_REPLY):
    return provider_of(system_model(writer_reply))


def hashes(*roots):
    return {str(p): sha256_hex(p.read_bytes()) for r in roots for p in sorted(Path(r).rglob("*")) if p.is_file()}


def test_one_folder_is_rerun_and_reported(folder, tmp_path, SPEC):
    res, run = original(folder, tmp_path, SPEC)
    cache = run.parent.parent / "cache"     # make_system_run's record cache: <out>.parent / "cache"
    before = hashes(run, cache); answers = load_answers(res, "demo")
    out = measure_folder(res, "demo", 1, ["d01"], times=2, provider=fake())
    assert out["made"] == 2 and out["questions"]["d01"]["answers"]["same_text"] == 2
    assert (reexec_root(res, "demo", 1) / "report.json").is_file() and len(out["commits"]) == 2
    assert (reexec_root(res, "demo", 1) / "d01" / "stability.json").is_file()
    assert hashes(run, cache) == before and load_answers(res, "demo") == answers   # review M3
    assert not list(res.glob("**/*.answer.json"))   # F20: no answer was saved either
    assert not list((res / "demo" / "runs" / "s1").glob("*reexec*"))


def test_a_second_call_keeps_reruns_and_tops_up(folder, tmp_path, SPEC):
    res, _ = original(folder, tmp_path, SPEC)
    measure_folder(res, "demo", 1, ["d01"], times=2, provider=fake())
    assert measure_folder(res, "demo", 1, ["d01"], times=2, provider=fake())["made"] == 0
    assert measure_folder(res, "demo", 1, ["d01"], times=3, provider=fake())["made"] == 1


def test_a_replaced_run_moves_old_reruns_aside(folder, tmp_path, SPEC):
    res, run = original(folder, tmp_path, SPEC)
    measure_folder(res, "demo", 1, ["d01"], times=1, provider=fake())
    shutil.rmtree(run)
    original(folder, tmp_path, SPEC, answer_by="effect")   # another protocol: another chain head
    out = measure_folder(res, "demo", 1, ["d01"], times=1, provider=fake())
    assert out["made"] == 1 and (reexec_root(res, "demo", 1) / "d01.old-1").is_dir()


def test_missing_and_failing_runs_are_listed_and_the_rest_go_on(folder, tmp_path, SPEC, monkeypatch):
    res, _ = original(folder, tmp_path, SPEC)
    original(folder, tmp_path, SPEC, qid="d02")
    real = remeasure.reexec

    def flaky(run, **kw):
        if Path(run).name == "d02":
            raise RuntimeError("gateway down")
        return real(run, **kw)
    monkeypatch.setattr(remeasure, "reexec", flaky)
    out = measure_folder(res, "demo", 1, ["d01", "d02", "d03"], times=1, provider=fake())
    assert out["skipped"] == {"d03": "no complete run; run synth3 system-run first"}
    assert "gateway down" in out["failed"]["d02"] and out["questions"]["d01"]["reruns"] == 1


def test_a_run_without_calls_is_skipped_and_a_failing_measure_keeps_the_reruns(folder, tmp_path, SPEC, monkeypatch):
    res, _ = original(folder, tmp_path, SPEC)
    original(folder, tmp_path, SPEC, qid="d02")

    def boom(orig, reruns):
        if Path(orig).name == "d01":
            raise ValueError("no calls.jsonl in the run")
        return real(orig, reruns)
    real = remeasure.measure
    monkeypatch.setattr(remeasure, "measure", boom)
    out = measure_folder(res, "demo", 1, ["d01", "d02"], times=1, provider=fake())
    assert "no calls.jsonl" in out["skipped"]["d01"] and out["questions"]["d02"]["reruns"] == 1
    assert out["made"] == 2 and out["kept"] == 0
    assert len([p for p in (reexec_root(res, "demo", 1) / "d01").iterdir() if p.is_dir()]) == 1
    assert (reexec_root(res, "demo", 1) / "report.json").is_file()


def test_the_command(folder, tmp_path, spec_dir, monkeypatch, capsys):
    res, _ = original(folder, tmp_path, load_spec("demo", spec_dir), qid="d01")
    monkeypatch.setattr(replay_module, "default_provider", lambda alias: system_model(FACT_REPLY))
    args = ["reexec", "--domain", "demo", "--seed", "1", "--times", "1", "--questions", "d01",
            "--questions-root", str(FIX), "--spec-root", str(spec_dir), "--results", str(res)]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert out.startswith("Re-run measure: 1 runs x 1 re-runs, no cache") and "  d01: text same 1/1" in out
    unknown = [a if a != "d01" else "zz" for a in args]
    assert main(unknown) == 2
