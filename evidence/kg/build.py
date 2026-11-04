"""Records to graph (W4 task 4.1): the run's items as RDF in the `ev:` vocabulary (evidence/vocab/ev.ttl).

What becomes what:
- a paper -> `ev:Paper`; an `experiment` item -> `ev:Experiment` with one `ev:setting_<field>` literal per setting key;
- a measured value (the pack's role `measured_value`) -> `ev:Value`: `ev:of` its thing, `ev:onMetric` its metric,
  `ev:number`, `ev:inExperiment`. Its experiment is the paper's `experiment` item whose setting for the value's context
  field equals the value's context (or the paper's only one); else an implicit experiment `<paper>/context/<context>`
  holding that one setting. Things and metrics are shared across papers (a thing by its `names.clean` form, a metric by
  its canonical name), so a query can rank or list across papers;
- any two values of one experiment on one metric, of different things -> an `ev:Comparison` (`ev:a`, `ev:b`, `ev:delta`
  = a minus b, `ev:better` by the metric's direction: its `higher_is_better` field; none when unknown or equal);
- `claim` / `link` items -> `ev:Claim` / `ev:Link`;
- a thing or metric whose cleaned name equals a cleaned label of an ontology class gets `rdf:type` that class, and the
  ontology's labels and `rdfs:subClassOf` edges are copied in, so "kind of" is `rdfs:subClassOf*`.

Beyond the vocabulary, a few helper properties in the `kg:` namespace carry what a query needs from a value:
`kg:side` (its thing's side field, e.g. rag / baseline), `kg:position` (where its number sits in the paper),
`kg:inTable` (the number is in a table cell), `kg:context` (with `kg:contextKey`, its `names.clean` form; an experiment setting has `kg:key_<field>` likewise), and on a metric `kg:higherIsBetter`.

Everything is in the default graph and `serialize` sorts the N-Quads, so the same records give the same bytes."""
from __future__ import annotations

import json
from itertools import combinations
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import pyoxigraph as ox

from evidence import names, records, synthesis
from evidence.comparisons import name_of
from evidence.contract import Item, digest
from evidence.vocab import EV

if TYPE_CHECKING:
    from rdflib import Graph

    from evidence.pack import RoleMap
    from evidence.rundir import Paper

R = "https://w3id.org/thesis-ev/r/"
KG = "https://w3id.org/thesis-ev/kg#"
RDF_TYPE = ox.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
RDFS_SUBCLASS = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
XSD = "http://www.w3.org/2001/XMLSchema#"


def ev(local: str) -> ox.NamedNode:
    return ox.NamedNode(EV + local)


def kg(local: str) -> ox.NamedNode:
    return ox.NamedNode(KG + local)


def iri(kind: str, *parts: str) -> ox.NamedNode:
    return ox.NamedNode(R + kind + "/" + "/".join(quote(p, safe="") for p in parts))


def lit(text: Any) -> ox.Literal:
    return ox.Literal(str(text))


def num(x: float) -> ox.Literal:
    return ox.Literal(repr(float(x)), datatype=ox.NamedNode(XSD + "double"))


def flag(x: bool) -> ox.Literal:
    return ox.Literal("true" if x else "false", datatype=ox.NamedNode(XSD + "boolean"))


def setting_property(field: str) -> ox.NamedNode:
    return ev("setting_" + "".join(c if c.isalnum() else "_" for c in field))


def setting_key_property(field: str) -> ox.NamedNode:
    """The property holding the cleaned copy (`names.clean`) of an experiment setting: `kg:key_<field>`."""
    return kg("key_" + "".join(c if c.isalnum() else "_" for c in field))


def _classes(ontology: Graph | None) -> tuple[dict[str, list[str]], list[tuple[str, str, str]]]:
    """Cleaned label -> class IRIs, and the triples (labels and subclass edges of the classes) to copy in."""
    if ontology is None:
        return {}, []
    from rdflib import RDF, RDFS, URIRef
    from rdflib.namespace import OWL
    classes = {s for s in ontology.subjects(RDF.type, None) if isinstance(s, URIRef)
               and ((s, RDF.type, OWL.Class) in ontology or (s, RDF.type, RDFS.Class) in ontology)}
    for a, b in ontology.subject_objects(RDFS.subClassOf):
        classes |= {x for x in (a, b) if isinstance(x, URIRef)}
    by_label: dict[str, list[str]] = {}
    triples: list[tuple[str, str, str]] = []
    for c in sorted(classes):
        for label in ontology.objects(c, RDFS.label):
            by_label.setdefault(names.clean(str(label)), []).append(str(c))
            triples.append((str(c), RDFS_LABEL, str(label)))
        for parent in ontology.objects(c, RDFS.subClassOf):
            if isinstance(parent, URIRef):
                triples.append((str(c), RDFS_SUBCLASS, str(parent)))
    return {k: sorted(set(v)) for k, v in by_label.items()}, triples


