"""The read endpoints of the API on the fixture world (webapp/tests/world.py)."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.anchor import read_text
from agent.tests.runs import SPIDER_BIRD
from webapp.app import create_app

from .world import KEY_DRAFT, OUTPUT, SCORE, World


def test_health_and_config(client: TestClient, world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.get("/api/health").json()["ok"] is True
    monkeypatch.delenv("LITELLM_MASTER_KEY", raising=False)
    config = client.get("/api/config").json()
    assert config["llm_key_set"] is False
    assert (config["runs_root"], config["corpus"]) == (str(world.runs), str(world.corpus))
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-secret-value")
    response = client.get("/api/config")
    assert response.json()["llm_key_set"] is True and "sk-secret-value" not in response.text


def test_questions(client: TestClient) -> None:
    q01, q02 = client.get("/api/questions").json()
    assert q01["id"] == "q01" and q01["category"] == "corpus_wide"
    assert q01["concept"] == {"status": "picked", "title": "Benchmarks used by RAG papers", "picked_by": "user"}
    assert q01["runs"] == {"claim_on": 1, "claim_off": 1}  # both fixture runs use q01's picked concept
    assert q01["gold"] == {"status": "none", "rows": None, "facts": None}
    assert q02["concept"]["status"] == "none" and q02["runs"] == {"claim_on": 0, "claim_off": 0}
    assert q02["gold"] == {"status": "draft", "rows": 1, "facts": 1}


def test_question_detail(client: TestClient) -> None:
    q = client.get("/api/questions/q01").json()
    assert [b["id"] for b in q["briefs"]] == ["c1", "c2"]
    assert q["briefs"][0]["answer_shape"]["kind"] == "graph" and q["briefs"][1]["answer_shape"]["kind"] == "table"
    assert q["picked"]["choice"] == 1 and q["picked"]["picked_by"] == "user"
    assert q["concept_brief"]["title"] == "Benchmarks used by RAG papers"
    assert client.get("/api/questions/q02").json()["briefs"] == []
    assert client.get("/api/questions/q99").status_code == 404


def test_runs_list_and_filters(client: TestClient) -> None:
    runs = {r["run_id"]: r for r in client.get("/api/runs").json()}
    assert set(runs) == {"baseline-r1", "research-r1"}
    r = runs["research-r1"]
    assert (r["qid"], r["condition"], r["seed"], r["exit_status"], r["live"]) == ("q01", "claim_on", 1234, "submitted", False)
    assert (r["steps"], r["model_calls"], r["claims_accepted"], r["claims_rejected"]) == (6, 6, 6, 1)
    assert (r["rows"], r["facts"], r["attach"]) == (5, 5, "not_applicable")
    assert r["score"] == {"support_share": 0.6, "fact_f1": 0.889, "row_f1": 0.667}  # soft fact F1
    b = runs["baseline-r1"]
    assert (b["condition"], b["exit_status"], b["attach"], b["score"]) == ("claim_off", "submitted", "pending", None)
    assert b["tokens_without_attach"] is not None and b["claims_accepted"] == 3
    assert [x["run_id"] for x in client.get("/api/runs", params={"condition": "claim_off"}).json()] == ["baseline-r1"]
    assert len(client.get("/api/runs", params={"qid": "q01"}).json()) == 2
    assert client.get("/api/runs", params={"qid": "q02"}).json() == []
    checked = {x["run_id"]: x["verify"] for x in client.get("/api/runs", params={"verify": True}).json()}
    assert checked == {"baseline-r1": "ok", "research-r1": "ok"}


def test_run_detail(client: TestClient) -> None:
    d = client.get("/api/runs/research-r1").json()
    assert d["summary"]["verify"] == "ok" and d["verify"]["ok"] is True and d["verify"]["errors"] == []
    assert d["verify"]["stats"]["facts_with_claims"] == 4
    assert d["config"]["condition"] == "claim_on" and d["concept"]["title"] == "Benchmarks used by RAG papers"
    assert [row["id"] for row in d["answer"]["rows"]] == ["r1", "r2", "r3", "r4", "r5"]
    assert d["answer"]["rows"][0]["source"] == "p1" and d["answer"]["rows"][0]["facts"][0]["claims"] == ["claim-000001"]
    assert client.get("/api/runs/nope").status_code == 404


def test_steps(client: TestClient) -> None:
    steps = client.get("/api/runs/research-r1/steps").json()
    assert [(s["agent_id"], s["step"]) for s in steps] == [("main", 1), ("main", 2), ("main", 3), ("sub-01", 4),
                                                          ("main", 5), ("main", 6)]
    one = steps[0]
    assert one["command"].startswith('rg -n "Spider"') and one["origin"] == "research"
    assert one["output_head"] == "\n".join(OUTPUT.splitlines()[:12])
    assert [(c["claim_id"], c["status"]) for c in one["claims"]] == [("claim-000001", "accepted"), ("claim-000002", "accepted")]
    assert steps[2]["spawned"] == ["sub-01"] and steps[2]["command"] is None
    assert [c["claim_id"] for c in steps[3]["claims"]] == ["claim-000005", "claim-000006"]
    assert steps[4]["claims"] == [{"claim_id": None, "status": "rejected", "reason": "not_found", "s": "p3",
                                   "p": "evaluatesOn", "o": "HellaSwag"}]
    assert steps[5]["model_call"]["final_answer"] is True and steps[5]["model_call"]["task_id"].startswith("t")
    attach = client.get("/api/runs/baseline-r1/steps").json()[4:]
    assert [(s["step"], s["origin"], s["fact_id"]) for s in attach] == [
        (5, "attach", "f1"), (6, "attach", "f2"), (7, "attach", "f3"), (8, "attach", "f4")]
    assert attach[3]["claims"] == []


def test_step_output(client: TestClient) -> None:
    response = client.get("/api/runs/research-r1/steps/1/output")
    assert response.status_code == 200 and response.text == OUTPUT
    assert response.headers["content-type"].startswith("text/plain")
    assert client.get("/api/runs/research-r1/steps/1/output", params={"agent_id": "sub-01"}).status_code == 404
    assert client.get("/api/runs/research-r1/steps/2/output").status_code == 404  # no output file written
    assert client.get("/api/runs/research-r1/steps/6/output").status_code == 404  # no command at step 6


def test_claims(client: TestClient, world: World) -> None:
    claims = client.get("/api/runs/research-r1/claims").json()
    assert len(claims) == 7
    first = claims[0]
    assert (first["claim_id"], first["status"], first["file"], first["paper_id"], first["step"]) == \
        ("claim-000001", "accepted", "p1.md", "p1", 1)
    text = read_text(world.corpus / "p1.md")
    assert text[first["anchor"]["start"]:first["anchor"]["end"]] == first["quote"] == SPIDER_BIRD.text
    rejected = [c for c in claims if c["status"] == "rejected"]
    assert [(c["reason"], c["paper_id"], c["anchor"]) for c in rejected] == [("not_found", "p3", None)]
    assert rejected[0]["quote"] == "we evaluate on HellaSwag with exact match"
    sub = [c for c in claims if c["agent_id"] == "sub-01"]
    assert [c["claim_id"] for c in sub] == ["claim-000005", "claim-000006"]
    attach = client.get("/api/runs/baseline-r1/claims").json()
    assert {c["origin"] for c in attach} == {"attach"}


def test_graph(client: TestClient) -> None:
    graph = client.get("/api/runs/research-r1/graph").json()
    assert [e["id"] for e in graph["edges"]] == [f"edge-{n:06d}" for n in range(1, 7)]
    assert graph["edges"][0]["predicate"]["text"] == "evaluatesOn" and graph["edges"][0]["evidence"]["paper"] == "p1"
    assert {n["id"] for n in graph["nodes"]} >= {"paper:p1", "entity:spider"}
    assert graph["schema_version"] == 1  # graph.json as is, fields beyond the model kept
    assert len(client.get("/api/runs/baseline-r1/graph").json()["edges"]) == 3


def test_graph_of_a_run_without_graph_json(fresh: World) -> None:
    (fresh.research.run.root / "graph.json").unlink()
    with TestClient(create_app(fresh.settings)) as c:
        assert len(c.get("/api/runs/research-r1/graph").json()["edges"]) == 6  # built in memory
        assert not (fresh.research.run.root / "graph.json").exists()
    with TestClient(create_app(fresh.with_settings(corpus=None))) as c:
        assert c.get("/api/runs/research-r1/graph").status_code == 404


def test_walk(client: TestClient, world: World) -> None:
    walk = client.get("/api/runs/research-r1/facts/f1/walk", params={"judge": False}).json()
    assert (walk["fact"]["id"], walk["row_id"], walk["support"]) == ("f1", "r1", None)
    [item] = walk["claims"]
    assert item["claim_id"] == "claim-000001" and item["anchor_status"] == "ok"
    assert item["step"]["step"] == 1 and item["step"]["command"].startswith('rg -n "Spider"')
    passage = item["passage"]
    lo, hi = passage["highlight"]["start"], passage["highlight"]["end"]
    assert passage["text"][lo:hi] == SPIDER_BIRD.text and passage["paper_id"] == "p1"
    text = read_text(world.corpus / "p1.md")
    assert text[passage["offset"]:passage["offset"] + len(passage["text"])] == passage["text"]
    sub = client.get("/api/runs/research-r1/facts/f4/walk", params={"judge": False}).json()
    assert sub["claims"][0]["step"]["agent_id"] == "sub-01"
    assert client.get("/api/runs/research-r1/facts/f5/walk", params={"judge": False}).json()["claims"] == []
    assert client.get("/api/runs/research-r1/facts/f9/walk").status_code == 404


def test_walk_with_the_judge(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    asked = []

    def support(fact, quote, *, context=None):
        asked.append((fact, quote))
        return {"label": "supports" if "Spider" in quote else "no", "rationale": "the quote names it",
                "model": "sub-model-1", "prompt_sha256": "a" * 64, "cached": True}

    monkeypatch.setitem(sys.modules, "gold.judge", types.SimpleNamespace(support=support))
    walk = client.get("/api/runs/research-r1/facts/f1/walk").json()
    assert walk["support"]["label"] == "supports" and walk["claims"][0]["support"]["cached"] is True
    assert asked == [({"s": "p1", "p": "evaluatesOn", "o": "Spider"}, SPIDER_BIRD.text)]

    def broken(fact, quote, *, context=None):
        raise ConnectionError("no model")

    monkeypatch.setitem(sys.modules, "gold.judge", types.SimpleNamespace(support=broken))
    walk = client.get("/api/runs/research-r1/facts/f1/walk").json()
    assert walk["support"] is None and walk["claims"][0]["passage"] is not None


def test_score(client: TestClient) -> None:
    score = client.get("/api/runs/research-r1/score").json()
    assert score["support"]["support_share"] == 0.6 and score["verify_ok"] is True  # extra fields kept
    assert score["facts"]["soft"]["f1"] == SCORE["facts"]["soft"]["f1"]
    assert client.get("/api/runs/baseline-r1/score").status_code == 404


def test_corpus_passage(client: TestClient, world: World) -> None:
    text = read_text(world.corpus / "p1.md")
    start = text.index(SPIDER_BIRD.text)
    end = start + len(SPIDER_BIRD.text)
    p = client.get("/api/corpus/p1", params={"start": start, "end": end, "context": 100}).json()
    assert p["text"][p["highlight"]["start"]:p["highlight"]["end"]] == SPIDER_BIRD.text
    assert p["offset"] == start - 100 and len(p["text"]) == len(SPIDER_BIRD.text) + 200 and p["length"] == len(text)
    first_heading = next(line for line in text.splitlines() if line.startswith("#"))
    assert p["title"] == first_heading.lstrip("#").strip()
    head = client.get("/api/corpus/p1.md", params={"context": 50}).json()
    assert (head["offset"], head["highlight"], head["text"]) == (0, None, text[:100])
    assert client.get("/api/corpus/p1", params={"start": 10, "end": 5}).status_code == 400
    assert client.get("/api/corpus/p1", params={"start": 0, "end": len(text) + 1}).status_code == 400
    assert client.get("/api/corpus/p1", params={"start": -1, "end": 5}).status_code == 422
    assert client.get("/api/corpus/p99").status_code == 404  # failed conversion: no text
    assert client.get("/api/corpus/nope").status_code == 404


def test_gold(client: TestClient) -> None:
    gold = {g["qid"]: g for g in client.get("/api/gold").json()}
    assert gold["q01"]["status"] == "none" and gold["q01"]["key_version"] is None
    q02 = gold["q02"]
    assert (q02["status"], q02["key_version"], q02["rows"], q02["facts"]) == ("draft", "v1-draft", 1, 1)
    assert q02["coverage"] == {"papers": 10, "relevant": 4} and q02["counts"] == {"candidates": 7}
    key = client.get("/api/gold/q02/key").json()
    assert key["version"] == "v1-draft" and key["rows"] == KEY_DRAFT["rows"]
    assert client.get("/api/gold/q01/key").status_code == 404


def test_results(client: TestClient, fresh: World) -> None:
    assert client.get("/api/results").json() == {"primary": {"p_value": 0.03}}
    (fresh.runs / "report" / "report.json").unlink()
    with TestClient(create_app(fresh.settings)) as c:
        assert c.get("/api/results").status_code == 404


def test_nothing_there_yet(tmp_path: Path) -> None:
    """A server started before any run, concept or gold exists answers with empty lists, not errors."""
    from webapp.settings import Settings

    settings = Settings(runs=tmp_path / "runs", gold=tmp_path / "gold", concepts=tmp_path / "concepts",
                        questions=tmp_path / "questions.json", corpus=None, WEBAPP_DIST=tmp_path / "dist")
    with TestClient(create_app(settings)) as c:
        for url in ("/api/questions", "/api/runs", "/api/gold", "/api/jobs"):
            assert c.get(url).json() == [], url
        assert c.get("/api/results").status_code == 404
        assert c.post("/api/sparql", json={"query": "SELECT * WHERE { ?s ?p ?o }"}).json()["rows"] == []


def test_openapi_file_is_current() -> None:
    """webapp/web/openapi.json (the frontend's types come from it) is what `webapp openapi` prints."""
    path = Path(__file__).resolve().parents[1] / "web" / "openapi.json"
    committed, current = json.loads(path.read_text(encoding="utf-8")), create_app().openapi()
    for schema in (committed, current):
        schema["info"].pop("version")  # the package version; a bump alone changes no type
    assert committed == current, "run `uv run webapp openapi -o webapp/web/openapi.json`"
