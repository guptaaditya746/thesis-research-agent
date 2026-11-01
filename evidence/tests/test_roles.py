"""Kinds and synthesis address evidence types by their pack role (pack.RoleMap), never by name: a pack whose types
are called arm, outcome, result and conclusion gives the same answer as rag, an inventory lists any type the pack
names, and no kind module or synthesis.py names a rag type."""
from __future__ import annotations

import inspect
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from evidence import contract, engine, questions, synthesis
from evidence.contract import Item, Span
from evidence.kinds import MODULES
from evidence.pack import DOMAINS, PackError, Role, RoleMap, load_pack
from evidence.protocol import load, parse

from .conftest import DOCS, PAPERS, regex_run

HERE = Path(__file__).resolve().parent
RENAMED_DOMAINS = HERE / "fixtures" / "renamed"
RENAMED_PROTOCOL = RENAMED_DOMAINS / "rag-renamed" / "protocols" / "rag-factuality-funnel.yaml"
FUNNEL = DOMAINS / "rag" / "protocols" / "rag-factuality-funnel.yaml"
INV_DATASETS = FUNNEL.parent / "inv-datasets.yaml"
TEXTS = {doc: (PAPERS / f"{doc}.md").read_text(encoding="utf-8") for doc in DOCS}
KIND_MODULES = list(MODULES.values())


@pytest.fixture(autouse=True)
def _registry():
    """Each test leaves the type registry as it found it (the renamed pack registers arm, outcome, ...)."""
    before = dict(contract.ITEM_PREFIX)
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


def answer_of(out: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    return out[0]


def shape(answer: dict[str, Any]) -> dict[str, Any]:
    """The answer without item ids (they hash the type name, so they differ between the packs)."""
    studies = [{k: s[k] for k in ("document", "direction", "delta", "metric", "reason", "flags", "duplicate_of")}
               | {side: s[side] and s[side]["value"] for side in ("treatment", "control")}
               | {"claim": s["author_claim"] and s["author_claim"]["direction"]} for s in answer["studies"]]
    return {"label": answer["label"], "counts": answer["counts"], "studies": studies}


def inventory_protocol(tmp: Path, target: str, source: Path = INV_DATASETS) -> Path:
    """`source` as an inventory of `target` (its other kind blocks dropped)."""
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    data.pop("synthesis", None)
    data.update(id="inv-test", kind="inventory", inventory={"target": target})
    path = tmp / "inventory.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_effect_answer_is_the_same_with_renamed_types(tmp_path):
    a = regex_run(TEXTS, tmp_path / "a", FUNNEL)
    b = regex_run(TEXTS, tmp_path / "b", RENAMED_PROTOCOL, domains=RENAMED_DOMAINS)
    assert answer_of(a)["label"] == answer_of(b)["label"] != "insufficient"
    assert shape(answer_of(a)) == shape(answer_of(b))
    assert {i["evidence_type"] for i in b[1].values()} == {"arm", "outcome", "result", "conclusion"}


def test_inventory_lists_any_declared_type(tmp_path):
    out = regex_run(TEXTS, tmp_path, inventory_protocol(tmp_path, "dataset"))
    assert {"TriviaQA"} <= {e["name"] for e in answer_of(out)["entries"]}
    renamed = inventory_protocol(tmp_path, "outcome", RENAMED_PROTOCOL)
    out = regex_run(TEXTS, tmp_path / "renamed", renamed, domains=RENAMED_DOMAINS)
    assert answer_of(out)["target"] == "outcome" and answer_of(out)["entries"]


def test_inventory_target_must_be_a_declared_type_with_a_name(tmp_path):
    with pytest.raises(ValueError, match="inventory.target 'author_claim'"):
        load(inventory_protocol(tmp_path, "author_claim", FUNNEL))


def test_no_kind_module_names_a_rag_type():
    for mod in KIND_MODULES + [synthesis]:
        src = inspect.getsource(mod)
        assert '"condition"' not in src and '"measurement"' not in src, mod.__name__


def test_kind_field_comes_from_the_pack():
    roles = RoleMap(load_pack("rag"))
    assert roles.field("condition", "kind") == "kind"
    with pytest.raises(PackError, match="declares no kind_field"):
        roles.field("metric", "kind")


def test_renamed_protocol_needs_its_domains_root():
    text = RENAMED_PROTOCOL.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="rag-renamed"):
        parse(text)
    assert parse(text, domains=RENAMED_DOMAINS).roles().types_of(Role.COMPARED_THING) == ["arm"]


def test_focus_for_reads_the_renamed_types():
    p = parse(RENAMED_PROTOCOL.read_text(encoding="utf-8"), domains=RENAMED_DOMAINS)
    span = Span(role="condition_label", selector={"file": "p.md", "start": 0, "end": 3})
    arm = Item.build("arm", {"label": "RAG", "role": "rag"}, [span])
    acc = Item.build("outcome", {"name": "accuracy", "canonical": "factual_accuracy", "higher_is_better": True}, [span])
    focus = engine.focus_for("no_control_condition", p, {"arm": [arm], "outcome": [acc]})
    assert focus.have == {"roles": ["rag"], "metrics": ["factual_accuracy"]}


def test_question_target_is_a_type_of_the_pack(tmp_path):
    folder = tmp_path / "rag-renamed"
    shutil.copytree(RENAMED_DOMAINS / "rag-renamed", folder)
    entry = {"id": "inv", "question": "Which arms?", "kind": "inventory", "truth": {"target": "arm"}}
    (folder / "questions.yaml").write_text(yaml.safe_dump({"questions": [entry]}), encoding="utf-8")
    assert questions.load(folder / "questions.yaml")[0].truth.target == "arm"
    entry["truth"]["target"] = "condition"
    (folder / "questions.yaml").write_text(yaml.safe_dump({"questions": [entry]}), encoding="utf-8")
    with pytest.raises(ValueError, match="inv: condition"):
        questions.load(folder / "questions.yaml")
