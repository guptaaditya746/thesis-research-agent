"""The word writer: counts, dedupe, and that it never sees papers."""
from __future__ import annotations

import json

import pytest

from evidence import steps
from evidence.steps import Step, configure
from evidence.words import write
from modelcall.cache import JsonlCache
from modelcall.dspy_lm import RecordedLM


@pytest.fixture
def lm(tmp_path, monkeypatch):
    """Fake model: names from `script[thing]` (a list of replies, one per call), cues from `script['cues']`."""
    script: dict[str, list[list[str]]] = {}
    prompts: list[str] = []

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        if '"cues"' in prompt:
            return json.dumps({"cues": script["cues"][0]})
        for thing, replies in script.items():
            if f"thing: {thing}" in prompt or f"{thing}\n" in prompt.split("thing")[-1][:80]:
                return json.dumps({"names": replies.pop(0)})
        raise AssertionError(prompt)

    configure(RecordedLM("orch-model", ask, cache=JsonlCache(tmp_path / "c.jsonl")))
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    script["cues"] = [["we show", "outperforms", "we conclude"]]
    return script, prompts


def test_names_kept_between_20_and_50(lm):
    script, _ = lm
    script["zeta"] = [[f"name{i}" for i in range(60)]]
    words = write.write_words("q?", ["zeta"])
    assert words.things["zeta"] == [f"name{i}" for i in range(50)]
    assert words.written_by == "orch-model"
    assert words.cues == ["we show", "outperforms", "we conclude"]


def test_short_reply_gets_one_retry_then_is_kept_and_recorded(lm):
    script, prompts = lm
    script["zeta"] = [[f"n{i}" for i in range(12)], [f"m{i}" for i in range(3)]]
    words, short = write.write_words_report("q?", ["zeta"])
    assert short == ["zeta"] and len(words.things["zeta"]) == 15
    assert sum('"names"' in p for p in prompts) == 2
    script["eta"] = [[f"n{i}" for i in range(12)], [f"m{i}" for i in range(10)]]
    words, short = write.write_words_report("q?", ["eta"])
    assert short == [] and len(words.things["eta"]) == 22


def test_names_deduped_case_folded(lm):
    script, _ = lm
    script["zeta"] = [["RAG", "rag", "Rag ", *[f"n{i}" for i in range(25)]]]
    names = write.write_words("q?", ["zeta"]).things["zeta"]
    assert names[0] == "RAG" and [n.casefold() for n in names].count("rag") == 1


def test_writer_never_sees_papers():
    assert list(write.WriteWords.input_fields) == ["question", "thing"]
    assert list(write.WriteCues.input_fields) == ["question"]
    assert set(write.WriteMoreWords.input_fields) == {"question", "thing", "already"}
