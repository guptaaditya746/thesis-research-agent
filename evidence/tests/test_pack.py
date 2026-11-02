"""A domain pack (domains/<name>/) holds the topic words; the loader checks it and digests it."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from evidence.pack import DOMAINS, PackError, Role, load_pack

# the words each extractor used at EV3b, when the code still held them (Task 2's snapshot)
SNAPSHOT = json.loads((Path(__file__).resolve().parent / "fixtures" / "ev3b_configs.json").read_text(encoding="utf-8"))
FUNNEL = "rag-factuality-funnel"   # a protocol whose regex and gliner steps set no words of their own


def test_rag_pack_loads_with_the_ev3b_words():
    p = load_pack("rag")
    assert [list(m) for m in p.words.metrics] == SNAPSHOT[f"{FUNNEL}/metric/regex_metric"]["metrics"]
    assert p.words.gliner_labels["metric"] == SNAPSHOT[f"{FUNNEL}/metric/gliner_metric"]["labels"]
    assert p.types["condition"].role is Role.COMPARED_THING


def test_pack_words_equal_the_ev3b_snapshot():
    w, at = load_pack("rag").words, lambda key: SNAPSHOT[f"{FUNNEL}/{key}"]
    assert [list(c) for c in w.claims] == at("author_claim/regex_author_claim")["claims"]
    assert w.claim_subject == at("author_claim/regex_author_claim")["subject"]
    conditions = at("condition/regex_condition")["conditions"]
    assert w.conditions["rag"] == conditions["rag"]
    # the snapshot holds baseline patterns wrapped by the negated-object lookahead; the pack holds them unwrapped
    assert [p + w.not_a_system for p in w.conditions["baseline"]] == conditions["baseline"]
    assert w.not_a_system == at("condition/regex_condition")["not_a_system"]
    assert w.fraction_metrics == at("measurement/number_measurement")["fraction_metrics"]
    assert [list(m) for m in w.metric_supplement] == at("metric/abbrev_metric")["supplement"]
    assert w.gliner_labels["condition"] == at("condition/gliner_condition")["labels"]
    assert w.dataset_pattern == SNAPSHOT["inv-datasets/dataset/regex_dataset"]["pattern"]


def test_unknown_pack_names_the_folder(tmp_path):
    with pytest.raises(PackError, match="nope"):
        load_pack("nope", root=tmp_path)


def test_pack_digest_changes_when_a_word_changes(tmp_path):
    shutil.copytree(DOMAINS / "rag", tmp_path / "rag")
    before = load_pack("rag", root=tmp_path).sha256
    (tmp_path / "rag/words.yaml").write_text((tmp_path / "rag/words.yaml").read_text().replace("hallucination", "halluc"))
    assert load_pack("rag", root=tmp_path).sha256 != before


def test_pack_name_must_equal_its_folder(tmp_path):
    shutil.copytree(DOMAINS / "rag", tmp_path / "other")
    with pytest.raises(PackError, match="name 'rag'.*folder 'other'"):
        load_pack("other", root=tmp_path)
