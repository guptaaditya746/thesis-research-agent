"""The agentic extractor with the REAL research agent: agent.loop.research_run, its parser, sandbox
wrapper (unsandboxed), in-process broker and `claim` command; only the model is scripted (at
LiteLLM's call, as agent/tests/test_loop.py does). POSIX only: agent commands need bash and fd passing.
"""
from __future__ import annotations

import json
import os
import shutil
from typing import Any

import pytest

pytest.importorskip("minisweagent")

from agent.loop import OrchestratorModel  # noqa: E402
from evidence.agentic.extractor import AgenticExtractor  # noqa: E402
from evidence.agentic.runner import AgentSettings, ResearchAgentRunner  # noqa: E402

from . import fixtures as fx  # noqa: E402
from .agentic_fakes import MEASUREMENT_SCHEMA, Ctx, context, task  # noqa: E402

POSIX = os.name == "posix" and shutil.which("bash") is not None and shutil.which("timeout") is not None
FENCE = "`" * 3


class Scripted(OrchestratorModel):
    abort_exceptions = [*OrchestratorModel.abort_exceptions, IndexError]

    def __init__(self, replies: list[str], settings: AgentSettings) -> None:
        super().__init__(base_url="http://mock.invalid/v1", temperature=settings.temperature, seed=settings.seed)
        self.replies = list(replies)
        self.prompts: list[list[dict[str, Any]]] = []

    def _query(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        self.prompts.append(messages)
        return {"model": "orch-model", "choices": [{"message": {"content": self.replies.pop(0)}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 50, "total_tokens": 1050}}


@pytest.mark.skipif(not POSIX, reason="agent commands need bash, coreutils timeout and pass_fds")
def test_real_agent_run_becomes_items(tmp_path: Any) -> None:
    ids = {k: i.item_id for k, i in fx.perfect_items().items()}
    request = json.dumps({"s": "r1", "p": "value", "o": 0.7, "file": "S001.md", "quote": "0.70"})
    bad = json.dumps({"s": "r1", "p": "value", "o": 0.7, "file": "S001.md", "quote": "R scores 0.71"})
    row = {"id": "r1", "cells": {"condition": ids["S001.c2"], "metric": ids["S001.k1"], "value": 0.7},
           "facts": [{"id": "f1", "s": "r1", "p": "value", "o": "0.7", "claims": ["claim-000001"]}]}
    replies = [f"Read the table and claim.\n{FENCE}bash\nsed -n '/| System/,/R-noRerank/p' \"$CORPUS/S001.md\"; "
               f"echo '{bad}' | claim; echo '{request}' | claim\n{FENCE}",
               f"Done.\n{FENCE}json\n{json.dumps({'rows': [row], 'notes': ''})}\n{FENCE}"]
    holder: dict[str, Scripted] = {}

    def model(settings: AgentSettings) -> Scripted:
        holder["model"] = Scripted(replies, settings)
        return holder["model"]

    settings = AgentSettings(sandbox_mode="unsandboxed", broker="inprocess")
    runner = ResearchAgentRunner(settings, model_factory=model, work_dir=tmp_path)
    extractor = AgenticExtractor(runner, settings)
    result, record = extractor.extract_recorded(task(), Ctx(fx.S001, context(), MEASUREMENT_SCHEMA))
    assert record["outcome"]["exit_status"] == "submitted" and record["outcome"]["answer_from"] == "final"
    assert result.status == "ok" and len(result.items) == 1
    item = result.items[0]
    assert item.fields == {"condition": ids["S001.c2"], "metric": ids["S001.k1"], "value": 0.7}
    assert [(s.role, s.selector["exact"], s.selector["file"]) for s in item.spans] == [("value", "0.70", "papers/S001.md")]
    assert [(r.reason, r.quotes) for r in result.rejected] == [("not_found", ("R scores 0.71",))]
    assert any(c.status == "found" and c.found == 1 for c in result.coverage)
    assert any(c.status == "skipped" for c in result.coverage)  # the abstract was never shown
    assert len(result.model_calls) == 2 and record["trajectory"] is not None
    prompt = holder["model"].prompts[0][1]["content"]  # the task message holds the concept brief
    assert "Every measurement stated in S001.md" in prompt and ids["S001.c2"] in prompt
    corpus = tmp_path / result.model_calls[0].split("/")[0] / "corpus"
    assert sorted(p.name for p in corpus.iterdir()) == ["S001.md", "manifest.json"]  # the agent saw one paper only
