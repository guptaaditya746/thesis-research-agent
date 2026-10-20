"""RunDir: the read side of a run directory, and the torn-last-line tolerance."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from evidence.rundir import RunDir, read_lines

GOOD = ['{"task_id": "t1", "subtype": "screen"}', '{"task_id": "t2", "subtype": "extractor_call"}']


def events_file(root: Path, text: str) -> None:
    (root / "events.jsonl").write_text(text, encoding="utf-8", newline="")


def test_torn_last_line_is_skipped(tmp_path):
    events_file(tmp_path, "\n".join(GOOD) + '\n{"task_id": "t3", "sub')
    assert len(RunDir(tmp_path).events()) == 2


def test_bad_middle_line_raises(tmp_path):
    events_file(tmp_path, GOOD[0] + "\n{broken\n" + GOOD[1] + "\n")
    with pytest.raises(ValueError, match=r"events\.jsonl:2"):
        RunDir(tmp_path).events()


def test_bad_last_line_with_newline_raises(tmp_path):
    events_file(tmp_path, GOOD[0] + "\n{broken\n")
    with pytest.raises(ValueError, match=r"events\.jsonl:2"):
        read_lines(tmp_path / "events.jsonl")


@pytest.mark.parametrize("make,kind", [
    (lambda r: (r / "events.jsonl").write_text(""), "engine"),
    (lambda r: (r / "run.json").write_text("{}"), "engine"),
    (lambda r: (r / "answer.json").write_text('{"system": "rag"}'), "baseline"),
    (lambda r: None, None),
])
def test_kind(tmp_path, make, kind):
    make(tmp_path)
    assert RunDir(tmp_path).kind == kind


def test_usage_reads_torn_cache(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    row = {"key": "k1", "value": {"model_calls": [{"id": "m1", "usage": {"input_tokens": 5, "output_tokens": 2}}]}}
    (cache / "extractor_calls.jsonl").write_text(json.dumps(row) + '\n{"key": "k2", "val', encoding="utf-8")
    run = tmp_path / "run"
    run.mkdir()
    (run / "run.json").write_text(json.dumps({"settings": {"cache": str(cache)}}))
    assert RunDir(run).usage() == {"m1": {"input_tokens": 5, "output_tokens": 2}}


def test_usage_none_without_cache(tmp_path):
    (tmp_path / "run.json").write_text("{}")
    assert RunDir(tmp_path).usage() is None


def test_latest_reexec_picks_newest_and_ignores_symlinks(tmp_path):
    run = tmp_path / "r1"
    run.mkdir()
    for stamp in ("20260101T000000000000Z", "20260102T000000000000Z"):
        d = tmp_path / f"r1-reexec-{stamp}"
        d.mkdir()
        (d / "reexec.json").write_text("{}")
    link = tmp_path / "r1-reexec-20260103T000000000000Z"
    try:
        os.symlink(tmp_path / "r1-reexec-20260101T000000000000Z", link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks cannot be made here")
    assert RunDir(run).latest_reexec() == tmp_path / "r1-reexec-20260102T000000000000Z" / "reexec.json"


def test_latest_reexec_none(tmp_path):
    assert RunDir(tmp_path / "r1").latest_reexec() is None


def test_error_calls_counts_status_error(tmp_path):
    calls = tmp_path / "calls"
    calls.mkdir()
    for name, status in (("t1", "ok"), ("t2", "error"), ("t3", "error")):
        (calls / f"{name}.json").write_text(json.dumps({"status": status}))
    assert RunDir(tmp_path).error_calls() == 2
    assert RunDir(tmp_path / "none").error_calls() == 0


def test_empty_run_json_is_incomplete_but_engine(tmp_path):
    (tmp_path / "run.json").write_text("{}")
    run = RunDir(tmp_path)
    assert run.complete is False and run.kind == "engine"


def test_run_json_with_content_is_complete(tmp_path):
    (tmp_path / "run.json").write_text('{"protocol": "p"}')
    assert RunDir(tmp_path).complete is True


def test_corrupt_run_json_counts_as_absent(tmp_path):
    (tmp_path / "run.json").write_text('{"protocol": ')
    run = RunDir(tmp_path)
    assert run.complete is False and run.kind is None
    (tmp_path / "events.jsonl").write_text("")
    assert run.kind == "engine"


def test_corrupt_answer_json_counts_as_absent(tmp_path):
    (tmp_path / "answer.json").write_text('{"system": ')
    assert RunDir(tmp_path).kind is None


def test_non_dict_run_json_is_not_engine(tmp_path):
    (tmp_path / "run.json").write_text("[1]")
    run = RunDir(tmp_path)
    assert run.complete is False and run.kind is None


def test_corrupt_call_file_does_not_raise_in_error_calls(tmp_path):
    (tmp_path / "calls").mkdir()
    (tmp_path / "calls" / "a.json").write_text('{"status": "error"}')
    (tmp_path / "calls" / "b.json").write_text('{"status": ')
    assert RunDir(tmp_path).error_calls() == 1
