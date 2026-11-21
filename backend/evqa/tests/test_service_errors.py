"""A failed model service is not a bad reply: it is retried (lm.py), then fails the step; a bad reply is skipped."""
from __future__ import annotations

import http.client
import io
import json
import subprocess
import urllib.error
from types import SimpleNamespace

import dspy
import pytest
from dspy.utils.exceptions import AdapterParseError
from pydantic import ValidationError

from evqa import lm, slots
from evqa.contracts import Dimension, Row, RunConfig, Setting, SettingSet
from evqa.extract import links, settings_v2
from evqa.llm import LLMError, ServiceError, service_failed
from modelcall.dspy_lm import RecordedLM


def _http(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://x", code, "err", {}, io.BytesIO(b""))


@pytest.mark.parametrize("exc", [ConnectionRefusedError(), urllib.error.URLError("down"), TimeoutError(),
                                 http.client.RemoteDisconnected(), subprocess.TimeoutExpired("claude", 1),
                                 _http(503), _http(401), LLMError("claude failed: x"), ServiceError("no JSON")])
def test_service_failures(exc):
    assert service_failed(exc)


@pytest.mark.parametrize("exc", [ValueError("bad"), json.JSONDecodeError("x", "y", 0), _http(400), KeyError("rows")])
def test_reply_problems_are_not_service_failures(exc):
    assert not service_failed(exc)


def test_adapter_and_validation_errors_are_not_service_failures():
    with pytest.raises(ValidationError) as v:
        Row.model_validate({})
    assert not service_failed(v.value)
    assert not service_failed(AdapterParseError("JSONAdapter", dspy.Signature, "garbage"))


def test_dspy_passes_the_transport_error_through_unwrapped():
    def ask(text):
        raise ConnectionRefusedError(111, "refused")
    with pytest.raises(ConnectionRefusedError), dspy.context(lm=RecordedLM("f", ask), adapter=dspy.JSONAdapter()):
        dspy.Predict("q -> a")(q="hi")


def test_link_and_setting_steps_raise_on_a_failed_service():
    def ask(text):
        raise urllib.error.URLError("connection refused")
    dims = [Dimension(key="dose", question="Which dose?", why="")]
    sets = [SettingSet(id=f"P/s{i}", paper="P", settings=[Setting(dimension="dose", value=v)], label=v)
            for i, v in enumerate(["10 mg", "20 mg"])]
    with pytest.raises(urllib.error.URLError):
        links.judge(sets[0], sets[1], dims, "question", RecordedLM("f", ask), None)
    with pytest.raises(urllib.error.URLError):
        settings_v2.assign(Row(paper="P", subject="d", measure="m", raw="1", quote="q"), sets, "", RecordedLM("f", ask))


# ---------------------------------------------------------------- W2: retries in lm.py
class _Resp:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self.body).encode()


