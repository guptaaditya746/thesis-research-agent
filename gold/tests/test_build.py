"""gold/build.py on the D1 papers with a scripted sub-model: statuses, anchors and retries, resume, files."""
from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.function import FunctionModel

from agent.anchor import read_text
from jsonio import sha256_hex
from agent.concept import concept_sha256
from gold import build as build_module
from gold import calls, extract, llm, screen
from gold.build import (
    BuildSettings,
    BuildStopped,
    FolderInUse,
    QuestionDir,
    append_jsonl,
    build,
    git_state,
    live_stage,
    outcome,
    read_jsonl,
)
from gold.chunks import MIN_PIECE_CHARS

from .scripted import (
    GSM8K_AMBIGUOUS,
    GSM8K_FIXED,
    GSM8K_OK,
    INVENTED,
    MMLU_RETYPED,
    SETTINGS,
    Script,
    corpus,
    table_concept,
)

CONTRACT = {
    "chunks": {"paper_id", "chunk", "start", "end", "heading", "chars"},
    "screening": {"paper_id", "status", "chunks_relevant", "findings", "model", "prompt_sha256"},
    "candidates": {"id", "qid", "paper_id", "file", "row", "s", "p", "o", "quote", "anchor", "anchor_status",
                   "chunk", "model", "prompt_sha256"},
}


QUESTION = "Which benchmarks do the RAG papers evaluate on?"


@pytest.fixture
def built(tmp_path):
    c = corpus(tmp_path)
    script = Script()
    doc = build("q01", table_concept(), c, tmp_path / "gold", rotation=script.rotation(), settings=SETTINGS,
                question=QUESTION, log=lambda _: None)
    return {"corpus": c, "script": script, "doc": doc, "dir": QuestionDir(tmp_path / "gold" / "q01"), "tmp": tmp_path}


def by_quote(qdir):
    return {c.get("first_quote", c["quote"]): c for c in read_jsonl(qdir.candidates)}


def test_files_follow_the_contract(built):
    qdir, doc = built["dir"], built["doc"]
    for name, keys in CONTRACT.items():
        rows = read_jsonl(getattr(qdir, name))
        assert rows and all(keys <= set(r) for r in rows), name
    assert json.loads(qdir.doc.read_text(encoding="utf-8")) == doc
    assert doc["qid"] == "q01" and doc["concept_sha256"] == concept_sha256(table_concept())
    assert {"git_commit", "models", "settings", "started_at", "ended_at", "prompts"} <= set(doc["built"])
    assert doc["built"]["models"]["aliases"] == ["scripted-1", "scripted-2"]
    assert doc["built"]["settings"]["concurrency"] == 4
    assert {"papers", "relevant", "not_relevant", "no_text", "error"} <= set(doc["coverage"])
    assert all({"key", "cells", "candidates"} <= set(r) for r in doc["rows"])
    assert qdir.doc_md.read_text(encoding="utf-8").startswith("# q01: Which benchmarks")
    assert json.loads(qdir.progress.read_text(encoding="utf-8"))["stage"] == "done"


def test_prompt_hashes_are_recorded_in_doc_and_every_line(built):
    qdir, prompts = built["dir"], built["doc"]["built"]["prompts"]
    assert prompts["screen"]["prompt_sha256"] == screen.PROMPT.sha256
    assert prompts["screen"]["file"] == "gold/prompts/screen-v1.md"
    assert {r["prompt_sha256"] for r in read_jsonl(qdir.screening)} == {screen.PROMPT.sha256}
    extract_sha = prompts["extract"]["prompt_sha256"]
    assert extract_sha == extract.extract_prompt(table_concept())[0].sha256
    assert {c["prompt_sha256"] for c in read_jsonl(qdir.candidates)} == {extract_sha}
    retried = [c for c in read_jsonl(qdir.candidates) if c["attempts"] == 2]
    assert retried and {c["retry"]["prompt_sha256"] for c in retried} == {extract.RETRY_PROMPT.sha256}
    assert {c["model"] for c in read_jsonl(qdir.candidates)} <= {"scripted-1", "scripted-2"}
    assert all(c["served_model"] for c in read_jsonl(qdir.candidates))
    assert built["doc"]["built"]["models"]["served"]


