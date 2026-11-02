"""The baselines answer chaining, limitations and builds_on (plan 2 Task 14): their mapping prompts and reply models,
answer.json in the engine kind's shape (influence computed from the followers, never asked), and the effect mapping
prompt filled from the pack (no topic words in it). Drug questions resolve through their own pack's questions file
(preflight P19)."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from evaluation.baselines import common
from evaluation.baselines.common import kind_params, map_prompt
from evaluation.baselines.rag import SYSTEM, rag_baseline
from evaluation.canon import Canon
from evaluation.score import score_chaining
from evidence import contract

from .helpers import Scripted, guard_corpus

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "evidence" / "tests" / "fixtures"
QUESTION_IDS = {"effect": "drugtoy-response", "chaining": "drug-chain-zel-mor", "limitations": "drug-limits",
                "builds_on": "drug-builds-on"}
PASSAGES = "\n\nPassages:\n\n"
CITED = {"answer_text": "S001 compares Zelvora with Quintapride; S002 compares Quintapride with Morvectin.",
         "citations": []}
PAPERS = {"S001": "# Zelvora against Quintapride\n\nZelvora reached a response rate of 0.40, Quintapride 0.30.\n",
          "S002": "# Quintapride against Morvectin\n\nQuintapride reached a response rate of 0.35, Morvectin 0.25.\n"}


@pytest.fixture(autouse=True)
def _registry() -> Iterator[None]:
    """Each test leaves the evidence-type registry as it found it (loading a drugtoy protocol registers its types)."""
    before = dict(contract.ITEM_PREFIX)
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


def params_for(kind: str, pack: str = "drugtoy") -> common.KindParams:
    return kind_params(QUESTION_IDS[kind], questions=FIXTURES / pack / "questions.yaml")


def write_drug_corpus(root: Path) -> Path:
    """manifest.json and papers/ of two toy drug papers, plus a ground_truth.json no system may open."""
    corpus = root / "drug-corpus"
    (corpus / "papers").mkdir(parents=True)
    entries = []
    for pid, text in PAPERS.items():
        data = text.encode("utf-8")
        (corpus / "papers" / f"{pid}.md").write_bytes(data)
        entries.append({"id": pid, "file": f"papers/{pid}.md", "sha256": hashlib.sha256(data).hexdigest()})
    (corpus / "manifest.json").write_text(json.dumps({"corpus_id": "drug-corpus", "papers": entries}), encoding="utf-8")
    (corpus / "ground_truth.json").write_text("{}", encoding="utf-8")
    return corpus


def two_calls(mapped: dict[str, Any]) -> Scripted:
    """The answering call (its prompt lists passages) gets CITED; the mapping call gets `mapped`."""
    return Scripted(lambda prompt: CITED if PASSAGES in prompt else mapped)


def chain_reply() -> dict[str, Any]:
    return {"verdict": "better", "via": ["Quintapride"], "papers": ["S002", "S001", "S404"], "inferred": True}


# --- the brief's tests ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["chaining", "limitations", "builds_on"])
def test_map_prompt_is_filled_and_reply_shaped(kind):
    text, reply = map_prompt(params_for(kind))
    assert "<<" not in text and reply.model_json_schema()


def test_effect_map_prompt_has_no_rag_words():
    """P18: the drugtoy pack's display names fill the prompt, so Zelvora is in it; no RAG word is."""
    text, _ = map_prompt(params_for("effect", pack="drugtoy"))
    assert "retrieval" not in text.lower() and "Zelvora" in text and "placebo" in text
    assert "response rate" in text


def test_limitation_category_outside_pack_list_fails_validation():
    _, reply = map_prompt(params_for("limitations"))
    with pytest.raises(ValidationError):
        reply.model_validate({"entries": [{"thing": "Zelvora", "category": "weather", "papers": []}]})
    assert reply.model_validate({"entries": [{"thing": None, "category": "cost", "papers": []}]})


def test_baseline_chaining_answer_scores_like_engine(tmp_path, monkeypatch):
    corpus = write_drug_corpus(tmp_path)
    guard_corpus(monkeypatch, corpus)
    a = rag_baseline(corpus, model=two_calls(chain_reply()).model(), question_id="drug-chain-zel-mor",
                     questions=FIXTURES / "drugtoy" / "questions.yaml")
    assert a["kind"] == "chaining" and "verdict" in a
    assert (a["source"], a["target"], a["metric"]) == ("Zelvora", "Morvectin", "response_rate")
    assert a["verdict"] == "better" and a["inferred"] is True and a["via"] == ["Quintapride"]
    assert a["studies"] == ["S001", "S002"] and a["dropped"] == ["S404"] and a["system"] == SYSTEM
    exp = {"source": "Zelvora", "target": "Morvectin", "metric": "response_rate", "verdict": "better",
           "inferred": True, "via": ["Quintapride"], "studies": ["S001", "S002"], "reason": None}
    assert score_chaining(exp, a, Canon.from_truth(None))["headline"] == 1.0   # the engine's scorer reads it as is


