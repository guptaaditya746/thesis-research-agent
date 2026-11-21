"""/api/evqa/runs: list and read run folders under a tmp runs root; refuse anything that is not a direct child."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from webapp import evqa_runs_api
from webapp.evqa_runs_api import router


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r = tmp_path / "runs" / "evqa"
    run = r / "slice1-abc"
    (run / "Q1").mkdir(parents=True)
    (run / "config.yaml").write_text("name: slice1\ndomain: medical\nclosed_book: true\n", encoding="utf-8")
    (run / "events.jsonl").write_text("".join(json.dumps({"i": i}) + "\n" for i in range(300)), encoding="utf-8")
    (run / "Q1" / "spec.json").write_text(json.dumps({"qid": "Q1"}), encoding="utf-8")
    (run / "Q1" / "find.jsonl").write_text("", encoding="utf-8")
    (run / "Q1" / "rows.jsonl").write_text('{"paper": "P1"}\nnot json\n', encoding="utf-8")
    (r / "other").mkdir()
    (r / "llm-cache.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "runs" / "secret").mkdir()
    monkeypatch.setattr(evqa_runs_api, "RUNS_ROOT", r)
    return r


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_list_and_detail(root: Path) -> None:
    c = client()
    runs = {r["run_id"]: r for r in c.get("/api/evqa/runs").json()}
    assert set(runs) == {"slice1-abc", "other"}
    assert runs["slice1-abc"]["name"] == "slice1" and runs["slice1-abc"]["closed_book"]
    assert not runs["slice1-abc"]["has_eval"]
    (root / "slice1-abc" / "eval.json").write_text(json.dumps({"totals": {"l1": 0.0}}), encoding="utf-8")
    d = c.get("/api/evqa/runs/slice1-abc").json()
    assert d["config"]["name"] == "slice1" and d["eval"]["totals"]["l1"] == 0.0
    assert len(d["events"]) == 200 and d["events"][-1] == {"i": 299}
    q = d["questions"]["Q1"]
    assert q["spec"] == {"qid": "Q1"} and q["find"] == [] and q["answer"] is None
    assert q["rows"][0] == {"paper": "P1"} and "_error" in q["rows"][1]


def test_refuses_paths_outside_the_root(root: Path) -> None:
    c = client()
    for bad in ("nope", "..", "...", "%2E%2E", "..%2Fsecret", "llm-cache.jsonl", "slice1-abc%2FQ1"):
        assert c.get(f"/api/evqa/runs/{bad}").status_code == 404, bad


def test_missing_root_lists_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evqa_runs_api, "RUNS_ROOT", tmp_path / "none")
    assert client().get("/api/evqa/runs").json() == []


def test_graph(root: Path) -> None:
    c = client()
    (root / "slice1-abc" / "config.yaml").write_text("name: g\ndomain: medical\nclosed_book: true\n", encoding="utf-8")
    (root / "slice1-abc" / "Q-med-01").mkdir()
    r = c.get("/api/evqa/runs/slice1-abc/graph/Q-med-01")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["counts"]["found"] == 0 and body["counts"]["missed"] > 0 and body["elements"]["nodes"]
    for bad in ("/api/evqa/runs/slice1-abc/graph/Q-none", "/api/evqa/runs/nope/graph/Q-med-01",
                "/api/evqa/runs/slice1-abc/graph/..%2Fx", "/api/evqa/runs/slice1-abc/graph/.hidden"):
        assert c.get(bad).status_code == 404, bad


def test_explain_only_for_practice_runs(root: Path) -> None:
    c = client()
    assert c.get("/api/evqa/runs/slice1-abc/explain/Q1").status_code == 403          # config has no split: practice
    (root / "slice1-abc" / "config.yaml").write_text("name: p\ndomain: medical\nsplit: practice\n", encoding="utf-8")
    r = c.get("/api/evqa/runs/slice1-abc/explain/Q1")
    assert r.status_code == 200, r.text
    assert r.json()["qid"] == "Q1" and r.json()["facts"] == [] and not r.json()["scored"]
    assert c.get("/api/evqa/runs/slice1-abc/explain/Q-none").status_code == 404
    bench = root / "bench-q-1"
    (bench / "Q1").mkdir(parents=True)
    (bench / "config.yaml").write_text("name: b\nsplit: practice\n", encoding="utf-8")
    assert c.get("/api/evqa/runs/bench-q-1/explain/Q1").status_code == 403


def test_baseline_run(root: Path) -> None:
    run = root / "practice-pqa-rag-abc"
    (run / "Q1").mkdir(parents=True)
    (run / "baseline" / "answers").mkdir(parents=True)
    (run / "config.yaml").write_text("name: practice-pqa-rag\ndomain: medical\nsplit: practice\n"
                                     "system: paperqa2-rag\n", encoding="utf-8")
    (run / "Q1" / "answer_text.json").write_text(json.dumps({"qid": "Q1", "text": "-0.5 pp"}), encoding="utf-8")
    (run / "Q1" / "claims.json").write_text(json.dumps({"qid": "Q1", "claims": []}), encoding="utf-8")
    c = client()
    runs = {r["run_id"]: r for r in c.get("/api/evqa/runs").json()}
    assert runs["practice-pqa-rag-abc"]["system"] == "paperqa2-rag" and runs["slice1-abc"]["system"] == "evqa"
    d = c.get("/api/evqa/runs/practice-pqa-rag-abc").json()
    assert set(d["questions"]) == {"Q1"}                     # baseline/ is not a question
    q = d["questions"]["Q1"]
    assert q["answer_text"]["text"] == "-0.5 pp" and q["claims"] == {"qid": "Q1", "claims": []}
    assert q["answer"] is None and q["spec"] is None
    assert c.get("/api/evqa/runs/practice-pqa-rag-abc/explain/Q1").status_code == 409