def _qwen_with(monkeypatch, outcomes):
    """qwen_ask whose urlopen gives `outcomes` in order (an exception is raised); returns (ask, sleeps, held)."""
    sleeps, held = [], []
    seq = iter(outcomes)

    def urlopen(*a, **k):
        o = next(seq)
        if isinstance(o, BaseException):
            raise o
        return _Resp(o)
    monkeypatch.setattr(lm.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(lm, "SLEEP", lambda s: (sleeps.append(s), held.append(lm.QWEN_SLOTS._value)))
    return lm.qwen_ask("m"), sleeps, held


def test_qwen_retries_transient_failures_with_growing_waits_and_no_slot_held(monkeypatch, tmp_path):
    monkeypatch.setattr(slots, "SLOT_DIR", tmp_path)
    ok = {"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}
    ask, sleeps, held = _qwen_with(monkeypatch, [ConnectionRefusedError(), _http(503), _http(429), ok])
    out = ask("q")
    assert out == "hi" and out.usage == {"prompt_tokens": 5, "completion_tokens": 2}
    assert len(sleeps) == 3 and sleeps[0] < sleeps[1] < sleeps[2]
    assert held == [slots.MAX_SLOTS_QWEN] * 3   # every in-process slot free while waiting


def test_qwen_gives_up_after_the_retries(monkeypatch, tmp_path):
    monkeypatch.setattr(slots, "SLOT_DIR", tmp_path)
    ask, sleeps, _ = _qwen_with(monkeypatch, [TimeoutError()] * (lm.RETRIES + 1))
    with pytest.raises(TimeoutError):
        ask("q")
    assert len(sleeps) == lm.RETRIES


def test_qwen_does_not_retry_other_4xx(monkeypatch, tmp_path):
    monkeypatch.setattr(slots, "SLOT_DIR", tmp_path)
    ask, sleeps, _ = _qwen_with(monkeypatch, [_http(401)])
    with pytest.raises(urllib.error.HTTPError):
        ask("q")
    assert sleeps == []


def test_claude_retries_a_timeout_and_non_json_and_reports_usage(monkeypatch, tmp_path):
    monkeypatch.setattr(slots, "SLOT_DIR", tmp_path)
    good = json.dumps({"result": "ok", "usage": {"input_tokens": 3, "cache_read_input_tokens": 10,
                                                 "output_tokens": 4}})
    outcomes = iter([subprocess.TimeoutExpired("claude", 1), SimpleNamespace(stdout="", stderr="boom", returncode=1),
                     SimpleNamespace(stdout=good, stderr="", returncode=0)])

    def run(*a, **k):
        o = next(outcomes)
        if isinstance(o, BaseException):
            raise o
        return o
    sleeps = []
    monkeypatch.setattr(lm.subprocess, "run", run)
    monkeypatch.setattr(lm, "SLEEP", sleeps.append)
    out = lm.claude_ask("m")("q")
    assert out == "ok" and out.usage == {"prompt_tokens": 13, "completion_tokens": 4} and len(sleeps) == 2


def test_claude_error_reply_is_not_retried(monkeypatch):
    monkeypatch.setattr(lm.subprocess, "run", lambda *a, **k: SimpleNamespace(
        stdout=json.dumps({"is_error": True, "result": "quota"})))
    monkeypatch.setattr(lm, "SLEEP", lambda s: pytest.fail("no retry"))
    with pytest.raises(RuntimeError, match="claude failed"):
        lm.claude_ask("m")("q")


# ---------------------------------------------------------------- W6 / W8 / W4 through make_lm
def test_qwen_slot_cap_is_separate(monkeypatch, tmp_path):
    import fcntl
    monkeypatch.setattr(slots, "MAX_SLOTS", 1)
    held = [(tmp_path / "slot-0.lock").open("a+")]
    fcntl.flock(held[0], fcntl.LOCK_EX | fcntl.LOCK_NB)
    with slots.model_slot(tmp_path, poll=0.005, limit=3) as index:   # Qwen limit above the shared cap
        assert index == 1
    held[0].close()


def test_token_usage_is_counted_and_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(lm, "CACHE_FILE", tmp_path / "cache.jsonl")
    monkeypatch.setattr(lm, "_caches", {})

    def ask(text):
        return lm._reply(json.dumps({"a": "x"}), {"prompt_tokens": 7, "completion_tokens": 3})
    for _ in range(2):   # the second call is a cache hit: no tokens counted
        with lm.counting("Q/step") as counts:
            m = lm.make_lm(RunConfig().llm, ask=ask)
            with dspy.context(lm=m, adapter=dspy.JSONAdapter()):
                assert dspy.Predict("q -> a")(q="hi").a == "x"
    assert counts["calls"] == 1 and counts["cache_hits"] == 1
    assert counts["prompt_tokens"] == 7 and counts["completion_tokens"] == 3
    record = json.loads((tmp_path / "cache.jsonl").read_text().splitlines()[0])["value"]
    assert record["usage"] == {"prompt_tokens": 7, "completion_tokens": 3} and record["output"] == '{"a": "x"}'


def test_model_revision_from_env_changes_the_key(monkeypatch, tmp_path):
    monkeypatch.setattr(lm, "CACHE_FILE", tmp_path / "cache.jsonl")
    monkeypatch.setattr(lm, "_caches", {})
    calls = []

    def ask(text):
        calls.append(text)
        return json.dumps({"a": "x"})

    def once():
        with dspy.context(lm=lm.make_lm(RunConfig().llm, ask=ask), adapter=dspy.JSONAdapter()):
            dspy.Predict("q -> a")(q="hi")
    monkeypatch.delenv("EVQA_MODEL_REVISION", raising=False)
    once()
    once()
    monkeypatch.setenv("EVQA_MODEL_REVISION", "weights-2026-11-20")
    once()
    assert len(calls) == 2
