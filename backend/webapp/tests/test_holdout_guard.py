"""Hold-out runs are score only, hold-out gold stays closed (evqa/holdout.py): every per-question endpoint answers
403 with a plain message; totals stay readable; bench-* and practice runs stay browsable."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from evqa import holdout
from webapp import evqa_runs_api
from webapp.evqa_api import router as data_router
from webapp.evqa_questions_api import router as questions_router
from webapp.evqa_runs_api import router as runs_router

CONFIGS = {
    "h-by-domain": "name: other\ndomain: medical_holdout\nsplit: test\n",
    "h-by-name": "name: holdout-qwen\ndomain: medical\nsplit: test\n",
    "holdout-no-config": None,
    "h-bad-yaml": "name: [unclosed\n",
    "bench-qwen-abc": "name: bench-qwen\ndomain: medical\nsplit: test\n",
    "practice-abc": "name: practice-qwen\ndomain: medical\nsplit: practice\n",
}
CLOSED = ("h-by-domain", "h-by-name", "holdout-no-config", "h-bad-yaml")


def client() -> TestClient:
    app = FastAPI()
    for r in (runs_router, questions_router, data_router):
        app.include_router(r, prefix="/api")
    return TestClient(app)


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r = tmp_path / "runs" / "evqa"
    for run, cfg in CONFIGS.items():
        (r / run / "Q1").mkdir(parents=True)
        if cfg is not None:
            (r / run / "config.yaml").write_text(cfg, encoding="utf-8")
        (r / run / "Q1" / "spec.json").write_text(json.dumps({"qid": "Q1"}), encoding="utf-8")
        (r / run / "Q1" / "answer.json").write_text(json.dumps({"qid": "Q1", "sentence": "secret"}), encoding="utf-8")
        (r / run / "events.jsonl").write_text(
            json.dumps({"step": "run", "kind": "start", "qid": None}) + "\n"
            + json.dumps({"step": "spec", "kind": "problem", "qid": "Q1", "data": {"error": "secret"}}) + "\n",
            encoding="utf-8")
        (r / run / "eval.json").write_text(json.dumps({"totals": {"l3": 0.5}, "questions": {"Q1": {"l3": 1}}}),
                                           encoding="utf-8")
    monkeypatch.setattr(evqa_runs_api, "RUNS_ROOT", r)
    return r


def test_holdout_rule() -> None:
    assert holdout.run_closed({"domain": "medical_holdout"}) and holdout.run_closed({"name": "holdout-x"})
    assert holdout.run_closed({}, "holdout-x") and holdout.run_closed({"_error": "bad"})
    assert holdout.run_closed({"name": "bench-qwen", "domain": "medical"}) is None
    assert holdout.gold_closed("medical_holdout") and holdout.gold_closed("medical") is None


@pytest.mark.parametrize("run", CLOSED)
def test_holdout_run_shows_totals_only(root: Path, run: str) -> None:
    c = client()
    d = c.get(f"/api/evqa/runs/{run}")
    assert d.status_code == 200
    body = d.json()
    assert "hold-out run" in body["closed"] and body["questions"] == {}
    assert body["eval"]["totals"] == {"l3": 0.5} and body["eval"]["questions"] == {}
    assert all(not e.get("qid") for e in body["events"]) and "secret" not in d.text
    for path in ("graph/Q1", "explain/Q1", "graph/nope!", "explain/Q9"):
        r = c.get(f"/api/evqa/runs/{run}/{path}")
        assert r.status_code == 403 and "score only" in r.json()["detail"], path


@pytest.mark.parametrize("run", ["bench-qwen-abc", "practice-abc"])
def test_bench_and_practice_runs_stay_browsable(root: Path, run: str) -> None:
    body = client().get(f"/api/evqa/runs/{run}").json()
    assert body["closed"] is None and body["questions"]["Q1"]["answer"]["sentence"] == "secret"
    assert body["eval"]["questions"] == {"Q1": {"l3": 1}}


def test_holdout_gold_is_not_served() -> None:
    c = client()
    listing = c.get("/api/evqa/questions/medical_holdout")
    assert listing.status_code == 200
    qs = listing.json()["questions"]
    assert qs and all(q["question"] and "answerable" not in q for q in qs)
    d = c.get(f"/api/evqa/questions/medical_holdout/{qs[0]['qid']}")
    assert d.status_code == 403 and "gold answers stay closed" in d.json()["detail"]
    assert c.get("/api/evqa/questions/medical/Q-med-01").status_code == 200
    gold = [f["path"] for f in c.get("/api/evqa/files").json() if "/medical_holdout/gold/" in f["path"]]
    assert gold and all(c.get("/api/evqa/file", params={"path": p}).status_code == 403 for p in gold[:3])
    other = next(f["path"] for f in c.get("/api/evqa/files").json() if "/medical/gold/" in f["path"])
    assert c.get("/api/evqa/file", params={"path": other}).status_code == 200
