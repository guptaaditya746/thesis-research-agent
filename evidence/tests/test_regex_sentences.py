"""Regex measurements in sentences (review finding 2): a value is not attached to a condition across another
system or another number, signed deltas and "from X to Y" changes are no values, and "RAG with/without ..."
names another system."""
from __future__ import annotations

from pathlib import Path

import pytest

from evidence.extractors import terms

from .conftest import PROTOCOL, measurements, pack_words, regex_run

ABSTRACT = "# P\n\n## Abstract\n\nWe compare a closed-book model with a retrieval-augmented model. {}\n"


def test_no_reach_back_across_another_system(tmp_path: Path) -> None:
    text = ABSTRACT.format("The retrieval-augmented model reaches an accuracy of 71%, while a fine-tuned model "
                           "reaches 57%, compared with 62% for the closed-book model.")
    _, items = regex_run({"S": text}, tmp_path)
    assert measurements(items, "S") == [("rag", 0.71), ("baseline", 0.62)]


def test_signed_delta_is_not_a_value(tmp_path: Path) -> None:
    text = ABSTRACT.format("The retrieval-augmented model reaches an accuracy of 71% (+9%) over the closed-book "
                           "model at 62%.")
    _, items = regex_run({"S": text}, tmp_path)
    assert measurements(items, "S") == [("rag", 0.71), ("baseline", 0.62)]


def test_from_to_change_is_skipped(tmp_path: Path) -> None:
    text = ABSTRACT.format("The RAG model raises accuracy from 62% to 71% over the closed-book model.")
    _, items = regex_run({"S": text}, tmp_path)
    assert measurements(items, "S") == []


def test_rag_without_reranking_is_another_system(tmp_path: Path) -> None:
    text = ("# D\n\n## Method\n\nWe compare the closed-book model, the retrieval-augmented generator and the RAG "
            "without reranking.\n\n## Results\n\nThe closed-book model shows 36.1% hallucination rate on TriviaCheck. "
            "The RAG without reranking shows 19.5% hallucination rate on TriviaCheck. The retrieval-augmented "
            "generator shows 30.5% hallucination rate on TriviaCheck.\n")
    answer, items = regex_run({"D": text}, tmp_path)
    assert measurements(items, "D") == [("baseline", 0.361), ("rag", 0.305)]
    assert answer["studies"][0]["direction"] == "supports"


# A parenthetical right after a condition qualifies it ("RAG (no retrieval)" is the control); an alias code
# "(B)" and a negated object ("no retrieval failures") do not. Same cases under the built-in roles and under
# the frozen EV1 proposal's roles (extraction-research/probe.py).
PROPOSAL = Path(__file__).resolve().parents[2] / "tests" / "EV1" / "diagnostics" / "proposal" / "protocol.yaml"
ROLE_SETS = [pytest.param(PROTOCOL, "baseline", id="built-in"), pytest.param(PROPOSAL, "closed_book", id="proposal")]


def roles_of(text: str, protocol: Path, tmp: Path) -> list[str]:
    _, items = regex_run({"P": f"# P\n\n{text}\n"}, tmp, protocol)
    found = [(min(s["selector"]["start"] for s in i["spans"]), i["fields"]["role"])
             for i in items.values() if i["evidence_type"] == "condition"]
    return [role for _, role in sorted(found)]


@pytest.mark.parametrize("protocol,control", ROLE_SETS)
@pytest.mark.parametrize("text,roles", [
    ("RAG (no retrieval) answers from its parameters.", ["CONTROL"]),
    ("RAG (without retrieval) answers from its parameters.", ["CONTROL"]),
    ("RAG (no reranking) is an ablation.", ["other"]),
    ("RAG without reranking is an ablation.", []),
    ("The RAG model has no retrieval failures.", ["rag"]),
    ("We compare RAG against a closed-book model.", ["rag", "CONTROL"]),
    # review round 1: a control ending in its system noun is no negated object; a qualified control stays control
    ("The no-retrieval baseline errors are frequent.", ["CONTROL"]),
    ("The RAG model reaches 50%, the closed-book model (no fine-tuning) reaches 40%.", ["rag", "CONTROL"]),
    ("Llama-2 without retrieval (no context) answers from its parameters.", ["CONTROL"]),
])
def test_condition_roles_resolve_local_qualifiers(text: str, roles: list[str], protocol: Path, control: str,
                                                  tmp_path: Path) -> None:
    assert roles_of(text, protocol, tmp_path) == [control if r == "CONTROL" else r for r in roles]


