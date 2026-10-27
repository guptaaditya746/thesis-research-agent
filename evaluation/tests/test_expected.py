"""Expected answers per question kind, computed from ground_truth.json (evaluation/expected.py, evaluation/canon.py)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from evaluation import canon
from evaluation.expected import expected
from evaluation.truth import TYPES, GroundTruth
from evidence import protocol as protocol_module
from evidence.questions import QuestionTruth
from synth import vocab

ROOT = Path(__file__).resolve().parents[2]
MIXED = ROOT / "tests" / "EV2" / "corpora" / "rag-claude-s1-mixed" / "ground_truth.json"
HARD = ROOT / "tests" / "EV2" / "corpora" / "rag-tpl-hard-complex" / "ground_truth.json"
PROTOCOLS = ROOT / "evidence" / "protocols"


@pytest.fixture(scope="module")
def mixed() -> GroundTruth:
    return GroundTruth.load(MIXED)


@pytest.fixture(scope="module")
def rag_factuality() -> protocol_module.Protocol:
    return protocol_module.load(PROTOCOLS / "rag-factuality.yaml")


def _study(paper: str, conditions: list[tuple[str, str]], metric: tuple[str, str, bool],
           measurements: list[tuple[int, float, str | None]], *, claim: str = "improves",
           experiments: list[tuple[str, list[int]]] | None = None, **extra: Any) -> dict[str, Any]:
    """A hand-made study: conditions (role, label) c1.., one metric (canonical, name, higher_is_better) k1,
    measurements (condition number, value, experiment name or None) on dataset D1; the effect pairs c2 with c1."""
    exp_id = {name: f"{paper}.e{i + 1}" for i, (name, _) in enumerate(experiments or [])}
    ms = [{"id": f"{paper}.m{i + 1}", "condition": f"{paper}.c{c}", "metric": f"{paper}.k1", "value": v,
           "dataset": "OpenFactQA", **({"experiment": exp_id[e]} if e else {})} for i, (c, v, e) in enumerate(measurements)]
    out = {"study_id": paper, "paper": paper, "level": "explicit", "relevant": True, "flags": [], "duplicate_of": None,
           "missing": None,
           "conditions": [{"id": f"{paper}.c{i + 1}", "role": r, "label": label, "aliases": []}
                          for i, (r, label) in enumerate(conditions)],
           "metrics": [{"id": f"{paper}.k1", "canonical": metric[0], "name": metric[1], "higher_is_better": metric[2]}],
           "measurements": ms,
           "author_claim": {"id": f"{paper}.a1", "direction": claim},
           "effect": {"direction": "supports", "delta": 0.0, "metric": f"{paper}.k1", "treatment": f"{paper}.m2",
                      "control": f"{paper}.m1"}}
    if experiments:
        out["experiments"] = [{"id": exp_id[name], "name": name, "conditions": [f"{paper}.c{c}" for c in cs],
                               "datasets": ["OpenFactQA"], "synthesis": i == 0} for i, (name, cs) in enumerate(experiments)]
    out.update(extra)
    return out


def _truth(tmp_path: Path, studies: list[dict[str, Any]]) -> GroundTruth:
    path = tmp_path / "ground_truth.json"
    path.write_text(json.dumps({"corpus_id": "hand", "question": "q", "studies": studies, "placements": [],
                                "answer": {}}), encoding="utf-8")
    return GroundTruth.load(path)


def test_effect_matches_saved_answer(mixed, rag_factuality):
    got = expected(mixed, "effect", QuestionTruth(metric="factual_accuracy", min_effect=0.01), rag_factuality)
    for key in ("label", "supporting", "contradicting", "neutral"):
        assert got[key] == mixed.answer[key]


def test_effect_computed_agrees_with_saved_directions(mixed):
    """Without the saved-answer shortcut, every study whose question metric is factual_accuracy gets the
    direction the generator saved, and no study of another metric is counted."""
    got = expected(mixed, "effect", QuestionTruth(metric="factual_accuracy", min_effect=0.01))
    saved = {d: mixed.answer[g] for g, d in (("supporting", "supports"), ("contradicting", "contradicts"),
                                              ("neutral", "neutral"))}
    accuracy = {s["paper"] for s in mixed.studies if s["metrics"][0]["canonical"] == "factual_accuracy"}
    assert accuracy and len(accuracy) < len(mixed.studies)
    for group, direction in (("supporting", "supports"), ("contradicting", "contradicts"), ("neutral", "neutral")):
        assert got[group] == [p for p in saved[direction] if p in accuracy]
    assert set(got["undetermined"]) == {s["paper"] for s in mixed.studies} - accuracy
    assert got["label"] == "mixed" and got["counts"]["supporting"] == len(got["supporting"])


def test_inventory_datasets_are_vocab_names(mixed):
    got = expected(mixed, "inventory", QuestionTruth(target="dataset"))
    assert got["kind"] == "inventory" and got["target"] == "dataset" and got["entries"]
    for entry in got["entries"]:
        assert entry["name"] in vocab.DATASETS
        assert entry["papers"] and entry["papers"] == sorted(entry["papers"])


def test_inventory_metrics_merge_synonyms(mixed):
    assert canon.key("metric", "answer accuracy") == canon.key("metric", "AA") == "answer accuracy"
    assert canon.key("metric", "  Answer   ACCURACY ") == "answer accuracy"
    assert canon.key("metric", "proportion of questions answered with correct facts") == "answer accuracy"
    assert canon.key("metric", "Lat.") == "latency"
    assert canon.key("metric", "perplexity") is None
    got = expected(mixed, "inventory", QuestionTruth(target="metric"))
    names = [e["name"] for e in got["entries"]]
    assert names == sorted(names, key=lambda n: (n.casefold(), n)) and len(set(names)) == len(names)
    # the description "share of answers that contain at least one unsupported statement" joins hallucination rate
    hr = next(e for e in got["entries"] if e["name"] == "hallucination rate")
    assert "share of answers that contain at least one unsupported statement" in hr["aliases"]


def test_inventory_conditions_key_to_labels(mixed):
    assert canon.key("condition", "model that answers from its own parameters") == "closed-book model"
    assert canon.key("condition", "RAG Pipeline") == "RAG pipeline"
    assert canon.key("dataset", "openfactqa") == "OpenFactQA"
    assert canon.key("dataset", "ImageNet") is None
    got = expected(mixed, "inventory", QuestionTruth(target="condition"))
    pb = next(e for e in got["entries"] if e["name"] == "parametric-only model")
    assert "generator without any document access" in pb["aliases"]
    assert all(e["items"] for e in got["entries"])


def test_kind_of_matches_best_protocol():
    data = yaml.safe_load((PROTOCOLS / "best-accuracy.yaml").read_text(encoding="utf-8"))
    kinds = data["best"]["kinds"]
    assert list(dict.fromkeys(canon.KIND_OF.values())) == list(kinds)
    for kind, names in kinds.items():
        for name in names:
            assert canon.KIND_OF[canon.key("condition", name)] == kind, name
    assert set(canon.KIND_OF) == {label for label, _, _ in (*vocab.BASELINES, *vocab.RAGS, *vocab.OTHERS)}


def test_best_uses_main_experiment_only(tmp_path):
    study = _study("S001", [("baseline", "vanilla LLM"), ("rag", "RAG pipeline"), ("other", "fine-tuned model")],
                   ("factual_accuracy", "answer accuracy", True),
                   [(1, 0.60, "main comparison"), (2, 0.70, "main comparison"),
                    (2, 0.65, "ablation"), (3, 0.90, "ablation")],
                   experiments=[("main comparison", [1, 2]), ("ablation", [2, 3])])
    got = expected(_truth(tmp_path, [study]), "best", QuestionTruth(metric="factual_accuracy"))
    assert got["kind"] == "best" and got["metric"] == "factual_accuracy"
    entry = got["studies"][0]
    assert entry == {"document": "S001", "winner": "rag", "tied": [], "values": {"no-retrieval": 0.6, "rag": 0.7},
                     "reason": None}
    assert got["wins"] == {"rag": 1} and got["winner"] == "rag" and got["tied"] == []


def test_best_tie_and_missing_metric(tmp_path):
    tie = _study("S001", [("baseline", "vanilla LLM"), ("rag", "RAG pipeline")],
                 ("hallucination_rate", "HR", False), [(1, 0.2, None), (2, 0.2, None)])
    other = _study("S002", [("baseline", "vanilla LLM"), ("rag", "RAG pipeline")],
                   ("factual_accuracy", "FA", True), [(1, 0.5, None), (2, 0.6, None)])
    got = expected(_truth(tmp_path, [tie, other]), "best", QuestionTruth(metric="hallucination_rate"))
    first, second = got["studies"]
    assert first["winner"] is None and first["tied"] == ["no-retrieval", "rag"] and first["reason"] is None
    assert second["winner"] is None and second["reason"]["code"] == "no_comparison"
    assert got["wins"] == {} and got["winner"] is None and got["tied"] == []


def test_latency_effect_lower_is_better(tmp_path):
    study = _study("S001", [("baseline", "vanilla LLM"), ("rag", "RAG pipeline")], ("other", "latency", False),
                   [(1, 1.25, None), (2, 1.21, None)])
    got = expected(_truth(tmp_path, [study]), "effect", QuestionTruth(metric="latency", min_effect=0.05))
    assert got["neutral"] == ["S001"] and got["label"] == "no_effect"
    entry = got["studies"][0]
    assert entry["direction"] == "neutral" and entry["delta"] == pytest.approx(0.04)
    got = expected(_truth(tmp_path, [study]), "effect", QuestionTruth(metric="latency", min_effect=0.01))
    assert got["supporting"] == ["S001"]


def test_counted_studies_leave_out_duplicates_missing_and_irrelevant(tmp_path):
    base = [("baseline", "vanilla LLM"), ("rag", "RAG pipeline")]
    metric = ("factual_accuracy", "FA", True)
    studies = [_study("S001", base, metric, [(1, 0.5, None), (2, 0.6, None)]),
               _study("S002", base, metric, [(1, 0.5, None), (2, 0.6, None)], duplicate_of="S001"),
               _study("S003", base, metric, [(2, 0.6, None)], missing="control"),
               {"study_id": "S004", "paper": "S004", "level": "explicit", "relevant": False, "flags": [],
                "duplicate_of": None, "missing": None, "conditions": [], "metrics": [], "measurements": [],
                "author_claim": None, "effect": {"direction": "undetermined", "delta": None, "metric": None,
                                                 "treatment": None, "control": None, "reason": "screened_out"}}]
    truth = _truth(tmp_path, studies)
    got = expected(truth, "effect", QuestionTruth(metric="factual_accuracy", min_effect=0.01))
    assert got["supporting"] == ["S001"] and got["duplicates"] == ["S002"]
    assert got["undetermined"] == ["S003", "S004"]
    cons = expected(truth, "consistency", QuestionTruth(metric="factual_accuracy", min_effect=0.01))
    assert cons["agreeing"] == ["S001"] and cons["disagreeing"] == []
    assert [s["document"] for s in cons["studies"]] == ["S001", "S002", "S003"]
    assert cons["undetermined"] == ["S002", "S003"]
    inv = expected(truth, "inventory", QuestionTruth(target="condition"))
    assert all("S004" not in e["papers"] for e in inv["entries"])
    # on another metric the duplicate has no pair: undetermined, not a duplicate
    other = expected(truth, "effect", QuestionTruth(metric="hallucination_rate", min_effect=0.01))
    assert other["duplicates"] == [] and other["undetermined"] == ["S001", "S002", "S003", "S004"]


def test_consistency_only_claim_metric_studies(tmp_path):
    base = [("baseline", "vanilla LLM"), ("rag", "RAG pipeline")]
    studies = [_study("S001", base, ("factual_accuracy", "FA", True), [(1, 0.5, None), (2, 0.6, None)],
                      claim="no_effect"),
               _study("S002", base, ("hallucination_rate", "HR", False), [(1, 0.5, None), (2, 0.3, None)])]
    got = expected(_truth(tmp_path, studies), "consistency", QuestionTruth(metric="factual_accuracy", min_effect=0.01))
    assert got["kind"] == "consistency" and got["metric"] == "factual_accuracy"
    assert got["studies"] == [{"document": "S001", "claim": "no_effect", "direction": "supports", "agrees": False,
                               "reason": None}]
    assert got["disagreeing"] == ["S001"] and got["agreeing"] == [] and got["undetermined"] == []


def test_dataset_facts_loaded(mixed):
    facts = mixed.of("S001", "dataset")
    study = next(s for s in mixed.studies if s["paper"] == "S001")
    assert [f.data["name"] for f in facts] == list(dict.fromkeys(m["dataset"] for m in study["measurements"]))
    assert [f.data["name"] for f in facts] == ["LawFactQA"]
    assert facts[0].id == "S001.d:LawFactQA" and facts[0].type == "dataset" and facts[0].paper == "S001"
    assert not mixed.placements_of(facts[0].id)
    # effect scoring sees the same facts as before: datasets stay out of `facts` and TYPES
    assert "dataset" not in TYPES and all(f.type != "dataset" for f in mixed.facts.values())


def test_hard_corpus_best_and_inventory_run():
    truth = GroundTruth.load(HARD)
    best = expected(truth, "best", QuestionTruth(metric="factual_accuracy"))
    assert len(best["studies"]) == len(truth.studies) and sum(best["wins"].values()) > 0
    inv = expected(truth, "inventory", QuestionTruth(target="condition"))
    names = {e["name"] for e in inv["entries"]}
    assert "RAG pipeline" in names and "RAG pipeline without reranking" in names   # an ablation keeps its own name


def _edited(protocol: protocol_module.Protocol, **changes: Any) -> protocol_module.Protocol:
    """A copy of `protocol` as a user may have edited it (no validation: the point is what expected reads)."""
    synthesis = changes.pop("synthesis", None)
    update: dict[str, Any] = dict(changes)
    if synthesis is not None:
        update["synthesis"] = protocol.synthesis.model_copy(update=synthesis)
    return protocol.model_copy(update=update)


def test_user_protocol_does_not_change_truth(mixed, rag_factuality):
    """Roles, claim vocabulary and flag thresholds are the generator's, whatever protocol is passed."""
    edited = _edited(rag_factuality, id="my-rag", synthesis={
        "compare": rag_factuality.synthesis.compare.model_copy(update={"treatment": "retrieval", "control": "plain"}),
        "claim_map": {"improves": "contradicts", "worsens": "supports", "no_effect": "neutral"},
        "flags": rag_factuality.synthesis.flags.model_copy(update={"duplicates": False}),
        "min_effect": 0.5})
    for kind, params in (("effect", QuestionTruth(metric="hallucination_rate", min_effect=0.01)),
                         ("consistency", QuestionTruth(metric="factual_accuracy", min_effect=0.01))):
        plain = expected(mixed, kind, params)
        got = expected(mixed, kind, params, edited)
        got.pop("question", None), plain.pop("question", None)
        assert got == plain
    assert expected(mixed, "consistency", QuestionTruth(metric="factual_accuracy", min_effect=0.01))["disagreeing"]


