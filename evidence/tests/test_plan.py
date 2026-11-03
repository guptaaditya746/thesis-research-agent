"""The plan file: what a human confirms before a run; it hashes canonically and goes into the lock."""
from __future__ import annotations

from pathlib import Path

from evidence import engine, lockfile
from evidence.plan import Decision, EvidenceLine, Plan, WordList, load_plan, write_plan
from evidence.protocol import load
from jsonio import canonical_bytes

from .conftest import PROTOCOL

FIXTURE = Path(__file__).parent / "fixtures" / "locks" / "rag-factuality.lock.json"


def make_plan(confirmed: bool = True) -> Plan:
    who = "tim" if confirmed else None
    return Plan(
        question="Does retrieval help factuality?", field="cs",
        lines=[EvidenceLine(id="main", question="Accuracy with RAG?", query="accuracy rag", template=None),
               EvidenceLine(id="oversell", question="Do authors oversell?", query="claims", template=None,
                            removable=False)],
        main_rule="compare accuracy with and without retrieval",
        words=WordList(things={"rag": ["RAG", "retrieval-augmented generation"]}, cues=["improves"],
                       written_by="model-x", ontology_names={"rag": ["Retrieval Augmented Generation"]}),
        decisions=[Decision(id="d1", type="must_match", value="same dataset", reason="fair comparison",
                            confirmed_by=who, confirmed_at="2026-11-03" if who else None),
                   Decision(id="d2", type="threshold", value=0.05, reason="noise floor", flagged=True,
                            flag_reason="guess", confirmed_by=who)],
        clarifications=[{"asked": "which metric?", "answer": "accuracy"}])


def test_ready_needs_every_decision_confirmed():
    assert make_plan(True).ready()
    assert not make_plan(False).ready()
    plan = make_plan(True)
    partly = plan.model_copy(update={"decisions": [plan.decisions[0],
                                                   plan.decisions[1].model_copy(update={"confirmed_by": None})]})
    assert not partly.ready()


def test_plan_roundtrip_same_sha(tmp_path):
    plan = make_plan()
    write_plan(plan, tmp_path / "plan.json")
    again = load_plan(tmp_path / "plan.json")
    assert again == plan and again.sha256 == plan.sha256
    assert make_plan(False).sha256 != plan.sha256


def test_old_protocol_lock_unchanged():
    protocol = load(PROTOCOL)
    cascades = engine.build_extractors(protocol, "cascade", None, None, None)
    assert canonical_bytes(lockfile.lock(protocol, cascades)) == FIXTURE.read_bytes()


def test_lock_with_plan_has_plan_and_words_sha():
    protocol = load(PROTOCOL)
    cascades = engine.build_extractors(protocol, "cascade", None, None, None)
    plan = make_plan()
    out = lockfile.lock(protocol, cascades, plan=plan)
    assert out["plan_sha256"] == plan.sha256 and out["words_sha256"] == plan.words.sha256


# --- Wave 2: the main-answer rule is its own decision type; "how?" sentences and the measures live in the plan --------

def test_main_rule_is_its_own_decision_type():
    d = Decision(id="main_rule", type="main_rule", value="any_line", reason="how lines add up")
    assert d.type == "main_rule"


def test_an_old_main_rule_row_is_migrated_on_load(tmp_path):
    plan = make_plan()
    data = plan.model_dump(mode="json")
    data["decisions"].append({"id": "main_rule", "type": "counts_as", "value": "any_line", "reason": "r"})
    data["lines"][0].pop("how", None)
    data.pop("measures", None)
    path = tmp_path / "old.json"
    import json
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = load_plan(path)
    rule = next(d for d in loaded.decisions if d.id == "main_rule")
    assert rule.type == "main_rule" and rule.value == "any_line"
    assert loaded.lines[0].how == [] and loaded.measures == []


def test_how_sentences_and_measures_survive_a_reload(tmp_path):
    plan = make_plan()
    plan = plan.model_copy(update={"measures": ["rag"], "lines": [
        plan.lines[0].model_copy(update={"how": ["It looks at values.", "It keeps big gaps."]}), plan.lines[1]]})
    write_plan(plan, tmp_path / "plan.json")
    again = load_plan(tmp_path / "plan.json")
    assert again.lines[0].how == ["It looks at values.", "It keeps big gaps."]
    assert again.measures == ["rag"] and again.sha256 == plan.sha256
