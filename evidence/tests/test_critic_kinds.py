"""The checker per kind: serious and advisory checks, and the four kind checks (critic.py)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from evidence.propose import cards, critic, frame
from evidence.propose.cards import ProposalError

from .propose_support import RAG_FRAME, Scripted, flow


def _checks(tmp_path: Path, kind: str, edit=None) -> dict[str, dict]:
    flow(tmp_path, Scripted(frame_reply={**RAG_FRAME, "kind": kind, "kind_reason": "test"}), until="draft")
    data = yaml.safe_load((tmp_path / "draft.yaml").read_text(encoding="utf-8"))
    if edit:
        edit(data)
    found = critic.checks(yaml.safe_dump(data), frame.load(tmp_path / "frame.json"))
    return {c["id"]: c for c in found}


def _kinds(data: dict, kinds: dict) -> None:
    data["best"]["kinds"] = kinds
    data["evidence_types"]["condition"]["fields"]["properties"]["kind"]["enum"] = list(kinds)


def test_best_kinds_disjoint_serious(tmp_path: Path) -> None:
    found = _checks(tmp_path, "best", lambda d: _kinds(d, {"a": ["x", "y"], "b": ["y"]}))
    c = found["best_kinds_disjoint"]
    assert not c["ok"] and c["severity"] == "serious" and "y" in c["message"]
    assert found["best_kinds_nonempty"]["ok"]


def test_best_kinds_nonempty_serious(tmp_path: Path) -> None:
    found = _checks(tmp_path, "best", lambda d: _kinds(d, {"a": ["x"], "b": []}))
    assert not found["best_kinds_nonempty"]["ok"] and found["best_kinds_nonempty"]["severity"] == "serious"


def test_kind_checks_pass_on_the_templates_and_are_not_applicable_elsewhere(tmp_path: Path) -> None:
    best = _checks(tmp_path / "b", "best")
    assert best["best_kinds_disjoint"]["ok"] and best["best_kinds_nonempty"]["ok"]
    assert "not applicable" in best["claim_type_present"]["message"]
    inv = _checks(tmp_path / "i", "inventory")
    assert inv["inventory_target_declared"]["ok"] and "not applicable" in inv["best_kinds_disjoint"]["message"]
    cons = _checks(tmp_path / "c", "consistency")
    assert cons["claim_type_present"]["ok"]


def test_claim_type_missing_is_serious(tmp_path: Path) -> None:
    found = _checks(tmp_path, "consistency", lambda d: d["evidence_types"].pop("author_claim"))
    assert not found["claim_type_present"]["ok"] and found["claim_type_present"]["severity"] == "serious"


def test_inventory_target_undeclared_is_serious(tmp_path: Path) -> None:
    found = _checks(tmp_path, "inventory", lambda d: d["inventory"].update(target="dataset"))
    assert not found["inventory_target_declared"]["ok"] and found["inventory_target_declared"]["severity"] == "serious"


def test_old_blocking_severity_still_counts() -> None:
    old = [{"id": "x", "ok": False, "severity": "blocking"}, {"id": "y", "ok": False, "severity": "advisory"}]
    assert [c["id"] for c in critic.serious_failures(old)] == ["x"]


def test_waiver_needs_reason() -> None:
    ok = {"check": "metric_rules_collide", "reason": "known and harmless here", "by": "aditya"}
    assert cards.waivers({"waivers": [ok]})[0]["reason"] == "known and harmless here"
    with pytest.raises(ProposalError, match="at least 10"):
        cards.waivers({"waivers": [{**ok, "reason": "ok fine"}]})
