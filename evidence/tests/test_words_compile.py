"""Word list -> extractor config."""
from __future__ import annotations

import re

from evidence.pack import load_pack
from evidence.plan import WordList
from evidence.words.compile import compile_words

NAMES = [f"alpha {i}" for i in range(20)]


def words(**things: list[str]) -> WordList:
    return WordList(things=things, cues=["we show", "outperforms"], written_by="orch-model", ontology_names={})


def hits(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


def test_word_boundaries():
    config = compile_words(words(rag=["RAG", "retrieval"]))
    pattern = config["conditions"]["rag"][0]
    assert hits(pattern, "we use RAG here") and not hits(pattern, "a fRAGment")
    assert not hits(pattern, "retrievals")


def test_acronym_case():
    pattern = compile_words(words(nlp=["NLP", "language processing"]))["conditions"]["nlp"][0]
    assert hits(pattern, "NLP tools") and not hits(pattern, "nlp tools")
    assert hits(pattern, "Language   Processing")


def test_ontology_names_included():
    wl = WordList(things={"t": ["alpha"]}, cues=[], written_by="orch-model", ontology_names={"t": ["beta gamma", "ALPHA"]})
    config = compile_words(wl)
    assert hits(config["conditions"]["t"][0], "a beta gamma thing")
    assert config["screen_terms"] == ["alpha", "beta gamma"]


def test_controls_get_not_a_system_and_cues_compile():
    config = compile_words(words(a=["aa"], b=["bb"]))
    assert not config["conditions"]["a"][0].endswith(config["not_a_system"])
    assert config["conditions"]["b"][0].endswith(config["not_a_system"])
    assert not hits(config["conditions"]["b"][0], "bb errors")
    assert hits(config["claims"][0][0], "We show that") and hits(config["subject"], "bb")


def test_metric_things():
    config = compile_words(words(a=["aa"], acc=["accuracy"]), metric_things={"acc"})
    assert config["metrics"] == [[config["metrics"][0][0], "acc", True]] and "acc" not in config["conditions"]


def test_same_config_keys_as_pack():
    pack = load_pack("rag")
    pack_keys = set()
    for etype, extractor in (("condition", "regex_condition"), ("metric", "regex_metric"), ("author_claim", "regex_author_claim")):
        pack_keys |= set(pack.extractor_config(etype, extractor))
    assert set(compile_words(words(a=["aa"]))) - {"screen_terms"} == pack_keys
