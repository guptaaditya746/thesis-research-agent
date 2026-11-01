"""The generator recipe format: the rag recipe holds the old vocabulary, and the two rules of a recipe are checked."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from evidence.pack import DOMAINS
from jsonio import sha256_hex
from synth.recipe import load_recipe


def rag_recipe_copy(root: Path, *, intro_extra: str | None = None, other_label: str | None = None) -> Path:
    """A copy of domains/rag/generator.yaml under `root/rag/`, with one sentence or one name changed."""
    data = yaml.safe_load((DOMAINS / "rag" / "generator.yaml").read_text(encoding="utf-8"))
    if intro_extra:
        data["text"]["intro"].append(intro_extra)
    if other_label:
        data["others"][0]["label"] = other_label
    path = root / "rag" / "generator.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_rag_recipe_holds_the_old_vocabulary():
    r = load_recipe("rag")
    assert r.sides["baseline"].names[0].label == "closed-book model"
    assert r.sides["rag"].names[0].code == "R" and r.contexts[0] == "OpenFactQA"
    assert r.question_metrics[0].pair_range == (0.35, 0.80) and r.effects["large"] == (0.30, 0.45)
    assert r.reporting.count_base == 1000 and r.network is None


def test_rag_recipe_counts_match_vocab():
    r = load_recipe("rag")
    assert [len(s.names) for s in r.sides.values()] == [4, 4] and len(r.others) == 6 and len(r.contexts) == 10
    assert r.other_codes == ["A1", "A2"] and r.effect_protocol == "rag-factuality"
    assert [m.canonical for m in r.other_metrics] == ["bleu", "rouge_l", "latency"]
    assert r.other_metrics[2].unit == "seconds" and r.other_metrics[2].range == (0.40, 3.50)
    assert set(r.text.claims) == {"improves", "no_effect", "worsens"} and set(r.text.irrelevant) == {"survey", "other"}
    assert "<<" not in r.text.blind_examples and r.reporting.allowed_numbers == [r"\b1,000 questions\b"]


def test_recipe_digit_rule_is_checked(tmp_path):
    rag_recipe_copy(tmp_path, intro_extra="We used 3 runs.")
    with pytest.raises(ValueError, match="digit"):
        load_recipe("rag", root=tmp_path)


def test_recipe_names_must_not_clash(tmp_path):
    rag_recipe_copy(tmp_path, other_label="closed-book model plus")
    with pytest.raises(ValueError, match="clash"):
        load_recipe("rag", root=tmp_path)


def test_unchanged_copy_loads_with_the_same_sha256(tmp_path):
    path = rag_recipe_copy(tmp_path)
    assert load_recipe("rag", root=tmp_path).sha256 == sha256_hex(path.read_bytes().replace(b"\r\n", b"\n"))


def test_sha256_ignores_line_endings(tmp_path):
    path = rag_recipe_copy(tmp_path)
    lf = load_recipe("rag", root=tmp_path).sha256
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))   # CRLF, whatever the OS wrote
    assert load_recipe("rag", root=tmp_path).sha256 == lf


def test_missing_recipe_is_refused(tmp_path):
    with pytest.raises(ValueError, match="no generator recipe"):
        load_recipe("rag", root=tmp_path)


def test_provenance_records_the_generator_and_keeps_the_old_entries():
    prov = json.loads((DOMAINS / "rag" / "provenance.json").read_text(encoding="utf-8"))
    assert prov["generator"] == {"source": "hand-moved from synth/vocab.py and synth/truth.py at tag ev3b-code"}
    assert {"words", "pack"} <= set(prov) and set(prov["files"]) == {"words.yaml", "pack.yaml"}
