"""Card sets per question kind (evidence/propose/cards.yaml): the ids each kind offers, what the new cards write
into the protocol, and the flow from frame to a frozen protocol for every kind."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from evidence.propose import cards, frame
from evidence.propose.common import ProposalError
from evidence.protocol import parse

from .propose_support import QUESTION, RAG_FRAME, Scripted, flow

EFFECT_SET = ["screen", "roles", "metrics", "min_effect", "pairing", "label"]
ADVANCED = ["cascade", "locate"]
SETS = {"effect": EFFECT_SET, "consistency": [*EFFECT_SET, "claim_check"],
        "inventory": ["screen", "list_target", "same_names"],
        "best": ["screen", "best_metric", "method_kinds", "win_rule"]}


def _frame(kind: str) -> dict:
    return {**RAG_FRAME, "kind": kind, "kind_reason": "test"}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("kind", SETS)
def test_card_set_per_kind(kind: str) -> None:
    specs = cards.for_kind(kind)
    assert [c["id"] for c in specs] == [*SETS[kind], *ADVANCED]
    assert [c["id"] for c in specs if c["advanced"]] == ADVANCED
    assert all(kind in c["kinds"] for c in specs)


def _draft(tmp_path: Path, kind: str) -> tuple[dict, frame.Frame]:
    model = Scripted(frame_reply=_frame(kind))
    flow(tmp_path, model, until="draft")
    return yaml.safe_load((tmp_path / "draft.yaml").read_text(encoding="utf-8")), frame.load(tmp_path / "frame.json")


def test_method_kinds_card_writes_enum_and_kinds(tmp_path: Path) -> None:
    draft, f = _draft(tmp_path, "best")
    kinds = {"no-retrieval": ["closed-book model"], "rag": ["retrieval-augmented model", "RAG pipeline"]}
    p, _ = cards.apply(draft, [{"card": "method_kinds", "value": {"kinds": kinds}}], f)
    protocol = parse(yaml.safe_dump(p))
    assert {k: list(v) for k, v in protocol.best.kinds.items()} == kinds
    assert list(protocol.evidence_types["condition"].enum_of("kind")) == ["no-retrieval", "rag"]


def test_list_target_card_swaps_the_evidence_type(tmp_path: Path) -> None:
    draft, f = _draft(tmp_path, "inventory")
    p, _ = cards.apply(draft, [{"card": "list_target", "value": {"target": "dataset"}},
                               {"card": "same_names", "value": {"same": {"MMLU": ["Massive Multitask"]}}}], f)
    protocol = parse(yaml.safe_dump(p))
    assert protocol.inventory.target == "dataset" and list(protocol.evidence_types) == ["dataset"]
    assert {k: list(v) for k, v in protocol.inventory.same.items()} == {"MMLU": ["Massive Multitask"]}


def test_validate_rejects_card_of_other_kind(tmp_path: Path) -> None:
    flow(tmp_path, Scripted(frame_reply=_frame("effect")), until="cards")
    data = _json(tmp_path / "cards.json")
    assert [c["id"] for c in data["cards"]] == [*SETS["effect"], *ADVANCED]
    decisions = yaml.safe_load((tmp_path / "decisions.yaml").read_text(encoding="utf-8"))
    decisions["decisions"].append({"card": "claim_check", "choice": "draft", "reason": "x", "by": "model"})
    with pytest.raises(ProposalError, match="claim_check.*not a card of this proposal"):
        cards.validate(data["cards"], decisions)


@pytest.mark.parametrize("kind", SETS)
def test_every_kind_flows_to_a_frozen_protocol(tmp_path: Path, kind: str) -> None:
    flow(tmp_path / kind, Scripted(frame_reply=_frame(kind)))
    d = tmp_path / kind
    assert [c["id"] for c in _json(d / "cards.json")["cards"]] == [*SETS[kind], *ADVANCED]
    protocol = parse((d / "protocol.yaml").read_text(encoding="utf-8"))
    record = _json(d / "proposal.json")
    assert protocol.kind == kind and record["kind"] == kind and record["kind_by"] == "model"
    assert [x["card"] for x in record["decisions"]] == [*SETS[kind], *ADVANCED]