# --- shapes of the new kinds --------------------------------------------------------------------------------------

def test_the_rag_baseline_has_its_spec_name():
    assert SYSTEM == "bm25-answer-baseline"


def test_limitations_answer_has_the_kind_shape():
    params = params_for("limitations")
    _, reply_type = map_prompt(params)
    reply = reply_type.model_validate({"entries": [
        {"thing": "Zelvora", "category": "cost", "papers": ["S002"]},
        {"thing": "zelvora ", "category": "cost", "papers": ["S001", "S9"]},
        {"thing": "Zelvora", "category": "small_sample", "papers": ["S001"]},
        {"thing": None, "category": "side_effects", "papers": ["S002"]}]})
    a = common.kind_answer_json(SYSTEM, params, reply, ["S001", "S002"])
    assert a["kind"] == "limitations" and a["thing"] is None and a["dropped"] == ["S9"]
    assert a["entries"] == [
        {"thing": "Zelvora", "category": "small_sample", "papers": ["S001"], "items": []},
        {"thing": "Zelvora", "category": "cost", "papers": ["S001", "S002"], "items": []},
        {"thing": None, "category": "side_effects", "papers": ["S002"], "items": []}]
    assert a["counts"] == {"Zelvora": {"small_sample": 1, "cost": 2}} and a["unlinked"] == {"side_effects": 1}


def test_builds_on_influence_is_computed_from_followers_not_asked():
    params = params_for("builds_on")
    text, reply_type = map_prompt(params)
    assert set(reply_type.model_fields) == {"links", "followers"}   # no influence or ranking asked of the model
    reply = reply_type.model_validate({
        "links": [{"from": "S002", "to": "S001", "reuses": "method"},
                  {"from": "S003", "to": "S001", "reuses": "dataset"}],
        "followers": [{"thing": "Zelvora", "papers": ["S003", "S002"]}, {"thing": "Morvectin", "papers": ["S003"]}]})
    a = common.kind_answer_json(SYSTEM, params, reply, ["S001", "S002", "S003"])
    assert a["kind"] == "builds_on" and a["links"] == [
        {"from": "S002", "to": "S001", "reuses": "method", "items": []},
        {"from": "S003", "to": "S001", "reuses": "dataset", "items": []}]
    assert a["followers"] == {"Zelvora": ["S002", "S003"], "Morvectin": ["S003"]}
    assert a["influence"] == {"Zelvora": 2, "Morvectin": 1} and a["ranking"] == ["Zelvora", "Morvectin"]
    with pytest.raises(ValidationError):   # reuses is the protocol's enum
        reply_type.model_validate({"links": [{"from": "S1", "to": "S2", "reuses": "money"}], "followers": []})


@pytest.mark.parametrize("kind", ["chaining", "limitations", "builds_on"])
def test_an_empty_answer_is_the_kinds_empty_answer(kind):
    params = params_for(kind)
    a = common.kind_answer_json(SYSTEM, params, common.empty_reply(params), ["S001"])
    assert a["kind"] == kind and a["dropped"] == []
    if kind == "chaining":
        assert a["verdict"] is None and a["studies"] == [] and a["reason"] == "not_stated"
    elif kind == "limitations":
        assert a["entries"] == [] and a["counts"] == {}
    else:
        assert a["links"] == [] and a["influence"] == {} and a["ranking"] == []


def test_new_prompts_name_no_topic_word_of_their_own():
    """The prompt files hold placeholders, never a pack's words: the drug names come only from the fill."""
    for name in ("map-effect-v2.md", "map-chaining-v1.md", "map-limitations-v1.md", "map-builds-on-v1.md"):
        raw = (common.PROMPTS / name).read_text(encoding="utf-8")
        assert "Zelvora" not in raw and "retriev" not in raw.lower() and "<<" in raw


def test_default_question_and_effect_prompt_come_from_the_default_pack():
    """D36: the default question's mapping call is map-effect-v2 filled from its protocol (old caches miss)."""
    default = kind_params(common.default_question_id())
    assert common.DEFAULT_QUESTION == default.question and default.kind == "effect"
    text, reply = map_prompt(None)
    assert (text, reply) == map_prompt(default) and reply is common.AnswerReply
    assert "<<" not in text and not hasattr(common, "MAP_INSTRUCTIONS")


