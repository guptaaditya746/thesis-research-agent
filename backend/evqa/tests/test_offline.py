"""EVQA_OFFLINE=1: a cache hit answers, a cache miss raises OfflineCacheMiss (a service failure: the step stops and
the question is logged as a problem, never skipped as a bad reply)."""
from __future__ import annotations

import json

import dspy
import pytest

from evqa import corpus, lm
from evqa import run as runner
from evqa.contracts import Dimension, Name, RunConfig, Setting, SettingSet, Spec
from evqa.extract import links
from evqa.llm import ServiceError, service_failed

Q = [{"qid": "Q1", "type": "lookup", "question": "question 1", "intent_card": []}]


class Sig(dspy.Signature):
    """Say hi."""
    x: str = dspy.InputField()
    y: str = dspy.OutputField()


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "CACHE_FILE", tmp_path / "cache.jsonl")
    monkeypatch.setattr(lm, "_caches", {})
    calls: list[str] = []

    def ask(text):
        calls.append(text)
        return json.dumps({"y": "hi"})

    def predict(x: str):
        with dspy.context(lm=lm.make_lm(RunConfig().llm, ask=ask), adapter=dspy.JSONAdapter()):
            return dspy.Predict(Sig)(x=x).y
    return predict, calls


def test_offline_hit_answers_and_miss_raises(cache, monkeypatch) -> None:
    predict, calls = cache
    assert predict("cached") == "hi" and len(calls) == 1      # online: recorded
    monkeypatch.setenv("EVQA_OFFLINE", "1")
    assert predict("cached") == "hi" and len(calls) == 1      # offline hit: no model call
    with lm.counting("Q1/spec"), pytest.raises(lm.OfflineCacheMiss, match=r"^Q1/spec key [0-9a-f]{12}$"):
        predict("not cached")
    assert len(calls) == 1
    assert issubclass(lm.OfflineCacheMiss, ServiceError) and service_failed(lm.OfflineCacheMiss("x"))


def test_offline_miss_is_not_skipped_by_a_step(cache, monkeypatch) -> None:
    monkeypatch.setenv("EVQA_OFFLINE", "1")
    dims = [Dimension(key="dose", question="Which dose?", why="")]
    sets = [SettingSet(id=f"P/s{i}", paper="P", settings=[Setting(dimension="dose", value=v)], label=v)
            for i, v in enumerate(["10 mg", "20 mg"])]
    m = lm.make_lm(RunConfig().llm, ask=lambda t: pytest.fail("offline must not call the model"))
    with pytest.raises(lm.OfflineCacheMiss):
        links.judge(sets[0], sets[1], dims, "question", m, None)


def test_run_question_offline_logs_a_problem_not_a_skip(cache, tmp_path, monkeypatch) -> None:
    predict, _ = cache
    monkeypatch.setenv("EVQA_OFFLINE", "1")
    monkeypatch.setattr(corpus, "questions", lambda domain, split: Q)

    def spec(q, cfg):
        predict("never recorded")
        return Spec(qid=q["qid"], question=q["question"], type="lookup", subjects=[Name(label="d")],
                    measure=Name(label="m")).seal()
    monkeypatch.setattr(runner, "_step", lambda name: {"spec": spec}.get(name) or pytest.fail(name))
    out = runner.run(RunConfig(name="off"), root=tmp_path / "runs")
    ev = [json.loads(x) for x in (out / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    problem = [e for e in ev if e["kind"] == "problem" and e["qid"] == "Q1"]
    assert len(problem) == 1 and problem[0]["data"]["error"].startswith("OfflineCacheMiss: Q1/spec key ")
    assert not any(e["data"].get("skipped") for e in ev if e.get("qid") == "Q1")
    assert not (out / "Q1" / "spec.json").exists() and ev[-1]["data"]["failed"] == ["Q1"]
