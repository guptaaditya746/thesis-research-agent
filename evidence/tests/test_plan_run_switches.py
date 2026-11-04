"""Final review C3 (3) and I1: the links and reasoning switches of a plan run, recorded in run.json settings, and their
replays byte-identical."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from evidence import planrun, stages
from evidence.plan import write_plan
from evidence.replay import replay
from evidence.rundir import RunDir
from evidence.tests.conftest import provider_of
from evidence.tests.test_plan_run import make_plan, read
from evidence.tests.test_plan_run_failures import corpus, failing_model


@pytest.fixture(autouse=True)
def clean_registry() -> Iterator[None]:
    with stages.registered():
        yield


def run(tmp: Path, monkeypatch: pytest.MonkeyPatch, calls: list[str], field: str = "cs", **kw: Any) -> tuple[Path, list[str]]:
    from evidence import openalex
    fetched: list[str] = []
    monkeypatch.setattr(openalex, "_urlopen", lambda url: fetched.append(url) or {"results": []})
    tmp.mkdir(parents=True, exist_ok=True)
    path = tmp / "plan.json"
    write_plan(make_plan(field=field), path)
    model = failing_model(lambda p: calls.append(p) and False)
    root = planrun.run(path, corpus(tmp), tmp / "runs", cache=tmp / "cache", selection="regex-only",
                       provider=provider_of(model), workers=1, **kw)
    return root, fetched


def test_links_off_runs_no_links_stage_and_asks_no_openalex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    root, fetched = run(tmp_path, monkeypatch, calls, links="off")
    rec = read(root, "run.json")
    assert rec["settings"]["links"] == "off"
    assert "links" not in rec["stages"]["after_document"]
    assert read(root, "answer.json")["links"] == [] and fetched == []
    assert not any("Your output fields are:\n1. `relation`" in c for c in calls)
    _, report = replay(root)
    assert report["ok"] and report["mismatched"] == [], report


def test_links_on_is_the_default_and_unchanged_in_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, fetched = run(tmp_path, monkeypatch, [])
    rec = read(root, "run.json")
    assert "links" not in rec["settings"] and "links" in rec["stages"]["after_document"] and fetched


def test_reasoning_off_reads_no_ontology_and_asks_no_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    root, _ = run(tmp_path, monkeypatch, calls, field="medicine", reasoning="off")
    rec = read(root, "run.json")
    assert rec["settings"]["reason"] == "off"
    assert read(root, "ontology.json") == {"tree": "reasoning off: no tree"}
    assert not any("`parent`" in c for c in calls)                       # no LLM mini-tree
    assert read(root, "protocol.lock.json")["field_ontology_sha256"] == {}
    assert not (root / "reason.json").exists()
    assert b"subClassOf" not in (root / "records.nq").read_bytes()
    assert RunDir(root).complete
    _, report = replay(root)
    assert report["ok"] and report["mismatched"] == [], report


def test_reasoning_off_builds_the_graph_without_the_field_ontology(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Any] = []
    import evidence.kg.build as kg_build
    real = kg_build.build
    monkeypatch.setattr(kg_build, "build", lambda papers, items, roles, graph: seen.append(graph) or real(papers, items, roles, graph))
    run(tmp_path / "on", monkeypatch, [])
    run(tmp_path / "off", monkeypatch, [], reasoning="off")
    assert seen[0] is not None and seen[1] is None   # cs on: the fallback ontology; off: none at all
    on_lock = read(next((tmp_path / "on" / "runs").iterdir()), "protocol.lock.json")
    assert on_lock["field_ontology_sha256"]


def test_a_bad_switch_value_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="reasoning"):
        planrun.run(tmp_path / "p.json", tmp_path, tmp_path, reasoning="maybe")


def test_the_answer_links_carry_the_openalex_work_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Final review I2: `work` is the resolved work's id (what `evaluate wholerun` compares), null when unresolved."""
    from evidence import openalex
    path = tmp_path / "plan.json"
    write_plan(make_plan(), path)
    monkeypatch.setattr(openalex, "_urlopen", lambda url: {"results": [{"id": "https://openalex.org/W2741809807",
                                                                       "title": "Lewis et al. (2020)"}]})
    root = planrun.run(path, corpus(tmp_path), tmp_path / "runs", cache=tmp_path / "cache", selection="regex-only",
                       provider=provider_of(failing_model(lambda p: False)), workers=1)
    links = read(root, "answer.json")["links"]
    assert links and {x["work"] for x in links} == {"W2741809807"}


def test_the_lock_records_only_the_tuned_steps_the_run_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Final review C4, runs review I2: {step: sha256} of the tuned instructions the run's own steps run on; a tuned
    file of a step the run never calls (the word writer) is not in the lock, so adding one later keeps the replay."""
    import hashlib

    from evidence import steps
    tuned = tmp_path / "tuned"
    tuned.mkdir()
    monkeypatch.setattr(steps, "TUNED_DIR", tuned)
    (tuned / "recheck.json").write_text('{"instructions": "Check each find."}', encoding="utf-8")
    root, _ = run(tmp_path / "a", monkeypatch, [])
    want = hashlib.sha256((tuned / "recheck.json").read_bytes()).hexdigest()
    assert read(root, "protocol.lock.json")["tuned_steps_sha256"] == {"recheck": want}
    (tuned / "write_words.json").write_text('{"instructions": "x"}', encoding="utf-8")   # a re-tune of the word writer
    _, report = replay(root)
    assert report["ok"] and report["mismatched"] == [], report


def test_a_module_level_step_reports_what_it_loaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from evidence import lockfile, steps
    from evidence.claims import GroupRelations
    tuned = tmp_path / "tuned"
    tuned.mkdir()
    monkeypatch.setattr(steps, "TUNED_DIR", tuned)
    (tuned / "g.json").write_text('{"instructions": "old"}', encoding="utf-8")
    step = steps.Step(GroupRelations, "g")
    old = step.tuned_sha256
    (tuned / "g.json").write_text('{"instructions": "new"}', encoding="utf-8")   # changed after the step was made
    assert steps.tuned_sha256([step]) == {"g": old} and steps.tuned_sha256(["g"]) != {"g": old}
    assert steps.tuned_sha256(["nothing"]) == {}
    want = old or ""
    assert lockfile._lock_lines({"extractors": {}, "pack": 1, "ontology_sha256": None, "tuned_steps_sha256": {}},
                                {"extractors": {}, "pack": 1, "ontology_sha256": None,
                                 "tuned_steps_sha256": {"g": want}}) == [f"tuned step g: none -> {want[:12]}"]