def test_chunk_offsets_give_the_files_back(built):
    rows = read_jsonl(built["dir"].chunks)
    for paper in {r["paper_id"] for r in rows}:
        text = read_text(built["corpus"].root / f"{paper}.md")
        mine = sorted((r for r in rows if r["paper_id"] == paper), key=lambda r: r["chunk"])
        assert "".join(text[r["start"]:r["end"]] for r in mine) == text
        assert all(r["chars"] == r["end"] - r["start"] for r in mine)


def test_screening_statuses(built):
    records = {r["paper_id"]: r for r in read_jsonl(built["dir"].screening)}
    assert [r["paper_id"] for r in read_jsonl(built["dir"].screening)] == built["corpus"].papers
    assert {p for p, r in records.items() if r["status"] == "relevant"} == {"p3", "p5", "p6"}
    assert records["p99"]["status"] == "no_text" and records["p99"]["chunks"] == 0
    assert {r["status"] for p, r in records.items() if p not in {"p3", "p5", "p6", "p99"}} == {"not_relevant"}
    assert records["p6"]["findings"] == ["evaluates on HotpotQA"]
    cov = built["doc"]["coverage"]
    assert (cov["papers"], cov["relevant"], cov["not_relevant"], cov["no_text"], cov["error"]) == (11, 3, 7, 1, 0)
    assert cov["partial"] is False


def test_anchors_ok_rejected_and_retried(built):
    found = by_quote(built["dir"])
    ok = found[GSM8K_OK]
    assert ok["anchor_status"] == "ok" and ok["attempts"] == 1 and ok["anchor"]["exact"] == GSM8K_OK
    assert ok["anchor"]["file"] == "p5.md" and ok["anchor_in_chunk"] is True
    retyped = found[MMLU_RETYPED]
    assert retyped["anchor_status"] == "ok" and retyped["anchor"]["exact"] == "general reasoning using MMLU"
    fixed = found[GSM8K_AMBIGUOUS]
    assert (fixed["first_reason"], fixed["attempts"], fixed["quote"], fixed["anchor_status"]) == \
        ("ambiguous", 2, GSM8K_FIXED, "ok")
    invented = found[INVENTED]
    assert (invented["first_reason"], invented["anchor_status"], invented["anchor"]) == ("not_found", "not_found", None)
    counts = built["doc"]["counts"]
    assert counts["rejected"] == {"not_found": 1}
    assert (counts["retried"], counts["fixed_by_retry"]) == (2, 1)
    assert built["script"].calls["retry"] == 2  # one per chunk with rejected quotes (p3 and p5)


def test_rows_are_merged_across_papers(built):
    rows = {r["cells"]["dataset"]: r for r in built["doc"]["rows"]}
    assert set(rows) == {"MMLU", "HellaSwag", "GSM8K", "HotpotQA"}
    mmlu = rows["MMLU"]
    assert mmlu["cells"] == {"dataset": "MMLU", "papers": ["p3", "p5"], "paper_count": 2}
    assert mmlu["key"] == "mmlu" and mmlu["papers"] == ["p3", "p5"] and len(mmlu["candidates"]) == 2
    assert rows["GSM8K"]["cells"]["paper_count"] == 1 and len(rows["GSM8K"]["candidates"]) == 2
    assert rows["HellaSwag"]["anchored"] == 0


def test_rerun_makes_no_model_call(built):
    qdir = built["dir"]
    before = {name: getattr(qdir, name).read_text(encoding="utf-8") for name in ("chunks", "screening", "candidates")}
    silent = Script(fail=lambda *_: True)
    doc = build("q01", table_concept(), built["corpus"], built["tmp"] / "gold", rotation=silent.rotation(),
                settings=SETTINGS, question="Which benchmarks do the RAG papers evaluate on?", log=lambda _: None)
    assert sum(silent.calls.values()) == 0
    assert doc["counts"]["model_calls"]["made"] == 0 and doc["counts"]["model_calls"]["cached"] > 0
    assert {name: getattr(qdir, name).read_text(encoding="utf-8") for name in before} == before
    assert doc["rows"] == built["doc"]["rows"]


def chunk_count(qdir, paper):
    return sum(r["paper_id"] == paper for r in read_jsonl(qdir.chunks))


