"""Each run keeps its own calls.jsonl: one row per model-backed extractor or screen call, with the full model-call
records (prompts and replies), written as each call completes (the warm pass too), outside the hash chain."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest

from evidence.calls import cache_key
from evidence.rundir import RUN_CALLS_FILE, RunCalls

from .test_funnel import events, read
from .test_parallel import go

FIELDS = {"key", "phase", "document", "evidence_type", "extractor_id", "attempt", "status", "source", "started_at",
          "ended_at", "task", "result", "model_calls"}


def rows(root: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (root / RUN_CALLS_FILE).read_text(encoding="utf-8").splitlines()]


def model_backed_keys(root: Path) -> set[str]:
    return {cache_key(e["agent_id"], e["custom_metadata"]["task_sha256"], e["custom_metadata"]["attempt"])
            for e in events(root, "extractor_call") if e["custom_metadata"]["model_calls"]}


@pytest.mark.parametrize("workers", [1, 3])
def test_calls_jsonl_has_every_call_once(tmp_path: Path, workers: int) -> None:
    root = go(tmp_path, "a", workers=workers)
    found = rows(root)
    keys = [r["key"] for r in found]
    assert len(keys) == len(set(keys))
    assert set(keys) == model_backed_keys(root) and keys
    assert all(set(r) == FIELDS for r in found)
    assert {r["phase"] for r in found} == ({"run"} if workers == 1 else {"warm"})
    assert "screen" in {r["evidence_type"] for r in found}       # screen calls are calls too
    assert all(r["source"] == "fresh" for r in found)


def test_calls_jsonl_holds_prompts(tmp_path: Path) -> None:
    root = go(tmp_path, "a", workers=3)
    for row in rows(root):
        assert row["model_calls"][0]["request"]["user_prompt"]
        assert row["task"]["document"]["id"] == row["document"]
        assert row["result"]["extractor_id"] == row["extractor_id"]


def test_a_second_run_from_the_cache_keeps_its_own_rows(tmp_path: Path) -> None:
    go(tmp_path, "a", workers=3, cache="shared")
    again = go(tmp_path, "b", workers=3, cache="shared")
    found = rows(again)
    assert {r["key"] for r in found} == model_backed_keys(again)
    assert {r["source"] for r in found} == {"cache"}


def test_outputs_still_identical_with_calls_jsonl(tmp_path: Path) -> None:
    a, b = go(tmp_path, "a", workers=1), go(tmp_path, "b", workers=3)
    ra, rb = read(a, "run.json"), read(b, "run.json")
    assert ra["outputs"] == rb["outputs"] and RUN_CALLS_FILE not in ra["outputs"]
    for name in ra["outputs"]:
        assert (a / name).read_bytes() == (b / name).read_bytes(), name
    order = lambda root: [(e["task_id"], e["subtype"], e["custom_metadata"]) for e in events(root)]  # noqa: E731
    assert order(a) == order(b)
    files = lambda root: sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())  # noqa: E731
    assert files(a) == files(b) and RUN_CALLS_FILE in files(a)


def test_run_calls_skips_a_key_already_written_and_is_thread_safe(tmp_path: Path) -> None:
    path = tmp_path / RUN_CALLS_FILE
    calls = RunCalls(path)
    threads = [threading.Thread(target=calls.add, args=({"key": f"k{i % 5}", "n": i},)) for i in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    keys = [json.loads(x)["key"] for x in path.read_text(encoding="utf-8").splitlines()]
    assert sorted(keys) == [f"k{i}" for i in range(5)]
