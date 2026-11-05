"""Per-extractor rows and cost in report.json (score_extractors) and `evaluate benchmark` pooling them into
the B11 record per extractor id."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evaluation import benchmark as bm
from evaluation.score import score
from evaluation.truth import Run

from . import fixtures as fx
from .test_score import row

TYPES = ("condition", "metric", "measurement", "author_claim")


# (extractor, document, evidence type) of the calls a cascade `until_found` makes on the hand corpus: the regex
# extractor sees every type of S001 (found everything there, so the LLM is not called on S001 except for
# measurements, where the cascade went on), the LLM every type of S002.
TASKS = [(fx.REGEX, "S001", t) for t in TYPES] + [(fx.LLM, "S002", t) for t in TYPES] + [(fx.LLM, "S001", "measurement")]


def add_calls(run: Path, cache_dir: Path | None = None) -> None:
    """calls/*.json (one per TASKS entry), extractor_call events of one second each, and a record cache with
    the token usage of the LLM's model calls (1000 in, 10 out per call)."""
    calls, events, cache = [], [], []
    for n, (extractor, paper, kind) in enumerate(TASKS, start=1):
        call_id = f"t{n:06d}"
        model_calls = [f"mc-{n}"] if extractor == fx.LLM else []
        calls.append({"call_id": call_id, "extractor_id": extractor, "task_sha256": "0" * 64, "status": "ok",
                      "error": None, "items": [], "rejected": [], "coverage": [], "model_calls": model_calls})
        events.append({"task_id": call_id, "subtype": "extractor_call", "agent_id": extractor, "status": "ok",
                       "started_at": "2026-10-17T10:00:00.000000Z", "ended_at": "2026-10-17T10:00:01.000000Z",
                       "custom_metadata": {"model_calls": model_calls, "document": paper, "evidence_type": kind,
                                           "position": 0 if extractor == fx.REGEX else 1}})
        if model_calls:
            cache.append({"key": f"k{n}", "value": {"extractor_id": extractor, "result": {},
                                                    "model_calls": [{"id": model_calls[0], "request": {},
                                                                     "usage": {"input_tokens": 1000,
                                                                               "output_tokens": 10}}]}})
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
    assert len(run.calls) == 9 and len(run.events) == 9
    assert run.usage == {f"mc-{n}": {"input_tokens": 1000, "output_tokens": 10} for n in range(5, 10)}
    cost = {r["extractor"]: r for r in report["extractors"]["cost"]}
    assert cost[fx.REGEX] == {"extractor": fx.REGEX, "calls": 4, "model_calls": 0, "input_tokens": 0, "output_tokens": 0,
                              "seconds": 4.0}
    assert cost[fx.LLM] == {"extractor": fx.LLM, "calls": 5, "model_calls": 5, "input_tokens": 5000, "output_tokens": 50,
                            "seconds": 5.0}


def test_without_a_cache_tokens_are_null_and_without_calls_cost_is_null(tmp_path: Path) -> None:
    report = scored(tmp_path, with_cache=False)
    cost = {r["extractor"]: r for r in report["extractors"]["cost"]}
    assert cost[fx.LLM]["input_tokens"] is None and cost[fx.LLM]["model_calls"] == 5 and cost[fx.LLM]["seconds"] == 5.0
    corpus = fx.write_corpus(tmp_path / "plain")
    run = fx.write_run(tmp_path / "plain" / "runs", list(fx.perfect_items().values()), fx.engine_answer(fx.perfect_items()))
    plain = score(run, corpus)
    assert plain["extractors"]["cost"] is None and plain["extractors"]["recall_scope"] == "all_facts"
    regex = ext_row(plain, fx.REGEX)
    assert (regex["items"], regex["facts"], regex["recall"]) == (9, 15, 0.6)   # no events: every fact counts


def test_per_extractor_rows_count_an_item_for_every_finder(tmp_path: Path) -> None:
    report = scored(tmp_path)
    assert report["extractors"]["recall_scope"] == "called"
    regex, llm = ext_row(report, fx.REGEX), ext_row(report, fx.LLM)
    assert (regex["items"], regex["matched"], regex["facts"], regex["precision"], regex["recall"]) == (9, 9, 9, 1.0, 1.0)
    assert (llm["items"], llm["only"], llm["only_matched"], llm["facts"]) == (7, 6, 6, 9)   # S002's 6 + S001's 3 measurements
    assert llm["recall"] == pytest.approx(7 / 9)
    m = ext_row(report, fx.REGEX, "measurement")
    assert (m["items"], m["facts"], m["span_accuracy"], m["association_accuracy"], m["associated"]) == (3, 3, 1.0, 1.0, 3)
    assert ext_row(report, fx.REGEX, "condition")["association_accuracy"] is None
    assert ext_row(report, fx.LLM, "measurement", "paraphrased")["recall"] == 1.0
    assert not [r for r in report["extractors"]["rows"] if r["extractor"] == fx.REGEX and r["level"] == "paraphrased"]
    explicit = ext_row(report, fx.LLM, "measurement", "explicit")
    assert (explicit["items"], explicit["facts"]) == (1, 3) and explicit["recall"] == pytest.approx(1 / 3)   # S001.m3


def test_recall_denominator_follows_the_calls_not_the_items(tmp_path: Path) -> None:
    """An extractor never called on a document is not charged with its facts; one called and finding nothing is."""
    corpus = fx.write_corpus(tmp_path)
    items = fx.perfect_items()
    run = fx.write_run(tmp_path / "runs", list(items.values()), fx.engine_answer(items))
    add_calls(run)
    events = [json.loads(x) for x in (run / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    events.append({"subtype": "extractor_call", "agent_id": fx.REGEX, "status": "ok",
                   "started_at": "2026-10-17T10:00:00.000000Z", "ended_at": "2026-10-17T10:00:01.000000Z",
                   "custom_metadata": {"document": "S002", "evidence_type": "author_claim", "model_calls": []}})
    (run / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8", newline="\n")
    report = score(run, corpus)
    regex = ext_row(report, fx.REGEX)
    assert (regex["items"], regex["facts"], regex["recall"]) == (9, 10, 0.9)             # + S002's claim, not found
    claim = ext_row(report, fx.REGEX, "author_claim", "paraphrased")
    assert (claim["items"], claim["facts"], claim["recall"]) == (0, 1, 0.0)


def test_benchmark_pools_rows_per_level_and_cost_per_call(tmp_path: Path) -> None:
    a = scored(tmp_path, "a", "explicit")
    b = scored(tmp_path, "b", "paraphrased", with_cache=False)
    records = bm.benchmark([a, b])
    assert set(records) == {fx.REGEX, fx.LLM}
    r = records[fx.REGEX]
    assert (r["name"], r["version"], r["levels"]) == ("regex_result", "1", ["explicit", "paraphrased"])
    assert [c["corpus_id"] for c in r["corpora"]] == ["c-a", "c-b"]
    overall = row(r["rows"], evidence_type="all", level="all")
    assert (overall["items"], overall["facts"], overall["recall"]) == (18, 18, 1.0)
    explicit = row(r["rows"], evidence_type="measurement", level="explicit")
    assert (explicit["items"], explicit["facts"], explicit["association_accuracy"]) == (3, 3, 1.0)
    assert r["recall_scope"] == ["called", "called"]
    llm = records[fx.LLM]
    assert row(llm["rows"], evidence_type="measurement", level="paraphrased")["items"] == 3
    cost = llm["cost"]
    assert (cost["runs"], cost["calls"], cost["model_calls"], cost["input_tokens"]) == (2, 10, 10, 5000)
    assert cost["per_call"]["input_tokens"] == 1000.0 and cost["calls_recorded"]["input_tokens"] == 5   # b has no cache
    assert cost["per_call"]["seconds"] == 1.0 and cost["per_call"]["model_calls"] == 1.0
    assert llm["stability"] is None and llm["stability_ambiguous"] == []


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


def test_a_bare_name_shared_by_two_ids_leaves_stability_null(tmp_path: Path) -> None:
    reexec = {"calls": [{"document": "S001", "evidence_type": "measurement", "extractor": "regex_result",
                         "outcome": "identical", "items_original": 3, "items_reproduced": 3}]}
    report = scored(tmp_path, reexec=reexec)
    second = "regex_result@2#cccccccccccc"                     # another version of the same name in this report
    report["extractors"]["cost"].append({"extractor": second, "calls": 1, "model_calls": 0, "input_tokens": 0,
                                         "output_tokens": 0, "seconds": 1.0})
    records = bm.benchmark([report])
    assert records[fx.REGEX]["stability"] is None and records[fx.REGEX]["stability_ambiguous"] == ["c-a"]
    assert records[second]["stability"] is None and records[second]["stability_ambiguous"] == ["c-a"]
    text = bm.render(records)
    assert "Stability rows keyed by the bare name `regex_result` were left out for c-a" in text
    alone = bm.benchmark([scored(tmp_path, "b", reexec=reexec)])
    assert alone[fx.REGEX]["stability"]["calls"] == 1 and alone[fx.REGEX]["stability_ambiguous"] == []


def test_benchmark_writes_a_record_per_extractor_and_one_markdown(tmp_path: Path) -> None:
    records = bm.benchmark([scored(tmp_path, "a", "explicit")])
    paths = bm.write_benchmark(records, tmp_path / "bench")
    assert paths[-1] == tmp_path / "bench" / "benchmark.md"
    for extractor in (fx.REGEX, fx.LLM):
        path = tmp_path / "bench" / extractor / "benchmark.json"
        assert path in paths and json.loads(path.read_text(encoding="utf-8"))["extractor_id"] == extractor
    text = paths[-1].read_text(encoding="utf-8")
    assert f"## {fx.REGEX}" in text and f"## {fx.LLM}" in text and "Re-execution stability: not measured." in text
    assert "| measurement" in text and "5000 [1000.000]" in text and "recall scope called" in text
    assert bm.benchmark([{"corpus_id": "x", "synthesis": []}]) == {}
    assert bm.split_id("plain") == ("plain", None) and bm.split_id("a@2#ff") == ("a", "2")


def test_report_markdown_has_the_per_extractor_section(tmp_path: Path) -> None:
    from evaluation import report as rep

    text = rep.render(scored(tmp_path))
    assert "## Per extractor" in text and "Cost per extractor" in text and fx.LLM in text


def test_benchmark_pools_f1_with_a_cluster_interval_over_parent_studies(tmp_path: Path) -> None:
    a = scored(tmp_path, "a", "explicit")
    b = scored(tmp_path, "b", "paraphrased")   # same seed and study ids: the same two parent clusters
    records = bm.benchmark([a, b])
    llm = records[fx.LLM]["pooled"]["f1"]   # called on S002 and on S001's measurements: two clusters over both levels
    assert (llm["unit"], llm["n_clusters"]) == ("cluster", 2)
    assert llm["point"] == pytest.approx(0.875)   # 14 items, all matched, of 18 facts
    assert records[fx.REGEX]["pooled"]["f1"]["n_clusters"] == 1   # called on S001 alone
    assert {(r["extractor"], r["cluster"]) for r in a["extractors"]["papers"]} == {
        (fx.REGEX, "1/S001"), (fx.LLM, "1/S001"), (fx.LLM, "1/S002")}


def test_a_duplicate_paper_belongs_to_its_parent_studys_cluster() -> None:
    from evaluation.truth import GroundTruth
    truth = GroundTruth("c", "q", [{"study_id": "S001", "paper": "S001", "level": "explicit"},
                                   {"study_id": "S009", "paper": "S009", "level": "explicit", "duplicate_of": "S001"}],
                        [], {})
    truth.seed = 7
    assert truth.cluster_of("S009") == truth.cluster_of("S001") == "7/S001"


def test_benchmark_md_shows_the_pooled_cluster_f1(tmp_path: Path) -> None:
    records = bm.benchmark([scored(tmp_path, "a", "explicit"), scored(tmp_path, "b", "paraphrased")])
    text = bm.write_benchmark(records, tmp_path / "bench")[-1].read_text(encoding="utf-8")
    assert "Pooled F1 (cluster bootstrap over parent studies): 0.875 [" in text and "2 clusters" in text


def test_an_extractor_without_call_events_counts_every_fact_in_its_papers(tmp_path: Path,
                                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    """As score_extractors: an extractor id with no extractor_call event at all (its items are in the run) is
    scored against every fact, in its per-paper rows too (the benchmark's pooled F1 resamples those)."""
    monkeypatch.setitem(globals(), "TASKS", [t for t in TASKS if t[0] == fx.REGEX])   # the LLM: no events
    report = scored(tmp_path)
    facts = sum(r["facts"] for r in report["extractors"]["papers"] if r["extractor"] == fx.LLM)
    assert facts == ext_row(report, fx.LLM)["facts"] > 0
