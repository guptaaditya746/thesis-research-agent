"""Step: a DSPy signature run on the recorded gateway, with tuned instructions when a file exists."""
from __future__ import annotations

import json

import dspy
import pytest
from dspy.utils.exceptions import AdapterParseError

from evidence import steps
from evidence.steps import Step, configure
from modelcall.cache import JsonlCache
from modelcall.dspy_lm import RecordedLM


class EchoSig(dspy.Signature):
    """Echo the text."""
    text: str = dspy.InputField()
    echo: str = dspy.OutputField()


@pytest.fixture
def calls(tmp_path, monkeypatch):
    seen: list[str] = []

    def ask(prompt: str) -> str:
        seen.append(prompt)
        return '{"echo": "x"}'

    configure(RecordedLM("alias", ask, cache=JsonlCache(tmp_path / "calls.jsonl")))
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    return seen


def test_step_returns_prediction_and_second_call_is_cached(calls):
    step = Step(EchoSig, "echo")
    assert step(text="x").echo == "x"
    assert step(text="x").echo == "x"
    assert len(calls) == 1


def test_docstring_instructions_without_tuned_file(calls):
    Step(EchoSig, "echo")(text="x")
    assert "Echo the text." in calls[0]


def test_tuned_instructions_replace_the_docstring(calls, tmp_path):
    (tmp_path / "tuned").mkdir()
    (tmp_path / "tuned" / "echo.json").write_text(json.dumps({"instructions": "Repeat it back."}))
    Step(EchoSig, "echo")(text="x")
    assert "Repeat it back." in calls[0] and "Echo the text." not in calls[0]


def test_step_without_configure_fails_clearly(monkeypatch):
    monkeypatch.setattr(steps, "_LM", None)
    with pytest.raises(RuntimeError, match="configure"):
        Step(EchoSig, "echo")(text="x")


def _replies(tmp_path, monkeypatch, replies):
    seen: list[str] = []
    it = iter(replies)

    def ask(prompt: str) -> str:
        seen.append(prompt)
        return next(it)

    def lm():
        return RecordedLM("alias", ask, cache=JsonlCache(tmp_path / "calls.jsonl"))

    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    return seen, lm


def test_bad_reply_is_retried_and_replays_with_no_calls(tmp_path, monkeypatch):
    seen, lm = _replies(tmp_path, monkeypatch, ["not json {", '{"echo": "x"}'])
    configure(lm())
    assert Step(EchoSig, "echo")(text="x").echo == "x"
    assert len(seen) == 2
    configure(lm())
    assert Step(EchoSig, "echo")(text="x").echo == "x"
    assert len(seen) == 2


def test_three_bad_replies_raise_after_three_calls(tmp_path, monkeypatch):
    seen, lm = _replies(tmp_path, monkeypatch, ["bad {"] * 5)
    configure(lm())
    with pytest.raises(AdapterParseError):
        Step(EchoSig, "echo")(text="x")
    assert len(seen) == 3
