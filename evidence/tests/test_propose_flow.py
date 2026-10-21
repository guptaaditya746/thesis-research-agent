"""The proposal flow end to end with a scripted model (docs/evidence-system.md Part E): the RAG question
frozen equals the hand-written protocol up to free text; the flow without a vocabulary; the record cache."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from evidence import cli
from evidence.propose import cards, critic, draft, frame, freeze, vocab
from evidence.propose.common import ProposalError
from evidence.protocol import load

from .propose_support import QUESTION, RAG_FRAME, Scripted, comparable, flow, hand_written, query_tokens


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_rag_question_freezes_to_the_hand_written_protocol(tmp_path: Path) -> None:
    model = Scripted()
    d = flow(tmp_path / "rag-factuality", model)
    assert model.calls == ["frame", "critic", "cards"]
    frozen = load(d / "protocol.yaml")
    hand = hand_written()
    assert frozen.id == "rag-factuality" and frozen.version == 2 and frozen.revision == 1
    assert comparable(frozen) == comparable(hand)
    assert frozen.screen.question == hand.screen.question       # free text, here equal too
    for t, words in query_tokens(hand).items():                  # bm25 query: the frame's names plus type words
        assert words <= query_tokens(frozen)[t], t
    # no regex step got a config: the built-in patterns find every frame name
    assert all(not s.config for spec in frozen.evidence_types.values() for s in spec.extractors)

    proposal = _json(d / "proposal.json")
    assert proposal["protocol"] == {"file": "protocol.yaml", "id": "rag-factuality", "version": 2, "revision": 1,
                                    "sha256": frozen.sha256}
    assert proposal["vocabulary"] == vocab.load("rag-factuality").ref()
    assert set(proposal["models"]) == {"frame", "critic", "cards"} and proposal["models"]["frame"] == "scripted-propose"
    assert all(len(h) == 64 for h in proposal["prompts"].values())
    assert proposal["decided_by"] == {"model": list(cards.HANDLERS)}
    assert [d_["card"] for d_ in proposal["decisions"]] == list(cards.HANDLERS)
    assert all(d_["by"] == "model" and d_["reason"].startswith("default: ") for d_ in proposal["decisions"])
    assert proposal["run_settings"] == {"strategy": "all"}
    assert all(c["ok"] for c in proposal["checks"]), proposal["checks"]
    assert (d / "protocol.v1.yaml").read_text(encoding="utf-8") == (d / "protocol.yaml").read_text(encoding="utf-8")
    assert cli.main(["protocol", "check", str(d / "protocol.yaml")]) == 0


def test_frame_sources_come_from_the_vocabulary(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="draft")
    f = _json(d / "frame.json")
    assert f["vocabulary"]["name"] == "rag-factuality" and len(f["vocabulary"]["sha256"]) == 64
    assert f["treatment"]["source"] == "ontology" and f["treatment"]["vocab_id"] == "hand:retrieval_augmented_generation"
    assert f["control"]["vocab_id"] == "hand:closed_book"
    assert [o["vocab_id"] for o in f["outcomes"]] == ["hand:factual_accuracy", "hand:hallucination_rate"]
    assert f["outcomes"][1]["vocab_higher_is_better"] is False
    by_term = {t["term"]: t for t in f["population"]["terms"]}
    assert by_term["RAG"]["source"] == "ontology" and by_term["retrieval"]["source"] == "invented"
    sources = _json(d / "draft.sources.json")
    kinds = {x["source"] for x in sources["fields"] + sources["terms"]}
    assert kinds == {"ontology", "protocol", "invented"}
    compare = next(x for x in sources["fields"] if x["path"] == "synthesis.compare.treatment")
    assert compare == {"path": "synthesis.compare.treatment", "source": "ontology",
                       "vocab_id": "hand:retrieval_augmented_generation"}
    hib = next(x for x in sources["fields"] if x["path"] == "synthesis.metrics[1].higher_is_better")
    assert hib["source"] == "ontology"


def test_flow_without_a_vocabulary(tmp_path: Path) -> None:
    d = flow(tmp_path / "novocab", Scripted(), vocab=None)
    f = _json(d / "frame.json")
    assert f["vocabulary"] is None
    names = [f["treatment"], f["control"], *f["outcomes"], *f["population"]["terms"],
             *(s for r in (f["treatment"], f["control"], *f["outcomes"]) for s in r["synonyms"])]
    assert {x["source"] for x in names} == {"invented"} and all(x["vocab_id"] is None for x in names)
    sources = _json(d / "draft.sources.json")
    assert {x["source"] for x in sources["fields"] + sources["terms"]} == {"protocol", "invented"}
    assert sources["vocabulary"] is None
    proposal = _json(d / "proposal.json")
    assert proposal["vocabulary"] is None
    assert comparable(load(d / "protocol.yaml")) == comparable(hand_written())
    names = [c["id"] for c in proposal["checks"]]
    assert "vocabulary_direction" in names and all(c["ok"] for c in proposal["checks"])


def test_rerun_of_model_steps_hits_the_cache(tmp_path: Path) -> None:
    model = Scripted()
    d = flow(tmp_path / "p", model, until="cards")
    assert model.calls == ["frame", "critic", "cards"]
    before = {n: _json(d / n)["call"] for n in ("frame.json", "critic.json", "cards.json")}
    assert not any(c["cached"] for c in before.values())
    frame.run(QUESTION, d, vocab="rag-factuality", model=model.model)
    draft.run(d)
    critic.run(d, model=model.model)
    cards.run(d, model=model.model)
    assert model.calls == ["frame", "critic", "cards"]            # zero model calls on the rerun
    after = {n: _json(d / n)["call"] for n in ("frame.json", "critic.json", "cards.json")}
    assert all(c["cached"] for c in after.values())
    assert {n: c["cache_key"] for n, c in after.items()} == {n: c["cache_key"] for n, c in before.items()}
    # a different question is a different key: one new call
    frame.run("Does reranking improve the factual accuracy of RAG answers?", tmp_path / "other", model=model.model)
    assert model.calls == ["frame", "critic", "cards", "frame"]


def test_cards_offer_options_and_prefill_decisions(tmp_path: Path) -> None:
    model = Scripted(cards={"min_effect": "lenient", "label": ("model", {"rows": [{"when": {"supporting": ">0"},
                                                                                       "then": "supported"},
                                                                                      {"then": "insufficient"}]})})
    d = flow(tmp_path / "p", model, until="cards")
    data = _json(d / "cards.json")
    by_id = {c["id"]: c for c in data["cards"]}
    assert list(by_id) == list(cards.HANDLERS)
    assert [o["id"] for o in by_id["min_effect"]["options"]] == ["draft", "strict", "lenient"]   # usual = draft
    assert "(= usual" in by_id["min_effect"]["options"][0]["summary"]
    assert {o["id"] for o in by_id["cascade"]["options"]} == {"draft", "gaps", "with_agentic"}
    assert by_id["label"]["default"] == "model" and by_id["label"]["options"][-1]["id"] == "model"
    assert by_id["roles"]["vocabulary"][0]["vocab_id"] == "hand:retrieval_augmented_generation"
    decisions = yaml.safe_load((d / "decisions.yaml").read_text(encoding="utf-8"))["decisions"]
    assert [x["card"] for x in decisions] == list(cards.HANDLERS)
    assert {x["by"] for x in decisions} == {"model"}
    assert next(x for x in decisions if x["card"] == "min_effect")["choice"] == "lenient"
    freeze.run(d)
    p = load(d / "protocol.yaml")
    assert p.synthesis.min_effect == 0.02 and [r.then for r in p.synthesis.label] == ["supported", "insufficient"]


def test_a_person_overrides_a_default_and_a_custom_value(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="cards")
    data = yaml.safe_load((d / "decisions.yaml").read_text(encoding="utf-8"))
    for x in data["decisions"]:
        if x["card"] == "cascade":
            x.update(choice="gaps", reason="the answering run escalates only the gaps", by="AG")
        if x["card"] == "metrics":
            x.update(choice="custom", by="AG", reason="factual accuracy alone answers the question",
                     value={"metrics": [{"canonical": "factual_accuracy", "higher_is_better": True}]})
    (d / "decisions.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    freeze.run(d)
    p = load(d / "protocol.yaml")
    assert p.synthesis.metric_names == ("factual_accuracy",)
    assert p.evidence_types["metric"].enum_of("canonical") == ("factual_accuracy", "other")
    assert p.evidence_types["measurement"].bounds[0].when.values == ("factual_accuracy",)
    proposal = _json(d / "proposal.json")
    assert proposal["run_settings"] == {"strategy": "gaps"}
    assert proposal["decided_by"]["AG"] == ["metrics", "cascade"]
    assert next(x for x in proposal["decisions"] if x["card"] == "metrics")["choice"] == "custom"


def test_freeze_refuses_a_stale_draft_and_a_second_freeze(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="cards")
    text = (d / "draft.yaml").read_text(encoding="utf-8")
    (d / "draft.yaml").write_text(text.replace("min_effect: 0.01", "min_effect: 0.03"), encoding="utf-8")
    with pytest.raises(ProposalError, match="changed after"):
        freeze.run(d)
    (d / "draft.yaml").write_text(text, encoding="utf-8")
    freeze.run(d)
    with pytest.raises(ProposalError, match="frozen"):
        freeze.run(d)


def test_freeze_refuses_cards_built_from_a_changed_critic(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="cards")
    critic_data = _json(d / "critic.json")
    critic_data["checks"].append({"id": "changed-after-cards", "kind": "llm", "ok": False, "message": "x"})
    (d / "critic.json").write_text(json.dumps(critic_data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                   newline="\n")
    with pytest.raises(ProposalError, match="critic.json changed after `evidence propose cards`"):
        freeze.run(d)


def test_a_question_the_built_in_patterns_do_not_know(tmp_path: Path) -> None:
    """Roles the regex extractors have no patterns for: the draft gives the regex steps patterns from the
    frame's names, and the critic's coverage check passes."""
    cot = {
        "population": {"description": "Papers comparing chain-of-thought prompting with direct prompting.",
                       "screening_question": "Does the paper compare chain-of-thought prompting with direct answering?",
                       "terms": ["chain-of-thought", "CoT"]},
        "treatment": {"role": "cot", "label": "chain-of-thought prompting", "definition": "prompting with reasoning steps",
                      "synonyms": ["CoT"]},
        "control": {"role": "direct", "label": "direct prompting", "definition": "the same model answering directly",
                    "synonyms": ["standard prompting"]},
        "outcomes": [{"canonical": "answer_accuracy", "label": "answer accuracy", "higher_is_better": True,
                      "scale": "fraction", "synonyms": ["solve rate"]}],
        "effect_labels": RAG_FRAME["effect_labels"],
    }
    d = flow(tmp_path / "cot-accuracy", Scripted(frame_reply=cot), vocab=None,
             question="Does chain-of-thought prompting improve answer accuracy?")
    p = load(d / "protocol.yaml")
    assert p.synthesis.compare.treatment == "cot" and p.synthesis.metric_names == ("answer_accuracy",)
    steps = {s.name: s.config for spec in p.evidence_types.values() for s in spec.extractors}
    assert set(steps["regex_condition"]["conditions"]) == {"cot", "direct"}
    assert steps["regex_measurement"]["conditions"] == steps["regex_condition"]["conditions"]
    assert {m[1] for m in steps["regex_metric"]["metrics"]} <= {"answer_accuracy", "other"}
    assert "chain" in steps["regex_author_claim"]["subject"]
    checks = {c["id"]: c for c in _json(d / "proposal.json")["checks"]}
    assert checks["terms_cover_synonyms"]["ok"], checks["terms_cover_synonyms"]["message"]
    terms = _json(d / "draft.sources.json")["terms"]
    assert any(t["path"] == "regex.conditions.cot" and t["term"] == "CoT" for t in terms)
