"""Safety: no path leaves its root, other hosts and other sites cannot write or rebind, the built frontend is
served safely."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.rundir import RunDir
from webapp.agenttrace import output_head, steps_of
from webapp.app import create_app
from webapp.files import NotFound, inside
from webapp.settings import Settings

SECRET = "top secret, outside every root"


@pytest.fixture(scope="module")
def ev(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An $EV with every directory and a secret file next to them that no request may read."""
    root = tmp_path_factory.mktemp("safety") / "ev"
    for d in ("corpora", "runs/cascade", "scores", "proposals", "cache/engine"):
        (root / d).mkdir(parents=True)
    (root / "secret.txt").write_text(SECRET, encoding="utf-8")
    (root / "runs" / "secret.txt").write_text(SECRET, encoding="utf-8")
    return root


@pytest.fixture(scope="module")
def client(ev: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(EV=ev, WEBAPP_DIST=ev / "no-dist"))) as c:  # type: ignore[call-arg]
        yield c


@pytest.mark.parametrize("url", [
    "/api/ev/runs/..%2Fsecret.txt",
    "/api/ev/runs/%2e%2e~secret.txt",
    "/api/ev/runs/cascade~..%2F..%2Fsecret.txt",
    "/api/ev/runs/..~secret.txt/graph",
    "/api/ev/runs/.jobs~x",
    "/api/ev/runs/a~b~c",
    "/api/ev/corpora/..%2Fsecret.txt",
    "/api/ev/corpora/%2e%2e",
    "/api/ev/corpora/x/papers/..%2F..%2Fsecret.txt",
    "/api/ev/protocols/..%2F..%2F..%2Fpyproject",
    "/api/ev/proposals/..%2Fsecret.txt",
    "/api/ev/scores/reports/..~secret.txt",
    "/api/ev/scores/compares/..%2F..",
    "/api/ev/questions/..%2Fsecret.txt",
    "/api/ev/jobs/..%2F..%2Fsecret",
    "/api/ev/jobs/%2e%2e/log",
    "/api/ev/jobs/.jobs/log",
])
def test_paths_outside_the_roots_are_refused(client: TestClient, url: str) -> None:
    response = client.get(url)
    assert response.status_code in (404, 422), (url, response.status_code)
    assert SECRET not in response.text


def test_inside() -> None:
    root = Path(__file__).resolve().parent
    assert inside(root, "conftest.py") == root / "conftest.py"
    for bad in ("../app.py", str(root.parent / "app.py"), "a/../../app.py", ".."):
        with pytest.raises(NotFound):
            inside(root, bad)


def test_a_record_cannot_point_outside_its_run(tmp_path: Path) -> None:
    """Output files named in an agent's events.jsonl are read only inside its run directory."""
    (tmp_path / "secret.txt").write_text(SECRET, encoding="utf-8")
    run = RunDir(tmp_path / "runs" / "r1")
    (tmp_path / "runs" / "r1").mkdir(parents=True)
    assert output_head(run, "../../secret.txt") is None
    record = {"task_id": "t000001", "subtype": "agent_tool", "step_id": 1, "agent_id": "main",
              "used": {"command": "ls"}, "generated": {"output_file": "../../secret.txt"}, "custom_metadata": {}}
    [step] = steps_of(run, [record])
    assert step.output_head is None


def test_other_sites_and_hosts_cannot_write_or_rebind(ev: Path) -> None:
    """A form POST from another site (no JSON, no preflight), a cross-origin JSON request and a request from a
    client that is not loopback are refused before any job starts; a Host that is not a loopback name (DNS
    rebinding) gets nothing at all."""
    body = {"name": "x", "seed": 1, "studies": 2, "levels": ["explicit"]}
    with TestClient(create_app(Settings(EV=ev))) as c:  # type: ignore[call-arg]
        form = {"content-type": "application/x-www-form-urlencoded", "origin": "https://evil.example"}
        assert c.post("/api/ev/jobs/synth", content=b"name=x", headers=form).status_code == 403
        assert c.post("/api/ev/jobs/synth", content=b"{}", headers={"content-type": "text/plain"}).status_code == 403
        assert c.post("/api/ev/jobs/x/cancel").status_code == 403
        cross = c.post("/api/ev/jobs/synth", json=body, headers={"origin": "https://evil.example"})
        assert cross.status_code == 403 and "cross-origin" in cross.json()["detail"]
        put = c.put("/api/ev/proposals/p/decisions", content=b"x", headers={"content-type": "text/plain"})
        assert put.status_code == 403
        assert c.get("/api/ev/jobs").json() == []  # nothing was queued
        assert c.get("/api/health", headers={"host": "attacker.example:8080"}).status_code == 400
        assert c.get("/api/health", headers={"host": "127.0.0.1:8080"}).status_code == 200
        assert c.get("/api/health", headers={"host": "[::1]:8080"}).status_code == 200
    with TestClient(create_app(Settings(EV=ev)), client=("192.0.2.7", 40000)) as remote:  # type: ignore[call-arg]
        assert remote.get("/api/ev/jobs").status_code == 200       # reading is the Host rule's business
        refused = remote.post("/api/ev/jobs/synth", json=body, headers={"host": "127.0.0.1:8080"})
        assert refused.status_code == 403 and "192.0.2.7" in refused.json()["detail"]
        assert remote.get("/api/ev/jobs").json() == []
    with TestClient(create_app(Settings(EV=ev, WEBAPP_WRITE_CLIENTS="127.0.0.1")),  # type: ignore[call-arg]
                    client=("127.0.0.1", 40000)) as local:
        same = local.post("/api/ev/jobs/synth", json={**body, "studies": 0},
                          headers={"host": "127.0.0.1:8080", "origin": "http://127.0.0.1:8080"})
        assert same.status_code == 422  # the app's own page from loopback reaches the endpoint (and its validation)


def test_frontend_is_served_with_a_fallback(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>app</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text(SECRET, encoding="utf-8")
    with TestClient(create_app(Settings(WEBAPP_DIST=dist))) as c:  # type: ignore[call-arg]
        assert c.get("/").text.startswith("<!doctype html>")
        assert c.get("/flow/rag-factuality/run").text.startswith("<!doctype html>")  # a client-side route
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/api/nope").status_code == 404 and c.get("/api/nope").json()["detail"]
        assert c.get("/api/health").json()["ok"] is True
        for url in ("/..%2Fsecret.txt", "/%2e%2e/secret.txt", "/assets/..%2F..%2Fsecret.txt"):
            response = c.get(url)
            assert SECRET not in response.text, url


def test_no_frontend_without_dist(client: TestClient) -> None:
    assert client.get("/").status_code == 404
