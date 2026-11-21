"""The model-call cache (#7): atomic writes, broken files, key, re-check on read, --no-cache, clearing a step."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperfactory import config, llm
from paperfactory.tests.test_llm import scripted, settings

SCHEMA = {"type": "object", "required": ["choice"], "properties": {"choice": {"type": "string"}}}


def files_in(s: config.Settings) -> list[Path]:
    return sorted((s.out_dir / "cache" / "llm").glob("*.json"))


def test_second_call_comes_from_the_cache(tmp_path: Path) -> None:
    s = settings(tmp_path)
    b = scripted({"choice": "a"})
    c = llm.Caller(s, backend=b)
    assert c("judge", "judge:t", "sys", "u", SCHEMA) == {"choice": "a"}
    assert c("judge", "judge:t", "sys", "u", SCHEMA) == {"choice": "a"}
    assert len(b.seen) == 1 and len(files_in(s)) == 1
    assert not list((s.out_dir / "cache" / "llm").glob(".*.tmp"))          # no temp file left behind


def test_broken_cache_file_warns_and_calls_again(tmp_path: Path) -> None:
    s = settings(tmp_path)
    b = scripted({"choice": "a"})
    c = llm.Caller(s, backend=b)
    c("judge", "judge:t", "sys", "u", SCHEMA)
    files_in(s)[0].write_text('{"output": {"cho')                        # a run stopped mid-write (old code)
    with pytest.warns(UserWarning, match="unusable"):
        assert c("judge", "judge:t", "sys", "u", SCHEMA) == {"choice": "a"}
    assert len(b.seen) == 2
    assert json.loads(files_in(s)[0].read_text())["output"] == {"choice": "a"}     # repaired


def test_cached_answer_failing_todays_check_is_asked_again(tmp_path: Path) -> None:
    s = settings(tmp_path)
    b = scripted({"choice": "a"}, {"choice": "b"})
    c = llm.Caller(s, backend=b)
    c("judge", "judge:t", "sys", "u", SCHEMA)
    with pytest.warns(UserWarning):
        got = c("judge", "judge:t", "sys", "u", SCHEMA, check=lambda o: None if o["choice"] == "b" else "need b")
    assert got == {"choice": "b"} and len(b.seen) == 2


def test_key_covers_output_params(tmp_path: Path) -> None:
    b = scripted({"choice": "a"})
    s1 = settings(tmp_path, default={"model": "m", "backend": "openai", "base_url": "http://x", "max_tokens": 100})
    s2 = config.Settings("law", "argument", out=s1.out, slot_dir=s1.slot_dir,
                         models={"default": {"model": "m", "backend": "openai", "base_url": "http://x",
                                             "max_tokens": 200}})
    llm.Caller(s1, backend=b)("judge", "j", "sys", "u", SCHEMA)
    llm.Caller(s2, backend=b)("judge", "j", "sys", "u", SCHEMA)
    assert len(b.seen) == 2 and len(files_in(s1)) == 2


def test_no_cache_and_clear_one_step(tmp_path: Path) -> None:
    s = settings(tmp_path)
    b = scripted({"choice": "a"})
    c = llm.Caller(s, backend=b)
    c("judge", "verify:P1", "sys", "u1", SCHEMA)
    c("judge", "qa:Q1", "sys", "u2", SCHEMA)
    llm.Caller(s, backend=b, use_cache=False)("judge", "verify:P1", "sys", "u1", SCHEMA)
    assert len(b.seen) == 3
    assert c.clear("verify:") == 1 and len(files_in(s)) == 1
    c("judge", "qa:Q1", "sys", "u2", SCHEMA)
    assert len(b.seen) == 3                                               # the other step is still cached


def test_writer_cache_follows_the_writer_settings(tmp_path: Path) -> None:
    """Review finding 3: a changed writer setting must not give back PaperOrchestra's old cached paper."""
    from paperfactory import meta, write
    lab = lambda **kw: llm.po_runner({"model": "m", "backend": "openai", "base_url": "http://x", **kw})[1]  # noqa: E731
    assert lab(max_tokens=100) != lab(max_tokens=200)
    assert llm.po_runner({"model": "claude-haiku-5-5"})[1] == "claude-haiku-5-5"      # old claude cache stays valid
    s = settings(tmp_path)
    assert write.po_cache(s, 1, True).name == "po"
    fresh = write.po_cache(s, 1, False)
    assert fresh.name == "po-nocache-1" and not fresh.exists()
    a = settings(tmp_path, writer={"model": "claude-haiku-5-5", "max_tokens": 100})
    b = settings(tmp_path, writer={"model": "claude-haiku-5-5", "max_tokens": 200})
    assert meta.role(a, "writer") == meta.role(b, "writer")          # claude_cli ignores max_tokens: no paid redo
