"""Picking a concept brief in the web app, and changing the pick until the gold build starts (row 2.2)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.canonical import file_sha256
from agent.chain import verify
from webapp.app import create_app

from .world import build_world, propose_q01


@pytest.fixture
def unpicked(tmp_path: Path):
    return build_world(tmp_path, pick=None)


def pick_records(session: Path) -> list[dict]:
    lines = (session / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [r for r in map(json.loads, lines) if r["subtype"] == "concept_pick"]


def test_pick_then_change_the_pick(unpicked) -> None:
    session = unpicked.root / "concepts" / "q01"
    with TestClient(create_app(unpicked.settings)) as c:
        assert c.get("/api/questions/q01").json()["concept"]["status"] == "proposed"
        assert c.get("/api/runs/research-r1").json()["summary"]["qid"] is None  # no concept picked yet
        q = c.post("/api/questions/q01/concepts/pick", json={"choice": 2, "picked_by": "claude",
                                                               "reason": "a table is easier to score"}).json()
        assert q["concept"] == {"status": "picked", "title": "Most first-author papers at ACL 2025", "picked_by": "claude"}
        assert q["picked"]["choice"] == 2 and q["picked"]["reason"] == "a table is easier to score"
        assert q["concept_brief"]["answer_shape"]["kind"] == "table"
        picks = json.loads((unpicked.root / "concepts" / "picks.json").read_text(encoding="utf-8"))
        assert picks == {"q01": {"choice": 2, "title": "Most first-author papers at ACL 2025", "picked_by": "claude",
                                 "reason": "a table is easier to score",
                                 "concept_sha256": file_sha256(session / "concept.json")}}
        first_sha = picks["q01"]["concept_sha256"]
        # The user changes it: the runs' concept (brief 1) becomes q01's concept.
        q = c.post("/api/questions/q01/concepts/pick", json={"choice": 1}).json()
        assert (q["picked"]["choice"], q["picked"]["picked_by"], q["concept"]["title"]) == \
            (1, "user", "Benchmarks used by RAG papers")
        assert c.get("/api/runs/research-r1").json()["summary"]["qid"] == "q01"
        # Picking the same brief again only records who confirmed it.
        c.post("/api/questions/q01/concepts/pick", json={"choice": 1, "picked_by": "supervisor"})
        assert c.get("/api/questions").json()[0]["concept"]["picked_by"] == "supervisor"
    records = pick_records(session)
    assert [(r["used"]["choice"], r["agent_id"]) for r in records] == [(2, "user"), (1, "user")]
    assert records[-1]["generated"]["concept_sha256"] == file_sha256(session / "concept.json")
    assert file_sha256(session / "concept.replaced-1.json") == first_sha  # the replaced pick is kept
    assert (session / "concept.sha256").read_text().split()[0] == file_sha256(session / "concept.json")
    report = verify(session / "events.jsonl", session / "claims.jsonl")
    assert report.ok, report.errors


def test_pick_problems(unpicked) -> None:
    with TestClient(create_app(unpicked.settings)) as c:
        assert c.post("/api/questions/q01/concepts/pick", json={"choice": 3}).status_code == 400  # 2 briefs
        assert c.post("/api/questions/q01/concepts/pick", json={"choice": 0}).status_code == 422
        assert c.post("/api/questions/q02/concepts/pick", json={"choice": 1}).status_code == 409  # nothing proposed
        assert c.post("/api/questions/q99/concepts/pick", json={"choice": 1}).status_code == 404
        assert c.post("/api/questions/q01/concepts/pick", json={"choice": 1}).status_code == 200
        (unpicked.root / "gold-data" / "q01").mkdir()
        (unpicked.root / "gold-data" / "q01" / "chunks.jsonl").write_text("{}\n", encoding="utf-8")
        response = c.post("/api/questions/q01/concepts/pick", json={"choice": 2})
        assert response.status_code == 409 and "gold" in response.json()["detail"]
        assert c.get("/api/questions/q01").json()["picked"]["choice"] == 1  # unchanged


def test_a_pick_made_on_the_command_line(tmp_path: Path) -> None:
    """`agent concepts pick` writes no picks.json entry: the pick shows as the user's."""
    propose_q01(tmp_path / "concepts", pick=2)
    from webapp.settings import Settings

    settings = Settings(runs=tmp_path / "runs", concepts=tmp_path / "concepts", gold=tmp_path / "gold",
                        questions=tmp_path / "none.json", WEBAPP_DIST=tmp_path / "dist")
    with TestClient(create_app(settings)) as c:
        [q] = c.get("/api/questions").json()  # no questions.json: the concept sessions are the questions
        assert (q["id"], q["question"].startswith("Which benchmarks")) == ("q01", True)
        assert q["concept"] == {"status": "picked", "title": "Most first-author papers at ACL 2025", "picked_by": "user"}
        assert c.get("/api/questions/q01").json()["picked"]["choice"] == 2
