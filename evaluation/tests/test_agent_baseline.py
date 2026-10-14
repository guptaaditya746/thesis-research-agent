"""The agent baseline: corpus conversion, the question-only concept, the mapping call, the hard rule."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agent.concept import validate_concept
from evaluation.baselines import agent as baseline
from evaluation.score import score_answers
from evidence.agentic.runner import AgentSettings, ResearchAgentRunner, write_agent_corpus
from gold.llm import JsonlCache

from . import fixtures as fx
from .agentic_fakes import FakeRunner
from .helpers import Scripted, guard_corpus

MAPPED = {"label": "mixed", "answer_text": "Retrieval helped in S001 and hurt in S002.",
          "studies": [{"document": "S001", "stance": "supports"}, {"document": "S002", "stance": "contradicts"}]}


def agent_record() -> dict[str, Any]:
    return {"run_id": "agent-baseline", "outcome": {"exit_status": "submitted", "answer_from": "final", "steps": 9,
                                                    "tokens": 90_000},
            "claims": [{"claim_id": "claim-000001", "status": "accepted", "file": "S002.md",
                        "quote": "this rose to 25%"}],
            "model_calls": [{"task_id": "task-000001"}],
            "answer": {"rows": [{"id": "r1", "cells": {"conclusion": "Mixed: helps in S001, hurts in S002",
                                                      "papers": ["S001", "S002"]},
                                 "facts": [{"id": "f1", "s": "S002", "p": "hallucination with retrieval", "o": "25%",
                                            "claims": ["claim-000001"]}]}], "notes": "two papers"}}


def test_agent_baseline_maps_the_answer_to_label_and_stances(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = fx.write_corpus(tmp_path)
    attempts = guard_corpus(monkeypatch, corpus)
    runner, mapper = FakeRunner(agent_record()), Scripted(MAPPED)
    answer = baseline.agent_baseline(corpus, runner=runner, model=mapper.model())
    assert attempts == []
    job = runner.jobs[0]
    assert job.files == {"S001.md": fx.S001, "S002.md": fx.S002} and job.budget == baseline.BUDGET
    assert validate_concept(job.concept) == [] and job.concept["title"] == fx.QUESTION
    assert "rag" not in json.dumps(job.concept["answer_shape"]).lower()  # nothing of the protocol
    assert answer["system"] == "agent-baseline" and answer["label"] == "mixed"
    assert answer["studies"] == [{"document": "S001", "direction": "supports"},
                                 {"document": "S002", "direction": "contradicts"}]
    assert answer["agent"]["claims"] == 1 and answer["agent"]["exit_status"] == "submitted"
    prompt = mapper.prompts[0]
    assert "Corpus paper ids: S001, S002" in prompt and 'quote from S002.md: "this rose to 25%"' in prompt
    assert "Notes: two papers" in prompt
    monkeypatch.undo()
    fx.dump(tmp_path / "agent.json", answer)
    assert score_answers(corpus, [tmp_path / "agent.json"])["synthesis"][0]["label_correct"]


def test_no_rows_is_insufficient_without_a_call(tmp_path: Path) -> None:
    record = agent_record() | {"answer": {"rows": [], "notes": "harness: no valid final answer (exit status budget)"}}
    mapper = Scripted(MAPPED)
    answer = baseline.agent_baseline(fx.write_corpus(tmp_path), runner=FakeRunner(record), model=mapper.model())
    assert answer["label"] == "insufficient" and answer["studies"] == [] and mapper.prompts == []


def test_mapping_is_cached(tmp_path: Path) -> None:
    corpus, cache = fx.write_corpus(tmp_path), JsonlCache(tmp_path / "map.jsonl")
    a = baseline.agent_baseline(corpus, runner=FakeRunner(agent_record()), model=Scripted(MAPPED).model(), cache=cache)
    again = Scripted({"label": "refuted", "studies": [], "answer_text": ""})
    b = baseline.agent_baseline(corpus, runner=FakeRunner(agent_record()), model=again.model(), cache=cache)
    assert again.prompts == [] and a == b


def test_agent_corpus_layout_is_what_the_broker_reads(tmp_path: Path) -> None:
    from agent.broker import Corpus

    root, manifest = write_agent_corpus({"S001.md": fx.S001}, tmp_path / "c")
    corpus = Corpus(root, manifest)
    assert corpus.name("S001") == "S001.md" and corpus.index("S001.md").text == fx.S001


def test_baseline_with_the_real_agent(tmp_path: Path) -> None:
    from .test_agentic_agent import FENCE, POSIX, Scripted as ScriptedAgent

    if not POSIX:
        pytest.skip("agent commands need bash, coreutils timeout and pass_fds")
    claim = json.dumps({"s": "S002", "p": "hallucination with retrieval", "o": "25%", "file": "S002.md",
                        "quote": "this rose to 25%"})
    rows = [{"id": "r1", "cells": {"conclusion": "Retrieval hurt in S002", "papers": ["S002"]},
             "facts": [{"id": "f1", "s": "S002", "p": "hallucination with retrieval", "o": "25%",
                        "claims": ["claim-000001"]}]}]
    replies = [f"Look.\n{FENCE}bash\nrg -n 'rose' \"$CORPUS\"; echo '{claim}' | claim\n{FENCE}",
               f"Done.\n{FENCE}json\n{json.dumps({'rows': rows, 'notes': ''})}\n{FENCE}"]
    settings = AgentSettings(sandbox_mode="unsandboxed", broker="inprocess")
    runner = ResearchAgentRunner(settings, model_factory=lambda s: ScriptedAgent(replies, s))
    mapper = Scripted({"label": "refuted", "answer_text": "S002: worse",
                       "studies": [{"document": "S002", "stance": "contradicts"}]})
    answer = baseline.agent_baseline(fx.write_corpus(tmp_path), runner=runner, model=mapper.model())
    assert answer["agent"]["exit_status"] == "submitted" and answer["agent"]["claims"] == 1
    assert answer["label"] == "refuted" and 'quote from S002.md: "this rose to 25%"' in mapper.prompts[0]
