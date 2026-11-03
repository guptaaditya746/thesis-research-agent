"""Evidence types are open: a pack declares its types and their item prefixes, and the contract takes them once
they are registered. `pack check` names a role a question kind needs when no type of the pack has it."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from evidence import contract, pack as pack_module
from evidence.cli import main
from evidence.contract import Item, Span
from evidence.pack import DOMAINS, Pack, PackError, Role, RoleMap, check, load_pack, register_pack
from evidence.protocol import parse

SPAN = Span(role="condition_label", selector={"file": "p.md", "start": 0, "end": 3})
RAG_TYPES = yaml.safe_load((DOMAINS / "rag" / "pack.yaml").read_text(encoding="utf-8"))["types"]
EFFECT = (DOMAINS / "rag" / "protocols" / "rag-factuality.yaml").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _registry():
    """Each test leaves the type registry as it found it."""
    before = dict(contract.ITEM_PREFIX)
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


def toy_pack(tmp_path: Path, types: dict[str, tuple[str, str]] | None = None, drop_role: str | None = None,
             name: str = "toy") -> Pack:
    """The rag pack copied to `tmp_path/<name>`, with `types` ({name: (prefix, role)}) instead of its own, or
    without the types of role `drop_role`."""
    folder = tmp_path / name
    shutil.copytree(DOMAINS / "rag", folder)
    head: dict[str, Any] = yaml.safe_load((folder / "pack.yaml").read_text(encoding="utf-8"))
    head["name"] = name
    if types is not None:
        head["types"] = {t: {"prefix": p, "role": r} for t, (p, r) in types.items()}
    if drop_role is not None:
        head["types"] = {t: d for t, d in head["types"].items() if d["role"] != drop_role}
    (folder / "pack.yaml").write_text(yaml.safe_dump(head), encoding="utf-8")
    return load_pack(name, root=tmp_path)


def test_pack_type_registers_with_its_prefix(tmp_path):
    pack = toy_pack(tmp_path, types={"arm": ("z", "compared_thing")})
    register_pack(pack)
    assert contract.ITEM_PREFIX["arm"] == "z"


def test_existing_type_ids_keep_their_prefix():
    item = Item.build("condition", {"label": "RAG", "role": "rag"}, spans=[SPAN])
    assert item.item_id.startswith("c-")
    assert {t: contract.ITEM_PREFIX[t] for t in RAG_TYPES} == {t: d["prefix"] for t, d in RAG_TYPES.items()}


def test_prefix_clash_is_refused(tmp_path):
    with pytest.raises(PackError, match="prefix 'c'"):
        register_pack(toy_pack(tmp_path, types={"arm": ("c", "compared_thing")}))


def test_pack_check_names_missing_role(tmp_path):
    pack = toy_pack(tmp_path, drop_role="metric")
    with pytest.raises(PackError, match="no type has role 'metric'.*kind 'effect'"):
        check(pack, kinds=["effect"])


def test_an_inventory_needs_no_value_or_claim_types(tmp_path):
    pack = toy_pack(tmp_path, types={"method": ("z", "compared_thing"), "task": ("t", "context")})
    check(pack, kinds=["inventory"])
    no_claims = toy_pack(tmp_path, drop_role="author_claim", name="noclaims")
    check(no_claims, kinds=["effect", "best"])
    with pytest.raises(PackError, match="pack 'noclaims': no type has role 'author_claim' \\(needed by kind 'consistency'\\)"):
        check(no_claims, kinds=["consistency"])


def test_a_registered_pack_type_makes_items_and_an_unregistered_one_is_refused(tmp_path):
    register_pack(toy_pack(tmp_path, types={"arm": ("z", "compared_thing")}))
    assert Item.build("arm", {"name": "drug A"}, [SPAN]).item_id.startswith("z-")
    with pytest.raises(ValueError, match="not registered"):
        Item.build("limb", {"name": "drug A"}, [SPAN])


def test_role_map_finds_types_and_fields_by_role():
    roles = RoleMap(load_pack("rag"))
    assert roles.type_of(Role.COMPARED_THING) == "condition"
    assert roles.field("condition", "side") == "role"
    assert roles.field("metric", "canonical") == "canonical"
    assert roles.field("author_claim", "direction") == "direction"
    assert roles.types_of(Role.CONTEXT) == ["dataset"]


def test_role_map_names_a_missing_role(tmp_path):
    with pytest.raises(PackError, match="pack 'toy': no type has role 'author_claim'"):
        RoleMap(toy_pack(tmp_path, drop_role="author_claim")).type_of(Role.CLAIM)


def test_a_protocol_naming_a_type_its_pack_lacks_is_refused():
    with pytest.raises(ValueError, match="'widget'.*pack 'rag'"):
        parse(EFFECT.replace("\n  condition:", "\n  widget:", 1))


def test_a_protocol_whose_pack_lacks_a_role_fails_at_load(tmp_path, monkeypatch):
    toy_pack(tmp_path, drop_role="metric")
    monkeypatch.setattr(pack_module, "DOMAINS", tmp_path)
    text = yaml.safe_load(EFFECT)
    text["domain"] = "toy"
    with pytest.raises(ValueError, match="pack 'toy': no type has role 'metric' \\(needed by kind 'effect'\\)"):
        parse(yaml.safe_dump(text))


def test_pack_check_command_passes_rag_and_fails_a_pack_without_a_needed_role(tmp_path, monkeypatch, capsys):
    assert main(["pack", "check", "rag"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pack"] == "rag" and set(out["kinds"]) == {"effect", "inventory", "consistency", "best"}
    toy_pack(tmp_path, drop_role="measured_value")
    monkeypatch.setattr(pack_module, "DOMAINS", tmp_path)
    assert main(["pack", "check", "toy"]) == 2
    assert "no type has role 'measured_value'" in capsys.readouterr().err


def test_the_agentic_brief_takes_a_pack_type_it_does_not_know():
    from evidence.agentic.convert import ITEM_ID, span_role
    from evidence.agentic.task import what
    assert span_role("arm", "name") == "context" and span_role("condition", "label") == "condition_label"
    assert what("study_arm") == "one study arm the paper states"
    assert ITEM_ID.match("x-0123456789abcdef")


def test_pack_check_validates_every_protocol_file_and_prints_both_counts(tmp_path, monkeypatch, capsys):
    from evidence import questions
    assert main(["pack", "check", "rag"]) == 0
    out = json.loads(capsys.readouterr().out)
    qfile = DOMAINS / "rag" / "questions.yaml"
    named = {questions.protocol_file(f, qfile) for q in questions.load(qfile)
             for f in (q.protocol, q.agentic_protocol) if f}
    assert out["protocols"] == len(list((DOMAINS / "rag" / "protocols").glob("*.yaml")))
    assert out["question_protocols"] == len(named)
    shutil.copytree(DOMAINS / "rag", tmp_path / "rag")
    (tmp_path / "rag" / "protocols" / "unasked.yaml").write_text(EFFECT.replace("\n  condition:", "\n  widget:", 1),
                                                                 encoding="utf-8")
    monkeypatch.setattr(pack_module, "DOMAINS", tmp_path)
    assert main(["pack", "check", "rag"]) == 2
    assert "unasked.yaml" in capsys.readouterr().err


def test_a_role_with_several_types_is_an_error_not_a_silent_default(tmp_path):
    from evidence.extractors.base import Slots
    pack = toy_pack(tmp_path, types={"arm": ("xa", "compared_thing"), "drug": ("xd", "compared_thing"),
                                     "outcome": ("xo", "metric"), "result": ("xr", "measured_value")})
    given = pack.extractor_config("result", "regex_measurement")
    assert given["types"]["compared_thing"] == ["arm", "drug"] and given["types"]["metric"] == "outcome"
    with pytest.raises(ValueError, match="several types of role 'compared_thing'.*\['arm', 'drug'\]"):
        Slots.of(given)
    # the measured-value type's links name one of them: that one is the compared thing
    slots = Slots.of({**given, "links": {"arm": "arm", "outcome": "outcome"}})
    assert (slots.thing, slots.metric, slots.to_thing, slots.to_metric) == ("arm", "outcome", "arm", "outcome")
