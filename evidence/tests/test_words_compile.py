"""Word list -> extractor config."""
from __future__ import annotations

import re

import jsonschema

from agent.anchor import Index
from evidence import protocol
from evidence.calls import EngineContext
from evidence.contract import DocumentRef, ExtractionTask, ProtocolRef
from evidence.pack import load_pack, protocol_path
from evidence import extractors
from evidence.plan import WordList
from evidence.words.compile import compile_words

NAMES = [f"alpha {i}" for i in range(20)]


def words(**things: list[str]) -> WordList:
    return WordList(things=things, cues=["improves: we show", "improves: outperforms", "worsens: hurts", "no_effect: no difference", "stray cue"], written_by="orch-model", ontology_names={})


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
    assert [d for _, d in config["claims"]] == ["no_effect", "worsens", "improves"]
    assert hits(config["claims"][2][0], "We show that") and hits(config["subject"], "bb")
    assert not any(hits(p, "stray cue") for p, _ in config["claims"])


def test_metric_things():
    config = compile_words(words(a=["aa"], acc=["accuracy"]), metric_things={"acc"})
    assert config["metrics"] == [[config["metrics"][0][0], "acc", True]] and "acc" not in config["conditions"]


def test_same_config_keys_as_pack():
    pack = load_pack("rag")
    pack_keys = set()
    for etype, extractor in (("condition", "regex_condition"), ("metric", "regex_metric"), ("author_claim", "regex_author_claim")):
        pack_keys |= set(pack.extractor_config(etype, extractor))
    assert set(compile_words(words(a=["aa"]))) - {"screen_terms"} == pack_keys


def test_empty_word_list_matches_no_subject():
    assert not hits(compile_words(words())["subject"], "any sentence")


def test_compiled_claims_pass_the_author_claim_schema_through_the_extractor():
    spec = protocol.load(protocol_path("rag", "cons-accuracy")).evidence_types["author_claim"]
    config = compile_words(words(a=["aa"]))
    config = {k: config[k] for k in ("subject", "claims")} | {"evidence_type": "author_claim",
              "field_schema": spec.fields, "roles": list(spec.roles)}
    text = "# T\n\n## Conclusion\n\nWe show that aa works well in practice.\n"
    task = ExtractionTask(protocol=ProtocolRef(id="x", sha256="0" * 64), evidence_type="author_claim",
                          field_schema_sha256="x", document=DocumentRef(id="P", file="papers/P.md", sha256="0" * 64))
    from agent.anchor import text_sha256
    task = task.model_copy(update={"document": task.document.model_copy(update={"sha256": text_sha256(text)})})
    result = extractors.get("regex_author_claim", config).extract(task, EngineContext(text, Index(text), [], {}, None))
    assert [i.fields for i in result.items] == [{"direction": "improves"}]
    for i in result.items:
        jsonschema.validate(i.fields, spec.fields)
