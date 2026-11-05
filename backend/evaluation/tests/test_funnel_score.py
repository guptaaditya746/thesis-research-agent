"""score_funnel (Part D) on a hand-written run directory with known numbers, its report section and the compare
columns, and on a real `gaps` run of the engine over a committed synth corpus."""
from __future__ import annotations

import json
import re
from pathlib import Path

import repo_paths
from typing import Any

import pytest

from evaluation import report as rep
from evaluation.score import score
from evidence import engine
from evidence.protocol import load

from . import fixtures as fx

REPO = Path(__file__).resolve().parents[2]
PROTOCOL = repo_paths.DOMAINS / "rag" / "protocols" / "rag-factuality.yaml"


def event(subtype: str, document: str, **custom: Any) -> dict[str, Any]:
    return {"task_id": f"t{len(document)}", "subtype": subtype, "agent_id": "x", "status": "ok",
            "started_at": "2026-10-17T10:00:00.000000Z", "ended_at": "2026-10-17T10:00:01.000000Z",
            "custom_metadata": {"document": document, **custom}}


def hand_run(tmp_path: Path) -> Path:
    """S001 complete after position 0 (5 calls, one LLM screen call of 1000/10 tokens), S002 exhausted after
    position 1 (7 calls, two model calls), S004 screened out wrongly and skipped, S005 screened out rightly."""
    items = fx.perfect_items()
    cache = tmp_path / "cache"
    run = fx.write_run(tmp_path / "runs", list(items.values()), fx.f_answer(),
                       settings={"strategy": "gaps", "cache": str(cache)})
    calls = ([event("extractor_call", "S001", evidence_type="screen", model_calls=["mc-1"], position=1)]
             + [event("extractor_call", "S001", evidence_type=t, model_calls=[], position=0)
                for t in ("condition", "metric", "measurement", "author_claim")]
             + [event("extractor_call", "S002", evidence_type=t, model_calls=[], position=0)
                for t in ("screen", "condition", "metric", "measurement", "author_claim")]
             + [event("extractor_call", "S002", evidence_type=t, model_calls=[f"mc-{t}"], position=1)
                for t in ("condition", "measurement")]
             + [event("extractor_call", d, evidence_type="screen", model_calls=[], position=0) for d in ("S004", "S005")])
    screens = [event("screen", d, relevant=r, reason="r", extractor="e", status="ok", calls=[])
               for d, r in (("S001", True), ("S002", True), ("S004", False), ("S005", False))]
    (run / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in calls + screens), encoding="utf-8", newline="\n")
    fx.dump(run / "funnel.json", {"strategy": "gaps", "documents": {
        "S001": {"screen": {"relevant": True}, "skipped": False, "steps": [], "decisions": [], "stopped_after": 0},
        "S002": {"screen": {"relevant": True}, "skipped": False, "steps": [], "decisions": [], "stopped_after": None},
        "S004": {"screen": {"relevant": False}, "skipped": True, "steps": [], "decisions": [], "stopped_after": None},
        "S005": {"screen": {"relevant": False}, "skipped": True, "steps": [], "decisions": [], "stopped_after": None}}})
    cache.mkdir()
    usage = [{"key": "k1", "value": {"model_calls": [{"id": "mc-1", "usage": {"input_tokens": 1000, "output_tokens": 10}},
                                                     {"id": "mc-condition", "usage": {"input_tokens": 200, "output_tokens": 5}},
                                                     {"id": "mc-measurement", "usage": {"input_tokens": 300, "output_tokens": 5}}]}}]
    (cache / "extractor_calls.jsonl").write_text("".join(json.dumps(u) + "\n" for u in usage), encoding="utf-8", newline="\n")
    return run


def test_funnel_numbers_on_the_hand_written_run(tmp_path: Path) -> None:
    corpus = fx.write_f_corpus(tmp_path)
    result = score(hand_run(tmp_path), corpus)
    funnel = result["funnel"]
    assert funnel["strategy"] == "gaps" and funnel["documents"] == 4
    rows = {r["document"]: r for r in funnel["rows"]}
    assert (rows["S001"]["calls"], rows["S001"]["model_calls"], rows["S001"]["tokens"], rows["S001"]["stop"]) == (5, 1, 1010, "0")
    assert (rows["S002"]["calls"], rows["S002"]["model_calls"], rows["S002"]["tokens"], rows["S002"]["stop"]) == (7, 2, 510, "exhausted")
    assert rows["S004"] == {"document": "S004", "level": "complex", "expected_relevant": True, "relevant": False, "screened": True,
                            "skipped": True, "stop": "skipped", "calls": 1, "model_calls": 0, "input_tokens": 0,
                            "output_tokens": 0, "tokens": 0}
    assert rows["S005"]["expected_relevant"] is False and rows["S005"]["screened"] is True
    assert funnel["per_document"] == {"calls": 14 / 4, "model_calls": 3 / 4, "input_tokens": 1500 / 4, "output_tokens": 20 / 4,
                                      "tokens": 1520 / 4}
    assert funnel["stop_positions"] == {"0": 1, "exhausted": 1, "skipped": 2}
    screen = funnel["screen"]
    assert (screen["tp"], screen["fp"], screen["fn"], screen["tn"], screen["documents"]) == (2, 0, 1, 1, 4)
    assert screen["precision"] == 1.0 and screen["recall"] == pytest.approx(2 / 3)
    assert screen["screened_out"] == ["S004", "S005"] and screen["screened_out_wrongly"] == ["S004"]
    text = rep.render(result)
    assert "## Funnel" in text and "Screened out wrongly: S004" in text and "| exhausted" in text
    row = next(r for r in rep.compare([result])["rows"] if r["system"] == "evidence-engine")
    assert (row["strategy"], row["calls_per_document"], row["tokens_per_document"]) == ("gaps", 3.5, 380.0)
    assert row["screen_precision"] == 1.0 and row["screen_recall"] == pytest.approx(2 / 3)
    compare_text = rep.render_compare(rep.compare([result]))
    assert "calls_per_document" in compare_text and "screen_recall" in compare_text
    js, _ = rep.write_report(result, tmp_path / "out")
    assert '"stop_positions"' in js.read_text(encoding="utf-8")