def test_failed_screening_is_an_error_and_retried_on_rerun(tmp_path):
    c = corpus(tmp_path)
    qdir = QuestionDir(tmp_path / "gold" / "q01")
    down = Script(fail=lambda stage, paper, part: stage == "screen" and paper == "p6")
    doc = build("q01", table_concept(), c, tmp_path / "gold", rotation=down.rotation(), settings=SETTINGS,
                log=lambda _: None)
    parts = chunk_count(qdir, "p6")
    record = {r["paper_id"]: r for r in read_jsonl(qdir.screening)}["p6"]
    assert record["status"] == "error" and record["chunks_error"] == list(range(parts))
    assert "scripted failure" in record["error"]
    assert doc["coverage"]["error"] == 1 and doc["counts"]["chunks_error"] == parts
    up = Script()
    doc = build("q01", table_concept(), c, tmp_path / "gold", rotation=up.rotation(), settings=SETTINGS,
                log=lambda _: None)
    assert up.calls == {"screen": parts, "extract": 1}  # only p6's chunks; one holds HotpotQA
    assert doc["coverage"]["error"] == 0 and doc["coverage"]["relevant"] == 3


def test_a_relevant_paper_keeps_its_failed_chunks_listed(tmp_path):
    c = corpus(tmp_path)
    qdir = QuestionDir(tmp_path / "gold" / "q01")
    script = Script(fail=lambda stage, paper, part: stage == "screen" and paper == "p5" and part >= 5)
    build("q01", table_concept(), c, tmp_path / "gold", rotation=script.rotation(),
          settings=replace(SETTINGS, chunk_chars=20_000), log=lambda _: None)
    record = {r["paper_id"]: r for r in read_jsonl(qdir.screening)}["p5"]
    parts = chunk_count(qdir, "p5")
    assert parts > 5
    assert record["status"] == "relevant" and record["chunks_error"] == list(range(4, parts))
    assert record["chunks_relevant"] and max(record["chunks_relevant"]) < 4


def test_failed_extraction_is_retried_on_rerun(tmp_path):
    c = corpus(tmp_path)
    down = Script(fail=lambda stage, paper, part: stage == "extract" and paper == "p6")
    doc = build("q01", table_concept(), c, tmp_path / "gold", rotation=down.rotation(), settings=SETTINGS,
                log=lambda _: None)
    record = {r["paper_id"]: r for r in read_jsonl(QuestionDir(tmp_path / "gold" / "q01").screening)}["p6"]
    assert record["status"] == "relevant" and record["extraction_errors"] == record["chunks_relevant"]
    assert record["candidates"] == 0
    assert doc["counts"]["extraction_errors"] == 1
    up = Script()
    doc = build("q01", table_concept(), c, tmp_path / "gold", rotation=up.rotation(), settings=SETTINGS,
                log=lambda _: None)
    assert up.calls == {"extract": 1} and doc["counts"]["extraction_errors"] == 0
    assert "HotpotQA" in {r["cells"]["dataset"] for r in doc["rows"]}


def test_a_failed_quote_retry_is_counted_and_retried_on_rerun(tmp_path):
    c = corpus(tmp_path)
    qdir = QuestionDir(tmp_path / "gold" / "q01")
    down = Script(fail=lambda stage, paper, part: stage == "retry")
    doc = build("q01", table_concept(), c, tmp_path / "gold", rotation=down.rotation(), settings=SETTINGS,
                log=lambda _: None)
    found = by_quote(qdir)
    for quote in (GSM8K_AMBIGUOUS, INVENTED):
        failed = found[quote]
        assert failed["retry"]["kind"] == "failed" and "scripted failure" in failed["retry"]["error"]
        assert failed["attempts"] == 1 and failed["anchor"] is None and failed["first_reason"]
    assert (doc["counts"]["retry_errors"], doc["counts"]["retried"]) == (2, 0)
    assert outcome(doc)[0] == 1 and "quote retries" in outcome(doc)[1]
    records = {r["paper_id"]: r for r in read_jsonl(qdir.screening)}
    assert records["p3"]["retry_errors"] and records["p5"]["retry_errors"]
    assert "2 facts whose quote retry failed" in qdir.doc_md.read_text(encoding="utf-8")
    ids = {q: c["id"] for q, c in found.items()}
    up = Script()
    doc = build("q01", table_concept(), c, tmp_path / "gold", rotation=up.rotation(), settings=SETTINGS,
                log=lambda _: None)
    assert up.calls == {"retry": 2}  # the failures were not cached; nothing else is asked again
    assert doc["counts"]["retry_errors"] == 0 and outcome(doc) == (0, "")
    again = by_quote(qdir)
    assert again[GSM8K_AMBIGUOUS]["anchor_status"] == "ok" and {q: c["id"] for q, c in again.items()} == ids


