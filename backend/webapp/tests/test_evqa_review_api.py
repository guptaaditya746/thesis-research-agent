"""/api/evqa/review: the optional review queue. Labels go to a temp folder; verdicts stay hidden until labelled."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from evqa.eval import review
from webapp.evqa_review_api import router


@pytest.fixture
def c(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(review, "REVIEWS", tmp_path / "reviews")
    monkeypatch.setattr(review, "RUNS", tmp_path / "runs")
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_fidelity_sample_holds_flagged_and_ordinary_items_without_verdicts(c: TestClient) -> None:
    items = c.get("/api/evqa/review/fidelity/items", params={"scope": "medical", "reviewer": "ann"}).json()
    assert items and all("automated" not in i and "stratum" not in i and i["label"] is None for i in items)
    strata = [i["stratum"] for i in review.fidelity_items("medical")]
    assert set(strata) <= {"flagged", "pass"} and 0 < strata.count("pass") <= review.PASS_SAMPLE
    first = items[0]
    assert {p["part"] for p in first["show"]["claim"]} >= {"drug", "measure", "patients", "number or unit"}
    for e in first["show"]["evidence"]:
        assert all(e["text"][a:b].strip() for a, b in e["marks"])          # each mark is the written value
    tables = [e for i in items for e in i["show"]["evidence"] if e["kind"] == "table"]
    assert tables and all("|---" in e["text"] or "| ---" in e["text"] for e in tables)   # header row kept


def test_label_reveals_verdict_resumes_and_counts_per_reviewer(c: TestClient) -> None:
    s0 = c.get("/api/evqa/review/fidelity/summary", params={"scope": "medical"}).json()
    assert s0["status"] == "awaiting optional review" and s0["reviewed"] == 0 and s0["items"] > 0
    it = c.get("/api/evqa/review/fidelity/items", params={"scope": "medical", "reviewer": "ann"}).json()[0]
    body = {"scope": "medical", "item_id": it["id"], "item_version": it["version"], "reviewer": "ann",
            "choice": "partly", "parts": ["dose"], "note": "two 25 mg values"}
    r = c.post("/api/evqa/review/fidelity/labels", json=body).json()
    assert r["saved"]["choice"] == "partly" and "l0" in r["automated"]
    again = c.get("/api/evqa/review/fidelity/items", params={"scope": "medical", "reviewer": "ann"}).json()[0]
    assert again["label"]["choice"] == "partly" and "automated" in again          # resume: shows own answer
    other = c.get("/api/evqa/review/fidelity/items", params={"scope": "medical", "reviewer": "bo"}).json()[0]
    assert other["label"] is None and "automated" not in other                     # independent reviewer
    c.post("/api/evqa/review/fidelity/labels", json={**body, "reviewer": "bo", "choice": "supported", "parts": []})
    c.post("/api/evqa/review/fidelity/labels", json={**body, "choice": "supported", "parts": []})   # ann changes
    s = c.get("/api/evqa/review/fidelity/summary", params={"scope": "medical"}).json()
    assert s["reviewed"] == 1 and s["labels"] == 2 and s["reviewers"] == ["ann", "bo"]
    assert s["counts"]["supported"] == 2 and s["disagreements"] == 0 and s["double_reviewed"] == 1
    assert s["status"] == f"1 of {s['items']} reviewed"
    lines = (review.REVIEWS / "fidelity.jsonl").read_text().splitlines()
    assert len(lines) == 3                                                         # every submit kept


def test_bad_labels_are_refused(c: TestClient) -> None:
    it = c.get("/api/evqa/review/fidelity/items", params={"scope": "medical"}).json()[0]
    body = {"scope": "medical", "item_id": it["id"], "item_version": it["version"], "reviewer": "ann",
            "choice": "supported"}
    assert c.post("/api/evqa/review/fidelity/labels", json={**body, "choice": "maybe"}).status_code == 422
    assert c.post("/api/evqa/review/fidelity/labels", json={**body, "reviewer": " "}).status_code == 422
    assert c.post("/api/evqa/review/fidelity/labels", json={**body, "item_version": "old"}).status_code == 409
    assert c.post("/api/evqa/review/fidelity/labels", json={**body, "item_id": "nope"}).status_code == 404
    assert c.get("/api/evqa/review/nope/items", params={"scope": "medical"}).status_code == 404


def test_population_pairs_come_from_the_judge_file(c: TestClient) -> None:
    run = review.RUNS / "practice-x"
    run.mkdir(parents=True)
    (run / "config.yaml").write_text("name: practice-x\nsplit: practice\ndomain: medical\n")
    details = [{"label": "older adults", "conditions": "adults aged 65 or older", "verdict": "matches", "reason": "r"},
               {"label": "older adults", "conditions": "adults aged 65 or older", "verdict": "matches", "reason": "r"}]
    (run / "population_judge.json").write_text(json.dumps({"judge_model": "m", "details": details}))
    items = c.get("/api/evqa/review/population/items", params={"scope": "practice-x", "reviewer": "ann"}).json()
    assert len(items) == 1 and items[0]["show"]["facts"] == 2 and "automated" not in items[0]
    r = c.post("/api/evqa/review/population/labels", json={"scope": "practice-x", "item_id": items[0]["id"],
               "item_version": items[0]["version"], "reviewer": "ann", "choice": "different"}).json()
    assert r["automated"]["judge"] == "matches"
    s = c.get("/api/evqa/review/population/summary", params={"scope": "practice-x"}).json()
    assert s["by_automated"] == {"matches": {"different": 1}}
    assert c.get("/api/evqa/review/population/items", params={"scope": "../x"}).status_code == 404
