"""Amendments of a frozen protocol (docs/evidence-system.md Part E): the revision goes up by one, the line
records the previous protocol's sha256, the reason and the changed keys; no reason or no change is refused."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence import cli
from evidence.propose import amend
from evidence.propose.common import ProposalError
from evidence.protocol import load

from .propose_support import Scripted, flow


@pytest.fixture
def frozen(tmp_path: Path) -> Path:
    return flow(tmp_path / "p", Scripted())


def rewrite(d: Path, old: str, new: str) -> None:
    path = d / "protocol.yaml"
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def lines(d: Path) -> list[dict]:
    return [json.loads(x) for x in (d / "amendments.jsonl").read_text(encoding="utf-8").splitlines()]


def test_amendment_bumps_the_revision_and_records_the_change(frozen: Path) -> None:
    first = load(frozen / "protocol.yaml")
    proposal = json.loads((frozen / "proposal.json").read_text(encoding="utf-8"))
    assert proposal["protocol"]["sha256"] == first.sha256 and first.revision == 1
    rewrite(frozen, "min_effect: 0.01", "min_effect: 0.02")
    entry = amend.run(frozen, "the benchmark's smallest planted effect is 0.02", before_main_run=True,
                      at="2026-10-17T13:00:00+00:00")
    second = load(frozen / "protocol.yaml")
    assert second.revision == 2 and second.version == 2 and second.synthesis.min_effect == 0.02
    assert entry == {"revision": 2, "sha256": second.sha256, "amends_sha256": first.sha256,
                     "reason": "the benchmark's smallest planted effect is 0.02", "impact": ["synthesis.min_effect"],
                     "before_main_run": True, "at": "2026-10-17T13:00:00+00:00"}
    assert lines(frozen) == [entry]
    assert load(frozen / "protocol.v2.yaml").sha256 == second.sha256
    assert load(frozen / "protocol.v1.yaml").sha256 == first.sha256          # the base stays as it was

    rewrite(frozen, "on_fail: skip", "on_fail: extract_anyway")
    path = frozen / "protocol.yaml"
    path.write_text("".join(x for x in path.read_text(encoding="utf-8").splitlines(keepends=True)
                            if x.strip() != "- name: llm_author_claim"), encoding="utf-8")
    third = amend.run(frozen, "screen recall first; the claim needs no model")
    assert third["revision"] == 3 and third["amends_sha256"] == second.sha256 and third["before_main_run"] is False
    assert third["impact"] == ["evidence_types.author_claim.extractors", "screen.on_fail"]   # the protocol's key order
    assert [x["revision"] for x in lines(frozen)] == [2, 3]


def test_amendment_without_a_reason_or_a_change_is_refused(frozen: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(ProposalError, match="nothing to amend"):
        amend.run(frozen, "no edit made")
    rewrite(frozen, "min_effect: 0.01", "min_effect: 0.02")
    with pytest.raises(ProposalError, match="needs a reason"):
        amend.run(frozen, "  ")
    assert not (frozen / "amendments.jsonl").exists() and load(frozen / "protocol.yaml").revision == 1
    assert cli.main(["propose", "amend", str(frozen), "--reason", ""]) == 2
    assert cli.main(["propose", "amend", str(frozen), "--reason", "smaller effects count", "--before-main-run"]) == 0
    assert json.loads(capsys.readouterr().out)["impact"] == ["synthesis.min_effect"]
    assert cli.main(["propose", "amend", str(frozen), "--reason", "again"]) == 2   # protocol.yaml is revision 2 now


def test_a_broken_edit_is_refused(frozen: Path) -> None:
    rewrite(frozen, "min_effect: 0.01", "min_effect: -1")
    with pytest.raises(ProposalError, match="does not validate"):
        amend.run(frozen, "typo")


def test_a_revision_line_is_added_when_the_person_removed_it(frozen: Path) -> None:
    rewrite(frozen, "revision: 1\n", "")
    rewrite(frozen, "min_effect: 0.01", "min_effect: 0.02")
    assert amend.run(frozen, "smaller")["revision"] == 2
    assert load(frozen / "protocol.yaml").revision == 2


def test_changes_walks_keys_and_compares_lists_whole() -> None:
    old = {"a": {"b": 1, "c": [1, 2]}, "d": 1}
    new = {"a": {"b": 2, "c": [2, 1], "e": 0}}
    assert amend.changes(old, new) == ["a.b", "a.c", "a.e", "d"]
    assert amend.changes(old, old) == []