def test_a_chunk_too_long_for_one_call_is_read_in_halves(tmp_path):
    c = corpus(tmp_path)
    out = tmp_path / "gold"
    only = replace(SETTINGS, only_papers=("p5", "p6"))
    plain = build("q01", table_concept(), c, tmp_path / "plain", rotation=Script().rotation(), settings=only,
                  log=lambda _: None)
    long = Script(too_long=lambda stage, text: stage in ("screen", "extract") and len(text) > 25_000)
    doc = build("q01", table_concept(), c, out, rotation=long.rotation(), settings=only, log=lambda _: None)
    qdir = QuestionDir(out / "q01")
    long_chunks = [r for r in read_jsonl(qdir.chunks) if r["chars"] > 25_000]
    assert long_chunks and doc["counts"]["split_chunks"] == len(long_chunks)
    assert doc["counts"]["too_long"] == 0 and outcome(doc) == (0, "")
    assert doc["counts"]["model_calls"]["too_long"] >= len(long_chunks)
    records = {r["paper_id"]: r for r in read_jsonl(qdir.screening)}
    assert sorted(r["chunk"] for r in long_chunks if r["paper_id"] == "p5") == records["p5"]["chunks_split"]
    pieces = [x for x in read_jsonl(qdir.candidates) if x.get("piece")]
    assert pieces and all(x["piece"] in ("1", "2") for x in pieces)
    spans = {(r["paper_id"], r["chunk"]): (r["start"], r["end"]) for r in read_jsonl(qdir.chunks)}
    for x in pieces:
        start, end = spans[(x["paper_id"], x["chunk"])]
        assert start <= x["span"][0] < x["span"][1] <= end and x["anchor_in_chunk"] is not False
    def cells(d):
        return sorted(json.dumps(r["cells"], sort_keys=True) for r in d["rows"])

    assert cells(doc) == cells(plain)  # the same rows, read in pieces
    silent = Script(fail=lambda *_: True)
    build("q01", table_concept(), c, out, rotation=silent.rotation(), settings=only, log=lambda _: None)
    assert sum(silent.calls.values()) == 0  # the too-long verdicts are cached too


def test_a_piece_still_too_long_is_a_failure_a_rerun_cannot_fix(tmp_path):
    c = corpus(tmp_path)
    only = replace(SETTINGS, only_papers=("p6",))
    always = Script(too_long=lambda stage, text: stage == "extract")
    doc = build("q01", table_concept(), c, tmp_path / "gold", rotation=always.rotation(), settings=only,
                log=lambda _: None)
    qdir = QuestionDir(tmp_path / "gold" / "q01")
    record = read_jsonl(qdir.screening)[0]
    assert record["status"] == "relevant" and len(record["chunks_relevant"]) == 1
    assert record["extraction_too_long"] == record["extraction_errors"] == record["chunks_relevant"]
    assert "too_long" in record["extraction_error"]
    assert (doc["counts"]["too_long"], doc["counts"]["extraction_errors"]) == (1, 1)
    assert outcome(doc)[0] == 3 and "cannot fix" in outcome(doc)[1]
    size = read_jsonl(qdir.chunks)[record["chunks_relevant"][0]]["chars"]
    assert always.calls["extract"] >= size // (2 * MIN_PIECE_CHARS)  # halved down to the smallest pieces
    silent = Script(fail=lambda *_: True)
    doc = build("q01", table_concept(), c, tmp_path / "gold", rotation=silent.rotation(), settings=only,
                log=lambda _: None)
    assert sum(silent.calls.values()) == 0 and outcome(doc)[0] == 3


