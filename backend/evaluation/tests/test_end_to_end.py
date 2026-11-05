"""The three packages together, offline: a committed synth corpus → the engine (regex only) → replay →
scoring. Checks the files between the packages (docs/evidence-system.md Part A) fit, not how good regex is."""
from __future__ import annotations

import json
from pathlib import Path

import repo_paths

import pytest

from evaluation import cli
from evidence import engine, extractors, replay

REPO = Path(__file__).resolve().parents[2]
PROTOCOL = repo_paths.DOMAINS / "rag" / "protocols" / "rag-factuality.yaml"
EXAMPLES = REPO / "synth" / "examples"


@pytest.mark.parametrize("level", ["explicit", "distributed", "contradictory"])
def test_synth_corpus_through_engine_replay_and_score(tmp_path: Path, level: str) -> None:
    corpus = EXAMPLES / f"rag-demo-{level}"
    run = engine.run(PROTOCOL, corpus, tmp_path / "runs", selection="regex-only", run_id=level)
    _, check = replay.replay(run)
    assert check["ok"], check["mismatched"]

    assert cli.main(["score", "--run", str(run), "--corpus", str(corpus), "--out", str(tmp_path / "out")]) == 0
    report = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    truth = json.loads((corpus / "ground_truth.json").read_text(encoding="utf-8"))
    answer = json.loads((run / "answer.json").read_text(encoding="utf-8"))
    assert {s["document"] for s in answer["studies"]} == {s["paper"] for s in truth["studies"]}
    assert report  # every section of the report is computed from the engine's real files
    assert (tmp_path / "out" / "report.md").read_text(encoding="utf-8").strip()


def test_agentic_extractor_registers_on_first_use() -> None:
    assert "agentic" in extractors.names()
    assert extractors.get("agentic", {}).spec.kind == "agent"