def test_saved_answer_only_for_the_rag_factuality_question(mixed, rag_factuality):
    params = QuestionTruth(metric="factual_accuracy", min_effect=0.01)
    assert expected(mixed, "effect", params, rag_factuality) == mixed.answer
    agentic = protocol_module.load(PROTOCOLS / "rag-factuality-agentic.yaml")
    assert expected(mixed, "effect", params, agentic) == mixed.answer
    same_text = _edited(rag_factuality, id="my-copy")          # another protocol asking the same question
    computed = expected(mixed, "effect", params, same_text)
    assert computed != mixed.answer and computed["system"] == "ground-truth" and "studies" in computed
    other_metric = expected(mixed, "effect", QuestionTruth(metric="hallucination_rate", min_effect=0.01), rag_factuality)
    assert other_metric["system"] == "ground-truth"


def test_best_keeps_a_study_with_one_side_missing(tmp_path):
    conditions = [("baseline", "vanilla LLM"), ("rag", "RAG pipeline"), ("other", "fine-tuned model")]
    metric = ("factual_accuracy", "FA", True)
    missing = _study("S001", conditions, metric, [(2, 0.6, None), (3, 0.7, None)], missing="control")
    missing["effect"] = {"direction": "undetermined", "delta": None, "metric": "S001.k1", "treatment": "S001.m1",
                         "control": None, "reason": "missing_control"}
    dup = _study("S002", conditions, metric, [(1, 0.5, None), (2, 0.6, None), (3, 0.7, None)], duplicate_of="S001")
    got = expected(_truth(tmp_path, [missing, dup]), "best", QuestionTruth(metric="factual_accuracy"))
    first, second = got["studies"]
    assert first == {"document": "S001", "winner": "fine-tuned", "tied": [], "values": {"rag": 0.6, "fine-tuned": 0.7},
                     "reason": None}
    assert second["winner"] is None and second["reason"]["code"] == "duplicate"
    assert got["wins"] == {"fine-tuned": 1} and got["winner"] == "fine-tuned"


