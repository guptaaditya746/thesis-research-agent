"""Picking a concept brief in the web app (row 2.2): every pick goes through agent/concept_step.py.

The chain is the record of every pick, so `agent concepts check` (concept_step.check_session) must
pass after each one. Changing a pick goes through its `pick(..., replace=True)`.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent import concept_step
from agent.canonical import file_sha256
from webapp.app import create_app

from .world import build_world, propose_q01


@pytest.fixture
def unpicked(tmp_path: Path):
    return build_world(tmp_path, pick=None)


def pick_records(session: Path) -> list[dict]:
    lines = (session / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [r for r in map(json.loads, lines) if r["subtype"] == "concept_pick"]


def test_pick(unpicked) -> None:
    session = unpicked.root / "concepts" / "q01"
    with TestClient(create_app(unpicked.settings)) as c:
        assert c.get("/api/questions/q01").json()["concept"]["status"] == "proposed"
        assert c.get("/api/runs/research-r1").json()["summary"]["qid"] is None  # no concept picked yet
        q = c.post("/api/questions/q01/concepts/pick", json={"choice": 2}).json()
        assert q["concept"] == {"status": "picked", "title": "Most first-author papers at ACL 2025", "picked_by": "user"}
        assert q["picked"]["choice"] == 2 and q["picked"]["concept_sha256"] == file_sha256(session / "concept.json")
        assert q["concept_brief"]["answer_shape"]["kind"] == "table"
    [record] = pick_records(session)
    assert (record["used"]["choice"], record["agent_id"]) == (2, "user")
    assert concept_step.check_session(session) == []  # `agent concepts check` passes


def test_pick_problems(unpicked) -> None:
    with TestClient(create_app(unpicked.settings)) as c:
        assert c.post("/api/questions/q01/concepts/pick", json={"choice": 3}).status_code == 400  # 2 briefs
        assert c.post("/api/questions/q01/concepts/pick", json={"choice": 0}).status_code == 422
        assert c.post("/api/questions/q01/concepts/pick", json={"choice": 1, "picked_by": "supervisor"}).status_code == 422
        assert c.post("/api/questions/q02/concepts/pick", json={"choice": 1}).status_code == 409  # nothing proposed
        assert c.post("/api/questions/q99/concepts/pick", json={"choice": 1}).status_code == 404
        assert c.post("/api/questions/q01/concepts/pick", json={"choice": 1}).status_code == 200
        (unpicked.root / "gold-data" / "q01").mkdir()
        (unpicked.root / "gold-data" / "q01" / "chunks.jsonl").write_text("{}\n", encoding="utf-8")
        response = c.post("/api/questions/q01/concepts/pick", json={"choice": 2})
        assert response.status_code == 409 and "gold" in response.json()["detail"]
        assert c.get("/api/questions/q01").json()["picked"]["choice"] == 1  # unchanged
    assert concept_step.check_session(unpicked.root / "concepts" / "q01") == []


def test_change_the_pick(unpicked) -> None:
    """Each pick, a confirmation too, is a concept_pick record; B rewrites picks.json from the chains."""
    session = unpicked.root / "concepts" / "q01"
    with TestClient(create_app(unpicked.settings)) as c:
        q = c.post("/api/questions/q01/concepts/pick", json={"choice": 2, "picked_by": "claude",
                                                               "reason": "a table is easier to score"}).json()
        assert q["concept"]["picked_by"] == "claude" and q["picked"]["reason"] == "a table is easier to score"
        first = q["picked"]["concept_sha256"]
        q = c.post("/api/questions/q01/concepts/pick", json={"choice": 1}).json()  # no run uses brief 2
        assert (q["picked"]["choice"], q["picked"]["picked_by"], q["picked"]["replaces_concept_sha256"]) == (1, "user", first)
        assert c.get("/api/runs/research-r1").json()["summary"]["qid"] == "q01"
        q = c.post("/api/questions/q01/concepts/pick", json={"choice": 1, "picked_by": "claude", "reason": "checked"}).json()
        assert (q["concept"]["picked_by"], q["picked"]["reason"]) == ("claude", "checked")  # a confirmation
    records = pick_records(session)
    assert [(r["used"]["choice"], r["agent_id"]) for r in records] == [(2, "claude"), (1, "user"), (1, "claude")]
    assert records[1]["used"]["replaces_concept_sha256"] == first
    assert concept_step.check_session(session) == []
    picks = json.loads((unpicked.root / "concepts" / "picks.json").read_text(encoding="utf-8"))
    assert picks["q01"] | {"concept_sha256": None} == {"choice": 1, "title": "Benchmarks used by RAG papers",
                                                       "picked_by": "claude", "reason": "checked", "concept_sha256": None}


def test_a_pick_runs_used_changes_only_with_force(unpicked) -> None:
    with TestClient(create_app(unpicked.settings)) as c:
        c.post("/api/questions/q01/concepts/pick", json={"choice": 1})  # the fixture runs' concept
        assert c.get("/api/questions").json()[0]["runs"] == {"claim_on": 1, "claim_off": 1}
        refused = c.post("/api/questions/q01/concepts/pick", json={"choice": 2})
        assert refused.status_code == 409 and "2 run(s)" in refused.json()["detail"]
        q = c.post("/api/questions/q01/concepts/pick", json={"choice": 2, "reason": "user", "force": True}).json()
        assert q["picked"]["reason"] == "user [changed with 2 run(s) on the replaced concept]"
        assert q["runs"] == {"claim_on": 0, "claim_off": 0}  # the runs are on the replaced concept now
        runs = c.get("/api/runs").json()
        assert {(r["qid"], r["concept_current"]) for r in runs} == {("q01", False)}  # found by the replaced pick
        assert c.get("/api/runs", params={"qid": "q01"}).json() == []
        assert len(c.get("/api/runs", params={"qid": "q01", "include_stale": True}).json()) == 2
    assert concept_step.check_session(unpicked.root / "concepts" / "q01") == []


def test_a_pick_made_on_the_command_line(tmp_path: Path) -> None:
    """`agent concepts pick`: the pick record says who picked."""
    propose_q01(tmp_path / "concepts", pick=2)
    from webapp.settings import Settings

    settings = Settings(runs=tmp_path / "runs", concepts=tmp_path / "concepts", gold=tmp_path / "gold",
                        questions=tmp_path / "none.json", WEBAPP_DIST=tmp_path / "dist")
    with TestClient(create_app(settings)) as c:
        [q] = c.get("/api/questions").json()  # no questions.json: the concept sessions are the questions
        assert (q["id"], q["question"].startswith("Which benchmarks")) == ("q01", True)
        assert q["concept"] == {"status": "picked", "title": "Most first-author papers at ACL 2025", "picked_by": "user"}
        assert c.get("/api/questions/q01").json()["picked"]["choice"] == 2


def test_runs_on_another_concept_are_not_the_questions(tmp_path: Path) -> None:
    """A run whose concept is not the question's current pick: listed, flagged, left out of its counts."""
    world = build_world(tmp_path)
    old = world.runs / "q01-claim_on-r1-a1"  # a batch run on a concept q01 no longer has
    shutil.copytree(world.research.run.root, old)
    config = json.loads((old / "config.json").read_text(encoding="utf-8"))
    config["hashes"]["concept_sha256"] = "9" * 64
    (old / "config.json").write_text(json.dumps(config), encoding="utf-8")
    with TestClient(create_app(world.settings)) as c:
        runs = {r["run_id"]: r for r in c.get("/api/runs").json()}
        assert (runs["q01-claim_on-r1-a1"]["qid"], runs["q01-claim_on-r1-a1"]["concept_current"]) == ("q01", False)
        assert runs["research-r1"]["concept_current"] is True
        assert c.get("/api/questions").json()[0]["runs"] == {"claim_on": 1, "claim_off": 1}
        assert {r["run_id"] for r in c.get("/api/runs", params={"qid": "q01"}).json()} == {"research-r1", "baseline-r1"}
        assert len(c.get("/api/runs", params={"qid": "q01", "include_stale": True}).json()) == 3