def test_a_build_for_another_concept_is_refused_unless_replaced(tmp_path):
    from gold.triage import load_labels, triage

    c = corpus(tmp_path)
    out, qdir = tmp_path / "gold", QuestionDir(tmp_path / "gold" / "q01")
    only = replace(SETTINGS, only_papers=("p5", "p6"))
    build("q01", table_concept(), c, out, rotation=Script().rotation(), settings=only, log=lambda _: None)
    triage("q01", out, c, Script().rotation(), settings=SETTINGS, log=lambda _: None)
    first = {x["id"] for x in read_jsonl(qdir.candidates)}
    assert len(load_labels(qdir)) == len(first) == 4
    other = {**table_concept(), "title": "Another reading", "definition": "Datasets named in the papers."}
    with pytest.raises(FolderInUse, match="another concept"):
        build("q01", other, c, out, rotation=Script().rotation(), settings=only, log=lambda _: None)
    assert json.loads(qdir.doc.read_text(encoding="utf-8"))["concept_sha256"] == concept_sha256(table_concept())
    logged = []
    doc = build("q01", other, c, out, rotation=Script().rotation(), settings=only, log=logged.append, replace=True)
    assert doc["concept_sha256"] == concept_sha256(other)
    [moved] = list(qdir.superseded.iterdir())
    assert moved.name.startswith(concept_sha256(table_concept())[:12]) and any("moved to" in line for line in logged)
    assert (moved / "doc.json").exists() and (moved / "triage.jsonl").exists() and not qdir.triage.exists()
    assert qdir.cache.exists() and qdir.ids.exists()
    second = {x["id"] for x in read_jsonl(qdir.candidates)}
    assert len(second) == 4 and not first & second  # same facts, new concept: new ids
    assert load_labels(qdir) == {}
    assert len(doc["built"]["invocations"]) == 1  # the old concept's builds went with it


def test_a_trial_does_not_silently_replace_a_whole_corpus_d(built):
    out = built["tmp"] / "gold"
    trial = replace(SETTINGS, only_papers=("p6",))
    with pytest.raises(FolderInUse, match="whole corpus"):
        build("q01", table_concept(), built["corpus"], out, rotation=Script().rotation(), settings=trial,
              log=lambda _: None)
    doc = build("q01", table_concept(), built["corpus"], out, rotation=Script().rotation(), settings=trial,
                log=lambda _: None, replace=True)
    assert doc["coverage"]["partial"] is True and doc["coverage"]["papers"] == 1


def test_invocations_add_up_what_d_cost(built):
    first = built["doc"]["counts"]["model_calls"]
    assert first["made"] > 0 and first["total"]["calls"] == first["made"] + first["cached"]
    doc = build("q01", table_concept(), built["corpus"], built["tmp"] / "gold", rotation=Script().rotation(),
                settings=SETTINGS, question=QUESTION, log=lambda _: None)
    again = doc["counts"]["model_calls"]
    assert again["made"] == 0 and again["cached"] == first["made"]
    assert again["total"] == first["total"]  # every call D rests on, with what it cost when it was made
    runs = doc["built"]["invocations"]
    assert [r["made"] for r in runs] == [first["made"], 0]
    assert runs[0]["started_at"] == built["doc"]["built"]["started_at"]
    assert doc["counts"]["cost"]["calls_made"] == first["made"] and doc["counts"]["cost"]["invocations"] == 2
    assert doc["counts"]["cost"]["input_tokens"] == first["input_tokens"] > 0


@pytest.mark.skipif(os.name != "posix", reason="loop signal handlers and SIGTERM are POSIX")
def test_sigterm_stops_the_build_and_progress_says_so(tmp_path):
    c = corpus(tmp_path)
    qdir = QuestionDir(tmp_path / "gold" / "q01")
    sent = []

    def term(stage, paper, part):
        if stage == "extract" and not sent:
            sent.append(stage)
            os.kill(os.getpid(), signal.SIGTERM)
        return False

    with pytest.raises(BuildStopped, match="SIGTERM"):
        build("q01", table_concept(), c, tmp_path / "gold", rotation=Script(fail=term).rotation(), settings=SETTINGS,
              log=lambda _: None)
    progress = json.loads(qdir.progress.read_text(encoding="utf-8"))
    assert (progress["stage"], progress["reason"], progress["pid"]) == ("stopped", "SIGTERM", os.getpid())
    assert not qdir.doc.exists()
    doc = build("q01", table_concept(), c, tmp_path / "gold", rotation=Script().rotation(), settings=SETTINGS,
                log=lambda _: None)
    assert outcome(doc) == (0, "") and doc["coverage"]["relevant"] == 3


