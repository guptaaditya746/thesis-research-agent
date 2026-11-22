"""Shared fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperfactory import world

_PILOT = json.loads((Path(__file__).resolve().parents[1] / "worlds" / "law-pilot.json").read_text())
PILOT_FOCUS = [sorted({c[0] for c in p["claims"]}) for p in _PILOT["papers"].values()]


@pytest.fixture
def pilot_focus(monkeypatch):
    """Fake world models answer with the pilot papers: give each paper the pilot paper's subjects as its focus."""
    monkeypatch.setattr(world, "plan_focus", lambda w, f, seed, n: (PILOT_FOCUS * (n // len(PILOT_FOCUS) + 1))[:n])
