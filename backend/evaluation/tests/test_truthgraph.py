import json
from pathlib import Path

import repo_paths
from types import SimpleNamespace

import pytest

from evaluation.truth import GroundTruth
from evidence import contract
from evidence.kg.build import build
from evidence.kg.query import Answer, run_template
from evidence.kg.truthgraph import matches, split, truth_items, truth_store
from evidence.pack import RoleMap, load_pack
from evidence.protocol import load

ROOT = Path(__file__).resolve().parents[2]
CORPUS = repo_paths.TESTS / "EV2" / "corpora" / "rag-claude-s1-mixed"
PROTOCOL = repo_paths.DOMAINS / "rag" / "protocols" / "rag-factuality.yaml"


@pytest.fixture(autouse=True)
def _registry():
    before = dict(contract.ITEM_PREFIX)
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


@pytest.fixture(scope="module")
def truth() -> GroundTruth:
    return GroundTruth.load(CORPUS / "ground_truth.json")


def params(**more):
    spec = load(PROTOCOL).synthesis
    base = {"sides": [spec.compare.treatment, spec.compare.control], "metrics": list(spec.metric_names),
            "higher_is_better": {m.canonical: m.higher_is_better for m in spec.metrics},
            "min_effect": spec.min_effect, "prefer": list(spec.pairing.prefer)}
    return {**base, **more}


def expected_directions(truth: GroundTruth) -> list[dict]:
    key = {"supporting": "supports", "contradicting": "contradicts", "neutral": "neutral"}
    return [{"paper": p, "direction": d} for group, d in key.items() for p in truth.answer[group]]


def test_the_answer_key_gives_the_expected_answer(truth):
    answer = run_template(truth_store(truth), "effect", params())
    assert matches(Answer(rows=[r for r in answer.rows if r["direction"] != "undetermined"], empty=False),
                   expected_directions(truth))


def test_wrong_query_is_synthesis_error(truth):
    """Treatment and control swapped: wrong on the answer key too, so the fault is in the query, not the records."""
    expected = expected_directions(truth)
    bad = params(sides=list(reversed(params()["sides"])))
    ours = run_template(truth_store(truth), "effect", bad)
    gold = run_template(truth_store(truth), "effect", bad)
    assert split(ours, gold, expected) == "synthesis error"


def test_missing_record_is_extraction_error(truth):
    """The right query, but one paper's records are missing from ours: right on the answer key, wrong on ours."""
    expected = expected_directions(truth)
    items = truth_items(truth)
    dropped = sorted(items)[0]
    ours_store = build([SimpleNamespace(id=p) for p in items if p != dropped], {p: i for p, i in items.items() if p != dropped},
                       RoleMap(load_pack("rag")), None)
    ours = run_template(ours_store, "effect", params())
    gold = run_template(truth_store(truth), "effect", params())
    ours = Answer(rows=[r for r in ours.rows if r["direction"] != "undetermined"], empty=False)
    gold = Answer(rows=[r for r in gold.rows if r["direction"] != "undetermined"], empty=False)
    assert split(ours, gold, expected) == "extraction error"


def test_right_answer_is_right(truth):
    gold = run_template(truth_store(truth), "effect", params())
    gold = Answer(rows=[r for r in gold.rows if r["direction"] != "undetermined"], empty=False)
    assert split(gold, gold, expected_directions(truth)) == "right"


def test_a_real_question_gives_its_gold(truth):
    store_a = truth_store(SimpleNamespace(gold=truth))
    assert run_template(store_a, "inventory", {}).rows


def test_no_answer_key_is_a_clear_error():
    with pytest.raises(TypeError):
        truth_store(SimpleNamespace(gold=None))