def _source(item: Item) -> ox.Literal:
    return lit(json.dumps([{"role": s.role, **s.selector} for s in item.spans], sort_keys=True, separators=(",", ":")))


def _experiment_of(experiments: list[tuple[ox.NamedNode, dict[str, str]]], field: str,
                   context: str | None) -> ox.NamedNode | None:
    if context is not None:
        hit = [e for e, s in experiments if s.get(field) == context]
        if hit:
            return hit[0]
    if len(experiments) == 1 and (context is None or field not in experiments[0][1]):
        return experiments[0][0]
    return None


def build(papers: list[Paper], items: dict[str, list[Item]], roles: RoleMap, ontology: Graph | None) -> ox.Store:
    from evidence.pack import Role
    store = ox.Store()

    def add(s: ox.NamedNode, p: ox.NamedNode, o: Any) -> None:
        store.add(ox.Quad(s, p, o, ox.DefaultGraph()))

    by_label, ontology_triples = _classes(ontology)
    for s, p, o in ontology_triples:
        add(ox.NamedNode(s), ox.NamedNode(p), ox.NamedNode(o) if p == RDFS_SUBCLASS else lit(o))

    def thing_like(kind: str, key: str, label: str, cls: str) -> ox.NamedNode:
        node = iri(kind, key)
        add(node, RDF_TYPE, ev(cls))
        add(node, ev("name"), lit(label))
        for c in by_label.get(names.clean(label), []):
            add(node, RDF_TYPE, ox.NamedNode(c))
        return node

    value_types = set(roles.types_of(Role.VALUE))
    thing_types = set(roles.types_of(Role.COMPARED_THING))
    metric_types = set(roles.types_of(Role.METRIC))
    limitation_types = set(roles.types_of(Role.LIMITATION))
    directions: dict[ox.NamedNode, bool] = {}   # one direction per metric: the first a paper gives
    values_by_exp: dict[ox.NamedNode, list[tuple[ox.NamedNode, ox.NamedNode, ox.NamedNode, float, bool | None]]] = {}
    for paper in sorted(papers, key=lambda p: p.id):
        pnode = iri("paper", paper.id)
        add(pnode, RDF_TYPE, ev("Paper"))
        add(pnode, ev("name"), lit(paper.id))
        mine = sorted(items.get(paper.id, []), key=lambda i: i.item_id)
        by_id = {i.item_id: i for i in mine}
        experiments: list[tuple[ox.NamedNode, dict[str, str]]] = []
        for it in (i for i in mine if i.evidence_type == records.EXPERIMENT):
            node = iri("exp", paper.id, str(it.fields["exp_id"]))
            setting = {str(k): str(v) for k, v in (it.fields.get("setting") or {}).items()}
            add(node, RDF_TYPE, ev("Experiment"))
            add(node, ev("inPaper"), pnode)
            add(node, ev("name"), lit(it.fields.get("label", it.fields["exp_id"])))
            add(node, ev("source"), _source(it))
            for k, v in sorted(setting.items()):
                add(node, setting_property(k), lit(v))
                add(node, setting_key_property(k), lit(names.clean(v)))
            experiments.append((node, setting))
        implicit: set[ox.NamedNode] = set()
        for it in (i for i in mine if i.evidence_type in value_types):
            number = it.fields.get("value")
            if isinstance(number, bool) or not isinstance(number, (int, float)):
                continue
            linked: dict[str, Item] = {}
            for target in it.links.values():
                t = by_id.get(target)
                if t is not None and t.evidence_type in thing_types | metric_types:
                    linked.setdefault("thing" if t.evidence_type in thing_types else "metric", t)
            thing, metric = linked.get("thing"), linked.get("metric")
            tname = name_of(thing, roles)
            mfield = roles.field_or_none(metric.evidence_type, "canonical") if metric else None
            mname = metric.fields.get(mfield) if metric is not None and mfield else None
            mname = mname if mname is not None else name_of(metric, roles)
            if tname is None or mname is None:
                continue
            context_field = roles.context_field(it.evidence_type)
            context = it.fields.get(context_field)
            context = None if context is None else str(context)
            exp = _experiment_of(experiments, context_field, context)
            if exp is None:
                exp = iri("exp", paper.id, "context", context if context is not None else "none")
                if exp not in implicit:
                    implicit.add(exp)
                    add(exp, RDF_TYPE, ev("Experiment"))
                    add(exp, ev("inPaper"), pnode)
                    add(exp, ev("name"), lit(context if context is not None else "none"))
                    if context is not None:
                        add(exp, setting_property(context_field), lit(context))
                        add(exp, setting_key_property(context_field), lit(names.clean(context)))
            tnode = thing_like("thing", names.clean(tname), tname, "Thing")
            mnode = thing_like("metric", str(mname), str(mname), "Metric")
            better = metric.fields.get("higher_is_better") if metric is not None else None
            if isinstance(better, bool):
                directions.setdefault(mnode, better)
                better = directions[mnode]
            vnode = iri("value", it.item_id)
            add(vnode, RDF_TYPE, ev("Value"))
            add(vnode, ev("of"), tnode)
            add(vnode, ev("onMetric"), mnode)
            add(vnode, ev("number"), num(number))
            add(vnode, ev("inExperiment"), exp)
            add(vnode, ev("source"), _source(it))
            add(vnode, kg("position"), ox.Literal(str(synthesis.value_start(it)),
                                                  datatype=ox.NamedNode(XSD + "integer")))
            add(vnode, kg("inTable"), flag(synthesis.in_table(it)))
            side_field = roles.field_or_none(thing.evidence_type, "side") if thing is not None else None
            if side_field and thing is not None and thing.fields.get(side_field) is not None:
                add(vnode, kg("side"), lit(thing.fields[side_field]))
            if context is not None:
                add(vnode, kg("context"), lit(context))
                add(vnode, kg("contextKey"), lit(names.clean(context)))
            values_by_exp.setdefault(exp, []).append(
                (vnode, tnode, mnode, float(number), better if isinstance(better, bool) else None))
        for it in (i for i in mine if i.evidence_type in limitation_types):   # a limitation is a claim of relation "limitation"
            node = iri("claim", it.item_id)
            target = by_id.get(next((t for t in it.links.values() if t in by_id), ""))
            about = name_of(target, roles) if target is not None and target.evidence_type in thing_types else None
            add(node, RDF_TYPE, ev("Claim"))
            add(node, ev("inPaper"), pnode)
            add(node, ev("relation"), lit("limitation"))
            if about is not None:
                add(node, ev("subject"), lit(about))
            if it.fields.get("category") is not None:
                add(node, ev("object"), lit(it.fields["category"]))
            add(node, ev("source"), _source(it))
        for it in (i for i in mine if i.evidence_type == records.CLAIM):
            node = iri("claim", it.item_id)
            f = it.fields
            add(node, RDF_TYPE, ev("Claim"))
            add(node, ev("inPaper"), pnode)
            add(node, ev("subject"), lit(f["subject"]))
            add(node, ev("relation"), lit(f["relation"]))
            for key, prop in (("relation_group", "relationGroup"), ("object", "object"), ("strength", "strength"),
                              ("direction", "direction")):
                if f.get(key) is not None:
                    add(node, ev(prop), lit(f[key]))
            for k, v in sorted((f.get("setting") or {}).items()):
                add(node, setting_property(k), lit(v))
            add(node, ev("source"), _source(it))
        for it in (i for i in mine if i.evidence_type == records.LINK):
            node = iri("link", it.item_id)
            f = it.fields
            add(node, RDF_TYPE, ev("Link"))
            add(node, ev("inPaper"), iri("paper", str(f.get("subject_doc") or paper.id)))
            add(node, ev("relation"), lit(f["relation"]))
            add(node, ev("ref"), lit(f["object_ref"]))
            add(node, ev("outsideSet"), flag(bool(f["outside_set"])))
            if f.get("object_doc"):
                add(node, ev("cites"), iri("paper", str(f["object_doc"])))
            add(node, ev("source"), _source(it))
    for mnode, higher in directions.items():
        add(mnode, kg("higherIsBetter"), flag(higher))
    for exp, vals in values_by_exp.items():
        ordered = sorted(vals, key=lambda v: (v[1].value, v[0].value))
        for (va, ta, ma, xa, da), (vb, tb, mb, xb, db) in combinations(ordered, 2):
            if ma != mb or ta == tb:
                continue
            node = iri("cmp", digest([va.value, vb.value])[:16])
            add(node, RDF_TYPE, ev("Comparison"))
            add(node, ev("a"), va)
            add(node, ev("b"), vb)
            add(node, ev("inExperiment"), exp)
            add(node, ev("delta"), num(round(xa - xb, 6)))
            higher = directions.get(ma)
            if higher is not None and xa != xb:
                add(node, ev("better"), va if (xa > xb) == higher else vb)
    return store


def serialize(store: ox.Store) -> bytes:
    """The store as sorted N-Quads: the same records give the same bytes (`records.nq`)."""
    raw = store.dump(format=ox.RdfFormat.N_QUADS) or b""
    return b"".join(sorted(line + b"\n" for line in raw.splitlines() if line.strip()))
