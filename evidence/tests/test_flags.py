"""The synthesis flags (docs/evidence-system.md F1) on inline papers: duplicates reported with their direction
but not counted, large effects and disagreeing claims reported only, the protocol switch, the graph edge,
and replay reproducing the flags."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evidence import engine, protocol
from evidence.replay import replay

from .conftest import PROTOCOL, corpus_of, regex_run

HEAD = "# T\n\n## Setup\n\nWe compare a closed-book baseline (B) with its retrieval-augmented variant (R).\n\n## Results\n\n"
FLAGS_BLOCK = ("  flags:                      # reported in answer.json (Part F); only duplicates change the counts\n"
               "    duplicates: true\n"
               "    large_effect: {factor: 3.0, min_studies: 3}\n")


def paper(control: float, treatment: float, conclusion: str | None = None) -> str:
    text = HEAD + ("| System | Dataset | Accuracy (%) |\n|---|---|---|\n"
                   f"| B | NQ | {control:.1f} |\n| R | NQ | {treatment:.1f} |\n")
    return text + (f"\n## Conclusion\n\n{conclusion}\n" if conclusion else "")


DUPLICATED = {"P1": paper(60, 70), "P2": paper(60, 50), "P3": paper(60, 50), "P4": paper(60, 70)}


def test_a_duplicate_keeps_its_direction_but_is_not_counted(tmp_path: Path) -> None:
    answer, _ = regex_run(DUPLICATED, tmp_path)
    by_doc = {s["document"]: s for s in answer["studies"]}
    assert by_doc["P3"]["direction"] == "contradicts" and by_doc["P3"]["delta"] == pytest.approx(-0.1)
    assert by_doc["P3"]["flags"] == ["duplicate"] and by_doc["P3"]["duplicate_of"] == "P2"
    assert by_doc["P4"]["flags"] == ["duplicate"] and by_doc["P4"]["duplicate_of"] == "P1"
    assert by_doc["P1"]["flags"] == [] and by_doc["P1"]["duplicate_of"] is None
    assert answer["counts"] == {"supporting": 1, "contradicting": 1, "neutral": 0, "undetermined": 0, "duplicates": 2}
    assert answer["supporting"] == ["P1"] and answer["contradicting"] == ["P2"] and answer["duplicates"] == ["P3", "P4"]
    assert answer["flags"] == {"claim_disagrees": [], "duplicate": ["P3", "P4"], "large_effect": []}
    assert answer["label"] == "mixed"


def test_a_chain_of_duplicates_points_to_the_first_and_order_is_the_manifest_order(tmp_path: Path) -> None:
    docs = {"P3": paper(60, 70), "P2": paper(60, 70), "P2b": paper(60, 70), "P1": paper(60, 50)}
    answer, _ = regex_run(docs, tmp_path)
    by_doc = {s["document"]: s for s in answer["studies"]}
    assert by_doc["P2"]["duplicate_of"] == "P3" and by_doc["P2b"]["duplicate_of"] == "P3"
    assert answer["duplicates"] == ["P2", "P2b"] == answer["flags"]["duplicate"]
    assert answer["counts"] == {"supporting": 1, "contradicting": 1, "neutral": 0, "undetermined": 0, "duplicates": 2}


def test_large_effect_median_leaves_out_duplicates_and_neutral_studies(tmp_path: Path) -> None:
    """P5 repeats P4's big effect: without dedup the median would rise and P4 would not stand out; P6 is
    neutral and must not pull the median down either."""
    docs = {"P1": paper(60, 65), "P2": paper(60, 66), "P3": paper(60, 67), "P4": paper(50, 90), "P5": paper(50, 90),
            "P6": paper(60, 60.5)}
    answer, _ = regex_run(docs, tmp_path)
    assert answer["flags"]["large_effect"] == ["P4"] and answer["flags"]["duplicate"] == ["P5"]
    assert {s["document"]: s["direction"] for s in answer["studies"]}["P6"] == "neutral"


def test_manifest_order_decides_the_original(tmp_path: Path) -> None:
    answer, _ = regex_run({"P3": paper(60, 50), "P2": paper(60, 50)}, tmp_path)
    by_doc = {s["document"]: s for s in answer["studies"]}
    assert by_doc["P2"]["duplicate_of"] == "P3" and by_doc["P3"]["duplicate_of"] is None
    assert answer["contradicting"] == ["P3"] and answer["duplicates"] == ["P2"] and answer["label"] == "refuted"


def test_duplicate_detection_can_be_switched_off(tmp_path: Path) -> None:
    variant = tmp_path / "no-dedup.yaml"
    text = PROTOCOL.read_bytes().decode("utf-8")
    assert text.count("duplicates: true") == 1
    variant.write_text(text.replace("duplicates: true", "duplicates: false"), encoding="utf-8", newline="\n")
    assert protocol.load(variant).synthesis.flags.duplicates is False
    answer, _ = regex_run(DUPLICATED, tmp_path, variant)
    assert answer["counts"] == {"supporting": 2, "contradicting": 2, "neutral": 0, "undetermined": 0, "duplicates": 0}
    assert answer["duplicates"] == [] and answer["flags"]["duplicate"] == []
    assert all(s["flags"] == [] and s["duplicate_of"] is None for s in answer["studies"])
    assert answer["supporting"] == ["P1", "P4"] and answer["label"] == "mixed"


def test_large_effect_is_flagged_and_still_counted(tmp_path: Path) -> None:
    docs = {"P1": paper(60, 65), "P2": paper(60, 66), "P3": paper(60, 67), "P4": paper(50, 90)}
    answer, _ = regex_run(docs, tmp_path)
    by_doc = {s["document"]: s for s in answer["studies"]}
    assert by_doc["P4"]["delta"] == pytest.approx(0.4) and by_doc["P4"]["flags"] == ["large_effect"]
    assert all(by_doc[d]["flags"] == [] for d in ("P1", "P2", "P3"))
    assert answer["flags"] == {"claim_disagrees": [], "duplicate": [], "large_effect": ["P4"]}
    assert answer["counts"]["supporting"] == 4 and answer["supporting"] == ["P1", "P2", "P3", "P4"]
    assert answer["label"] == "supported"


def test_large_effect_needs_enough_studies_and_follows_the_protocol(tmp_path: Path) -> None:
    docs = {"P1": paper(60, 65), "P2": paper(50, 90)}
    answer, _ = regex_run(docs, tmp_path)
    assert answer["flags"]["large_effect"] == []           # two non-neutral studies, min_studies is 3
    variant = tmp_path / "two.yaml"
    text = PROTOCOL.read_bytes().decode("utf-8")
    assert text.count("{factor: 3.0, min_studies: 3}") == 1
    variant.write_text(text.replace("{factor: 3.0, min_studies: 3}", "{factor: 1.5, min_studies: 2}"),
                       encoding="utf-8", newline="\n")
    answer, _ = regex_run(docs, tmp_path / "b", variant)
    assert answer["flags"]["large_effect"] == ["P2"]


def test_a_claim_that_disagrees_with_the_table_is_flagged(tmp_path: Path) -> None:
    docs = {"P1": paper(60, 50, "Retrieval improves accuracy."), "P2": paper(60, 70, "Retrieval improves accuracy.")}
    answer, _ = regex_run(docs, tmp_path)
    p1, p2 = answer["studies"]
    assert p1["direction"] == "contradicts" and p1["author_claim"]["direction"] == "improves"
    assert p1["author_claim"]["agrees_with_data"] is False and p1["flags"] == ["claim_disagrees"]
    assert p2["author_claim"]["agrees_with_data"] is True and p2["flags"] == []
    assert answer["flags"] == {"claim_disagrees": ["P1"], "duplicate": [], "large_effect": []}
    assert answer["counts"] == {"supporting": 1, "contradicting": 1, "neutral": 0, "undetermined": 0, "duplicates": 0}


def test_a_duplicate_can_carry_more_flags(tmp_path: Path) -> None:
    docs = {"P1": paper(60, 50), "P2": paper(60, 50, "Retrieval improves accuracy.")}
    answer, _ = regex_run(docs, tmp_path)
    p2 = answer["studies"][1]
    assert p2["flags"] == ["claim_disagrees", "duplicate"] and p2["duplicate_of"] == "P1"
    assert answer["flags"] == {"claim_disagrees": ["P2"], "duplicate": ["P2"], "large_effect": []}


def test_flag_keys_are_present_on_an_undetermined_study(tmp_path: Path) -> None:
    answer, _ = regex_run({"P1": "# T\n\n## Abstract\n\nA position paper on retrieval.\n"}, tmp_path)
    (study,) = answer["studies"]
    assert study["direction"] == "undetermined" and study["flags"] == [] and study["duplicate_of"] is None
    assert answer["counts"] == {"supporting": 0, "contradicting": 0, "neutral": 0, "undetermined": 1, "duplicates": 0}
    assert answer["duplicates"] == [] and answer["flags"] == {"claim_disagrees": [], "duplicate": [], "large_effect": []}
    assert answer["label"] == "insufficient"


def test_graph_links_a_duplicate_to_its_original_and_replay_reproduces_the_flags(tmp_path: Path) -> None:
    root = engine.run(PROTOCOL, corpus_of(tmp_path / "corpus", DUPLICATED), tmp_path / "runs", selection="regex-only",
                      provider=None)
    graph = json.loads((root / "graph.json").read_text(encoding="utf-8"))
    dup_edges = [e for e in graph["edges"] if e["rel"] == "duplicate_of"]
    assert dup_edges == [{"src": "P3", "dst": "P2", "rel": "duplicate_of"}, {"src": "P4", "dst": "P1", "rel": "duplicate_of"}]
    assert sum(e["rel"] in ("supports", "contradicts") for e in graph["edges"]) == 4   # a duplicate keeps its direction
    new, report = replay(root)
    assert report["ok"] and report["mismatched"] == []
    old_answer = json.loads((root / "answer.json").read_text(encoding="utf-8"))
    new_answer = json.loads((new / "answer.json").read_text(encoding="utf-8"))
    assert new_answer == old_answer and new_answer["flags"]["duplicate"] == ["P3", "P4"]
    assert (new / "graph.json").read_bytes() == (root / "graph.json").read_bytes()


def test_protocol_flags_are_version_2_with_strict_models() -> None:
    for name in ("rag-factuality.yaml", "rag-factuality-agentic.yaml"):
        p = protocol.load(PROTOCOL.parent / name)
        assert p.version == 2
        assert p.synthesis.flags == protocol.Flags(duplicates=True, large_effect=protocol.LargeEffect(factor=3.0, min_studies=3))
    assert protocol.Flags().large_effect.factor == 3.0 and protocol.Flags().large_effect.min_studies == 3
    with pytest.raises(ValidationError):
        protocol.Flags.model_validate({"duplicates": True, "outliers": True})
    with pytest.raises(ValidationError):
        protocol.LargeEffect.model_validate({"factor": 0})
    text = PROTOCOL.read_bytes().decode("utf-8")
    assert text.count(FLAGS_BLOCK) == 1
    without = text.replace(FLAGS_BLOCK, "")
    assert "flags:" not in without
    assert protocol.parse(without).synthesis.flags == protocol.Flags()   # the defaults are the written block
    assert protocol.parse(without).sha256 == protocol.parse(text).sha256
