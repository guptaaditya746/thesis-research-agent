"""The write contract the frontend's mock is checked against (frontend/src/mocks/contract.test.ts) is what the
backend answers today (write_contract.py)."""
from __future__ import annotations

import json
from pathlib import Path

from .evidence_world import EvidenceWorld
from .write_contract import CONTRACT, SCENARIOS, record

REGENERATE = ("regenerate: uv run python -m webapp.tests.evidence_world <tmp> --mocks "
              "frontend/src/mocks/ev-fixtures.json")


def test_recorded_contract_is_current(ev_world: EvidenceWorld, tmp_path: Path) -> None:
    recorded = record(ev_world.copy(tmp_path / "world"))
    on_file = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert [s["name"] for s in on_file] == [s["name"] for s in SCENARIOS], REGENERATE
    for fresh, kept in zip(recorded, on_file, strict=True):
        assert fresh == kept, f"{fresh['name']}: the backend answers otherwise; {REGENERATE}"


def test_scenarios_cover_the_rules_the_mock_keeps() -> None:
    """Accepted and refused writes both: the statuses the brief asks for, in order."""
    on_file = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert [s["status"] for s in on_file] == [202, 409, 202, 409, 404, 409, 409, 202, 200, 409, 202, 409, 202, 409]
    assert len(on_file[8]["response"]["problems"]) == 4
