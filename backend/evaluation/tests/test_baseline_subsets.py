"""A baseline's chance to answer "depends" (the subsets question): the mapping call of a question whose protocol has
`synthesis.moderators` asks for a verdict, the condition and the sides, and answer.json carries them as `conclusion`,
the engine's shape, so C scores every system against the same synth2 key."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from evaluation.baselines import common, rag
from evaluation.baselines.common import kind_params, map_prompt
from evaluation.score import score_answers
from modelcall import prompt_sha256
from synth2.corpus import Settings, build_base
from synth2.engine_answers import answer_form

from .test_rag import scripted

QID = "rag-factuality-subsets"
DEPENDS = {"verdict": "depends", "condition": "fact_rarity",
           "sides": [{"level": "rare", "effect": "supports"}, {"level": "common", "effect": "neutral"}],
           "untested": [], "studies": [{"document": "S001", "stance": "supports"}],
           "answer_text": "Retrieval helps on rare facts only."}
OVERALL = {"verdict": "supported", "condition": None, "sides": [], "untested": [],
           "studies": [{"document": "S001", "stance": "supports"}], "answer_text": "Retrieval helps."}


def test_the_subsets_question_gets_its_own_prompt_file_and_the_default_question_keeps_its_own() -> None:
    text, reply = map_prompt(kind_params(QID))
    assert common.MAP_SUBSETS == "map-effect-subsets-v1.md" and "<<" not in text
    for line in ("- fact_rarity (how often the asked fact appears in pre-training text): rare = rare-fact questions; "
                 "common = common-fact questions", "- model_size (", "- question_length ("):
        assert line in text
    assert "depends" in text and reply is not common.AnswerReply
    old, old_reply = map_prompt(None)
    assert old_reply is common.AnswerReply and common.MAP_PROMPTS["effect"] == "map-effect-v2.md"
    assert prompt_sha256(old, old_reply) == "e5df36a5b20b0bc513f9a27c515df74d8660a6a169c4bac9df2ad98f5df8b6d6"


def test_the_prompt_file_names_no_topic_word_of_its_own() -> None:
    raw = (common.PROMPTS / common.MAP_SUBSETS).read_text(encoding="utf-8")
    assert "retriev" not in raw.lower() and "rare" not in raw.lower() and "<<CONDITIONS>>" in raw


@pytest.mark.parametrize("bad", [
    {**DEPENDS, "condition": None},                                             # depends needs its condition
    {**DEPENDS, "sides": DEPENDS["sides"][:1]},                                 # and both of its levels
    {**DEPENDS, "sides": [{"level": "rare", "effect": "supports"}, {"level": "small", "effect": "neutral"}]},
    {**DEPENDS, "sides": [{"level": "rare", "effect": "supports"}, {"level": "common", "effect": "supports"}]},
    {**DEPENDS, "condition": "weather"},                                        # only a listed condition
    {**OVERALL, "condition": "fact_rarity"},                                    # one overall effect names none
    {**OVERALL, "sides": DEPENDS["sides"]},
    {**OVERALL, "untested": ["fact_rarity.tiny"]},                              # only a listed level
    {**OVERALL, "verdict": "mixed"},                                            # the key's answer space has no mixed
])
def test_a_reply_that_breaks_the_answer_form_is_refused(bad: dict[str, Any]) -> None:
    _, reply = map_prompt(kind_params(QID))
    reply.model_validate(DEPENDS)
    reply.model_validate(OVERALL)
    with pytest.raises(ValidationError):
        reply.model_validate(bad)


def test_the_mapped_answer_carries_the_conclusion_in_the_engines_shape() -> None:
    params = kind_params(QID)
    _, reply = map_prompt(params)
    answer = common.answer_json("x", params.question, reply.model_validate(DEPENDS), ["S001", "S002"],
                                protocol=params.protocol)
    assert answer["conclusion"] == {"verdict": "depends", "condition": "fact_rarity",
                                    "sides": {"rare": "supports", "common": "neutral"}, "untested": []}
    assert answer["label"] == "supported" == answer["label_by_rule"]   # depends has no label: the per-paper table's
    assert answer_form(answer) == {"verdict": "depends", "condition": "fact_rarity",
                                   "sides": {"rare": "helps", "common": "no_effect"}, "untested": []}
    overall = common.answer_json("x", params.question, reply.model_validate(
        {**OVERALL, "verdict": "refuted", "untested": ["model_size.large"]}), ["S001"], protocol=params.protocol)
    assert overall["label"] == "refuted"
    assert answer_form(overall) == {"verdict": "hurts", "condition": None, "sides": {},
                                    "untested": ["model_size.large"]}


def _depends_corpus(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    for seed in range(50):
        base = tmp_path / f"s{seed}"
        build_base(base, Settings("rag", seed, 12, "opposed", "table", exact=True))
        key = json.loads((base / "ground_truth.json").read_text(encoding="utf-8"))["key"]
        if key["verdict"] == "depends":
            return base, key
    raise AssertionError("no seed gives a depends key")


def test_a_baseline_that_says_depends_is_scored_right_against_the_key(tmp_path: Path) -> None:
    corpus, key = _depends_corpus(tmp_path)
    word = {"helps": "supports", "hurts": "contradicts", "no_effect": "neutral"}
    mapped = {**DEPENDS, "condition": key["condition"],
              "sides": [{"level": lv, "effect": word[w]} for lv, w in key["sides"].items()]}
    model = scripted(mapped=mapped, text="It depends.")
    answer = rag.rag_baseline(corpus, model=model.model(), question_id=QID, k=3, mode="global", max_chars=200)
    asked, mapping = model.prompts
    assert asked.startswith("Question: " + kind_params(QID).question)
    assert answer["question_id"] == QID and answer["conclusion"]["verdict"] == "depends"
    assert answer["mapping_call"]["prompt_sha256"] == prompt_sha256(*map_prompt(kind_params(QID)))
    path = tmp_path / "answer.json"
    path.write_text(json.dumps(answer), encoding="utf-8")
    c = score_answers(corpus, [path])["synthesis"][0]
    assert c["label_correct"] is True and (c["label"], c["expected_label"]) == ("depends", "depends")
    wrong = rag.rag_baseline(corpus, model=scripted(mapped=OVERALL, text="It helps.").model(), question_id=QID, k=3,
                             mode="global", max_chars=200)
    path.write_text(json.dumps(wrong), encoding="utf-8")
    c = score_answers(corpus, [path])["synthesis"][0]
    assert c["label_correct"] is False and c["key"]["given"]["verdict"] == "helps"


def test_an_empty_answer_to_the_subsets_question_is_insufficient(tmp_path: Path) -> None:
    corpus, _ = _depends_corpus(tmp_path)
    answer = rag.rag_baseline(corpus, model=scripted(text=" ").model(), question_id=QID, k=3, mode="global",
                              max_chars=200)
    assert answer["label"] == "insufficient" and answer["mapping_call"] is None
    assert answer_form(answer)["verdict"] == "insufficient"