def test_a_run_without_funnel_json_or_screen_events_scores_null_parts(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    run = fx.write_run(tmp_path / "runs", list(fx.perfect_items().values()), fx.engine_answer(fx.perfect_items()))
    assert score(run, corpus)["funnel"] is None
    fx.dump(run / "funnel.json", {"strategy": "all", "documents": {"S001": {"screen": None, "skipped": False, "steps": [],
                                                                          "decisions": [], "stopped_after": None}}})
    funnel = score(run, corpus)["funnel"]
    assert funnel["screen"] is None and funnel["stop_positions"] == {"exhausted": 1}
    assert funnel["rows"][0]["relevant"] is None and funnel["rows"][0]["tokens"] is None   # no events, no cache
    assert funnel["per_document"]["calls"] == 0.0 and funnel["per_document"]["tokens"] is None
    assert "## Funnel" in rep.render(score(run, corpus))


@pytest.mark.parametrize("strategy", ["all", "gaps"])
def test_an_engine_run_on_a_synth_corpus_is_scored_with_its_funnel(tmp_path: Path, strategy: str) -> None:
    corpus = REPO / "synth" / "examples" / "rag-demo-explicit"
    run = engine.run(PROTOCOL, corpus, tmp_path / "runs", selection="regex-only", run_id=strategy, strategy=strategy)
    funnel = score(run, corpus)["funnel"]
    truth = json.loads((corpus / "ground_truth.json").read_text(encoding="utf-8"))
    assert funnel["strategy"] == strategy and funnel["documents"] == len(truth["studies"])
    assert funnel["screen"]["documents"] == len(truth["studies"]) and funnel["screen"]["recall"] == 1.0
    assert sum(funnel["stop_positions"].values()) == len(truth["studies"])
    assert all(r["calls"] >= 1 for r in funnel["rows"])
    if strategy == "all":
        assert set(funnel["stop_positions"]) == {"exhausted"}
    # the screening extractor has no facts: no cascade or per-extractor rows, but its cost is kept
    result = score(run, corpus)
    assert not any(r["extractor"].startswith("regex_screen") for r in result["cascade"]["rows"])
    assert not any(r["extractor"].startswith("regex_screen") for r in result["extractors"]["rows"])
    assert any(r["extractor"].startswith("regex_screen") and r["calls"] == funnel["documents"]
               for r in result["extractors"]["cost"])
    intervals = rep.compare([result])["intervals"]
    assert intervals[0]["strategy"] == strategy and intervals[0]["run_id"] == strategy
    assert "| strategy" in rep.render_compare(rep.compare([result]))


def test_the_two_lexical_miss_arms_stand_apart_in_compare(tmp_path: Path) -> None:
    """The reject and escalate arms run with one run id and one strategy; the report records the protocol and
    the screen's lexical_miss from the run, so the compare rows (and interval rows) tell them apart."""
    corpus = REPO / "synth" / "examples" / "rag-demo-explicit"
    text = PROTOCOL.read_text(encoding="utf-8")
    escalate = tmp_path / "escalate.yaml"
    escalate.write_text(re.sub(r"(?m)^(  on_fail: skip.*)$", r"\1\n  lexical_miss: escalate", text, count=1),
                        encoding="utf-8")
    results = []
    for arm, protocol in (("reject", PROTOCOL), ("escalate", escalate)):
        run = engine.run(protocol, corpus, tmp_path / arm, selection="regex-only", run_id="same", strategy="gaps")
        results.append(score(run, corpus))
    reject, esc = (r["protocol"] for r in results)
    assert reject["lexical_miss"] == "reject" and esc["lexical_miss"] == "escalate"
    assert reject["sha256"] == load(PROTOCOL).sha256 and esc["sha256"] == load(escalate).sha256 != reject["sha256"]
    comparison = rep.compare(results)
    engine_rows = [r for r in comparison["rows"] if r["system"] == "evidence-engine"]
    assert sorted(r["lexical_miss"] for r in engine_rows) == ["escalate", "reject"]
    assert sorted(r["protocol"] for r in engine_rows) == sorted(x["sha256"][:12] for x in (reject, esc))
    assert sorted(r["lexical_miss"] for r in comparison["intervals"]) == ["escalate", "reject"]
    text = rep.render_compare(comparison)
    assert "| lexical_miss" in text and "| escalate" in text and "| reject" in text
