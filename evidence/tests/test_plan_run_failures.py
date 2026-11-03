"""Final review C3: one failed model call in a per-item stage skips that item, never the plan run; the run lists it in
stage_report.json, and its replay is byte-identical."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.models.function import FunctionModel

from evidence import planrun, stages
from evidence.plan import write_plan
from evidence.replay import replay
from evidence.rundir import RunDir
from evidence.tests.conftest import PAPERS, corpus_of, prompt_of, provider_of, respond
from evidence.tests.test_plan_run import fake_model, make_plan, read

CITE = "We build on Lewis et al. (2020) for the retrieval-augmented model."


@pytest.fixture(autouse=True)
def clean_registry() -> Iterator[None]:
    with stages.registered():
        yield


def failing_model(fail: Any) -> FunctionModel:
    """The plan-run fake model, but a prompt for which `fail(prompt)` is true raises (a failed model call)."""
    inner = fake_model([]).function

    def reply(messages: Any, info: Any) -> Any:
        prompt = prompt_of(messages)
        if fail(prompt):
            raise RuntimeError("gateway down")
        if "Your output fields are:\n1. `relation`" in prompt and "Lewis et al." in prompt:
            return respond(info, {"text": json.dumps({"relation": "builds on", "object": "Lewis et al. (2020)"})})
        return inner(messages, info)
    return FunctionModel(reply, model_name="fake")


def corpus(tmp: Path) -> Path:
    docs = {d: (PAPERS / f"{d}.md").read_text(encoding="utf-8").replace("\r\n", "\n") for d in ("S001", "S002")}
    docs["S001"] += f"\n\n{CITE}\n"
    docs["S002"] += "\n\nWe build on Smith et al. (2019) for the closed-book model.\n"
    return corpus_of(tmp / "corpus", docs)


def run(tmp: Path, fail: Any, monkeypatch: pytest.MonkeyPatch) -> Path:
    from evidence import openalex
    monkeypatch.setattr(openalex, "_urlopen", lambda url: {"results": []})
    path = tmp / "plan.json"
    write_plan(make_plan(), path)
    return planrun.run(path, corpus(tmp), tmp / "runs", cache=tmp / "cache", selection="regex-only",
                       provider=provider_of(failing_model(fail)), workers=1)


def is_claim_of(prompt: str) -> bool:
    return "Your output fields are:\n1. `is_claim`" in prompt


def test_a_failed_claim_call_skips_that_sentence_and_the_run_completes(tmp_path: Path,
                                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fail(prompt: str) -> bool:
        if is_claim_of(prompt):
            calls.append(prompt)
            return len(calls) == 1      # only the first claim sentence fails
        return False
    root = run(tmp_path, fail, monkeypatch)
    assert RunDir(root).complete
    report = read(root, "stage_report.json")
    assert set(report) == {"claims", "experiments", "links"}
    notes = [n for doc in report["claims"].values() for n in doc]
    assert len(notes) == 1 and notes[0].startswith("unchecked: sentence ") and "StageCallError" in notes[0]
    assert any(i.evidence_type == "claim" for i in RunDir(root).items())   # the other sentences were read
    assert read(root, "run.json")["outputs"]["stage_report.json"]


def test_a_failed_experiment_map_and_link_read_are_listed_not_fatal(tmp_path: Path,
                                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(prompt: str) -> bool:
        experiments = "Your output fields are:\n1. `experiments`" in prompt
        link = "Your output fields are:\n1. `relation`" in prompt and "Smith et al." in prompt
        return experiments or link
    root = run(tmp_path, fail, monkeypatch)
    assert RunDir(root).complete
    report = read(root, "stage_report.json")
    assert sorted(report["experiments"]) == ["S001", "S002"]
    assert all(len(notes) == 1 and notes[0].startswith("unchecked: experiment map: ")
               for notes in report["experiments"].values())
    assert list(report["links"]) == ["S002"] and report["links"]["S002"][0].startswith("unchecked: sentence ")
    links = read(root, "answer.json")["links"]
    assert [x["paper"] for x in links] == ["S001"]   # S001's link is kept


def test_a_run_with_failed_items_replays_byte_identical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = run(tmp_path, lambda p: is_claim_of(p) or "Your output fields are:\n1. `experiments`" in p, monkeypatch)
    _, report = replay(root)
    assert report["ok"] and report["mismatched"] == [], report


def test_a_failed_recheck_call_keeps_the_finds_unchecked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = run(tmp_path, lambda p: "Your output fields are:\n1. `verdicts`" in p, monkeypatch)
    assert RunDir(root).complete
    report = read(root, "recheck_report.json")
    whys = {u["why"] for doc in report.values() for u in doc["unchecked"]}
    assert whys and all(w.startswith("failed call: ") for w in whys)


def test_openalex_down_keeps_the_links_and_the_replay_is_identical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    from evidence import openalex
    path = tmp_path / "plan.json"
    write_plan(make_plan(), path)

    def down(url: str) -> Any:
        raise urllib.error.URLError("no network on the compute node")
    monkeypatch.setattr(openalex, "_urlopen", down)
    root = planrun.run(path, corpus(tmp_path), tmp_path / "runs", cache=tmp_path / "cache", selection="regex-only",
                       provider=provider_of(failing_model(lambda p: False)), workers=1)
    assert RunDir(root).complete
    links = read(root, "answer.json")["links"]
    assert links and links[0]["paper"] == "S001" and links[0]["text"] == "outside the set"
    assert links[0]["resolve_failed"].startswith("URLError")
    assert not (root / openalex.RECORD_FILE).is_file() or not (root / openalex.RECORD_FILE).read_text().strip()
    _, report = replay(root)
    assert report["ok"] and report["mismatched"] == [], report
