import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from evidence.kg.build import build, serialize
from evidence.vocab import EV

from .kg_support import ROLES, Doc, paper, register, restore


@pytest.fixture(autouse=True)
def _registry():
    before = register()
    yield
    restore(before)


def three_methods() -> Doc:
    d = Doc("p1")
    d.experiment("e1", {"population": "adults", "model": "7B"})
    for name, x in (("Alpha", 0.5), ("Beta", 0.4), ("Gamma", 0.3)):
        d.value(name, x)
    return d


def count(store, sparql: str) -> int:
    return len(list(store.query(sparql)))


def test_same_records_same_bytes():
    d = three_methods()
    a = serialize(build([paper("p1")], {"p1": d.items}, ROLES, None))
    b = serialize(build([paper("p1")], {"p1": list(reversed(d.items))}, ROLES, None))
    assert a == b and a.endswith(b"\n") and a.splitlines() == sorted(a.splitlines())


def test_comparison_edge_any_two_things():
    d = three_methods()
    store = build([paper("p1")], {"p1": d.items}, ROLES, None)
    q = f"PREFIX ev: <{EV}> SELECT ?c ?delta ?better WHERE {{ ?c a ev:Comparison ; ev:delta ?delta ; ev:better ?better }}"
    rows = list(store.query(q))
    assert len(rows) == 3
    assert sorted(round(float(r["delta"].value), 3) for r in rows) == [0.1, 0.1, 0.2]


def test_better_follows_metric_direction():
    d = Doc("p1")
    d.value("Alpha", 0.5, metric="err", higher=False)
    d.value("Beta", 0.4, metric="err", higher=False)
    store = build([paper("p1")], {"p1": d.items}, ROLES, None)
    [row] = list(store.query(f"PREFIX ev: <{EV}> SELECT ?n WHERE {{ ?c ev:better ?v . ?v ev:number ?n }}"))
    assert float(row["n"].value) == 0.4


def test_no_comparison_across_experiments():
    d = Doc("p1")
    d.experiment("e1", {"population": "adults"})
    d.experiment("e2", {"population": "children"})
    d.value("Alpha", 0.5, population="adults")
    d.value("Beta", 0.4, population="children")
    store = build([paper("p1")], {"p1": d.items}, ROLES, None)
    assert count(store, f"PREFIX ev: <{EV}> SELECT ?c WHERE {{ ?c a ev:Comparison }}") == 0
    # and not across papers either
    e = Doc("p2")
    e.value("Gamma", 0.2)
    store = build([paper("p1"), paper("p2")], {"p1": three_methods().items, "p2": e.items}, ROLES, None)
    assert count(store, f"PREFIX ev: <{EV}> SELECT ?c WHERE {{ ?c a ev:Comparison }}") == 3


def test_values_sit_in_experiments_with_settings():
    d = three_methods()
    store = build([paper("p1")], {"p1": d.items}, ROLES, None)
    q = f"PREFIX ev: <{EV}> SELECT ?v WHERE {{ ?v a ev:Value ; ev:inExperiment ?e . ?e ev:setting_model \"7B\" }}"
    assert count(store, q) == 3


def test_ontology_types_things_by_label():
    onto = Graph()
    cls, parent = URIRef("http://o/Retriever"), URIRef("http://o/Method")
    for c, label in ((cls, "alpha"), (parent, "Method")):
        onto.add((c, RDF.type, OWL.Class))
        onto.add((c, RDFS.label, Literal(label)))
    onto.add((cls, RDFS.subClassOf, parent))
    store = build([paper("p1")], {"p1": three_methods().items}, ROLES, onto)
    q = ("SELECT ?t WHERE { ?t a/<http://www.w3.org/2000/01/rdf-schema#subClassOf>* <http://o/Method> . "
         f"?t a <{EV}Thing> }}")
    assert count(store, q) == 1


def test_claims_and_links_in_the_graph():
    d = Doc("p1")
    d.claim("RAG", "raises", object="accuracy", direction="improves", relation_group="increases")
    d.link("builds_on", "10.1/x")
    store = build([paper("p1")], {"p1": d.items}, ROLES, None)
    assert count(store, f'PREFIX ev: <{EV}> SELECT ?c WHERE {{ ?c a ev:Claim ; ev:relationGroup "increases" ; '
                        'ev:object "accuracy" }') == 1
    assert count(store, f'PREFIX ev: <{EV}> SELECT ?c WHERE {{ ?c a ev:Link ; ev:ref "10.1/x" ; '
                        'ev:outsideSet true }') == 1
