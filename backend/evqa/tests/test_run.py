"""S4 runner with stub steps: files per question, events with timing and LLM counts, resume, closed book, failures."""
from __future__ import annotations

import json
from pathlib import Path

import dspy
import pytest
import yaml

from evqa import corpus, lm
from evqa import run as runner
from evqa.contracts import Answer, FindHit, Name, Passage, Row, RunConfig, Spec, read_jsonl

QUESTIONS = [{"qid": f"Q{i}", "type": "lookup", "question": f"question {i}", "intent_card": []} for i in range(1, 5)]


class Sig(dspy.Signature):
    """Say hi."""
    x: str = dspy.InputField()
    y: str = dspy.OutputField()


def llm_call() -> None:
    """One recorded LM request made the way the steps make theirs."""
    m = lm.make_lm(RunConfig().llm, ask=lambda t: json.dumps({"y": "hi"}))
    with dspy.context(lm=m, adapter=dspy.JSONAdapter()):
        dspy.Predict(Sig)(x="a")


@pytest.fixture
def stubs(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "CACHE_FILE", tmp_path / "cache.jsonl")
    monkeypatch.setattr(lm, "_caches", {})
    monkeypatch.setattr(corpus, "questions", lambda domain, split: QUESTIONS)
    called: dict[str, list[str]] = {"spec": [], "find": [], "extract": [], "link": [], "answer": []}
    fail: set[str] = set()

    def spec(q, cfg):
        called["spec"].append(q["qid"])
        llm_call()
        return Spec(qid=q["qid"], question=q["question"], type="lookup", subjects=[Name(label="d")],
                    measure=Name(label="m")).seal()

    def find(spec, domain, cfg):
        called["find"].append(spec.qid)
        if spec.qid in fail:
            raise RuntimeError("find broke")
        return [FindHit(paper="P1", passages=[Passage(start=0, end=3, text="abc")])]

    def extract(spec, hits, domain, cfg, audit=None):
        called["extract"].append(spec.qid)
        return [Row(paper="P1", subject="d", measure="m", raw="-1", quote="abc")]

    def link(spec, rows, cfg):
        called["link"].append(spec.qid)
        return []

    def answer(spec, rows, links=None):
        called["answer"].append(spec.qid)
        return Answer(qid=spec.qid, type="lookup", not_reported=not rows)

    steps = {"spec": spec, "find": find, "extract": extract, "extract.links": link, "answer": answer}
    monkeypatch.setattr(runner, "_step", lambda name: steps[name])
    return called, fail


