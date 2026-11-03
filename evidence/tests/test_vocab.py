"""The graph vocabulary (evidence/vocab/ev.ttl): every term the records and queries use is declared, with a comment."""
import re

import pytest
from pyoxigraph import Literal, NamedNode, RdfFormat, Store

from evidence.vocab import EV, TTL_PATH

RDF_TYPE = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
RDFS_COMMENT = NamedNode("http://www.w3.org/2000/01/rdf-schema#comment")
RDFS_CLASS = NamedNode("http://www.w3.org/2000/01/rdf-schema#Class")
RDF_PROPERTY = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#Property")

CLASSES = ["Paper", "Experiment", "Thing", "Metric", "Value", "Claim", "Link", "Comparison"]
PROPERTIES = ["inPaper", "inExperiment", "of", "onMetric", "number", "source", "name", "a", "b", "delta", "better",
              "subject", "relation", "object", "strength", "direction", "cites", "outsideSet", "madeBy",
              "relationGroup", "ref"]


@pytest.fixture(scope="module")
def store() -> Store:
    s = Store()
    s.load(TTL_PATH.read_bytes(), format=RdfFormat.TURTLE)
    return s


def test_namespace_matches_ttl_prefix():
    match = re.search(r"@prefix\s+ev:\s*<([^>]+)>", TTL_PATH.read_text(encoding="utf-8"))
    assert match is not None
    assert match.group(1) == EV == "https://w3id.org/thesis-ev#"


@pytest.mark.parametrize("name", CLASSES + PROPERTIES)
def test_term_is_declared_with_comment(store, name):
    term = NamedNode(EV + name)
    kinds = {q.object for q in store.quads_for_pattern(term, RDF_TYPE, None)}
    assert kinds & {RDFS_CLASS, RDF_PROPERTY}, f"ev:{name} is not declared as a class or property"
    comments = [q.object for q in store.quads_for_pattern(term, RDFS_COMMENT, None)]
    assert any(isinstance(c, Literal) and c.value.strip() for c in comments), f"ev:{name} has no rdfs:comment"


def test_no_fixed_setting_terms_declared(store):
    # ev:setting_<field> is one property per setting key, so none is declared in the ttl.
    declared = {str(q.subject) for q in store.quads_for_pattern(None, RDF_TYPE, None)}
    assert not [iri for iri in declared if iri.startswith(EV + "setting_")]


RDFS_DOMAIN = NamedNode("http://www.w3.org/2000/01/rdf-schema#domain")
RDFS_RANGE = NamedNode("http://www.w3.org/2000/01/rdf-schema#range")
XSD = "http://www.w3.org/2001/XMLSchema#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"


def test_relation_has_no_domain(store):
    # ev:relation serves both claims and links, so it must not be inferred as one of them.
    assert not list(store.quads_for_pattern(NamedNode(EV + "relation"), RDFS_DOMAIN, None))


def test_domains_and_ranges_name_declared_classes_or_builtin_types(store):
    declared = {q.subject.value for q in store.quads_for_pattern(None, RDF_TYPE, RDFS_CLASS)}
    bad = []
    for pred in (RDFS_DOMAIN, RDFS_RANGE):
        for q in store.quads_for_pattern(None, pred, None):
            target = q.object.value
            if target.startswith(XSD) or target.startswith(RDFS):
                continue
            if target not in declared:
                bad.append((q.subject.value, target))
    assert not bad, f"domain/range names an undeclared term: {bad}"
