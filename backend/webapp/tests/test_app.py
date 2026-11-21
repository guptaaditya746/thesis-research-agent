"""The app: health, the Host guard, the evqa routers mounted, and the built frontend with its index fallback."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from webapp.app import create_app
from webapp.settings import Settings


def client(dist: Path) -> TestClient:
    return TestClient(create_app(Settings(WEBAPP_DIST=str(dist))))  # type: ignore[call-arg]


def test_health_guard_and_routers(tmp_path: Path) -> None:
    c = client(tmp_path / "none")
    assert c.get("/api/health").json()["ok"] is True
    assert "medical" in c.get("/api/evqa/dataset").json()
    assert c.get("/api/health", headers={"Host": "evil.example"}).status_code == 400


def test_serves_the_frontend(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (tmp_path / "a.js").write_text("js", encoding="utf-8")
    c = client(tmp_path)
    assert c.get("/a.js").text == "js"
    assert c.get("/workbench").text == "<html>app</html>"
    assert c.get("/../pyproject.toml").text == "<html>app</html>"
    assert c.get("/api/nope").status_code == 404
