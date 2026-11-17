"""synth3.baseline: the RAG baseline on every question, saved in the judge's shape; fakes only."""
from pathlib import Path

import modelcall.gateway
from evaluation.tests.helpers import guard_corpus
from evaluation.tests.test_rag import scripted as rag_scripted
from modelcall import JsonlCache
from synth3 import baseline as baseline_mod
from synth3.answers import load_answers, save_answer
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
    second = rag_scripted()
    assert baseline_folder(f, qs, second.model(), "fake", c, tmp_path / "res")["skipped"] == 3
    assert second.prompts == []   # no model call
    changed = qs.model_copy(update={"questions": [qs.questions[0].model_copy(update={"question": "Other?"}),
                                                  *qs.questions[1:]]})
    third = baseline_folder(f, changed, rag_scripted().model(), "fake", c, tmp_path / "res")
    assert third["answered"] == 1 and third["skipped"] == 2   # the changed question is asked again


def test_an_answer_from_another_folder_is_asked_again(folder, tmp_path, SPEC):
    """After the template folder set is replaced by the `-real` one, every saved answer is of another corpus."""
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); c = JsonlCache(tmp_path / "c.jsonl")
    baseline_folder(f, qs, rag_scripted().model(), "fake", c, tmp_path / "res")
    for r in load_answers(tmp_path / "res", "demo"):
        save_answer(tmp_path / "res", r.model_copy(update={"corpus_id": "demo-template"}))
    out = baseline_folder(f, qs, rag_scripted().model(), "fake", c, tmp_path / "res")
    assert out["answered"] == 3 and out["skipped"] == 0
    assert all(r.corpus_id == f.corpus_id for r in load_answers(tmp_path / "res", "demo"))


def test_a_failing_call_is_listed_and_the_rest_go_on(folder, tmp_path, SPEC):
    out = baseline_folder(load_folder(folder), load_questions("demo", SPEC, FIX), failing(), "fake",
                          JsonlCache(tmp_path / "c.jsonl"), tmp_path / "res")
    assert set(out["failed"]) == {"d01", "d02", "d03"} and out["answered"] == 0
    assert all(why.startswith(f"{qid} s1: ") for qid, why in out["failed"].items())


def test_a_bad_citation_is_listed_and_the_rest_go_on(folder, tmp_path, SPEC, monkeypatch):
    real = baseline_mod.from_rag_answer

    def maybe_bad(answer, folder, q, source):
        if q.id == "d02":
            raise ValueError(f"{source}: cites S999, which is not a paper of the folder")
        return real(answer, folder, q, source)

    monkeypatch.setattr(baseline_mod, "from_rag_answer", maybe_bad)
    out = baseline_folder(load_folder(folder), load_questions("demo", SPEC, FIX), rag_scripted().model(), "fake",
                          JsonlCache(tmp_path / "c.jsonl"), tmp_path / "res")
    assert out["answered"] == 2 and list(out["failed"]) == ["d02"]
    assert out["failed"]["d02"].startswith("d02 s1: ") and "S999" in out["failed"]["d02"]
    assert not (tmp_path / "res" / "demo" / "s1" / "rag-baseline" / "d02.answer.json").exists()


def test_a_failed_question_by_command_exits_1_with_a_failed_line(folder, tmp_path, spec_dir, monkeypatch, capsys):
    monkeypatch.setattr(modelcall.gateway, "openai_model", lambda alias: failing())
    code = main(["baseline", "--domain", "demo", "--folders", str(folder.parent), "--seeds", "1",
                 "--spec-root", str(spec_dir), "--questions-root", str(FIX), "--results", str(tmp_path / "res")])
    out = capsys.readouterr().out
    assert code == 1 and "s1: answered 0, skipped 0, failed 3" in out and "  failed: d01 s1: " in out


def test_baseline_by_command(folder, tmp_path, spec_dir, monkeypatch, capsys):
    monkeypatch.setattr(modelcall.gateway, "openai_model", lambda alias: rag_scripted(text="An answer.").model())
    res = tmp_path / "res"
    code = main(["baseline", "--domain", "demo", "--folders", str(folder.parent), "--seeds", "1",
                 "--spec-root", str(spec_dir), "--questions-root", str(FIX), "--results", str(res)])
    assert code == 0 and len(load_answers(res, "demo")) == 3
    assert "s1: answered 3, skipped 0, failed 0" in capsys.readouterr().out
