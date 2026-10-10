from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable

import pytest

from agent.concept import claim_ids, concept_sha256, validate_answer, validate_concept
from agent.rundir import RunDir

from .conftest import MANIFEST, fixture
from .test_rundir import SETTINGS

TABLE = fixture("concept_table.json")
GRAPH = fixture("concept_graph.json")


def edited(doc: dict[str, Any], change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    change(out)
    return out


@pytest.mark.parametrize("concept,answer", [("concept_table.json", "answer_table.json"),
                                            ("concept_graph.json", "answer_graph.json")])
def test_worked_examples_validate(concept: str, answer: str) -> None:
    assert validate_concept(fixture(concept)) == []
    assert validate_answer(fixture(answer), fixture(concept)) == []


def test_answer_hash_is_concept_file_hash(tmp_path: Path) -> None:
    run = RunDir.create(tmp_path, "r1", TABLE, corpus_manifest=MANIFEST, **SETTINGS)
    assert run.load_config()["hashes"]["concept_sha256"] == concept_sha256(TABLE)
    run.answer.write_text(json.dumps(fixture("answer_table.json")), encoding="utf-8")
    assert run.validate(complete=True) == []


@pytest.mark.parametrize("change", [
    lambda c: c.__setitem__("subschema", {"classes": ["Person"]}),
    lambda c: c.__setitem__("competency_questions", ["Only one?"]),
    lambda c: c["competency_questions"].append("A fourth?"),
    lambda c: c.pop("measure"),
    lambda c: c.pop("scope"),
    lambda c: c.__setitem__("scope", {}),
    lambda c: c["answer_shape"]["columns"].append({"name": "author", "type": "Person"}),
    lambda c: c["answer_shape"]["columns"].append({"name": "Bad Name", "type": "string"}),
    lambda c: c["answer_shape"]["columns"].append({"name": "x", "type": "dict"}),
    lambda c: c["answer_shape"].__setitem__("kind", "list"),
], ids=["subschema", "one-cq", "four-cqs", "no-measure", "no-scope", "empty-scope", "dup-column",
        "bad-column-name", "bad-type", "bad-kind"])
def test_bad_table_concepts(change: Callable[[dict[str, Any]], None]) -> None:
    assert validate_concept(edited(TABLE, change))


def test_graph_edge_must_use_declared_nodes() -> None:
    bad = edited(GRAPH, lambda c: c["answer_shape"]["edges"].append(
        {"source": "Paper", "predicate": "proposes", "target": "Method"}))
    assert validate_concept(bad) == ["answer_shape: edge ('Paper', 'proposes', 'Method') uses undeclared node type 'Method'"]


def first_row(a: dict[str, Any]) -> dict[str, Any]:
    return a["rows"][0]


@pytest.mark.parametrize("change", [
    lambda a: first_row(a)["cells"].pop("papers"),
    lambda a: first_row(a)["cells"].__setitem__("venue", "ACL"),
    lambda a: first_row(a)["cells"].__setitem__("first_author_papers", "two"),
    lambda a: first_row(a)["cells"].__setitem__("papers", "p12"),
    lambda a: first_row(a).__setitem__("facts", []),
    lambda a: first_row(a)["facts"][0].pop("claims"),
    lambda a: first_row(a)["facts"][0].pop("origin"),
    lambda a: first_row(a)["facts"][0].__setitem__("origin", "model"),
    lambda a: first_row(a)["facts"][0].__setitem__("claims", ["c3"]),
    lambda a: first_row(a)["facts"][0].__setitem__("claims", ["claim-000003", "claim-000003"]),
    lambda a: first_row(a)["facts"][0].__setitem__("o", None),
    lambda a: a.__setitem__("kind", "graph"),
    lambda a: a.__setitem__("concept_sha256", "0" * 64),
    lambda a: a["rows"][1]["facts"][0].__setitem__("id", "f1"),
    lambda a: a["rows"][1].__setitem__("id", "r1"),
], ids=["missing-cell", "extra-cell", "wrong-int", "list-not-str", "no-facts", "no-claims", "no-origin",
        "bad-origin", "bad-claim-id", "dup-claim", "null-object", "wrong-kind", "hash", "dup-fact", "dup-row"])
def test_bad_table_answers(change: Callable[[dict[str, Any]], None]) -> None:
    assert validate_answer(edited(fixture("answer_table.json"), change), TABLE)


@pytest.mark.parametrize("change", [
    lambda a: first_row(a).__setitem__("predicate", "uses"),
    lambda a: first_row(a).__setitem__("target_type", "Method"),
    lambda a: first_row(a)["attributes"].__setitem__("split", "test"),
    lambda a: first_row(a).__setitem__("cells", {}),
], ids=["predicate", "node-type", "attribute", "table-cells"])
def test_bad_graph_answers(change: Callable[[dict[str, Any]], None]) -> None:
    assert validate_answer(edited(fixture("answer_graph.json"), change), GRAPH)


def test_cells_may_be_null_when_unknown() -> None:
    answer = edited(fixture("answer_table.json"),
                    lambda a: first_row(a)["cells"].__setitem__("first_author_papers", None))
    assert validate_answer(answer, TABLE) == []


def test_claim_ids() -> None:
    assert claim_ids(fixture("answer_table.json")) == {
        "claim-000003", "claim-000004", "claim-000007", "claim-000008", "claim-000011"}
