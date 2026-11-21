"""/api/evqa dataset pane endpoints over the checked-in medical seed."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from webapp.evqa_api import router


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_dataset_pane_endpoints() -> None:
    c = client()
    assert "medical" in c.get("/api/evqa/dataset").json()
    o = c.get("/api/evqa/dataset/medical").json()
    assert o["papers"] and o["rows"] and o["check"]["pass"]
    files = c.get("/api/evqa/files").json()
    seed = next(f for f in files if f["path"].endswith("medical/seed.ttl"))
    assert "ex:Result" in c.get("/api/evqa/file", params={"path": seed["path"]}).json()["text"]


def test_refuses_unknown_things() -> None:
    c = client()
    assert c.get("/api/evqa/dataset/nope").status_code == 404
    assert c.get("/api/evqa/file", params={"path": "../pyproject.toml"}).status_code == 404
