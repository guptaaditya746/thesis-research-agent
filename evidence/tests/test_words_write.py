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
        if "no_effect" in prompt:
            return json.dumps(script["cues"])
        for thing, replies in script.items():
            if f"thing: {thing}" in prompt or f"{thing}\n" in prompt.split("thing")[-1][:80]:
                return json.dumps({"names": replies.pop(0)})
        raise AssertionError(prompt)

    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    script["cues"] = {"improves": ["we show", "outperforms"], "worsens": ["hurts"], "no_effect": ["no difference"]}
    lm = RecordedLM("orch-model", ask, cache=JsonlCache(tmp_path / "c.jsonl"))
    return script, prompts, lm


def test_names_kept_between_20_and_50(lm):
    script, _, model = lm
    script["zeta"] = [[f"name{i}" for i in range(60)]]
    words = write.write_words("q?", lm=model, things=["zeta"])
    assert words.things["zeta"] == [f"name{i}" for i in range(50)]
    assert words.written_by == "orch-model"
    assert words.cues == ["no_effect: no difference", "worsens: hurts", "improves: we show", "improves: outperforms"]


def test_short_reply_gets_one_retry_then_is_kept_and_recorded(lm):
    script, prompts, model = lm
    script["zeta"] = [[f"n{i}" for i in range(12)], [f"m{i}" for i in range(3)]]
    words, short = write.write_words_report("q?", lm=model, things=["zeta"])
    assert short == ["zeta"] and len(words.things["zeta"]) == 15
    assert sum('"names"' in p for p in prompts) == 2
    script["eta"] = [[f"n{i}" for i in range(12)], [f"m{i}" for i in range(10)]]
    words, short = write.write_words_report("q?", lm=model, things=["eta"])
    assert short == [] and len(words.things["eta"]) == 22


def test_names_deduped_case_folded(lm):
    script, _, model = lm
    script["zeta"] = [["RAG", "rag", "Rag ", *[f"n{i}" for i in range(25)]]]
    names = write.write_words("q?", lm=model, things=["zeta"]).things["zeta"]
    assert names[0] == "RAG" and [n.casefold() for n in names].count("rag") == 1


def test_writer_never_sees_papers():
    assert list(write.WriteWords.input_fields) == ["question", "thing"]
    assert list(write.WriteCues.input_fields) == ["question"]
    assert set(write.WriteMoreWords.input_fields) == {"question", "thing", "already"}


def test_refuses_a_model_that_is_not_the_pinned_alias(lm):
    script, _, _ = lm
    claude = RecordedLM("claude-haiku", lambda prompt: "{}")
    with pytest.raises(ValueError, match="orch-model"):
        write.write_words("q?", lm=claude, things=["zeta"])


def test_the_word_list_records_the_tuned_writer_it_was_written_with(lm, tmp_path):
    """Runs review I2: which tuned instructions wrote the list is in the plan (`words.tuned_sha256`), at plan time."""
    import hashlib

    from evidence.plan import WordList
    script, _, model = lm
    script["zeta"] = [[f"name{i}" for i in range(30)]]
    assert write.write_words("q?", lm=model, things=["zeta"]).tuned_sha256 == {}
    assert "tuned_sha256" not in WordList(things={}, cues=[], written_by="x", ontology_names={}).model_dump_json()
    (tmp_path / "tuned").mkdir()
    (tmp_path / "tuned" / "write_words.json").write_text('{"instructions": "Write names."}', encoding="utf-8")
    script["zeta"] = [[f"name{i}" for i in range(30)]]
    words = write.write_words("q?", lm=model, things=["zeta"])
    assert words.tuned_sha256 == {"write_words": hashlib.sha256((tmp_path / "tuned" / "write_words.json").read_bytes()).hexdigest()}
    assert WordList.model_validate_json(words.model_dump_json()) == words
