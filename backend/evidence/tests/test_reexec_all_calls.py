from __future__ import annotations

import json
from pathlib import Path

import pytest
from modelcall import JsonlCache

from evidence import cli
from evidence import replay as replay_module
from evidence.calls import CallCache
from evidence.engine import CACHE_FILE
from evidence.replay import reexec
from evidence.rundir import RUN_CALLS_FILE, RunDir
from evidence.stability import compare_calls
from evidence.tests.conftest import provider_of
from evidence.tests.test_written_stage import writer_model, written_run

GOOD = lambda p: {"sentences": [{"text": "Retrieval helped.", "says": "finding", "facts": [1]}]}


def rows(run: Path) -> list[dict]:
    return [json.loads(x) for x in (run / RUN_CALLS_FILE).read_text(encoding="utf-8").splitlines()]


def folder_bytes(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_all_calls_asks_the_writer_and_the_stages_again_and_keeps_the_cache(tmp_path: Path) -> None:
    root = written_run(tmp_path, GOOD)
    cache = tmp_path / "cache" / CACHE_FILE
    before, original = cache.read_bytes(), folder_bytes(root)
    calls: list[str] = []
    others: list[str] = []
    new = reexec(root, all_calls=True, out_dir=tmp_path / "re",
                 provider=provider_of(writer_model(calls, GOOD, others=others)))
    assert len(calls) == 1 and others and cache.read_bytes() == before
    assert folder_bytes(root) == original
    assert RunDir(new).complete and (new / "reexec.json").is_file()
    assert json.loads((new / "reexec.json").read_text(encoding="utf-8"))["all_calls"] is True
    assert any(r["extractor_id"] == "stage:written-answer" and r["source"] == "fresh" for r in rows(new))


def test_without_all_calls_the_stages_read_the_record(tmp_path: Path) -> None:
    root = written_run(tmp_path, GOOD)
    calls: list[str] = []
    new = reexec(root, out_dir=tmp_path / "re", provider=provider_of(writer_model(calls, GOOD)))
    assert calls == []
    assert json.loads((new / "reexec.json").read_text(encoding="utf-8"))["all_calls"] is False


def test_the_same_fake_gives_identical_calls_and_every_row_is_fresh(tmp_path: Path) -> None:
    """M9: with the same fake, every model call of every group comes back identical, every re-run row was asked
    again (fresh) and the rows are the original's; a default re-run asks no model call (its stage rows are the
    record's)."""
    root = written_run(tmp_path, GOOD)
    new = reexec(root, all_calls=True, out_dir=tmp_path / "re", provider=provider_of(writer_model([], GOOD)))
    compared = compare_calls(root, new)
    assert sum(c["calls"] for c in compared.values()) > 0
    for group, c in compared.items():
        assert c["identical"] == c["calls"] and c["new"] == 0, group
    assert rows(new) and all(r["source"] == "fresh" for r in rows(new))
    assert sorted(r["key"] for r in rows(new)) == sorted(r["key"] for r in rows(root))
    calls: list[str] = []
    others: list[str] = []
    plain = reexec(root, out_dir=tmp_path / "re", provider=provider_of(writer_model(calls, GOOD, others=others)))
    assert calls == [] and others == []
    stage = [r for r in rows(plain) if r["extractor_id"].startswith("stage:")]
    assert stage and all(r["source"] == "cache" for r in stage)


def test_a_repeated_request_in_one_rerun_is_asked_once(tmp_path: Path) -> None:
    cache = CallCache(JsonlCache(tmp_path / "c.jsonl"), "reexec", fresh_recorded=True, attempts={})
    made: list[int] = []
    make = lambda: (made.append(1) or ({"status": "ok", "output": {"n": len(made)}}, []))
    first = cache.recorded("stage:x", {"q": 1}, make)
    again = cache.recorded("stage:x", {"q": 1}, make)
    assert len(made) == 1 and again.value == first.value and first.source == "fresh"
    assert not (tmp_path / "c.jsonl").exists() or (tmp_path / "c.jsonl").read_text(encoding="utf-8") == ""


def test_all_calls_names_no_extractor(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="all_calls re-runs every extractor"):
        reexec(written_run(tmp_path, GOOD), "regex_measurement", all_calls=True)


def test_the_command_takes_all_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = written_run(tmp_path, GOOD)
    calls: list[str] = []
    monkeypatch.setattr(replay_module, "default_provider", lambda alias: writer_model(calls, GOOD))
    assert cli.main(["reexec", str(root), "--all-calls", "--out", str(tmp_path / "re")]) == 0
    assert len(calls) == 1


def test_the_command_refuses_all_calls_with_an_extractor(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        cli.main(["reexec", str(tmp_path), "--all-calls", "--extractor", "x"])
    assert stop.value.code == 2
    assert "not allowed with" in capsys.readouterr().err
