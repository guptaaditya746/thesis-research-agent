"""The records graph (records.nq, kg/build.py) as nodes and edges a person can look at: the graph a plan run's answer
was computed from, not the older evidence graph (graph.json).

- A node is every IRI that is a record (an `ev:` type: Paper, Experiment, Thing, Metric, Value, Claim, Link,
  Comparison) and every ontology class one of them is typed with, with the classes above it (`rdfs:subClassOf`); the
  rest of a field ontology (MeSH has many thousand classes) is left out. `type` is the node's `ev:` type ("Class" for
  an ontology class), `types` every `rdf:type` (an ontology class by its label), `label` its `rdfs:label` or
  `ev:name` (a value: its number; a claim: subject, relation, object; a comparison: its delta), else the IRI's last
  part.
- Literals are node fields, keyed by the property's local name (`ev:source`, the span JSON, is left out); an edge is
  an IRI-valued property between two shown nodes, `rel` its local name (`type` for a typing by an ontology class).
- `document` is the paper a node belongs to (a paper itself; an experiment, claim or link by `ev:inPaper`; a value or
  comparison by its experiment's paper), None for what papers share (things, metrics, classes).
- At most `limit` nodes: records first, comparisons (one per pair of values) and then classes are dropped first;
  `omitted` counts what was dropped by type.

Nodes and edges are sorted, so the same records.nq gives the same view."""
from __future__ import annotations

from typing import Any

import pyoxigraph as ox

from evidence.vocab import EV

from .build import RDF_TYPE, RDFS_LABEL, RDFS_SUBCLASS

__all__ = ["LIMIT", "view"]

LIMIT = 1500
RECORD_TYPES = ("Paper", "Experiment", "Thing", "Metric", "Value", "Claim", "Link", "Comparison")
DROP_ORDER = ("Comparison", "Class", "Value", "Link", "Claim", "Experiment", "Metric", "Thing", "Paper")
CLASS = "Class"
HIDDEN = {EV + "source"}


def local(iri: str) -> str:
    """The last part of an IRI (after #, else after /)."""
    return iri.rsplit("#", 1)[-1] if "#" in iri else iri.rstrip("/").rsplit("/", 1)[-1]


def _value(term: Any) -> Any:
    if isinstance(term, ox.Literal):
        kind = term.datatype.value.rsplit("#", 1)[-1] if term.datatype is not None else "string"
        if kind == "boolean":
            return term.value == "true"
        if kind in ("double", "decimal", "float"):
            return float(term.value)
        if kind in ("integer", "int", "long"):
            return int(term.value)
        return term.value
    return term.value


def view(store: ox.Store, limit: int = LIMIT) -> dict[str, Any]:
    """{nodes, edges, omitted}: the records graph as the module docstring says."""
    types: dict[str, list[str]] = {}
    fields: dict[str, dict[str, Any]] = {}
    links: list[tuple[str, str, str]] = []
    labels: dict[str, str] = {}
    parents: dict[str, list[str]] = {}
    for quad in store.quads_for_pattern(None, None, None, None):
        s, p, o = quad.subject, quad.predicate.value, quad.object
        if not isinstance(s, ox.NamedNode):
            continue
        if p == RDF_TYPE.value and isinstance(o, ox.NamedNode):
            types.setdefault(s.value, []).append(o.value)
        elif p == RDFS_LABEL:
            labels.setdefault(s.value, str(_value(o)))
        elif p == RDFS_SUBCLASS and isinstance(o, ox.NamedNode):
            parents.setdefault(s.value, []).append(o.value)
        elif isinstance(o, ox.NamedNode):
            links.append((s.value, local(p), o.value))
        elif p not in HIDDEN:
            fields.setdefault(s.value, {})[local(p)] = _value(o)
    records = {iri: next(local(t) for t in ts if t.startswith(EV) and local(t) in RECORD_TYPES)
               for iri, ts in types.items() if any(t.startswith(EV) and local(t) in RECORD_TYPES for t in ts)}
    classes: set[str] = set()
    todo = [t for iri in records for t in types[iri] if not t.startswith(EV)]
    while todo:   # the classes a record is typed with, and every class above them
        c = todo.pop()
        if c not in classes and c not in records:
            classes.add(c)
            todo += parents.get(c, [])
    kind = {**records, **{c: CLASS for c in classes}}

    def paper_of(iri: str) -> str | None:
        own = {rel: dst for src, rel, dst in by_src.get(iri, [])}
        if kind[iri] == "Paper":
            return str(fields.get(iri, {}).get("name") or local(iri))
        if "inPaper" in own and own["inPaper"] in kind:
            return paper_of(own["inPaper"])
        if "inExperiment" in own and own["inExperiment"] in kind:
            return paper_of(own["inExperiment"])
        return None

    by_src: dict[str, list[tuple[str, str, str]]] = {}
    for s, rel, o in links:
        by_src.setdefault(s, []).append((s, rel, o))
    edges = [(s, rel, o) for s, rel, o in links if s in kind and o in kind]
    edges += [(iri, "type", t) for iri in records for t in types[iri] if t in classes]
    edges += [(c, "subClassOf", p) for c in classes for p in parents.get(c, []) if p in classes]

    def label(iri: str) -> str:
        f = fields.get(iri, {})
        if iri in labels:
            return labels[iri]
        if kind[iri] == "Value" and "number" in f:
            return f"{f['number']:g}" if isinstance(f["number"], float) else str(f["number"])
        if kind[iri] == "Claim":
            return " ".join(str(f[k]) for k in ("subject", "relation", "object") if f.get(k) is not None)
        if kind[iri] == "Comparison" and "delta" in f:
            return f"delta {f['delta']:g}" if isinstance(f["delta"], float) else f"delta {f['delta']}"
        if f.get("name") is not None:
            return str(f["name"])
        return local(iri)

    order = {t: n for n, t in enumerate(DROP_ORDER)}
    shown = sorted(kind, key=lambda i: (order[kind[i]], i), reverse=True)   # kept: the last ones to drop
    omitted: dict[str, int] = {}
    for iri in sorted(kind, key=lambda i: (order[kind[i]], i))[:max(0, len(kind) - limit)]:
        omitted[kind[iri]] = omitted.get(kind[iri], 0) + 1
    keep = set(shown[:limit])
    nodes = [{"id": iri, "type": kind[iri], "label": label(iri), "document": paper_of(iri),
              "types": sorted({labels.get(t, local(t)) for t in types.get(iri, [])}),
              "fields": {k: v for k, v in sorted(fields.get(iri, {}).items()) if not k.startswith("key_") and k != "contextKey"}}
             for iri in sorted(keep)]
    shown_edges = sorted({(s, rel, o) for s, rel, o in edges if s in keep and o in keep})
    return {"nodes": nodes, "edges": [{"src": s, "dst": o, "rel": rel} for s, rel, o in shown_edges],
            "omitted": dict(sorted(omitted.items()))}
