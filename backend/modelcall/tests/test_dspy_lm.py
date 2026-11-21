"""RecordedLM: every DSPy call goes through the recorder, so a rerun makes no new model call."""
from __future__ import annotations

import json

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


def test_keys_without_model_revision_are_the_old_keys_and_a_revision_makes_new_ones(tmp_path):
    cache = JsonlCache(tmp_path / "calls.jsonl")
    _run(RecordedLM("qwen:orch-model:nothink", lambda p: '{"echo": "x"}', cache=cache), "x")
    row = json.loads((tmp_path / "calls.jsonl").read_text().splitlines()[0])
    value = row["value"]
    # the key the code made before model_revision existed (computed with that code; DSPy pinned by uv.lock)
    assert row["key"] == "d7c628bc9057a874952d921eaeb4c18ab6762ff726f08fea0ae8a14d021f5623"
    assert "usage" not in value   # a plain-str fake reports no usage
    calls = []
    lm = RecordedLM("qwen:orch-model:nothink", lambda p: calls.append(p) or '{"echo": "x"}', cache=cache,
                    model_revision="sha-abc")
    _run(lm, "x")
    _run(lm, "x")
    assert len(calls) == 1   # new weights: asked once, then cached under the new key


def test_usage_of_a_reply_is_stored_but_not_in_the_text_or_key(tmp_path):
    class Reply(str):
        usage = {"prompt_tokens": 9, "completion_tokens": 1}
    cache = JsonlCache(tmp_path / "calls.jsonl")
    plain = JsonlCache(tmp_path / "plain.jsonl")
    _run(RecordedLM("alias", lambda p: Reply('{"echo": "x"}'), cache=cache), "x")
    _run(RecordedLM("alias", lambda p: '{"echo": "x"}', cache=plain), "x")
    a = json.loads((tmp_path / "calls.jsonl").read_text())
    b = json.loads((tmp_path / "plain.jsonl").read_text())
    assert a["key"] == b["key"] and a["value"]["output"] == b["value"]["output"] == '{"echo": "x"}'
    assert a["value"]["usage"] == {"prompt_tokens": 9, "completion_tokens": 1}
    out = RecordedLM("alias", lambda p: "unused", cache=JsonlCache(tmp_path / "calls.jsonl")).forward(
        messages=a["value"]["messages"])
    assert out.cache_hit and out.usage == {"prompt_tokens": 9, "completion_tokens": 1}
