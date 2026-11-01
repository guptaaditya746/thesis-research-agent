"""A domain pack (domains/<name>/) holds the topic words; the loader checks it and digests it."""
from __future__ import annotations

import shutil

import pytest

from evidence.extractors import gliner, terms, abbrev, units, dataset
from evidence.pack import DOMAINS, PackError, Role, load_pack


def test_rag_pack_loads_with_code_words():
    p = load_pack("rag")
    assert p.words.metrics[0] == terms.METRICS[0]
    assert p.words.gliner_labels == gliner.LABELS
    assert p.types["condition"].role is Role.COMPARED_THING


def test_pack_words_equal_the_code_constants():
    w = load_pack("rag").words
    assert [tuple(m) for m in w.metrics] == terms.METRICS
    assert [tuple(c) for c in w.claims] == terms.CLAIMS
    assert w.conditions["rag"] == terms.CONDITIONS["rag"]
    # the code holds baseline patterns wrapped by control_cue; the pack holds them unwrapped
    assert [terms.control_cue(p) for p in w.conditions["baseline"]] == terms.CONDITIONS["baseline"]
    assert w.not_a_system == terms.NOT_A_SYSTEM and w.claim_subject == terms.CLAIM_SUBJECT
    assert w.fraction_metrics == units.FRACTION_METRICS and w.dataset_pattern == dataset.DEFAULT_PATTERN
    assert [tuple(m) for m in w.metric_supplement] == abbrev.SUPPLEMENT


def test_unknown_pack_names_the_folder(tmp_path):
    with pytest.raises(PackError, match="nope"):
        load_pack("nope", root=tmp_path)


def test_pack_digest_changes_when_a_word_changes(tmp_path):
    shutil.copytree(DOMAINS / "rag", tmp_path / "rag")
    before = load_pack("rag", root=tmp_path).sha256
    (tmp_path / "rag/words.yaml").write_text((tmp_path / "rag/words.yaml").read_text().replace("hallucination", "halluc"))
    assert load_pack("rag", root=tmp_path).sha256 != before