def test_live_stage_tells_a_dead_or_stale_build_from_a_running_one():
    now = datetime.now(timezone.utc)
    stamp = (lambda t: t.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    running = {"stage": "building", "pid": os.getpid(), "host": socket.gethostname(), "updated_at": stamp(now),
               "call_timeout_s": 300}
    assert live_stage(running, now) == "building"
    elsewhere = {**running, "host": "elsewhere"}
    assert live_stage({**elsewhere, "updated_at": stamp(now - timedelta(minutes=12))}, now) == "stale"
    assert live_stage({**elsewhere, "updated_at": stamp(now - timedelta(minutes=10))}, now) == "building"
    assert live_stage({**running, "stage": "done", "updated_at": stamp(now - timedelta(days=3))}, now) == "done"
    if os.name == "posix":
        gone = subprocess.Popen(["true"])
        gone.wait()
        assert live_stage({**running, "pid": gone.pid}, now) == "dead"


def test_settings_refuse_values_that_mean_something_else():
    for bad in ({"max_papers": 0}, {"max_papers": -2}, {"chunk_chars": 0}, {"concurrency": 0}, {"call_timeout_s": 0}):
        with pytest.raises(ValueError):
            BuildSettings(**bad)
    assert BuildSettings(max_papers=1).max_papers == 1


def test_git_state_records_a_dirty_tree_and_warns_when_git_cannot_tell(monkeypatch):
    outputs = {"rev-parse": b"abc123\n", "status": b" M gold/build.py\n", "diff": b"diff --git a b\n"}

    def fake(args, **kw):
        return subprocess.CompletedProcess(args, 0, outputs[args[3]], b"")

    monkeypatch.setattr(build_module.subprocess, "run", fake)
    assert git_state(None) == {"commit": "abc123", "dirty": True, "diff_sha256": sha256_hex(b"diff --git a b\n")}

    def refuse(args, **kw):
        raise subprocess.CalledProcessError(128, args, b"", b"fatal: detected dubious ownership in repository\n")

    monkeypatch.setattr(build_module.subprocess, "run", refuse)
    logged = []
    assert git_state(logged.append) == {"commit": None, "dirty": None, "diff_sha256": None}
    assert "dubious ownership" in logged[0] and logged[0].startswith("WARNING")


def test_jsonl_files_survive_a_cut_last_line(tmp_path):
    path = tmp_path / "triage.jsonl"
    path.write_bytes(b'{"id": "a", "label": "answers"}\n{"id": "b", "lab')
    assert read_jsonl(path) == [{"id": "a", "label": "answers"}]
    append_jsonl(path, [{"id": "c", "label": "context"}])
    assert [r["id"] for r in read_jsonl(path)] == ["a", "c"]


def test_trial_then_full_build_keeps_candidate_ids(tmp_path):
    c = corpus(tmp_path)
    out = tmp_path / "gold"
    trial = build("q01", table_concept(), c, out, rotation=Script().rotation(),
                  settings=replace(SETTINGS, only_papers=("p5", "p6")), log=lambda _: None)
    assert trial["coverage"]["papers"] == 2 and trial["coverage"]["partial"] is True
    first = {x["first_quote"] if "first_quote" in x else x["quote"]: x["id"]
             for x in read_jsonl(QuestionDir(out / "q01").candidates)}
    assert sorted(first.values()) == [f"q01-c00000{n}" for n in range(1, 5)]  # p5's three, p6's one
    script = Script()
    build("q01", table_concept(), c, out, rotation=script.rotation(), settings=SETTINGS, log=lambda _: None)
    qdir = QuestionDir(out / "q01")
    full = by_quote(qdir)
    assert all(full[q]["id"] == i for q, i in first.items())
    assert {full[q]["id"] for q in full} - set(first.values()) == {"q01-c000005", "q01-c000006"}  # p3's two
    assert [c["id"] for c in read_jsonl(qdir.candidates)][:2] == ["q01-c000005", "q01-c000006"]  # p3 comes first
    trial_chunks = chunk_count(qdir, "p5") + chunk_count(qdir, "p6")
    assert script.calls["screen"] == len(read_jsonl(qdir.chunks)) - trial_chunks  # the trial's came from the cache


def test_max_papers_takes_the_first_of_the_manifest(tmp_path):
    doc = build("q01", table_concept(), corpus(tmp_path), tmp_path / "gold", rotation=Script().rotation(),
                settings=replace(SETTINGS, max_papers=3), log=lambda _: None)
    assert [r["paper_id"] for r in read_jsonl(QuestionDir(tmp_path / "gold" / "q01").screening)] == ["p1", "p2", "p3"]
    assert doc["built"]["settings"]["max_papers"] == 3


def test_unknown_only_papers_are_refused(tmp_path):
    with pytest.raises(ValueError, match="p77"):
        build("q01", table_concept(), corpus(tmp_path), tmp_path / "gold", rotation=Script().rotation(),
              settings=replace(SETTINGS, only_papers=("p77",)), log=lambda _: None)


def test_hash_mismatch_is_an_error(tmp_path):
    c = corpus(tmp_path)
    (c.root / "p6.md").write_text("tampered", encoding="utf-8")
    build("q01", table_concept(), c, tmp_path / "gold", rotation=Script().rotation(),
          settings=replace(SETTINGS, only_papers=("p6",)), log=lambda _: None)
    record = read_jsonl(QuestionDir(tmp_path / "gold" / "q01").screening)[0]
    assert (record["status"], record["error"]) == ("error", "corpus_file_hash_mismatch")


# --- calls.py ----------------------------------------------------------------------------------------

class Out(BaseModel):
    relevant: bool
    findings: list[str]


def test_caller_times_out_and_does_not_cache_failures(tmp_path):
    async def slow(messages, info):
        await asyncio.sleep(1)

    async def go():
        cache = llm.JsonlCache(tmp_path / "c.jsonl")
        caller = calls.Caller(llm.Rotation([FunctionModel(slow)]), cache, timeout_s=0.05)
        with pytest.raises(calls.CallError) as exc:
            await caller.call("screen", screen.PROMPT, screen.Screening, "x", max_tokens=10)
        return exc.value, caller, cache

    error, caller, cache = asyncio.run(go())
    assert error.reason == "timeout" and caller.counters.failed == 1
    assert not (tmp_path / "c.jsonl").exists()


def test_a_context_window_400_is_too_long_and_its_verdict_cached(tmp_path):
    def full(messages, info):
        raise ModelHTTPError(400, "sub-model-1", body={"error": {"message": "litellm.ContextWindowExceededError: "
                                                                 "maximum context length is 32768 tokens"}})

    async def go():
        caller = calls.Caller(llm.Rotation([FunctionModel(full)]), llm.JsonlCache(tmp_path / "c.jsonl"))
        errors = []
        for _ in range(2):
            with pytest.raises(calls.CallError) as exc:
                await caller.call("extract", screen.PROMPT, screen.Screening, "x", max_tokens=10)
            errors.append(exc.value)
        return errors, caller

    (first, again), caller = asyncio.run(go())
    assert first.kind == again.kind == "too_long" and "context window" in first.reason
    assert (first.cached, again.cached) == (False, True)
    assert (caller.counters.too_long, caller.counters.failed, caller.counters.made) == (2, 0, 0)


def test_failure_reasons_never_carry_the_key(tmp_path, monkeypatch):
    key = "sk-test-0123456789abcdef"
    monkeypatch.setenv("LITELLM_MASTER_KEY", key)

    def denied(messages, info):
        raise RuntimeError(f"Authentication Error, Received API Key = {key[:9]}...cdef, Key Hash (Token) = "
                           f"{sha256_hex(key.encode())}; key {key}")

    async def go():
        caller = calls.Caller(llm.Rotation([FunctionModel(denied)]), llm.JsonlCache(tmp_path / "c.jsonl"))
        with pytest.raises(calls.CallError) as exc:
            await caller.call("screen", screen.PROMPT, screen.Screening, "x", max_tokens=10)
        return exc.value

    error = asyncio.run(go())
    assert error.kind == "failed" and "Authentication Error" in error.reason
    assert key not in error.reason and key[:9] not in error.reason and sha256_hex(key.encode()) not in error.reason
    assert not (tmp_path / "c.jsonl").exists()


def test_cache_key_ignores_which_replica_answers():
    sub = llm.Rotation([llm.openai_model("sub-model-1"), llm.openai_model("sub-model-2")])
    one = llm.Rotation([llm.openai_model("sub-model-1")])
    assert calls.model_key(sub.models) == calls.model_key(one.models) == \
        f"{llm.SUB_MODEL['name']}@{llm.SUB_MODEL['revision']}"
    assert calls.model_key([FunctionModel(lambda m, i: None, model_name="b"),
                            FunctionModel(lambda m, i: None, model_name="a")]) == "a+b"


def test_retry_prompt_explains_every_quote_reason():
    for reason in extract.QUOTE_REASONS:
        assert f"- {reason}:" in extract.RETRY_PROMPT.text
