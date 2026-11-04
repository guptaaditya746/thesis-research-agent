"""`evaluate leak` on a recorded plan run of a Claude-written corpus, with nothing in the scoring mocked (M3): the metric
ids of a plan run are the plan's measure ids, not the truth's canonicals, and the run's question is in no questions.yaml."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation import cli
from evaluation.truth import GroundTruth
from evidence import planrun, stages
from evidence.plan import WordList, write_plan
from evidence.tests.conftest import provider_of
from evidence.tests.test_plan_run import fake_model, make_plan

CORPUS = Path(__file__).resolve().parents[2] / "tests" / "EV2" / "corpora" / "rag-claude-small-mixed"


@pytest.fixture(autouse=True)
def clean_registry():
    with stages.registered():
        yield


def _plan_with_the_corpus_names():
    """A plan whose word list holds the corpus's own condition and metric names (a half of them), measure id
    `accuracy`: the truth files the same metrics under `factual_accuracy` and `hallucination_rate`."""
    truth = GroundTruth.load(CORPUS / "ground_truth.json")
    names = lambda kind, key: [str(f.data[key]) for f in truth.facts.values() if f.type == kind]   # noqa: E731
    conditions, metrics = names("condition", "label"), names("metric", "name")
    things = {"cond": conditions[: len(conditions) // 2], "accuracy": metrics[: len(metrics) // 2]}
    base = make_plan()
    return base.model_copy(update={"words": WordList(things=things, cues=base.words.cues, written_by="orch-model",
                                                     ontology_names={})})


def test_leak_on_a_recorded_plan_run_scores_without_a_question_id(tmp_path: Path) -> None:
    write_plan(_plan_with_the_corpus_names(), tmp_path / "plan.json")
    root = planrun.run(tmp_path / "plan.json", CORPUS, tmp_path / "runs", cache=tmp_path / "cache",
                       selection="regex-only", provider=provider_of(fake_model([])), workers=1)
    assert cli.main(["leak", "--run", str(root), "--corpus", str(CORPUS), "--out", str(tmp_path / "o")]) == 0
    data = json.loads((tmp_path / "o" / "leak.json").read_text(encoding="utf-8"))
    assert set(data) == {"on the list", "unseen"}
    assert data["on the list"]["facts"] > 0 and data["on the list"]["matched"] > 0
