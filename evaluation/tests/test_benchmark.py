"""Per-extractor rows and cost in report.json (score_extractors) and `evaluate benchmark` pooling them into
the B11 record per extractor id."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluation import benchmark as bm
from evaluation.score import score
from evaluation.truth import Run

from . import fixtures as fx
from .test_score import row

TYPES = ("condition", "metric", "measurement", "author_claim")


def add_calls(run: Path, cache_dir: Path | None = None) -> None:
    """calls/*.json (one per extractor and paper), extractor_call events with durations, and a record cache
    with the token usage of the LLM's model calls."""
    calls, events, cache = [], [], []
    n = 0
    for extractor in (fx.REGEX, fx.LLM):
        for paper in fx.PAPERS:
            n += 1
            call_id = f"t{n:06d}"
            model_calls = [f"mc-{n}"] if extractor == fx.LLM else []
            calls.append({"call_id": call_id, "extractor_id": extractor, "task_sha256": "0" * 64, "status": "ok",
                          "error": None, "items": [], "rejected": [], "coverage": [], "model_calls": model_calls})
            events.append({"task_id": call_id, "subtype": "extractor_call", "agent_id": extractor, "status": "ok",
                           "started_at": "2026-10-17T10:00:00.000000Z",
                           "ended_at": f"2026-10-17T10:00:0{n}.500000Z",
                           "custom_metadata": {"model_calls": model_calls, "document": paper}})
            if model_calls:
                cache.append({"key": f"k{n}", "value": {"extractor_id": extractor, "result": {},
                                                        "model_calls": [{"id": model_calls[0], "request": {},
                                                                         "usage": {"input_tokens": 1000 * n,
                                                                                   "output_tokens": 10 * n}}]}})
    (run / "calls").mkdir()
    for call in calls:
        fx.dump(run / "calls" / f"{call['call_id']}.json", call)
    events.append({"subtype": "locate", "agent_id": "locate:whole"})   # not an extractor call: ignored
    (run / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8", newline="\n")
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "extractor_calls.jsonl").write_text("".join(json.dumps(c) + "\n" for c in cache),
                                                         encoding="utf-8", newline="\n")


def scored(tmp_path: Path, name: str = "a", level: str | None = None, with_cache: bool = True,
           reexec: Any = None) -> dict[str, Any]:
    corpus = fx.write_corpus(tmp_path / name, corpus_id=f"c-{name}")
    if level:
        truth = fx.ground_truth(f"c-{name}")
        for s in truth["studies"]:
            s["level"] = level
        fx.dump(corpus / "ground_truth.json", truth)
    cache_dir = tmp_path / name / "cache"
    items = fx.perfect_items()
    run = fx.write_run(tmp_path / name / "runs", list(items.values()), fx.engine_answer(items), reexec=reexec,
                       settings={"cache": str(cache_dir)} if with_cache else None)
    add_calls(run, cache_dir if with_cache else None)
    return score(run, corpus)


def ext_row(report: dict[str, Any], extractor: str, kind: str = "all", level: str = "all") -> dict[str, Any]:
    return row(report["extractors"]["rows"], extractor=extractor, evidence_type=kind, level=level)


def test_run_reads_calls_events_and_usage(tmp_path: Path) -> None:
    report = scored(tmp_path)
    run = Run.load(tmp_path / "a" / "runs" / "run-1")
    assert len(run.calls) == 4 and len(run.events) == 4
    assert run.usage == {"mc-3": {"input_tokens": 3000, "output_tokens": 30}, "mc-4": {"input_tokens": 4000, "output_tokens": 40}}
    cost = {r["extractor"]: r for r in report["extractors"]["cost"]}
    assert cost[fx.REGEX] == {"extractor": fx.REGEX, "calls": 2, "model_calls": 0, "input_tokens": 0, "output_tokens": 0,
                              "seconds": 4.0}   # 1.5 s + 2.5 s
    assert cost[fx.LLM] == {"extractor": fx.LLM, "calls": 2, "model_calls": 2, "input_tokens": 7000, "output_tokens": 70,
                            "seconds": 8.0}     # 3.5 s + 4.5 s


def test_without_a_cache_tokens_are_null_and_without_calls_cost_is_null(tmp_path: Path) -> None:
    report = scored(tmp_path, with_cache=False)
    cost = {r["extractor"]: r for r in report["extractors"]["cost"]}
    assert cost[fx.LLM]["input_tokens"] is None and cost[fx.LLM]["model_calls"] == 2 and cost[fx.LLM]["seconds"] == 8.0
    corpus = fx.write_corpus(tmp_path / "plain")
    run = fx.write_run(tmp_path / "plain" / "runs", list(fx.perfect_items().values()), fx.engine_answer(fx.perfect_items()))
    plain = score(run, corpus)
    assert plain["extractors"]["cost"] is None and plain["extractors"]["rows"]


def test_per_extractor_rows_count_an_item_for_every_finder(tmp_path: Path) -> None:
    report = scored(tmp_path)
    regex, llm = ext_row(report, fx.REGEX), ext_row(report, fx.LLM)
    assert (regex["items"], regex["matched"], regex["facts"], regex["precision"], regex["recall"]) == (9, 9, 15, 1.0, 0.6)
    assert (llm["items"], llm["only"], llm["only_matched"]) == (7, 6, 6)
    m = ext_row(report, fx.REGEX, "measurement")
    assert (m["items"], m["facts"], m["span_accuracy"], m["association_accuracy"], m["associated"]) == (3, 5, 1.0, 1.0, 3)
    assert ext_row(report, fx.REGEX, "condition")["association_accuracy"] is None
    assert ext_row(report, fx.LLM, "measurement", "paraphrased")["recall"] == 1.0
    assert not [r for r in report["extractors"]["rows"] if r["extractor"] == fx.REGEX and r["level"] == "paraphrased"]
    assert ext_row(report, fx.LLM, "measurement", "explicit")["items"] == 1   # S001.m3, found by both


def test_benchmark_pools_rows_per_level_and_cost_per_call(tmp_path: Path) -> None:
    a = scored(tmp_path, "a", "explicit")
    b = scored(tmp_path, "b", "paraphrased", with_cache=False)
    records = bm.benchmark([a, b])
    assert set(records) == {fx.REGEX, fx.LLM}
    r = records[fx.REGEX]
    assert (r["name"], r["version"], r["levels"]) == ("regex_result", "1", ["explicit", "paraphrased"])
    assert [c["corpus_id"] for c in r["corpora"]] == ["c-a", "c-b"]
    overall = row(r["rows"], evidence_type="all", level="all")
    assert (overall["items"], overall["facts"], overall["recall"]) == (18, 30, 0.6)
    explicit = row(r["rows"], evidence_type="measurement", level="explicit")
    assert (explicit["items"], explicit["facts"], explicit["association_accuracy"]) == (3, 5, 1.0)
    llm = records[fx.LLM]
    assert row(llm["rows"], evidence_type="measurement", level="paraphrased")["items"] == 3
    cost = llm["cost"]
    assert (cost["runs"], cost["calls"], cost["model_calls"], cost["input_tokens"]) == (2, 4, 4, 7000)
    assert cost["per_call"]["input_tokens"] == 3500.0 and cost["calls_recorded"]["input_tokens"] == 2   # b has no cache
    assert cost["per_call"]["seconds"] == 4.0 and cost["per_call"]["model_calls"] == 1.0   # 16 s over 4 calls
    assert llm["stability"] is None


def test_stability_rows_match_by_id_name_or_summary_listing(tmp_path: Path) -> None:
    def call(name: str, outcome: str, original: int, reproduced: int) -> dict:
        return {"document": "S001", "evidence_type": "measurement", "extractor": name, "outcome": outcome,
                "items_original": original, "items_reproduced": reproduced}

    reexec = {"calls": [call("regex_result", "identical", 3, 3), call("regex_result", "identical", 2, 2),
                        call("other", "items_missing", 2, 1), call("third", "identical", 1, 1)],
              "summary": {"other": {"calls": 1, "extractor_ids": [fx.LLM]}}}
    report = scored(tmp_path, reexec=reexec)
    records = bm.benchmark([report, report])
    regex = records[fx.REGEX]["stability"]
    assert (regex["reports"], regex["calls"], regex["identical"], regex["identical_share"]) == (2, 4, 4, 1.0)
    assert regex["items_original"] == 10 and regex["item_stability"] == 1.0
    llm = records[fx.LLM]["stability"]
    assert (llm["calls"], llm["identical_share"], llm["item_stability"], llm["outcomes"]) == (2, 0.0, 0.5, {"items_missing": 2})


def test_benchmark_writes_a_record_per_extractor_and_one_markdown(tmp_path: Path) -> None:
    records = bm.benchmark([scored(tmp_path, "a", "explicit")])
    paths = bm.write_benchmark(records, tmp_path / "bench")
    assert paths[-1] == tmp_path / "bench" / "benchmark.md"
    for extractor in (fx.REGEX, fx.LLM):
        path = tmp_path / "bench" / extractor / "benchmark.json"
        assert path in paths and json.loads(path.read_text(encoding="utf-8"))["extractor_id"] == extractor
    text = paths[-1].read_text(encoding="utf-8")
    assert f"## {fx.REGEX}" in text and f"## {fx.LLM}" in text and "Re-execution stability: not measured." in text
    assert "| measurement" in text and "7000 [3500.000]" in text
    assert bm.benchmark([{"corpus_id": "x", "synthesis": []}]) == {}
    assert bm.split_id("plain") == ("plain", None) and bm.split_id("a@2#ff") == ("a", "2")


def test_report_markdown_has_the_per_extractor_section(tmp_path: Path) -> None:
    from evaluation import report as rep

    text = rep.render(scored(tmp_path))
    assert "## Per extractor" in text and "Cost per extractor" in text and fx.LLM in text
