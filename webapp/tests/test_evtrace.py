"""The run trace API (GET /api/ev/runs/{run}/trace) and the call detail it links to, on hand-made run
directories: calls.jsonl and events.jsonl as the engine writes them, at any stage of a run."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from evidence.calls import cache_key
from webapp.app import create_app
from webapp.settings import Settings

RUN = "g~r1"


def put(path: Path, rows: list[dict[str, Any]], tail: str = "") -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows) + tail, encoding="utf-8")


def call_row(key: str, phase: str = "warm", document: str = "S001", *, tokens: tuple[int, int] = (10, 3)) -> dict[str, Any]:
    return {"key": key, "phase": phase, "document": document, "evidence_type": "result", "extractor_id": "llm-1", "attempt": 0,
            "status": "ok", "source": "fresh", "started_at": "2026-10-25T10:00:00+00:00", "ended_at": "2026-10-25T10:00:02+00:00",
            "task": {"evidence_type": "result"}, "result": {"call_id": "", "extractor_id": "llm-1", "task_sha256": "ab", "status": "ok"},
            "model_calls": [{"id": f"m-{key}", "request": {"model": "m", "instructions": "i", "user_prompt": f"prompt {key}"},
                             "response": {"output": "reply"}, "usage": {"input_tokens": tokens[0], "output_tokens": tokens[1]}}]}


def event(n: int, subtype: str, **meta: Any) -> dict[str, Any]:
    return {"task_id": f"t{n:04d}", "subtype": subtype, "agent_id": "llm-1", "group_id": "S001", "status": "ok",
            "generated": [], "started_at": "2026-10-25T10:00:00+00:00", "ended_at": "2026-10-25T10:00:01+00:00",
            "custom_metadata": {"document": "S001", **meta}}


def make_run(tmp_path: Path) -> Path:
    run = tmp_path / "runs" / "g" / "r1"
    run.mkdir(parents=True)
    (run / "protocol.yaml").write_text("{}", encoding="utf-8")   # the engine writes it first: the directory is a run
    return run


def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(Settings(EV=tmp_path, EV_RUNS=tmp_path / "runs")))


def test_trace_pages_with_after(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    put(run / "calls.jsonl", [call_row("k1"), call_row("k2", document="S002")])
    put(run / "events.jsonl", [event(1, "screen", calls=["t0001"]), event(2, "locate", evidence_type="result"),
                               event(3, "extractor_call", task_sha256="ab", source="cache", evidence_type="result"),
                               event(4, "merge")])
    with client(tmp_path) as c:
        page = c.get(f"/api/ev/runs/{RUN}/trace").json()
        assert [r["n"] for r in page["rows"]] == [1, 2, 3, 4, 5, 6] and page["next"] == 6 and page["done"] is False
        assert [(r["phase"], r["step"]) for r in page["rows"]] == [("warm", "call")] * 2 + [
            ("run", "screen"), ("run", "locate"), ("run", "extractor_call"), ("run", "merge")]
        assert page["rows"][0]["call"] == "k1" and page["rows"][0]["seconds"] == 2.0 and page["rows"][0]["input_tokens"] == 10
        assert page["rows"][2]["call"] == "t0001" and page["rows"][4]["call"] == "t0003"
        # only an extractor_call event carries a real start; the other steps' times would read ~0
        assert [r["seconds"] for r in page["rows"][2:]] == [None, None, 1.0, None]
        later = c.get(f"/api/ev/runs/{RUN}/trace", params={"after": 4}).json()
        assert [r["n"] for r in later["rows"]] == [5, 6] and later["next"] == 6
        nothing = c.get(f"/api/ev/runs/{RUN}/trace", params={"after": 6}).json()
        assert nothing["rows"] == [] and nothing["next"] == 6
        # the run grows: only the new rows come, numbered on
        with (run / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event(5, "completeness")) + "\n")
        assert [r["step"] for r in c.get(f"/api/ev/runs/{RUN}/trace", params={"after": 6}).json()["rows"]] == ["completeness"]


def test_trace_run_phase_rows_fill_event_tokens(tmp_path: Path) -> None:
    run = make_run(tmp_path)   # workers=1: calls.jsonl rows are phase run, and are the extractor_call events' calls
    put(run / "calls.jsonl", [{**call_row(cache_key("llm-1", "ab", 0), "run"), "source": "fresh"}])
    put(run / "events.jsonl", [event(1, "extractor_call", task_sha256="ab", source="fresh")])
    with client(tmp_path) as c:
        (row,) = c.get(f"/api/ev/runs/{RUN}/trace").json()["rows"]
    assert row["step"] == "extractor_call" and row["input_tokens"] == 10 and row["output_tokens"] == 3 and row["call"] == "t0001"


def test_trace_during_warm_pass(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    put(run / "calls.jsonl", [call_row("k1")], tail='{"key": "k2", "pha')   # a half-written last line
    with client(tmp_path) as c:
        response = c.get(f"/api/ev/runs/{RUN}/trace")
        assert response.status_code == 200
        page = response.json()
        assert [r["call"] for r in page["rows"]] == ["k1"] and page["done"] is False
        with (run / "calls.jsonl").open("a", encoding="utf-8") as fh:   # the writer finishes the line
            fh.write('se": "warm"}\n')
        assert [r["call"] for r in c.get(f"/api/ev/runs/{RUN}/trace", params={"after": 1}).json()["rows"]] == ["k2"]


def test_trace_without_calls_file_and_with_nothing_written(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    with client(tmp_path) as c:
        assert c.get(f"/api/ev/runs/{RUN}/trace").json() == {"rows": [], "next": 0, "done": False}
        put(run / "events.jsonl", [event(1, "locate")])
        assert [r["step"] for r in c.get(f"/api/ev/runs/{RUN}/trace").json()["rows"]] == ["locate"]
        assert c.get("/api/ev/runs/g~nope/trace").status_code == 404


def test_trace_done_after_answer(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    put(run / "events.jsonl", [event(1, "synthesis")])
    with client(tmp_path) as c:
        assert c.get(f"/api/ev/runs/{RUN}/trace").json()["done"] is False
        (run / "answer.json").write_text("{}", encoding="utf-8")
        assert c.get(f"/api/ev/runs/{RUN}/trace").json()["done"] is True


def test_call_detail_from_run_copy_when_cache_gone(tmp_path: Path) -> None:
    run = make_run(tmp_path)   # no cache directory at all
    key = cache_key("llm-1", "ab", 0)
    put(run / "calls.jsonl", [call_row(key)])
    put(run / "events.jsonl", [event(1, "extractor_call", task_sha256="ab", source="fresh", evidence_type="result",
                                     model_calls=["m-x"])])
    (run / "calls").mkdir()
    (run / "calls" / "t0001.json").write_text(json.dumps({"call_id": "t0001", "extractor_id": "llm-1", "task_sha256": "ab",
                                                           "status": "ok"}), encoding="utf-8")
    with client(tmp_path) as c:
        by_id = c.get(f"/api/ev/runs/{RUN}/calls/t0001").json()
        assert by_id["cached"] is True and by_id["model_calls"][0]["request"]["user_prompt"] == f"prompt {key}"
        assert by_id["task"] == {"evidence_type": "result"}
        by_key = c.get(f"/api/ev/runs/{RUN}/calls/{key}").json()
        assert by_key["call"]["call_id"] == key and by_key["call"]["document"] == "S001"
        assert by_key["model_calls"][0]["response"]["output"] == "reply" and by_key["result"]["status"] == "ok"
        assert c.get(f"/api/ev/runs/{RUN}/calls/nokey").status_code == 404


def test_trace_reads_again_when_the_file_is_rewritten(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    put(run / "calls.jsonl", [call_row("k1"), call_row("k2")])
    with client(tmp_path) as c:
        assert [r["call"] for r in c.get(f"/api/ev/runs/{RUN}/trace").json()["rows"]] == ["k1", "k2"]
        put(run / "calls.jsonl", [call_row("x1", document="S009"), call_row("x2"), call_row("x3")])   # longer, other content
        assert [r["call"] for r in c.get(f"/api/ev/runs/{RUN}/trace").json()["rows"]] == ["x1", "x2", "x3"]
        put(run / "calls.jsonl", [call_row("y1")])   # shorter
        assert [r["call"] for r in c.get(f"/api/ev/runs/{RUN}/trace").json()["rows"]] == ["y1"]
