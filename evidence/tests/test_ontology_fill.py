"""Never silent: the ontology report, LLM parents and the LLM mini-tree (fake model, no network)."""
import json
import re
from pathlib import Path

import pytest
import rdflib

from evidence import steps
from evidence.ontology import fill, load
from evidence.reasoner import NO_TREE
from rdflib import Namespace

from evidence.vocab import EV as EV_IRI
from modelcall.dspy_lm import RecordedLM

EV = Namespace(EV_IRI)
FIX = Path(__file__).parent / "fixtures"


def fake_model(parents: dict[str, str]):
    """A model that answers `parent` for the name the prompt asks about."""
    def ask(prompt: str) -> str:
        name = re.findall(r"\[\[ ## name ## \]\]\s*\n(.+)", prompt)[-1].strip()
        return json.dumps({"parent": parents.get(name, "")})
    steps.configure(RecordedLM("alias", ask))


@pytest.fixture(autouse=True)
def tuned_off(tmp_path, monkeypatch):
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    monkeypatch.setattr(steps, "_LM", None)


@pytest.fixture
def mesh(tmp_path, monkeypatch):
    (tmp_path / "mesh_desc.xml").write_bytes((FIX / "mesh_mini.xml").read_bytes())
    monkeypatch.setenv("EV_ONTOLOGY_DIR", str(tmp_path))
    return load("medicine")


def test_no_tree_says_so(tmp_path, monkeypatch):
    monkeypatch.setenv("EV_ONTOLOGY_DIR", str(tmp_path))
    graph = load("other")    # QUDT units only: a list of units, no tree
    rep = fill.report(graph, ["something unplaced"])
    assert rep["tree"] == NO_TREE == "reasoning off: no tree"
    assert rep["unplaced"] == 1
    assert fill.report(None, [])["tree"] == NO_TREE


def test_no_tree_run_finishes(tmp_path, monkeypatch):
    """The stage on a field with no tree: it reports, proposes a mini tree, and does not raise."""
    monkeypatch.setenv("EV_ONTOLOGY_DIR", str(tmp_path))
    fake_model({})
    out = fill.stage_result("other", ["alpha", "beta"], "q")
    assert out["tree"] == "reasoning off: no tree" and out["unplaced"] == 2 and out["links"] == []


def test_unplaced_counted(mesh):
    rep = fill.report(mesh, ["Heart Attack", "heart diseases", "Zorbitis"])
    assert rep["tree"] == "ontology tree" and rep["unplaced"] == 1
    assert {n["name"]: n["placed"] for n in rep["names"]} == {"Heart Attack": True, "heart diseases": True, "Zorbitis": False}


def test_parent_must_exist(mesh):
    fake_model({"Cardiac Zorbitis": "Heart Diseases", "Heart Zorbitis": "Invented Class"})
    got = fill.propose_parents(["Cardiac Zorbitis", "Heart Zorbitis"], mesh, "q")
    assert got == [("Cardiac Zorbitis", "Heart Diseases")]


def test_parent_may_be_another_proposed_name(mesh):
    fake_model({"Cardiac Zorbitis": "Heart Diseases", "Zorbitis B": "Cardiac Zorbitis"})
    got = fill.propose_parents(["Cardiac Zorbitis", "Zorbitis B"], mesh, "q")
    assert ("Zorbitis B", "Cardiac Zorbitis") in got
    fake_model({"A one": "B one", "B one": "A one"})   # a cycle is refused
    assert len(fill.propose_parents(["A one", "B one"], mesh, "q")) == 1


def test_llm_links_marked_made_by_llm(mesh):
    fake_model({"Cardiac Zorbitis": "Heart Diseases"})
    pairs = fill.propose_parents(["Cardiac Zorbitis"], mesh, "q")
    graph = fill.add_links(mesh, pairs)
    marks = list(graph.subject_objects(EV.madeBy))
    assert marks and all(str(o) == "llm" for _, o in marks)
    assert fill.report(graph, ["Cardiac Zorbitis"])["unplaced"] == 0
    fake_model({"Alpha cells": "Beta cells"})
    tree = fill.mini_tree(["Alpha cells", "Beta cells"], "q")
    assert fill.report(tree, [])["tree"] == "made by LLM"
    assert {str(o) for _, o in tree.subject_objects(EV.madeBy)} == {"llm"}


def test_review_writes_links_review_json(tmp_path):
    from evidence.rundir import RunDir
    fill.review(RunDir(tmp_path), ["a -> b"], ["c -> d"])
    assert json.loads((tmp_path / "links_review.json").read_text(encoding="utf-8")) == {
        "accepted": ["a -> b"], "rejected": ["c -> d"]}


def test_stage_through_the_seam_on_a_field_with_no_tree(tmp_path, monkeypatch):
    """Review Focus: no ontology for the field -> "reasoning off: no tree", and the run goes on."""
    from evidence import stages
    from evidence.plan import Plan, WordList
    from evidence.rundir import RunDir
    monkeypatch.setenv("EV_ONTOLOGY_DIR", str(tmp_path))
    plan = Plan(question="q?", field="other", lines=[], main_rule="m", decisions=[], clarifications=[],
                words=WordList(things={}, cues=[], written_by="t", ontology_names={}))

    def ask(*a, **k):
        from evidence.stages import Reply
        return Reply(text='{"parent": ""}')

    ctx = stages.StageContext(plan, None, "run", None, tmp_path, ask, "alias")
    with stages.registered():
        stages.register("ontology", "after_run", fill.ontology_stage)
        out = stages.after_run(RunDir(tmp_path), ctx)
    assert out["ontology"]["tree"] == "reasoning off: no tree"
    (tmp_path / "ontology.json").write_text(json.dumps(out["ontology"]), encoding="utf-8")
