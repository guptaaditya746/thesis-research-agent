"""`evidence estimate` (spec D41): calls and tokens before a run, with no model."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from evidence import engine
from evidence.cli import main
from evidence.estimate import CHARS_PER_TOKEN, OUTPUT_TOKENS, PROMPT_TOKENS, estimate

from .conftest import PROTOCOL, corpus_of, provider_of, scripted
from .test_funnel import DOCS, events, make_script


def llm_calls(root: Path) -> int:
    """Extractor and screen calls that reached the model (an event with model calls on it)."""
    return sum(1 for e in events(root, "extractor_call") if e["custom_metadata"]["model_calls"])


def funnel_run(tmp_path: Path, corpus: Path) -> Path:
    return engine.run(PROTOCOL, corpus, tmp_path / "runs", cache=tmp_path / "cache", model="scripted-alias",
                      provider=provider_of(scripted(make_script([]), [])), strategy="gaps", workers=1)


def test_estimate_needs_no_model(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "default_provider", lambda alias: pytest.fail("model"))
    corpus = corpus_of(tmp_path / "corpus", DOCS)
    e = estimate(PROTOCOL, corpus)
    assert e["papers"] == len(DOCS) and e["calls"]["low"] <= e["calls"]["high"]
    assert e["calls"]["high"] > 0 and e["basis"] == "chars/4"


def test_actual_llm_calls_fall_inside_the_estimate(tmp_path):
    corpus = corpus_of(tmp_path / "corpus", DOCS)
    e = estimate(PROTOCOL, corpus)
    out = funnel_run(tmp_path, corpus)
    assert 0 < e["calls"]["low"] <= llm_calls(out) <= e["calls"]["high"]


def test_screened_out_papers_reach_no_llm(tmp_path):
    corpus = corpus_of(tmp_path / "corpus", DOCS)
    e = estimate(PROTOCOL, corpus)
    assert e["screened_out"] >= 1
    assert e["papers_reaching_llm"] == e["papers"] - e["screened_out"]


def test_all_strategy_counts_every_position_and_every_paper(tmp_path):
    corpus = corpus_of(tmp_path / "corpus", DOCS)
    gaps, every = estimate(PROTOCOL, corpus), estimate(PROTOCOL, corpus, strategy="all")
    assert every["calls"]["low"] == every["calls"]["high"] >= gaps["calls"]["high"]
    assert every["papers_reaching_llm"] == every["papers"]


def test_regex_only_selection_has_no_llm_calls(tmp_path):
    e = estimate(PROTOCOL, corpus_of(tmp_path / "corpus", DOCS), selection="regex-only")
    assert e["calls"] == {"low": 0, "high": 0}


def test_input_tokens_follow_the_text_length(tmp_path):
    corpus = corpus_of(tmp_path / "corpus", {"P1": DOCS["P1"]})
    e = estimate(PROTOCOL, corpus, strategy="all")
    each = math.ceil(len(DOCS["P1"]) / CHARS_PER_TOKEN) + PROMPT_TOKENS
    assert e["tokens"]["input"]["high"] == e["calls"]["high"] * each
    assert e["tokens"]["output"]["low"] == e["calls"]["low"] * OUTPUT_TOKENS


def test_from_run_uses_the_runs_tokens_per_call(tmp_path):
    corpus = corpus_of(tmp_path / "corpus", DOCS)
    prior = funnel_run(tmp_path, corpus)
    record = json.loads((prior / "run.json").read_text(encoding="utf-8"))
    e = estimate(PROTOCOL, corpus, from_run=prior)
    assert e["basis"] == f"run {record['run_id']}"
    cost = record["cost"]
    assert e["tokens"]["output"]["high"] == pytest.approx(
        e["calls"]["high"] * cost["output_tokens"] / cost["made_model_calls"], abs=1)


def test_from_run_without_fresh_calls_falls_back_to_chars_per_token(tmp_path):
    corpus = corpus_of(tmp_path / "corpus", DOCS)
    prior = engine.run(PROTOCOL, corpus, tmp_path / "runs", selection="regex-only", provider=None, strategy="gaps")
    record = json.loads((prior / "run.json").read_text(encoding="utf-8"))
    assert record["cost"]["made_model_calls"] == 0
    e = estimate(PROTOCOL, corpus, from_run=prior)
    assert e["basis"] == f"chars/4 (run {record['run_id']} made no fresh calls)"
    assert e["tokens"] == estimate(PROTOCOL, corpus)["tokens"]


def test_reach_basis_says_why_papers_reaching_the_llm_exceed_the_unscreened(tmp_path):
    corpus = corpus_of(tmp_path / "corpus", DOCS)
    assert estimate(PROTOCOL, corpus)["reach_basis"] == "papers the regex screen did not stop"
    every = estimate(PROTOCOL, corpus, strategy="all")
    assert every["screened_out"] >= 1 and every["reach_basis"].startswith("all papers (strategy all")
    escalating = tmp_path / "escalate.yaml"
    miss = "  lexical_miss: escalate\n  on_fail: skip"
    text = PROTOCOL.read_text(encoding="utf-8").replace("  on_fail: skip", miss, 1)
    escalating.write_text(text, encoding="utf-8")
    e = estimate(escalating, corpus)
    assert e["reach_basis"].startswith("all papers (lexical_miss escalate")
    assert e["papers_reaching_llm"] == e["papers"] and e["screened_out"] >= 1


def test_cli_prints_json_and_writes_nothing(tmp_path, capsys):
    corpus = corpus_of(tmp_path / "corpus", DOCS)
    assert main(["estimate", "--protocol", str(PROTOCOL), "--corpus", str(corpus), "--strategy", "all"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["papers"] == len(DOCS) and "note" in printed
    assert not (tmp_path / "runs").exists()
