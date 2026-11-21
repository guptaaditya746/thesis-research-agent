"""D2: roles sharing a model are reported, judge inputs and outputs are logged. D3: token preflight."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperfactory import config, llm
from paperfactory.tests.test_llm import scripted, settings

SCHEMA = {"type": "object", "required": ["choice"], "properties": {"choice": {"type": "string"}}}


def test_shared_models_are_reported(tmp_path: Path) -> None:
    s = settings(tmp_path)
    [w] = config.shared_models(s)
    assert "writer, rewriter, judge, verifier share the model claude-haiku-5-5" in w
    s = settings(tmp_path, default="claude-haiku-5-5", judge="qwen:a", verifier="qwen:b", rewriter="claude-x")
    assert config.shared_models(s) == []


def test_judge_inputs_and_outputs_are_logged(tmp_path: Path) -> None:
    s = settings(tmp_path)
    c = llm.Caller(s, backend=scripted({"choice": "a"}))
    c("judge", "judge:paper", "sys", "the input", SCHEMA)
    c("judge", "judge:paper", "sys", "the input", SCHEMA)          # cached: logged too
    c("tagger", "tag:P1", "sys", "other", SCHEMA)
    rows = [json.loads(x) for x in (s.out_dir / "judge.jsonl").read_text().splitlines()]
    assert [r["cached"] for r in rows] == [False, True]
    assert rows[0]["input"] == "the input" and rows[0]["output"] == {"choice": "a"}


def test_preflight_skips_a_request_that_does_not_fit(tmp_path: Path) -> None:
    s = settings(tmp_path, default={"model": "small", "context_window": 1000, "max_tokens": 500})
    b = scripted({"choice": "a"})
    c = llm.Caller(s, backend=b)
    assert c("judge", "j", "sys", "short", SCHEMA) == {"choice": "a"}
    with pytest.warns(UserWarning, match="context_window 1000"):
        assert c("judge", "j2", "sys", "x" * 3000, SCHEMA) is None
    assert len(b.seen) == 1
    rec = json.loads((s.out_dir / "calls.jsonl").read_text().splitlines()[-1])
    assert rec["skipped"] == "context_window" and rec["parse_error"]


def test_preflight_in_paperorchestra_runner_fails_fast(monkeypatch) -> None:
    runner, _ = llm.po_runner({"model": "small", "context_window": 100, "max_tokens": 50})
    monkeypatch.setattr(llm, "run_backend", lambda *a: pytest.fail("must not call"))
    with pytest.raises(llm.LLMError, match="context_window"):
        runner("sys", "x" * 1000, SCHEMA)
