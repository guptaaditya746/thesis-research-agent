"""Both baselines answer every question kind (A7): one mapping reply per kind, answer.json in the kind's shape,
best's wins and winner computed by code, and `--question-id` on the two baseline commands."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evaluation import cli
from evaluation.baselines import agent as agent_baseline
from evaluation.baselines import common, rag
from evaluation.score import score_answers
from modelcall import prompt_sha256

from . import fixtures as fx
from .agentic_fakes import FakeRunner
from .helpers import Scripted
from .test_agent_baseline import agent_record

CITED = {"answer_text": "S001 reports EM; S002 reports exact match and latency.", "citations": []}
PASSAGES = "\n\nPassages:\n\n"


def two_calls(mapped: Any) -> Scripted:
    """The answering call (its prompt lists passages) gets CITED; the mapping call `mapped` (a dict, or a list
    of dicts given in turn, the last repeated)."""
    replies = list(mapped) if isinstance(mapped, list) else [mapped]

    def reply(prompt: str) -> dict[str, Any]:
        if PASSAGES in prompt:
            return CITED
        return replies.pop(0) if len(replies) > 1 else replies[0]
    return Scripted(reply)


def test_effect_mapping_prompt_unchanged() -> None:
    """Existing baseline caches still hit: the effect mapping prompt and its schema hash as before A7."""
    assert prompt_sha256(common.MAP_INSTRUCTIONS, common.AnswerReply) == \
        "7f9a52a35b2190006e383a553a4abcba1893ade394fe3f597e64aa003ffdf7ff"
    params = common.kind_params("rag-factuality")
    assert params.kind == "effect" and params.question == common.DEFAULT_QUESTION
    assert common.map_prompt(params) == (common.MAP_INSTRUCTIONS, common.AnswerReply)


def test_rag_baseline_inventory_shape(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    model = two_calls({"entries": [{"name": "Exact Match", "papers": ["S002", "S999"]},
                                   {"name": "exact  match", "papers": ["S001"]},
                                   {"name": "latency", "papers": ["S002"]}]})
    answer = rag.rag_baseline(corpus, model=model.model(), question_id="inv-metrics", k=2)
    assert answer["kind"] == "inventory" and answer["system"] == "rag-baseline" and answer["target"] == "metric"
    assert answer["question"] == "Which evaluation metrics do the papers report?"
    assert answer["entries"] == [{"name": "Exact Match", "aliases": ["exact match"], "papers": ["S001", "S002"],
                                  "items": []},
                                 {"name": "latency", "aliases": [], "papers": ["S002"], "items": []}]
    assert answer["dropped"] == ["S999"] and answer["question_id"] == "inv-metrics"
    answering, mapping = model.prompts
    assert answering.startswith("Question: Which evaluation metrics")
    assert "Corpus paper ids: S001, S002" in mapping
    instructions, reply_type = common.map_prompt(common.kind_params("inv-metrics"))
    assert answer["mapping_call"]["prompt_sha256"] == prompt_sha256(instructions, reply_type)
    fx.dump(tmp_path / "a.json", answer)
    result = score_answers(corpus, [tmp_path / "a.json"], question_id="inv-metrics")
    assert result["synthesis"][0]["kind"] == "inventory" and result["synthesis"][0]["system"] == "rag-baseline"


def test_best_wins_computed_not_asked(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    instructions, reply_type = common.map_prompt(common.kind_params("best-accuracy"))
    assert set(reply_type.model_fields) == {"studies"}          # no wins or winner asked of the model
    assert "- rag:" in instructions and "- no-retrieval:" in instructions
    split = {"studies": [{"paper": "S001", "winner": "rag"}, {"paper": "S002", "winner": "no-retrieval"}]}
    answer = rag.rag_baseline(corpus, model=two_calls(split).model(), question_id="best-accuracy")
    assert answer["kind"] == "best" and answer["metric"] == "factual_accuracy"
    assert answer["studies"] == [
        {"document": "S001", "winner": "rag", "tied": [], "values": {}, "reason": None},
        {"document": "S002", "winner": "no-retrieval", "tied": [], "values": {}, "reason": None}]
    assert answer["wins"] == {"no-retrieval": 1, "rag": 1} and answer["winner"] is None
    assert answer["tied"] == ["no-retrieval", "rag"]
    both = {"studies": [{"paper": "S002", "winner": "rag"}, {"paper": "S001", "winner": "rag"},
                        {"paper": "S001", "winner": "no-retrieval"}]}   # a paper named twice keeps its first winner
    answer = rag.rag_baseline(corpus, model=two_calls(both).model(), question_id="best-accuracy")
    assert answer["wins"] == {"rag": 2} and answer["winner"] == "rag" and answer["tied"] == []
    open_ = {"studies": [{"paper": "S001", "winner": None}]}
    answer = rag.rag_baseline(corpus, model=two_calls(open_).model(), question_id="best-accuracy")
    assert answer["studies"][0]["reason"]["code"] == "not_stated"
    assert answer["wins"] == {} and answer["winner"] is None and answer["tied"] == []


def test_unknown_kind_name_rejected(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    bad = {"studies": [{"paper": "S001", "winner": "RAG pipeline"}]}
    good = {"studies": [{"paper": "S001", "winner": "rag"}]}
    model = two_calls([bad, good])                        # pydantic-ai's retry: the second reply is accepted
    answer = rag.rag_baseline(corpus, model=model.model(), question_id="best-accuracy")
    assert answer["winner"] == "rag" and len(model.prompts) == 3
    with pytest.raises(RuntimeError):                    # never valid: the call fails as any failed call does
        rag.rag_baseline(corpus, model=two_calls(bad).model(), question_id="best-accuracy")


def test_consistency_shape_from_the_agent(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    mapped = {"studies": [{"paper": "S001", "claim": "improves", "agrees": True},
                          {"paper": "S002", "claim": None, "agrees": None},
                          {"paper": "S404", "claim": "worsens", "agrees": False}]}
    answer = agent_baseline.agent_baseline(corpus, runner=FakeRunner(agent_record()), model=Scripted(mapped).model(),
                                           question_id="cons-accuracy")
    assert answer["kind"] == "consistency" and answer["system"] == "agent-baseline"
    assert answer["metric"] == "factual_accuracy" and answer["dropped"] == ["S404"]
    assert answer["studies"][0] == {"document": "S001", "claim": "improves", "direction": None, "agrees": True,
                                    "reason": None}
    assert answer["agreeing"] == ["S001"] and answer["disagreeing"] == [] and answer["undetermined"] == ["S002"]
    assert answer["studies"][1]["reason"]["code"] == "not_stated"


def test_empty_answer_is_an_empty_kind_answer_without_a_call(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    record = agent_record() | {"answer": {"rows": [], "notes": "no answer"}}
    mapper = Scripted({})
    answer = agent_baseline.agent_baseline(corpus, runner=FakeRunner(record), model=mapper.model(),
                                           question_id="inv-datasets")
    assert answer["kind"] == "inventory" and answer["entries"] == [] and mapper.prompts == []
    assert answer["mapping_call"] is None and answer["target"] == "dataset"


def test_question_id_and_question_are_exclusive(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    with pytest.raises(ValueError, match="question_id"):
        rag.rag_baseline(corpus, model=Scripted({}).model(), question="x?", question_id="inv-metrics")
    with pytest.raises(ValueError, match="unknown question id"):
        common.kind_params("nope")


def test_cli_question_id_sets_question_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = fx.write_corpus(tmp_path)
    model = two_calls({"studies": [{"paper": "S001", "claim": "improves", "agrees": True}]})
    monkeypatch.setattr(cli, "_model", lambda alias: (model.model(alias), alias))
    assert cli.main(["rag-baseline", "--corpus", str(corpus), "--out", str(tmp_path / "rag"),
                     "--question-id", "cons-accuracy"]) == 0
    answer = json.loads((tmp_path / "rag" / "answer.json").read_text(encoding="utf-8"))
    question = "Do the authors' conclusions about factual accuracy agree with their reported results?"
    assert answer["question"] == question and answer["kind"] == "consistency"
    assert model.prompts[0].startswith(f"Question: {question}") and f"Question: {question}" in model.prompts[1]
    assert cli.parser().parse_args(["rag-baseline", "--corpus", "c", "--out", "o"]).question_id is None
    with pytest.raises(SystemExit, match="unknown question id"):
        cli.main(["rag-baseline", "--corpus", str(corpus), "--out", str(tmp_path / "x"), "--question-id", "nope"])
    with pytest.raises(SystemExit, match="--question-id"):
        cli.main(["agent-baseline", "--corpus", str(corpus), "--out", str(tmp_path / "y"), "--question-id",
                  "inv-metrics", "--question", "other?"])


def test_best_stated_tie_scores_correct_against_a_tied_truth(tmp_path: Path) -> None:
    from evaluation.score import score_best

    corpus = fx.write_corpus(tmp_path)
    _, reply_type = common.map_prompt(common.kind_params("best-accuracy"))
    assert set(reply_type.model_json_schema()["$defs"]["BestStudy"]["properties"]) == {"paper", "winner", "tied"}
    tie = {"studies": [{"paper": "S001", "winner": None, "tied": ["rag", "no-retrieval"]},
                       {"paper": "S002", "winner": "rag", "tied": ["rag", "fine-tuned"]},   # a winner: no tie
                       ]}
    answer = rag.rag_baseline(corpus, model=two_calls(tie).model(), question_id="best-accuracy")
    assert answer["studies"][0] == {"document": "S001", "winner": None, "tied": ["no-retrieval", "rag"],
                                    "values": {}, "reason": None}
    assert answer["studies"][1]["tied"] == [] and answer["wins"] == {"rag": 1}
    truth = {"metric": "factual_accuracy", "winner": None, "tied": [], "wins": {},
             "studies": [{"document": "S001", "winner": None, "tied": ["no-retrieval", "rag"], "reason": None}]}
    assert score_best(truth, answer)["studies"][0]["correct"] is True
    lone = {"studies": [{"paper": "S001", "winner": None, "tied": ["rag"]}]}   # one kind is no tie: not stated
    answer = rag.rag_baseline(corpus, model=two_calls(lone).model(), question_id="best-accuracy")
    assert answer["studies"][0]["tied"] == [] and answer["studies"][0]["reason"]["code"] == "not_stated"
    bad = {"studies": [{"paper": "S001", "winner": None, "tied": ["rag", "magic"]}]}
    with pytest.raises(RuntimeError):                    # tied names only the protocol's kinds
        rag.rag_baseline(corpus, model=two_calls(bad).model(), question_id="best-accuracy")


def test_best_prompt_examples_use_the_protocols_kinds() -> None:
    instructions, _ = common.map_prompt(common.kind_params("best-hallucination"))
    assert '"winner": "rag"' in instructions and '"tied": ["no-retrieval", "rag"]' in instructions
    assert "closed-book model" in instructions.split("Example 1")[1]   # the example names come from best.kinds


def test_effect_questions_by_id_get_their_metric_and_direction() -> None:
    latency, reply_type = common.map_prompt(common.kind_params("rag-latency"))
    assert reply_type is common.AnswerReply and latency != common.MAP_INSTRUCTIONS
    assert "lower latency" in latency and "is the improvement" in latency and "factual accuracy" not in latency
    assert "<<" not in latency
    hallucination, _ = common.map_prompt(common.kind_params("rag-hallucination"))
    assert "lower hallucination rate" in hallucination
    assert common.map_prompt(common.kind_params("rag-factuality"))[0] == common.MAP_INSTRUCTIONS   # cache unchanged


def test_paper_id_maps_loose_ids_to_the_manifest() -> None:
    known = ["S001", "S002", "S010"]
    for raw in ("S001", "s001", "S001.md", "s001.MD", "Paper S001", " S001 ", "paper s001.md"):
        assert common.paper_id(raw, known) == "S001", raw
    for raw in ("S999", "", "S001 and S002", "nothing"):
        assert common.paper_id(raw, known) is None, raw


def test_loose_ids_are_kept_not_dropped_in_every_kind(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    mapped = {"studies": [{"paper": "s001.md", "claim": "improves", "agrees": True},
                          {"paper": "Paper S002", "claim": None, "agrees": None},
                          {"paper": "S404", "claim": "worsens", "agrees": False}]}
    answer = agent_baseline.agent_baseline(corpus, runner=FakeRunner(agent_record()), model=Scripted(mapped).model(),
                                           question_id="cons-accuracy")
    assert [s["document"] for s in answer["studies"]] == ["S001", "S002"] and answer["dropped"] == ["S404"]
    model = two_calls({"entries": [{"name": "latency", "papers": ["s002", "S001.md", "S999"]}]})
    inv = rag.rag_baseline(corpus, model=model.model(), question_id="inv-metrics", k=2)
    assert inv["entries"][0]["papers"] == ["S001", "S002"] and inv["dropped"] == ["S999"]