@pytest.mark.parametrize("protocol,control", ROLE_SETS)
def test_unrelated_negation_keeps_the_treatment_mention(protocol: Path, control: str, tmp_path: Path) -> None:
    text = "The RAG model has no retrieval failures, unlike the closed-book model."
    assert roles_of(text, protocol, tmp_path) == ["rag", control]
    _, items = regex_run({"P": f"# P\n\n{text}\n"}, tmp_path / "labels", protocol)
    assert [i["fields"]["label"] for i in items.values()
            if i["evidence_type"] == "condition" and i["fields"]["role"] == control] in (["closed-book model"], ["closed-book"])


@pytest.mark.parametrize("protocol,control", ROLE_SETS)
def test_an_alias_code_is_not_a_qualifier(protocol: Path, control: str, tmp_path: Path) -> None:
    text = ("We compare a RAG system (R) with a closed-book baseline (B).\n\n| System | Accuracy (%) |\n|---|---|\n"
            "| R | 75 |\n| B | 60 |\n")
    _, items = regex_run({"P": f"# P\n\n{text}"}, tmp_path, protocol)
    assert set(measurements(items, "P")) == {("rag", 0.75), (control, 0.60)}


@pytest.mark.parametrize("protocol,control", ROLE_SETS)
def test_a_qualified_row_label_resolves_to_its_role(protocol: Path, control: str, tmp_path: Path) -> None:
    text = ("We compare RAG with RAG (no retrieval).\n\n| System | Accuracy (%) |\n|---|---|\n"
            "| RAG | 75 |\n| RAG (no retrieval) | 60 |\n\nRAG (no retrieval) reaches an accuracy of 58%.\n")
    _, items = regex_run({"P": f"# P\n\n{text}"}, tmp_path, protocol)
    assert set(measurements(items, "P")) == {("rag", 0.75), (control, 0.60), (control, 0.58)}


@pytest.mark.parametrize("roles", [["rag", "baseline", "other"], ["rag", "baseline"]])
def test_a_negated_qualifier_on_a_control_keeps_the_control(roles: list[str]) -> None:
    text = "the closed-book model (no fine-tuning) reaches 40%"
    words = pack_words("regex_condition", "condition")
    found = terms.find_conditions(text, terms.condition_patterns(words["conditions"]), roles,
                                  not_a_system=words["not_a_system"])
    assert [(m.key, m.text) for m in found] == [("baseline", "closed-book model")]


# "N out of M" counts are fractions, for rate-like metrics only.
@pytest.mark.parametrize("sentence,expected", [
    ("RAG answered 75 out of 100 questions correctly (factual accuracy); the closed-book model 60 out of 100.",
     [("rag", 0.75), ("baseline", 0.60)]),
    ("The RAG model gave 662 out of 1,000 answers judged factually correct (factual accuracy).", [("rag", 0.662)]),
    ("The RAG model scored 0 out of 0 on factual accuracy.", []),
    ("The RAG model scored 120 out of 100 on factual accuracy.", []),
    ("For the RAG model we sampled 500 out of 1,000 questions.", []),
])
def test_count_expressions_become_fractions(sentence: str, expected: list[tuple[str, float]], tmp_path: Path) -> None:
    _, items = regex_run({"S": ABSTRACT.format(sentence)}, tmp_path)
    assert measurements(items, "S") == expected


@pytest.mark.parametrize("sentence,expected", [
    ("We evaluate the RAG model on 500 out of 2,000 questions on the factual accuracy benchmark.", []),
    ("The RAG model was run on a random subset of 200 out of 1,000 questions for factual accuracy.", []),
    ("500 out of 2,000 questions were sampled for the RAG model's factual accuracy.", []),
    ("The RAG model answered 662 out of 1,000 questions correctly in terms of factual accuracy.", [("rag", 0.662)]),
    ("The RAG model answered 75 out of 100 (75%) correctly (factual accuracy).", [("rag", 0.75)]),
])
@pytest.mark.parametrize("section", ["Abstract", "Method"])
def test_count_sample_sizes_are_no_values(sentence: str, expected: list[tuple[str, float]], section: str,
                                          tmp_path: Path) -> None:
    text = f"# P\n\n## {section}\n\nWe compare a closed-book model with a retrieval-augmented model. {sentence}\n"
    _, items = regex_run({"S": text}, tmp_path)
    assert measurements(items, "S") == expected


@pytest.mark.parametrize("sentence", [
    "Evaluated on NQ, the RAG model answers 662 out of 1,000 questions correctly (factual accuracy).",
    "On evaluation, the RAG model answers 662 out of 1,000 questions correctly (factual accuracy).",
    "We evaluated the RAG model: it answered 662 out of 1,000 questions correctly (factual accuracy).",
    "Evaluated on TriviaQA, the RAG model answers 662 out of 1,000 questions correctly (factual accuracy).",
])
def test_result_verb_keeps_a_count_near_an_evaluation_word(sentence: str, tmp_path: Path) -> None:
    _, items = regex_run({"S": ABSTRACT.format(sentence)}, tmp_path)
    assert measurements(items, "S") == [("rag", 0.662)]