def test_claim_flags_only_when_the_claim_is_about_the_question_metric(tmp_path):
    """Minor 6: the author claim is about the study's first metric (accuracy here); it says nothing about
    latency, so the latency question raises no claim flag and leaves `agrees_with_data` null."""
    study = _study("S001", [("baseline", "vanilla LLM"), ("rag", "RAG pipeline")], ("factual_accuracy", "FA", True),
                   [(1, 0.5, None), (2, 0.6, None)], claim="worsens")
    study["metrics"].append({"id": "S001.k2", "canonical": "other", "name": "latency", "higher_is_better": False})
    study["measurements"] += [{"id": "S001.m3", "condition": "S001.c1", "metric": "S001.k2", "value": 1.0,
                               "dataset": "OpenFactQA"},
                              {"id": "S001.m4", "condition": "S001.c2", "metric": "S001.k2", "value": 2.0,
                               "dataset": "OpenFactQA"}]
    truth = _truth(tmp_path, [study])
    latency = expected(truth, "effect", QuestionTruth(metric="latency", min_effect=0.05))
    entry = latency["studies"][0]
    assert entry["direction"] == "contradicts"                    # RAG slower; the claim "worsens" is about accuracy
    assert entry["author_claim"]["agrees_with_data"] is None
    assert "claim_disagrees" not in entry["flags"] and latency["flags"]["claim_disagrees"] == []
    accuracy = expected(truth, "effect", QuestionTruth(metric="factual_accuracy", min_effect=0.01))
    assert accuracy["studies"][0]["author_claim"]["agrees_with_data"] is False
    assert accuracy["flags"]["claim_disagrees"] == ["S001"]