def events(folder: Path) -> list[dict]:
    return [json.loads(x) for x in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def test_run_writes_every_file_and_event(stubs, tmp_path) -> None:
    called, _ = stubs
    cfg = RunConfig(name="t", questions=["Q1", "Q3"])
    out = runner.run(cfg, root=tmp_path / "runs")
    assert out.name == cfg.run_id()
    assert RunConfig.model_validate(yaml.safe_load((out / "config.yaml").read_text())) == cfg
    for qid in ("Q1", "Q3"):
        assert Spec.model_validate_json((out / qid / "spec.json").read_text()).qid == qid
        assert len(read_jsonl(out / qid / "find.jsonl", FindHit)) == 1
        assert len(read_jsonl(out / qid / "rows.jsonl", Row)) == 1
        assert Answer.model_validate_json((out / qid / "answer.json").read_text()).not_reported is False
    assert not (out / "Q2").exists() and sorted(called["answer"]) == ["Q1", "Q3"]
    ev = events(out)
    ends = [e for e in ev if e["kind"] == "end" and e["step"] == "spec"]
    assert len(ends) == 2 and all(e["data"]["llm"]["requests"] == 1 and "seconds" in e["data"] for e in ends)
    assert sum(e["data"]["llm"].get("calls", 0) for e in ends) == 1      # same prompt: the second is a cache hit
    assert ev[-1]["step"] == "run" and ev[-1]["data"]["answered"] == 2 and ev[-1]["data"]["failed"] == []


def test_rerun_resumes_and_skips_done_steps(stubs, tmp_path) -> None:
    called, _ = stubs
    cfg = RunConfig(name="t")
    out = runner.run(cfg, root=tmp_path)
    (out / "Q2" / "answer.json").unlink()
    (out / "Q4" / "rows.jsonl").unlink()
    for v in called.values():
        v.clear()
    runner.run(cfg, root=tmp_path)
    assert called["spec"] == [] and called["find"] == [] and called["extract"] == ["Q4"]
    assert sorted(called["answer"]) == ["Q2", "Q4"]
    assert any(e["kind"] == "info" and e["data"]["skipped"] for e in events(out))


def test_closed_book_calls_no_find_and_answers_not_reported(stubs, tmp_path) -> None:
    called, _ = stubs
    out = runner.run(RunConfig(name="cb", closed_book=True, questions=["Q1"]), root=tmp_path)
    assert called["find"] == [] and called["extract"] == []
    assert (out / "Q1" / "find.jsonl").read_text() == ""
    assert Answer.model_validate_json((out / "Q1" / "answer.json").read_text()).not_reported


def test_a_failing_question_does_not_stop_the_others(stubs, tmp_path) -> None:
    called, fail = stubs
    fail.add("Q2")
    out = runner.run(RunConfig(name="f"), root=tmp_path)
    assert not (out / "Q2" / "find.jsonl").exists() and (out / "Q2" / "spec.json").exists()
    assert sorted(called["answer"]) == ["Q1", "Q3", "Q4"]
    ev = events(out)
    assert any(e["kind"] == "problem" and e["qid"] == "Q2" and "find broke" in e["data"]["error"] for e in ev)
    assert ev[-1]["data"]["failed"] == ["Q2"]


def test_unknown_question_id_is_refused(stubs, tmp_path) -> None:
    with pytest.raises(ValueError, match="Q9"):
        runner.run(RunConfig(name="x", questions=["Q9"]), root=tmp_path)


def test_cli_hook(stubs, tmp_path, monkeypatch) -> None:
    import argparse
    conf = tmp_path / "c.yaml"
    conf.write_text("name: cli\nquestions: [Q1]\n")
    monkeypatch.setattr(runner, "ROOT", tmp_path / "runs")
    parser = argparse.ArgumentParser()
    runner.add_cli(parser.add_subparsers())
    a = parser.parse_args(["run", "--config", str(conf)])
    assert a.fn(a) == 0
    assert (tmp_path / "runs" / RunConfig.load(conf).run_id() / "Q1" / "answer.json").is_file()


def test_steps_see_only_the_allowed_question_keys(stubs, tmp_path, monkeypatch) -> None:
    """Leak guard: a record carrying type, answerable, gold, why or closest facts reaches Spec stripped of them."""
    leaky = [{"qid": "Q1", "question": "question 1", "type": "near_miss", "answerable": False, "split": "test",
              "intent_text": "x", "why": "no paper", "near": ["R-1"], "template": "t", "gold": {"table": []},
              "intent_card": [{"point": "dose", "label": "dose", "ask": "Which dose?", "answer": "every dose",
                               "why": "leak"}]}]
    monkeypatch.setattr(corpus, "questions", lambda domain, split: leaky)
    seen: list[dict] = []
    real = runner._step

    def spy(name):
        fn = real(name)
        if name != "spec":
            return fn
        return lambda q, cfg: (seen.append(q), fn(q, cfg))[1]

    monkeypatch.setattr(runner, "_step", spy)
    runner.run(RunConfig(name="t"), root=tmp_path)
    assert seen and set(seen[0]) == set(corpus.QUESTION_KEYS)
    assert all(set(c) <= set(corpus.CARD_KEYS) for c in seen[0]["intent_card"])


def test_dataset_questions_carry_only_allowed_keys() -> None:
    for split in ("test", "practice"):
        for q in corpus.questions("medical", split):
            assert set(q) == set(corpus.QUESTION_KEYS)
            assert all(set(c) <= set(corpus.CARD_KEYS) for c in q["intent_card"])
