"""synth3.baseline: the RAG baseline on every question, saved in the judge's shape; fakes only."""
from pathlib import Path

import modelcall.gateway
from evaluation.tests.helpers import guard_corpus
from evaluation.tests.test_rag import scripted as rag_scripted
from modelcall import JsonlCache
from synth3.answers import load_answers
from synth3.baseline import baseline_folder
from synth3.cli import main
from synth3.questions import load_questions
from synth3.sheetfacts import load_folder
from synth3.tests.fakes import failing

FIX = Path(__file__).parent / "fixtures" / "questions"


def test_every_question_gets_a_baseline_record(folder, tmp_path, SPEC, monkeypatch):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX)   # the truth is read before the guard
    attempts = guard_corpus(monkeypatch, folder)
    out = baseline_folder(f, qs, rag_scripted(text="Targeted therapy helps (S001).").model(), "fake",
                          JsonlCache(tmp_path / "c.jsonl"), tmp_path / "res")
    assert out == {"answered": 3, "skipped": 0, "failed": {}} and attempts == []
    recs = load_answers(tmp_path / "res", "demo")
    assert [r.question_id for r in recs] == ["d01", "d02", "d03"] and all(r.system == "rag-baseline" for r in recs)
    assert recs[0].text == "Targeted therapy helps (S001)." and recs[0].passages and recs[0].facts is None
    assert (tmp_path / "res" / "demo" / "s1" / "rag-baseline" / "d01" / "answer.json").is_file()


def test_a_second_run_skips_answered_questions(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); c = JsonlCache(tmp_path / "c.jsonl")
    baseline_folder(f, qs, rag_scripted().model(), "fake", c, tmp_path / "res")
    assert baseline_folder(f, qs, rag_scripted().model(), "fake", c, tmp_path / "res")["skipped"] == 3


def test_a_failing_call_is_listed_and_the_rest_go_on(folder, tmp_path, SPEC):
    out = baseline_folder(load_folder(folder), load_questions("demo", SPEC, FIX), failing(), "fake",
                          JsonlCache(tmp_path / "c.jsonl"), tmp_path / "res")
    assert set(out["failed"]) == {"d01", "d02", "d03"} and out["answered"] == 0


def test_baseline_by_command(folder, tmp_path, spec_dir, monkeypatch, capsys):
    monkeypatch.setattr(modelcall.gateway, "openai_model", lambda alias: rag_scripted(text="An answer.").model())
    res = tmp_path / "res"
    code = main(["baseline", "--domain", "demo", "--folders", str(folder.parent), "--seeds", "1",
                 "--spec-root", str(spec_dir), "--questions-root", str(FIX), "--results", str(res)])
    assert code == 0 and len(load_answers(res, "demo")) == 3
    assert "s1: answered 3, skipped 0, failed 0" in capsys.readouterr().out
