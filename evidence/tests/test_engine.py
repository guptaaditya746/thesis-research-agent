"""The engine end to end with the regex extractors (offline): run directory, evidence, answer, chain,
replay, re-execution, the corpus files the engine may open, the locate strategies."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from agent.chain import verify
from evidence import engine, rundir
from evidence.calls import NotRecorded
from evidence.locate import LocateError
from evidence.replay import reexec, replay

from .conftest import POISON


def run_regex(protocol_file: Path, corpus: Path, out: Path, **kw):
    return engine.run(protocol_file, corpus, out, selection="regex-only", provider=None, **kw)


def lines(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_run_directory_and_answer(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    root = run_regex(protocol_file, corpus, tmp_path / "runs")
    files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    record = json.loads((root / "run.json").read_text(encoding="utf-8"))
    assert {"run.json", "protocol.yaml", "events.jsonl", "locate.json", "evidence.jsonl", "graph.json",
            "answer.json"} <= files
    assert set(record["outputs"]) == files - {"run.json", "events.jsonl"}
    assert record["mode"] == "run" and record["protocol"]["id"] == "rag-factuality"
    assert all(e.startswith("regex_") for e in record["extractors"]) and len(record["extractors"]) == 4
    assert record["cost"]["calls"] == 20 and record["cost"]["model_calls"] == 0
    answer = json.loads((root / "answer.json").read_text(encoding="utf-8"))
    directions = {s["document"]: s["direction"] for s in answer["studies"]}
    assert directions == {"S001": "supports", "S002": "supports", "S003": "contradicts", "S004": "neutral",
                          "S005": "undetermined"}
    assert answer["label"] == "mixed" and answer["counts"] == {"supporting": 2, "contradicting": 1, "neutral": 1,
                                                                "undetermined": 1}
    s1, s2, s3, s4, s5 = answer["studies"]
    assert s1["delta"] == pytest.approx(0.09) and s1["metric"] == "factual_accuracy"
    assert s1["rag"]["value"] == 0.71 and s1["baseline"]["value"] == 0.62
    assert s2["rag"]["value"] == 0.665 and s2["baseline"]["value"] == 0.58      # table codes R and B
    assert s3["metric"] == "hallucination_rate" and s3["delta"] == pytest.approx(-0.03)
    assert s3["author_claim"]["direction"] == "improves" and s3["author_claim"]["agrees_with_data"] is False
    assert s4["author_claim"]["direction"] == "no_effect" and s4["author_claim"]["agrees_with_data"] is True
    assert s5["reason"] == "no baseline condition found" and s5["delta"] is None
    assert verify(root / "events.jsonl", head=record["chain_head"]).ok


def test_same_value_twice_is_one_item_with_two_value_spans(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    root = run_regex(protocol_file, corpus, tmp_path / "runs")
    items = lines(root / "evidence.jsonl")
    s1 = [i for i in items if i["evidence_type"] == "measurement" and i["spans"][0]["selector"]["file"] == "papers/S001.md"
          and i["fields"]["value"] == 0.62]
    assert len(s1) == 1
    values = [s["selector"]["exact"] for s in s1[0]["spans"] if s["role"] == "value"]
    assert values == ["62%", "62.0"]
    assert s1[0]["found_by"] == [e for e in json.loads((root / "run.json").read_text())["extractors"]
                                 if e.startswith("regex_measurement")]
    # the table code R points to its definition in the setup section (distributed evidence)
    s2 = next(i for i in items if i["evidence_type"] == "measurement" and i["fields"]["value"] == 0.665)
    labels = [s["selector"]["exact"] for s in s2["spans"] if s["role"] == "condition_label"]
    assert "retrieval-augmented variant (R)" in labels and "R" in labels
    assert not any(i["fields"].get("value") == 0.67 for i in items)   # R+ is no condition of the context


def test_outputs_do_not_depend_on_time_or_run_id(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    a = run_regex(protocol_file, corpus, tmp_path / "runs", run_id="a", cache=tmp_path / "c1")
    b = run_regex(protocol_file, corpus, tmp_path / "runs", run_id="b", cache=tmp_path / "c2")
    outputs = [json.loads((r / "run.json").read_text())["outputs"] for r in (a, b)]
    assert outputs[0] == outputs[1]


def test_replay_reproduces_every_output_hash(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    root = run_regex(protocol_file, corpus, tmp_path / "runs")
    new, report = replay(root)
    assert report == {"ok": True, "mismatched": [], "source_run": root.name, "replay_run": new.name}
    assert json.loads((new / "run.json").read_text())["mode"] == "replay"
    assert json.loads((new / "run.json").read_text())["cost"]["cached_calls"] == 20


def test_replay_fails_on_a_cache_miss(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    root = run_regex(protocol_file, corpus, tmp_path / "runs", cache=tmp_path / "cache")
    with pytest.raises(NotRecorded, match="not recorded"):
        replay(root, cache=tmp_path / "empty-cache")


def test_replay_detects_a_changed_output(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    root = run_regex(protocol_file, corpus, tmp_path / "runs")
    record = json.loads((root / "run.json").read_text())
    record["outputs"]["answer.json"] = "0" * 64
    (root / "run.json").write_text(json.dumps(record), encoding="utf-8")
    _, report = replay(root)
    assert report["ok"] is False and report["mismatched"] == ["answer.json"]


def test_reexec_of_regex_is_identical(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    root = run_regex(protocol_file, corpus, tmp_path / "runs")
    new = reexec(root)
    report = json.loads((new / "reexec.json").read_text())
    assert report["totals"] == {"identical": 20}
    assert all(c["output_identical"] for c in report["calls"])
    assert set(report["summary"]) == {"regex_condition", "regex_metric", "regex_measurement", "regex_author_claim"}
    assert all(s["identical"] == s["calls"] == 5 for s in report["summary"].values())
    one = reexec(root, "regex_measurement")
    assert json.loads((one / "reexec.json").read_text())["extractor"] == "regex_measurement"


def test_engine_never_opens_ground_truth(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    opened: list[str] = []
    active = [True]

    def hook(event: str, args: tuple) -> None:
        if active[0] and event == "open" and args and isinstance(args[0], (str, bytes, Path)):
            opened.append(str(args[0]))

    sys.addaudithook(hook)   # audit hooks cannot be removed; `active` switches this one off
    try:
        root = run_regex(protocol_file, corpus, tmp_path / "runs")
        replay(root)
        reexec(root)
    finally:
        active[0] = False
    assert any(p.endswith("manifest.json") for p in opened)
    assert not [p for p in opened if Path(p).name in POISON]


def test_bm25_locate_gives_ranges_and_agent_needs_a_locator(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    text = protocol_file.read_text(encoding="utf-8").replace("strategy: exhaustive", "strategy: bm25")
    text = text.replace("top_k: 6", "top_k: 2").replace("chunk_chars: 1500", "chunk_chars: 200")
    protocol_file.write_text(text, encoding="utf-8")
    root = run_regex(protocol_file, corpus, tmp_path / "runs")
    located = json.loads((root / "locate.json").read_text())
    assert {e["strategy"] for e in located} == {"bm25"}
    assert all(e["scope"]["kind"] == "ranges" and len(e["scope"]["ranges"]) <= 2 for e in located)
    assert all(e["ranked"] for e in located)
    for call in (root / "calls").glob("*.json"):
        result = json.loads(call.read_text())
        assert all(c["range"] is not None for c in result["coverage"])
    protocol_file.write_text(text.replace("strategy: bm25", "strategy: agent"), encoding="utf-8")
    with pytest.raises(LocateError, match="Locator"):
        run_regex(protocol_file, corpus, tmp_path / "runs2")


def test_corpus_hash_is_checked(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    (corpus / "papers" / "S001.md").write_text("tampered", encoding="utf-8")
    with pytest.raises(rundir.CorpusError, match="sha256"):
        run_regex(protocol_file, corpus, tmp_path / "runs")
