from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from webapp.cli import main


def test_openapi_prints_the_schema(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert main(["openapi"]) == 0
    schema = json.loads(capsys.readouterr().out)
    paths = set(schema["paths"])
    assert {"/api/health", "/api/evqa/dataset", "/api/evqa/runs", "/api/evqa/questions/{domain}",
            "/api/evqa/papers/{domain}"} <= paths
    assert not any(p.startswith("/api/ev/") for p in paths)
    assert main(["openapi", "-o", str(tmp_path / "openapi.json")]) == 0
    assert json.loads((tmp_path / "openapi.json").read_text(encoding="utf-8")) == schema


def test_serve_binds_to_localhost_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: seen.update(app=app, **kw))
    assert main(["serve"]) == 0
    assert (seen["app"], seen["factory"], seen["host"], seen["port"], seen["reload"]) == \
        ("webapp.app:create_app", True, "127.0.0.1", 8080, False)
    main(["serve", "--port", "9000", "--reload"])
    assert seen["port"] == 9000 and seen["reload"] is True and seen["reload_dirs"][0].endswith("webapp")
