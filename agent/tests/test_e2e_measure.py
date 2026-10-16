"""scripts/e2e-measure.py: the measurement table of the Slurm e2e session (docs/earlier-work.md, Runbooks: the e2e session, step 8).

A real v2 run with a scripted model (a claim, then a conclude reply decoded under the reply schema), the
claim_on and attach-style runs of agent/tests/runs.py, and a small gold directory written by hand: every
column is read from what the agent, the attach step and the gold builder write, and a missing file gives
an empty cell, not an error.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from agent.canonical import write_json

from .conftest import REPO
from .runs import baseline_run, research_run
from .test_loop import corpus, go, posix_only, row, unique_quote, claim_cmd, bash  # noqa: F401
from .test_loop_v2 import bare

spec = importlib.util.spec_from_file_location("e2e_measure", REPO / "scripts" / "e2e-measure.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


@posix_only
def test_a_v2_run_with_a_guided_answer(tmp_path: Path, corpus: tuple[Path, Path]) -> None:  # noqa: F811
    from agent.loop import LoopSettings
    replies = [bash(claim_cmd(unique_quote())), bare([row(["claim-000001"])], "one paper")]
    run, outcome, _, _ = go(tmp_path, corpus, replies, budget={"steps": 1, "tokens": 10**6, "announced": True},
                            settings=LoopSettings())
    assert outcome.answer_from == "final"
    m = measure.measure_run(run.root)
    assert (m["exit_status"], m["answer_from"], m["answer_guided"], m["guided_calls"]) == ("submitted", "final", True, 1)
    assert (m["condition"], m["prompt_version"], m["spawn"]) == ("claim_on", "v2", False)
    assert (m["steps"], m["model_calls"], m["commands"], m["rows"], m["facts"]) == (2, 2, 1, 1, 1)
    assert (m["claims_accepted"], m["claims_rejected"], m["guided_refused"], m["model_timeouts"]) == (1, 0, 0, 0)
    assert m["max_prompt_tokens"] > 0 and m["max_masked"] == 0 and "attach" not in m


def test_claims_and_the_attach_step(tmp_path: Path) -> None:
    from agent.tests.conftest import write_corpus
    corpus = write_corpus(tmp_path)
    on = research_run(tmp_path, *corpus).run
    off = baseline_run(tmp_path, *corpus).run
    write_json(off.root / "attach.json", {"facts": [
        {"fact_id": "f1", "status": "attached", "tokens": 900, "steps": [5]},
        {"fact_id": "f4", "status": "no_source", "reason": "budget", "tokens": 60_100, "steps": [8, 9]}],
        "attached": 1, "attached_from_claim": 0, "no_source": 1})
    m_on, m_off = measure.measure_run(on.root), measure.measure_run(off.root)
    assert (m_on["claims_accepted"], m_on["claims_rejected"], m_on["rejected_by_reason"]) == (6, 1, {"not_found": 1})
    assert (m_on["facts"], m_on["facts_with_claims"], m_on["subagents"]) == (5, 4, 1)
    assert m_on["answer_guided"] is False  # these records have no decoding field: free
    a = m_off["attach"]
    assert (a["facts"], a["attached"], a["no_source"], a["max_fact_tokens"], a["max_fact_steps"]) == (2, 1, 1, 60_100, 2)
    assert a["gave_up"] == {"budget": 1} and a["tokens"] is not None  # from agent.verify.stats' attach part
    assert m_off["steps"] == 4  # research only: the attach step's steps are in `attach`
    text = measure.table([m_on, m_off], measure.RUN_COLUMNS)
    assert text.count("\n") == 3 and "| research-r1 | claim_on |" in text and "2 facts, 1 attached" in text


def test_gold_and_missing_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    q = tmp_path / "gold" / "q01"
    q.mkdir(parents=True)
    write_json(q / "doc.json", {"coverage": {"papers": 20, "relevant": 7, "not_relevant": 13, "partial": True},
                                "counts": {"chunks": 61, "chunks_relevant": 9, "candidates": 40, "anchored": 30,
                                           "rejected": {"not_found": 10}, "rows": 12,
                                           "cost": {"calls_made": 75, "input_tokens": 900_000, "seconds": 420.5}},
                                "built": {"models": {"served": ["sub-model"]}}})
    (q / "triage.jsonl").write_text("".join(json.dumps(x) + "\n" for x in [
        {"id": "c1", "label": "context"}, {"id": "c1", "label": "answers"}, {"id": "c2", "label": "irrelevant"}]))
    (q / "pool.jsonl").write_text('{"id": "c1"}\n')
    m = measure.measure_gold(tmp_path / "gold", "q01")
    assert (m["anchor_ok_share"], m["triage"], m["pool"], m["calls_made"]) == (0.75, {"answers": 1, "irrelevant": 1}, 1, 75)
    assert m["draft_facts"] == 0 and m["partial"] is True
    empty = measure.measure_gold(tmp_path / "gold", "q99")  # nothing built: empty cells
    assert empty["candidates"] == 0 and empty["anchor_ok_share"] is None
    out = tmp_path / "m.jsonl"
    assert measure.main(["gold", str(tmp_path / "gold"), "q01", "q99", "--json", str(out)]) == 0
    assert "| q01 | 20 | 7 | 61 | 9 | 40 | 0.75 | 12 | 1/0/1 | 1 | 0 | 75 | 900000 | 420.5 |" in capsys.readouterr().out
    assert len(out.read_text().splitlines()) == 2
    assert measure.main(["runs", str(tmp_path / "nope")]) == 1  # not a run directory: warned, nothing measured
