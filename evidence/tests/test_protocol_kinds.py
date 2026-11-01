"""Protocol kinds (effect, inventory, consistency, best) and the dataset evidence type."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from evidence import protocol
from evidence.contract import Item, Span
from evidence.pack import protocol_path

REPO = Path(__file__).resolve().parents[2]
RAG_FACTUALITY_SHA = json.loads(
    (REPO / "tests/EV2/corpora/rag-claude-s1-mixed/ground_truth.json").read_text(encoding="utf-8"))["protocol"]["sha256"]

SYNTHESIS: dict[str, Any] = {
    "compare": {"treatment": "rag", "control": "baseline"},
    "metrics": [{"canonical": "accuracy", "higher_is_better": True}],
    "min_effect": 0.01,
    "claim_map": {"improves": "supports", "worsens": "contradicts"},
    "label": [{"then": "mixed"}],
}


def _type(fields: dict[str, Any], role: str) -> dict[str, Any]:
    return {"fields": {"type": "object", "properties": fields}, "roles": [role],
            "extractors": [{"name": "regex_x"}]}


def minimal_yaml(kind: str = "effect", omit: str | None = None, target: str = "metric",
                 types: list[str] | None = None, kinds: dict[str, list[str]] | None = None,
                 condition_kind_enum: list[str] | None = None) -> str:
    types = types or ["condition", "metric", "author_claim"]
    cond_fields: dict[str, Any] = {"label": {"type": "string"}, "role": {"type": "string", "enum": ["rag", "baseline"]}}
    if condition_kind_enum:
        cond_fields["kind"] = {"type": "string", "enum": condition_kind_enum}
    specs = {"condition": _type(cond_fields, "condition_label"),
             "metric": _type({"canonical": {"type": "string", "enum": ["accuracy"]}}, "metric_label"),
             "author_claim": _type({"direction": {"type": "string", "enum": ["improves", "worsens"]}}, "claim"),
             "dataset": _type({"name": {"type": "string"}}, "dataset_name")}
    blocks: dict[str, Any] = {"synthesis": SYNTHESIS,
                              "inventory": {"target": target},
                              "best": {"metric": {"canonical": "accuracy", "higher_is_better": True},
                                       "kinds": kinds or {"rag": ["RAG"], "baseline": ["LLM"]}},
                              "consistency": {"by": "direction"}}
    wanted = {"effect": ["synthesis"], "inventory": ["inventory"], "consistency": ["synthesis", "consistency"],
              "best": ["best"]}[kind]
    doc: dict[str, Any] = {"id": "t", "version": 2, "question": "q?", "kind": kind,
                           "evidence_types": {t: specs[t] for t in types}}
    doc.update({b: blocks[b] for b in wanted if b != omit})
    return yaml.safe_dump(doc)


def test_existing_protocol_hash_unchanged() -> None:
    p = protocol.load(protocol_path("rag", "rag-factuality"))
    assert p.kind == "effect"
    assert p.sha256 == RAG_FACTUALITY_SHA


def test_each_kind_parses_with_its_block() -> None:
    for kind in ("effect", "consistency"):
        assert protocol.parse(minimal_yaml(kind=kind)).kind == kind
    assert protocol.parse(minimal_yaml(kind="inventory")).inventory.target == "metric"
    p = protocol.parse(minimal_yaml(kind="best", kinds={"rag": ["RAG"], "baseline": ["LLM"]},
                                    condition_kind_enum=["rag", "baseline"]))
    assert p.best.kinds["rag"] == ("RAG",)


def test_kind_needs_its_block() -> None:
    for kind, block in [("effect", "synthesis"), ("consistency", "synthesis"), ("inventory", "inventory"),
                        ("best", "best")]:
        with pytest.raises(ValidationError, match=block):
            protocol.parse(minimal_yaml(kind=kind, omit=block))


def test_consistency_needs_its_block_and_an_author_claim_type() -> None:
    with pytest.raises(ValidationError, match="consistency"):
        protocol.parse(minimal_yaml(kind="consistency", omit="consistency"))
    with pytest.raises(ValidationError, match="author_claim"):
        protocol.parse(minimal_yaml(kind="consistency", types=["condition", "metric"]))


def test_inventory_target_must_be_a_declared_type() -> None:
    with pytest.raises(ValidationError, match="inventory.target"):
        protocol.parse(minimal_yaml(kind="inventory", target="dataset", types=["metric"]))


def test_inventory_over_datasets_parses() -> None:
    p = protocol.parse(minimal_yaml(kind="inventory", target="dataset", types=["dataset"]))
    assert p.inventory.target == "dataset" and p.synthesis is None


def test_best_kinds_must_match_condition_kind_enum() -> None:
    with pytest.raises(ValidationError, match="best.kinds"):
        protocol.parse(minimal_yaml(kind="best", kinds={"rag": ["RAG"]}, condition_kind_enum=["rag", "baseline"]))


def test_new_fields_at_default_do_not_change_the_digest() -> None:
    p = protocol.parse(minimal_yaml())
    q = p.model_copy(update={"kind": "effect"})
    assert q.sha256 == p.sha256
    assert "kind" not in yaml.safe_load(minimal_yaml())["evidence_types"]
    assert protocol.parse(minimal_yaml(kind="inventory")).sha256 != p.sha256


def test_dataset_item_prefix() -> None:
    span = Span(role="dataset_name", selector={"file": "a.md", "start": 0, "end": 5, "exact": "TriviaCheck"})
    assert Item.build("dataset", {"name": "TriviaCheck"}, [span]).item_id.startswith("d")


def test_foreign_kind_block_is_rejected() -> None:
    """A block that belongs to another kind (an inventory block on an effect protocol) is a mistake, not ignored."""
    for kind, foreign in [("effect", "inventory"), ("effect", "consistency"), ("inventory", "synthesis"),
                          ("best", "inventory"), ("consistency", "best")]:
        data = yaml.safe_load(minimal_yaml(kind=kind, condition_kind_enum=["rag", "baseline"]))
        data[foreign] = {"synthesis": SYNTHESIS, "inventory": {"target": "metric"}, "consistency": {"by": "direction"},
                         "best": {"metric": {"canonical": "accuracy", "higher_is_better": True},
                                  "kinds": {"rag": ["RAG"], "baseline": ["LLM"]}}}[foreign]
        with pytest.raises(ValidationError, match=f"kind {kind!r} may not have a {foreign} block"):
            protocol.Protocol.model_validate(data)
