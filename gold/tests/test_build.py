"""gold/build.py on the D1 papers with a scripted sub-model: statuses, anchors and retries, resume, files."""
from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import pytest
from pydantic import BaseModel
from pydantic_ai.models.function import FunctionModel

from agent.anchor import read_text
from agent.concept import concept_sha256
from gold import calls, extract, llm, screen
from gold.build import QuestionDir, build, read_jsonl

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


@pytest.fixture
def built(tmp_path):
    c = corpus(tmp_path)
    script = Script()
    doc = build("q01", table_concept(), c, tmp_path / "gold", rotation=script.rotation(), settings=SETTINGS,
                question="Which benchmarks do the RAG papers evaluate on?", log=lambda _: None)
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