# --- fix round 1: a refusal's reason; pack-filled v2 prompts of inventory, consistency and best -------------------

def test_a_baseline_refusal_with_the_right_reason_is_refusal_correct():
    params = params_for("chaining")
    text, reply_type = map_prompt(params)
    assert '"context_differs"' in text and '"direct_comparison"' not in text   # every refusal reason, described
    reply = reply_type.model_validate({"verdict": "refused", "via": [], "papers": ["S001"], "inferred": False,
                                       "reason": "context_differs"})
    a = common.kind_answer_json(SYSTEM, params, reply, ["S001", "S002"])
    assert (a["verdict"], a["reason"]) == ("refused", "context_differs")
    exp = {"source": "Zelvora", "target": "Morvectin", "metric": "response_rate", "verdict": "refused",
           "inferred": False, "via": [], "studies": ["S001"], "reason": "context_differs"}
    canon = Canon.from_truth(None)
    assert score_chaining(exp, a, canon)["refusal_correct"] is True
    assert score_chaining(exp | {"reason": "no_path"}, a, canon)["refusal_correct"] is False
    with pytest.raises(ValidationError):   # direct_comparison is no refusal reason
        reply_type.model_validate({"verdict": "refused", "via": [], "papers": [], "inferred": False,
                                   "reason": "direct_comparison"})
    better = reply_type.model_validate({"verdict": "better", "via": [], "papers": [], "inferred": False,
                                        "reason": "no_path"})   # a reason given with a verdict is not passed through
    assert common.kind_answer_json(SYSTEM, params, better, ["S001"])["reason"] == "direct_comparison"


# The RAG questions' filled v2 mapping prompts (map-<kind>-v2.md), pinned. They differ from the filled v1 texts (pack
# examples, no topic words), so mapping calls cached before plan 2 miss once (D36).
RAG_V2 = {"inv-metrics": "e8c80ac537ed656c53397519207a2b4111ecc31105054ca9acde3e32ad38b9ca",
          "inv-methods": "0850f28f0699d5219e5f4dd93d7ab3e53eb9b8b40b1dff20bad1ab760f7507b9",
          "inv-datasets": "dc3391cc9039a14ad0d9ef7fedd85725bb053d4b635883e4a573ee19cebebfff",
          "cons-accuracy": "7711a2209a3e248758228dbcd7c4b38cc1a4aa827b85182ac9fe7e018caaf91e",
          "cons-hallucination": "38c721f3fdd5ba3d8923c36a24fddc990401c323a4fe60881ba99a4fb1d4b3b0",
          "best-accuracy": "2a119264f88445e4594ef21769d0eaea45aac5871df527c2cafc0b79096dcdd8",
          "best-hallucination": "e5f93a3d0e756a95d674715904f8ccaba1cf0c2695133a1baba041e44723af01"}


def test_inventory_consistency_best_use_pack_filled_v2_prompts():
    from modelcall import prompt_sha256
    assert {common.MAP_PROMPTS[k] for k in ("inventory", "consistency", "best")} == {
        "map-inventory-v2.md", "map-consistency-v2.md", "map-best-v2.md"}
    for name in ("map-inventory-v2.md", "map-consistency-v2.md", "map-best-v2.md"):
        raw = (common.PROMPTS / name).read_text(encoding="utf-8").lower()
        assert all(w not in raw for w in ("retriev", "closed-book", "rag", "natural questions")), name
    got = {}
    for qid in RAG_V2:
        text, reply = map_prompt(kind_params(qid))
        # inventory and consistency examples hold no topic word of the file; best's come from its protocol's kinds
        assert "<<" not in text and (qid.startswith("best") or "retriev" not in text.split("Example 1")[1].lower())
        got[qid] = prompt_sha256(text, reply)
    assert got == RAG_V2
    text, _ = map_prompt(kind_params("inv-methods"))
    assert "S001 reports RAG system and closed-book model." in text   # example names from the pack's display names
    assert "fact: S003 | reports | RAG system (RS)" in text           # and an abbreviation made from one


def test_the_default_question_is_the_first_effect_question():
    """The rule `evidence.questions.default_entry` applies; a reorder of domains/rag/questions.yaml is caught here."""
    assert common.default_question_id() == "rag-factuality" and str(common.DEFAULT_PROTOCOL).endswith(
        "rag-factuality.yaml")
