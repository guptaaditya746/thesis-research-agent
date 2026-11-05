"""A v2 plan run matches a query's names by bracket parts and the plan's word list (planrun.name_matcher): the
question's "ICSI Meeting Recorder Dialog Act Corpus (MRDA)" finds the graph's "mrda", and a literal with nothing
else to match renders exactly as before."""
from __future__ import annotations

from evidence.kg.build import build
from evidence.kg.query import render, run_query
from evidence.planrun import name_matcher
from evidence.tests.kg_support import ROLES, Doc, paper, register, restore
from evidence.tests.test_plan_run import make_plan


def _store():
    before = register()
    try:
        d = Doc("P1")
        d.value("BERT", 0.9, metric="F1", population="MRDA")
        d.value("BERT", 0.8, metric="F1", population="OntoNotes 5.0")
        d.experiment("e1", {"task": "Named Entity Recognition (NER)", "dataset": "CoNLL-2003"})
        return build([paper("P1")], {"P1": d.items}, ROLES, None)
    finally:
        restore(before)


CONTEXT = 'SELECT ?v WHERE {{ ?v a ev:Value ; kg:contextKey "{}" }}'
TASK = 'SELECT ?d WHERE {{ ?e a ev:Experiment ; kg:key_task "{}" ; ev:setting_dataset ?d }}'


def _plan(things=None):
    return make_plan(things=things or {"bert": ["BERT"], "f1": ["F1"]}, measures=("f1",))


def test_a_bracketed_short_form_matches_the_graph_name():
    store, q = _store(), CONTEXT.format("ICSI Meeting Recorder Dialog Act Corpus (MRDA)")
    assert run_query(store, q).rows == []                                          # v1: the cleaned literal only
    assert len(run_query(store, q, match=name_matcher(_plan(), store)).rows) == 1


def test_a_word_list_alias_matches_the_graph_name():
    store, q = _store(), CONTEXT.format("Ontonotes v5 - English")
    assert len(run_query(store, q, match=name_matcher(_plan(), store)).rows) == 0
    plan = _plan({"bert": ["BERT"], "f1": ["F1"], "ontonotes": ["Ontonotes v5 - English", "OntoNotes 5.0"]})
    assert len(run_query(store, q, match=name_matcher(plan, store)).rows) == 1


def test_a_graph_name_with_a_bracket_matches_its_parts():
    store = _store()
    rows = run_query(store, TASK.format("Named Entity Recognition"), match=name_matcher(_plan(), store)).rows
    assert [r["d"] for r in rows] == ["CoNLL-2003"]


def test_a_name_with_nothing_else_to_match_renders_as_before():
    store, q = _store(), TASK.format("Pose Estimation")
    assert render(q, {}, name_matcher(_plan(), store)) == render(q, {})


def test_a_shared_alias_or_a_bracket_modifier_never_merges_two_things():
    """Review: {"bert-large": ["BERT"], "bert-base": ["BERT"]} must not let "bert large" match "bert base"; "bert
    (large)" stays one name (its bracket is a modifier, not a short form)."""
    store = _store()
    match = name_matcher(_plan({"bert-large": ["BERT"], "bert-base": ["BERT"], "f1": ["F1"]}), store)
    assert match("bert large") == ["bert large"]
    assert match("bert (large)") == ["bert (large)"]


def test_a_typed_literal_stays_exact_and_helper_columns_are_dropped():
    store = _store()
    typed = 'SELECT ?v WHERE { ?v a ev:Value ; kg:contextKey "ICSI Meeting Recorder Dialog Act Corpus (MRDA)"^^xsd:string }'
    assert render(typed, {}, name_matcher(_plan(), store)) == render(typed, {})
    star = "SELECT * WHERE {{ ?v a ev:Value ; kg:contextKey \"{}\" }}".format("ICSI Meeting Recorder Dialog Act Corpus (MRDA)")
    assert [set(r) for r in run_query(store, star, match=name_matcher(_plan(), store)).rows] == [{"v"}]
