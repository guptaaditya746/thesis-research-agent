"""`--workers`: a warm pass fills the record cache with papers' model calls running at once, then the unchanged
sequential loop finds every call cached, so no output depends on the number of workers."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.models.function import FunctionModel

from evidence import cli, engine
from evidence.engine import Execution
from evidence.rundir import CACHE_FILE

from .conftest import PROTOCOL, corpus_of, provider_of, scripted
from .test_funnel import COMPLETE, DOCS as THREE, MISSING_BASELINE, events, make_script, read

DOCS = {**THREE, "P4": COMPLETE.replace("# T", "# T4", 1)}


def go(tmp_path: Path, name: str, *, docs: dict[str, str] = DOCS, workers: int, seen: list | None = None,
       model: FunctionModel | None = None, cache: str | None = None) -> Path:
    seen = [] if seen is None else seen
    model = model or scripted(make_script(seen), [])
    corpus = tmp_path / f"corpus-{name}"
    if not corpus.exists():
        corpus_of(corpus, docs)
    return engine.run(PROTOCOL, corpus, tmp_path / f"out-{name}", cache=tmp_path / (cache or f"cache-{name}"),
                      provider=provider_of(model), model="scripted-alias", workers=workers)


def test_workers_change_no_output(tmp_path: Path) -> None:
    a, b = go(tmp_path, "a", workers=1), go(tmp_path, "b", workers=3)
    ra, rb = read(a, "run.json"), read(b, "run.json")
    assert ra["outputs"] == rb["outputs"]
    keys = ("calls", "model_calls", "made_model_calls")
    assert {k: ra["cost"][k] for k in keys} == {k: rb["cost"][k] for k in keys}
    assert ra["cost"]["made_model_calls"] > 0 and rb["cost"]["workers"] == 3 and ra["cost"]["workers"] == 1
    order = lambda root: [(e["task_id"], e["subtype"], e["custom_metadata"].get("task_sha256")) for e in events(root)]  # noqa: E731
    assert order(a) == order(b)


def test_workers_keep_several_calls_in_flight(tmp_path: Path) -> None:
    inner = scripted(make_script([]), []).function
    state = {"now": 0, "peak": 0}

    async def reply(messages: Any, info: Any) -> Any:
        state["now"] += 1
        state["peak"] = max(state["peak"], state["now"])
        await asyncio.sleep(0.05)
        state["now"] -= 1
        return inner(messages, info)

    go(tmp_path, "a", workers=3, model=FunctionModel(reply, model_name="slow"))
    assert state["peak"] >= 2


def test_more_workers_than_papers(tmp_path: Path) -> None:
    two = {"P1": DOCS["P1"], "P2": MISSING_BASELINE}
    a, b = go(tmp_path, "a", docs=two, workers=1), go(tmp_path, "b", docs=two, workers=3)
    assert read(a, "run.json")["outputs"] == read(b, "run.json")["outputs"]


def test_a_fully_cached_run_with_workers_makes_no_model_call(tmp_path: Path) -> None:
    seen: list = []
    go(tmp_path, "a", workers=3, seen=seen, cache="shared")
    seen.clear()
    root = engine.run(PROTOCOL, tmp_path / "corpus-a", tmp_path / "out-again", cache=tmp_path / "shared",
                      provider=provider_of(scripted(make_script(seen), [])), model="scripted-alias", workers=3)
    assert seen == [] and read(root, "run.json")["cost"]["made_model_calls"] == 0


def test_replay_of_a_parallel_run_reproduces_every_hash(tmp_path: Path) -> None:
    from evidence.replay import replay
    root = go(tmp_path, "a", workers=3)
    _, report = replay(root)
    assert report["ok"] and report["mismatched"] == []


def test_a_crash_in_the_warm_pass_fails_the_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = Execution.document

    def document(self: Execution, paper: Any) -> None:
        if paper.id == "P2":
            raise RuntimeError("boom")
        real(self, paper)

    monkeypatch.setattr(Execution, "document", document)
    with pytest.raises(RuntimeError, match="boom"):
        go(tmp_path, "a", workers=3)
    assert not list((tmp_path / "out-a").glob("*/run.json"))


def test_the_cli_workers_flag() -> None:
    base = ["run", "--protocol", "p.yaml", "--corpus", "c"]
    assert cli._parser().parse_args(base).workers == 3
    assert cli._parser().parse_args([*base, "--workers", "1"]).workers == 1
    with pytest.raises(SystemExit):
        cli._parser().parse_args([*base, "--workers", "0"])


def test_retry_errors_with_workers_retries_an_error_once(tmp_path: Path) -> None:
    def failing(kind: str, doc: str, prompt: str) -> dict[str, Any]:
        if doc == "P2" and kind == "measurement":
            raise RuntimeError("provider down")
        return make_script([])(kind, doc, prompt)

    cache = tmp_path / "cache"
    corpus = corpus_of(tmp_path / "corpus", DOCS)
    engine.run(PROTOCOL, corpus, tmp_path / "out1", cache=cache, provider=provider_of(scripted(failing, [])),
               model="scripted-alias", workers=1)
    lines = lambda: len((cache / CACHE_FILE).read_text(encoding="utf-8").splitlines())  # noqa: E731
    before, seen = lines(), []
    root = engine.run(PROTOCOL, corpus, tmp_path / "out2", cache=cache, provider=provider_of(scripted(make_script(seen), [])),
                      model="scripted-alias", workers=3, retry_errors=True)
    assert seen == [("measurement", "P2")]
    assert lines() == before + 1
    assert read(root, "run.json")["cost"]["made_model_calls"] >= 1


def test_a_warm_pass_failure_cancels_the_papers_not_yet_started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real, started, raised_in = Execution.document, [], []

    def document(self: Execution, paper: Any) -> None:
        started.append(paper.id)
        if paper.id == "P1":
            raised_in.append(threading.current_thread().name)
            raise RuntimeError("boom")
        time.sleep(0.3)
        real(self, paper)

    monkeypatch.setattr(Execution, "document", document)
    with pytest.raises(RuntimeError, match="boom"):
        go(tmp_path, "a", workers=2)
    assert "P4" not in started                       # queued behind the failure, never started
    assert raised_in and raised_in[0] != "MainThread"   # the error came from the warm pass


def test_regex_only_never_enters_the_warm_pass_and_the_cost_row_is_not_per_paper(tmp_path: Path,
                                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    def no_warm(*args: Any, **kw: Any) -> None:
        raise AssertionError("_warm must not run")

    monkeypatch.setattr(engine, "_warm", no_warm)
    corpus = corpus_of(tmp_path / "corpus", DOCS)
    root = engine.run(PROTOCOL, corpus, tmp_path / "out", selection="regex-only", workers=3)
    cost = read(root, "run.json")["cost"]
    assert cost["workers"] == 3
    from evaluation.score import score_cost
    scored = score_cost({"cost": cost}, 4)
    assert "workers" not in scored["per_paper"] and scored["total"]["workers"] == 3 and "calls" in scored["per_paper"]
