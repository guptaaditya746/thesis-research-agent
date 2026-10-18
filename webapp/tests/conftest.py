from __future__ import annotations

import os

import pytest

from .evidence_world import EvidenceWorld, build

# Starlette's TestClient sends Host: testserver from the client address "testclient"; the app answers loopback
# names only and takes writes from loopback clients only (webapp/guard.py), so the tests add both.
os.environ.setdefault("WEBAPP_ALLOWED_HOSTS", "127.0.0.1,localhost,::1,testserver")
os.environ.setdefault("WEBAPP_WRITE_CLIENTS", "127.0.0.1,::1,testclient")


@pytest.fixture(scope="session")
def ev_world(tmp_path_factory: pytest.TempPathFactory) -> EvidenceWorld:
    """The evidence-level world made by the real tools with scripted models (evidence_world.py), built once;
    tests that change it take a copy."""
    return build(tmp_path_factory.mktemp("ev") / "world")
