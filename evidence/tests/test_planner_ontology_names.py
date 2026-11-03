"""Final review I6: the planner puts the field ontology's other names (MeSH entry terms) into the locked word list."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence import steps
from evidence.plan import WordList
from evidence.planner import propose
from modelcall.dspy_lm import RecordedLM

FIX = Path(__file__).parent / "fixtures"
QUESTION = "Does aspirin reduce myocardial infarction?"


def _plan(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    fresh = "SELECT ?paper WHERE { ?p ev:name ?paper } ORDER BY ?paper"
    replies = [{"lines": [{"question": "Which papers report it?", "kind": "inventory", "template": None}]},
               {"field": "medicine", "things": ["aspirin", "mi"], "measures": [], "lower_is_better": []},
               {"rule": "any_line"}, {"decisions": []}, {"query": fresh}, {"sentences": ["It lists papers."]}]
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    words = WordList(things={"aspirin": ["aspirin"], "mi": ["myocardial infarction", "MI"]}, cues=["reduces"],
                     written_by="orch-model", ontology_names={})
    with steps.using(RecordedLM("fake", lambda prompt: json.dumps(replies.pop(0)))):
        plan, _ = propose(QUESTION, write_words=lambda q, things: words)
    return plan


def test_propose_adds_the_mesh_entry_terms_to_the_word_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    onto = tmp_path / "onto"
    onto.mkdir()
    (onto / "mesh_desc.xml").write_bytes((FIX / "mesh_mini.xml").read_bytes())
    monkeypatch.setenv("EV_ONTOLOGY_DIR", str(onto))
    plan = _plan(monkeypatch, tmp_path)
    assert "Heart Attack" in plan.words.ontology_names["mi"]
    assert plan.words.written_by == "orch-model" and plan.words.things["mi"] == ["myocardial infarction", "MI"]


def test_propose_without_an_ontology_on_disk_keeps_the_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EV_ONTOLOGY_DIR", str(tmp_path / "empty"))
    plan = _plan(monkeypatch, tmp_path)
    assert plan.words.ontology_names == {}
