"""scoring/store.py: named graph per run, union queries, reload on change, read-only."""
from __future__ import annotations

import pytest

from scoring.store import RunStore

TTL = """@prefix prov: <http://www.w3.org/ns/prov#> .
<urn:thesis-agent:run:{run}/claim/claim-000001> a prov:Entity ;
    prov:wasGeneratedBy <urn:thesis-agent:run:{run}/step/1> .
"""

Q = "PREFIX prov: <http://www.w3.org/ns/prov#> SELECT ?c WHERE { ?c a prov:Entity } ORDER BY ?c"


def make_run(root, run_id, extra=""):
    d = root / run_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "graph.ttl").write_text(TTL.format(run=run_id) + extra, encoding="utf-8")
    return d


def test_union_and_per_run_queries(tmp_path):
    runs = tmp_path / "runs"
    make_run(runs, "a")
    make_run(runs, "b")
    (runs / "no-graph").mkdir()
    store = RunStore(tmp_path / "store")
    assert store.load_all(runs) == ["a", "b"]
    assert len(store.query(Q)["rows"]) == 2
    rows = store.query(Q, run_id="a")["rows"]
    assert rows == [{"c": "urn:thesis-agent:run:a/claim/claim-000001"}]
    assert store.query("ASK { ?s ?p ?o }") == {"boolean": True}


def test_reload_only_when_changed_and_persisted(tmp_path):
    runs = tmp_path / "runs"
    d = make_run(runs, "a")
    store = RunStore(tmp_path / "store")
    assert store.load_run(d) is True
    assert store.load_run(d) is False
    make_run(runs, "a", extra='<urn:x> a <http://www.w3.org/ns/prov#Entity> .\n')
    assert store.load_run(d) is True
    assert len(store.query(Q, run_id="a")["rows"]) == 2  # replaced, not appended twice
    del store
    assert RunStore(tmp_path / "store").runs() == ["a"]


def test_updates_are_refused(tmp_path):
    store = RunStore()
    with pytest.raises(ValueError):
        store.query("DELETE WHERE { ?s ?p ?o }")
    with pytest.raises(ValueError):
        store.query("INSERT DATA { <urn:a> <urn:b> <urn:c> }")
