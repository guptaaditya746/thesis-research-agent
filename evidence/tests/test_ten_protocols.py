"""The ten hand-written protocols (evidence/protocols/) and the question list (evidence/questions.yaml)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence import engine, protocol, questions
from synth import vocab

from .conftest import make_corpus, regex_run

REPO = Path(__file__).resolve().parents[2]
PROTOCOLS = REPO / "evidence" / "protocols"
IDS = ("rag-factuality", "rag-hallucination", "rag-latency", "inv-metrics", "inv-methods", "inv-datasets",
       "cons-accuracy", "cons-hallucination", "best-accuracy", "best-hallucination")
NEW = IDS[1:]
KINDS = {"rag-factuality": "effect", "rag-hallucination": "effect", "rag-latency": "effect",
         "inv-metrics": "inventory", "inv-methods": "inventory", "inv-datasets": "inventory",
         "cons-accuracy": "consistency", "cons-hallucination": "consistency",
         "best-accuracy": "best", "best-hallucination": "best"}
TRUTH = {"rag-factuality": {"metric": "factual_accuracy", "min_effect": 0.01},
         "rag-hallucination": {"metric": "hallucination_rate", "min_effect": 0.01},
         "rag-latency": {"metric": "latency", "min_effect": 0.05},
         "inv-metrics": {"target": "metric"}, "inv-methods": {"target": "condition"},
         "inv-datasets": {"target": "dataset"},
         "cons-accuracy": {"metric": "factual_accuracy", "min_effect": 0.01},
         "cons-hallucination": {"metric": "hallucination_rate", "min_effect": 0.01},
         "best-accuracy": {"metric": "factual_accuracy"}, "best-hallucination": {"metric": "hallucination_rate"}}
HASHES = {"rag-factuality": "6b360bca67ce74025cea4ee857de1a7089c3ecc110cbfc2f8e4da1a32b1751d9",
          "rag-factuality-agentic": "8fe0ed7ea0bbdd393f67177b725c3ba4f16a2f70c2316e35da72f5280863bb79"}


def load(qid: str) -> protocol.Protocol:
    return protocol.load(PROTOCOLS / f"{qid}.yaml")


def test_all_ten_parse_and_match_questions_yaml() -> None:
    entries = questions.load()
    assert [e.id for e in entries] == list(IDS)
    for e in entries:
        assert e.protocol == f"evidence/protocols/{e.id}.yaml"
        p = load(e.id)
        assert (p.id, p.question, p.kind) == (e.id, e.question, e.kind), e.id
        assert e.kind == KINDS[e.id]
        assert e.truth.model_dump(exclude_none=True) == TRUTH[e.id], e.id
    extra = {e.id: (e.agentic_protocol, e.vocab) for e in entries if e.agentic_protocol or e.vocab}
    assert extra == {"rag-factuality": ("evidence/protocols/rag-factuality-agentic.yaml", "rag-factuality")}


@pytest.mark.parametrize("name", list(HASHES))
def test_rag_factuality_untouched(name: str) -> None:
    assert protocol.load(PROTOCOLS / f"{name}.yaml").sha256 == HASHES[name]


def test_best_kinds_cover_vocab() -> None:
    kinds_of = {**{label: "no-retrieval" for label, _, _ in vocab.BASELINES},
                **{label: "rag" for label, _, _ in vocab.RAGS},
                **dict(zip((label for label, _, _ in vocab.OTHERS),
                           ("rag-no-rerank", "rag-random", "fine-tuned", "chain-of-thought", "self-consistency",
                            "query-rewriting"), strict=True))}
    for qid in ("best-accuracy", "best-hallucination"):
        best = load(qid).best
        assert best is not None
        for conditions in (vocab.BASELINES, vocab.RAGS, vocab.OTHERS):
            for label, synonym, _ in conditions:
                for name in (label, synonym):
                    owners = [k for k, names in best.kinds.items() if name in names]
                    assert owners == [kinds_of[label]], (qid, name, owners)
        assert sum(len(names) for names in best.kinds.values()) == 2 * len(kinds_of)


def test_best_metric_direction() -> None:
    assert load("best-accuracy").best.metric.model_dump() == {"canonical": "factual_accuracy", "higher_is_better": True}  # type: ignore[union-attr]
    assert load("best-hallucination").best.metric.model_dump() == {"canonical": "hallucination_rate",  # type: ignore[union-attr]
                                                                  "higher_is_better": False}


def test_effect_and_consistency_metrics() -> None:
    for qid, (metric, hib, min_effect) in {"rag-hallucination": ("hallucination_rate", False, 0.01),
                                           "rag-latency": ("latency", False, 0.05),
                                           "cons-accuracy": ("factual_accuracy", True, 0.01),
                                           "cons-hallucination": ("hallucination_rate", False, 0.01)}.items():
        s = load(qid).synthesis
        assert s is not None
        assert [m.model_dump() for m in s.metrics] == [{"canonical": metric, "higher_is_better": hib}], qid
        assert s.min_effect == min_effect, qid
    for qid in ("cons-accuracy", "cons-hallucination"):
        assert load(qid).consistency == protocol.Consistency(by="direction")


def test_latency_values_are_seconds_without_a_fraction_bound() -> None:
    p = load("rag-latency")
    assert p.evidence_types["metric"].enum_of("canonical") == ("latency", "other")
    for bound in p.evidence_types["measurement"].bounds:
        assert bound.max is None, bound


def test_inventory_types_are_only_the_ones_needed() -> None:
    assert set(load("inv-metrics").evidence_types) == {"metric"}
    assert set(load("inv-datasets").evidence_types) == {"dataset"}
    methods = load("inv-methods").evidence_types
    assert set(methods) == {"condition"} and "role" not in methods["condition"].properties


@pytest.mark.parametrize("qid", NEW)
def test_each_new_protocol_runs_regex_only(qid: str, tmp_path: Path) -> None:
    run = engine.run(PROTOCOLS / f"{qid}.yaml", make_corpus(tmp_path / "corpus"), tmp_path / "runs",
                     selection="regex-only", provider=None)
    answer = json.loads((run / "answer.json").read_text(encoding="utf-8"))
    if KINDS[qid] == "effect":   # effect answers keep today's shape: a label, no kind key
        assert "label" in answer and "kind" not in answer
    else:
        assert answer["kind"] == KINDS[qid]
    # the fixture papers name "closed-book model" and "retrieval-augmented model" and report accuracy tables
    if qid == "best-accuracy":
        assert any(s["winner"] == "rag" for s in answer["studies"]), answer["studies"]
    if KINDS[qid] == "inventory":
        assert answer["entries"], qid
    if qid == "inv-methods":
        assert {"closed-book model", "retrieval-augmented model"} <= {e["name"].casefold() for e in answer["entries"]}


def test_best_hallucination_finds_the_lowest_rate(tmp_path: Path) -> None:
    paper = ("# Study\nWe compare the vanilla LLM, the RAG pipeline and the fine-tuned model on TriviaCheck.\n\n"
             "| System | hallucination rate (%) |\n|---|---|\n| vanilla LLM | 31.0 |\n| RAG pipeline | 12.5 |\n"
             "| fine-tuned model | 22.0 |\n")
    answer, _ = regex_run({"S1": paper}, tmp_path, PROTOCOLS / "best-hallucination.yaml")
    [study] = answer["studies"]
    assert study["winner"] == "rag" and study["values"] == {"no-retrieval": 0.31, "rag": 0.125, "fine-tuned": 0.22}
    assert answer["winner"] == "rag"
