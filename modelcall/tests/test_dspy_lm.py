"""RecordedLM: every DSPy call goes through the recorder, so a rerun makes no new model call."""
from __future__ import annotations

import dspy

from modelcall.cache import JsonlCache
from modelcall.dspy_lm import RecordedLM


class Sig(dspy.Signature):
    """Echo the text."""
    text: str = dspy.InputField()
    echo: str = dspy.OutputField()


def _run(lm: RecordedLM, text: str) -> str:
    with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
        return dspy.Predict(Sig)(text=text).echo


def test_call_goes_through_ask_and_returns_its_json():
    seen: list[str] = []

    def ask(prompt: str) -> str:
        seen.append(prompt)
        return '{"echo": "x"}'

    assert _run(RecordedLM("alias", ask), "x") == "x"
    assert len(seen) == 1 and "Echo the text." in seen[0] and "x" in seen[0]


def test_second_identical_call_is_served_from_the_cache(tmp_path):
    calls: list[str] = []
    cache = JsonlCache(tmp_path / "calls.jsonl")

    def ask(prompt: str) -> str:
        calls.append(prompt)
        return '{"echo": "x"}'

    lm = RecordedLM("alias", ask, cache=cache)
    assert _run(lm, "x") == "x" and _run(lm, "x") == "x"
    assert len(calls) == 1
    # A fresh process (new LM, same file) replays with zero model calls.
    assert _run(RecordedLM("alias", ask, cache=JsonlCache(tmp_path / "calls.jsonl")), "x") == "x"
    assert len(calls) == 1
    # A different input, or a different alias, is a different call.
    _run(lm, "y")
    _run(RecordedLM("other", ask, cache=cache), "x")
    assert len(calls) == 3


def test_dspy_own_cache_is_off():
    assert RecordedLM("alias", lambda p: '{"echo": "x"}').cache is False
