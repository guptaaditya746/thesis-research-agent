"""Read-only safety: no path leaves its root, SPARQL cannot write, the built frontend is served safely."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.rundir import RunDir
from webapp.app import create_app
from webapp.files import NotFound, inside
from webapp.runs import output_head, steps_of

from .world import World

SECRET = "top secret, outside every root"


@pytest.fixture(scope="module")
def secret(world: World) -> Path:
    """A file next to the roots that no request may read."""
    path = world.root / "secret.txt"
    path.write_text(SECRET, encoding="utf-8")
    return path


@pytest.mark.parametrize("url", [
    "/api/runs/..%2Fsecret.txt",
    "/api/runs/%2e%2e/claims",
    "/api/runs/..%2F..%2Fetc/claims",
    "/api/runs/%2e%2e%2fruns%2fresearch-r1/claims",
    "/api/runs/.jobs/steps",
    "/api/runs/report/claims",
    "/api/runs/research-r1/facts/..%2F..%2Fsecret/walk",
    "/api/corpus/..%2Fsecret.txt",
    "/api/corpus/%2e%2e%2fsecret",
    "/api/corpus/manifest",
    "/api/gold/..%2Fsecret.txt/key",
    "/api/gold/%2e%2e/key",
    "/api/questions/..%2Fsecret.txt",
    "/api/jobs/..%2F..%2Fsecret",
    "/api/jobs/%2e%2e/log",
    "/api/queries/1?run_id=..%2Fsecret.txt",
])
def test_paths_outside_the_roots_are_refused(client: TestClient, secret: Path, url: str) -> None:
    response = client.get(url)
    assert response.status_code in (404, 422), (url, response.status_code)
    assert SECRET not in response.text


def test_inside() -> None:
    root = Path(__file__).resolve().parent
    assert inside(root, "world.py") == root / "world.py"
    for bad in ("../app.py", str(root.parent / "app.py"), "a/../../app.py", ".."):
        with pytest.raises(NotFound):
            inside(root, bad)


def test_a_record_cannot_point_outside_its_run(world: World, secret: Path) -> None:
    """Output files named in events.jsonl are read only inside the run directory."""
    run = RunDir(world.research.run.root)
    assert output_head(run, "../../secret.txt") is None
    record = {"task_id": "t000001", "subtype": "agent_tool", "step_id": 1, "agent_id": "main",
              "used": {"command": "ls"}, "generated": {"output_file": "../../secret.txt"}, "custom_metadata": {}}
    [step] = steps_of(run, [record])
    assert step.output_head is None


def test_concept_path_must_stay_in_the_roots(client: TestClient, world: World, secret: Path) -> None:
    for path in (str(secret), "../secret.txt", "../../etc/passwd", str(world.corpus / "manifest.json")):
        response = client.post("/api/runs", json={"concept_path": path, "condition": "claim_on", "seed": 1})
        assert response.status_code == 400, path


def test_sparql_is_read_only(client: TestClient) -> None:
    count = "SELECT (COUNT(?c) AS ?n) WHERE { ?c a <urn:thesis-agent:vocab#Claim> }"
    before = client.post("/api/sparql", json={"query": count}).json()["rows"][0]["n"]
    assert int(before) == 9  # 6 research + 3 attach claims
    for update in ("INSERT DATA { <urn:x> <urn:y> <urn:z> }",
                   "DELETE WHERE { ?s ?p ?o }",
                   "PREFIX ours: <urn:thesis-agent:vocab#>\nCLEAR ALL",
                   "DROP GRAPH <urn:thesis-agent:run:research-r1>",
                   "LOAD <http://example.org/data.ttl>",
                   "SELECT * WHERE { ?s ?p ?o } ; DELETE WHERE { ?s ?p ?o }"):
        response = client.post("/api/sparql", json={"query": update})
        assert response.status_code == 400, update
    assert client.post("/api/sparql", json={"query": count}).json()["rows"][0]["n"] == before


def test_sparql_queries(client: TestClient) -> None:
    query = ("PREFIX ours: <urn:thesis-agent:vocab#>\n"
             "SELECT ?id WHERE { ?c a ours:Claim ; ours:claimId ?id } ORDER BY ?id")
    one = client.post("/api/sparql", json={"query": query, "run_id": "research-r1"}).json()
    assert one["vars"] == ["id"] and [r["id"] for r in one["rows"]] == [f"claim-00000{n}" for n in range(1, 7)]
    assert len(client.post("/api/sparql", json={"query": query}).json()["rows"]) == 9
    ask = client.post("/api/sparql", json={"query": "ASK { ?s ?p ?o }", "run_id": "baseline-r1"}).json()
    assert ask == {"vars": [], "rows": [], "boolean": True}
    construct = client.post("/api/sparql", json={"query": "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o } LIMIT 3"}).json()
    assert construct["vars"] == ["s", "p", "o"] and len(construct["rows"]) == 3
    assert client.post("/api/sparql", json={"query": "SELECT nonsense"}).status_code == 400
    assert client.post("/api/sparql", json={"query": query, "run_id": "nope"}).status_code == 404


def test_provenance_queries(client: TestClient) -> None:
    q1 = client.get("/api/queries/1", params={"run_id": "research-r1"}).json()
    assert q1["name"] == "edge_to_passage" and len(q1["rows"]) == 6
    [q2] = client.get("/api/queries/2", params={"run_id": "research-r1", "fact": "f3"}).json()["rows"]
    assert (q2["claim_id"], q2["step_id"]) == ("claim-000003", 2)
    q3 = client.get("/api/queries/3", params={"run_id": "research-r1", "agent": "sub-01"}).json()["rows"]
    assert [r["claim_id"] for r in q3] == ["claim-000005", "claim-000006"]
    assert client.get("/api/queries/3", params={"run_id": "research-r1"}).status_code == 400  # needs step or agent
    assert client.get("/api/queries/4", params={"run_id": "research-r1"}).json()["rows"] == []  # every anchor resolves
    [q5] = client.get("/api/queries/5", params={"run_id": "research-r1"}).json()["rows"]
    assert q5["fact_id"] == "f5"
    baseline = client.get("/api/queries/1", params={"run_id": "baseline-r1"}).json()["rows"]
    assert {r["phase"] for r in baseline} == {"attach"}
    assert client.get("/api/queries/6", params={"run_id": "research-r1"}).status_code == 404
    assert client.get("/api/queries/1", params={"run_id": "nope"}).status_code == 404


def test_queries_need_graph_ttl(fresh: World) -> None:
    (fresh.research.run.root / "graph.ttl").unlink()
    with TestClient(create_app(fresh.settings)) as c:
        response = c.get("/api/queries/1", params={"run_id": "research-r1"})
        assert response.status_code == 404 and "export-prov" in response.json()["detail"]


def test_frontend_is_served_with_a_fallback(fresh: World) -> None:
    dist = fresh.root / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>app</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (fresh.root / "secret.txt").write_text(SECRET, encoding="utf-8")
    with TestClient(create_app(fresh.settings)) as c:
        assert c.get("/").text.startswith("<!doctype html>")
        assert c.get("/runs/research-r1").text.startswith("<!doctype html>")  # a client-side route
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/api/nope").status_code == 404 and c.get("/api/nope").json()["detail"]
        assert c.get("/api/health").json()["ok"] is True
        for url in ("/..%2Fsecret.txt", "/%2e%2e/secret.txt", "/assets/..%2F..%2Fsecret.txt"):
            response = c.get(url)
            assert SECRET not in response.text, url


def test_no_frontend_without_dist(client: TestClient) -> None:
    assert client.get("/").status_code == 404
