from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from webapp.app import create_app

from .world import World, build_world


@pytest.fixture(scope="session")
def template(tmp_path_factory: pytest.TempPathFactory) -> World:
    """The world, built once; tests get copies."""
    return build_world(tmp_path_factory.mktemp("template"))


@pytest.fixture(scope="module")
def world(template: World, tmp_path_factory: pytest.TempPathFactory) -> World:
    """One world per test module, for tests that only read."""
    return template.copy(tmp_path_factory.mktemp("module") / "world")


@pytest.fixture(scope="module")
def client(world: World) -> Iterator[TestClient]:
    with TestClient(create_app(world.settings)) as c:
        yield c


@pytest.fixture
def fresh(template: World, tmp_path: Path) -> World:
    """A world of its own, for tests that change it (picks, jobs)."""
    return template.copy(tmp_path / "world")
