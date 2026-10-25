"""PROV-O export of an evidence run (contract section 7): run directory -> prov.ttl (Turtle, rdflib).

- Each extractor call is a prov:Activity that `used` the document (an entity named by its sha256) and the
  protocol, and `wasAssociatedWith` its extractor, a prov:SoftwareAgent carrying its id, version, kind and
  code and config hashes.
- Each merged evidence item is a prov:Entity `wasGeneratedBy` the merge activity of its document and type,
  which `wasInformedBy` the calls whose results it merged (the item `wasInfluencedBy` each call that found
  it); the item is `wasAttributedTo` every extractor
  that found it and `wasDerivedFrom` its passages: oa:SpecificResource on the document with an
  oa:TextQuoteSelector and an oa:TextPositionSelector (agent/prov.py's pattern). PROV allows one
  generating activity per entity, so the calls are linked through the merge, not as generators.
- The answer is a prov:Entity `wasGeneratedBy` the synthesis activity and `wasDerivedFrom` every item it
  counted, so a number in the answer walks back to the table cell it came from.
- The funnel (Part D): a screening call is an `extractor_call` event like any other, so it is exported as a
  prov:Activity that `used` the document and `wasAssociatedWith` its extractor with no special case; the
  `screen` decision event is an activity that `used` the document, `wasAssociatedWith` the extractor that
  decided, and carries `ev:relevant` and `ev:reason`. The `completeness` decision needs no triple of its
  own: it is a pure function of the merged items the merge activities already generated, so its event is
  exported as a plain activity (subtype, times) like every other record of the chain.

The chain is verified first; a broken chain is not exported. IRIs depend on the run id and the record,
item and document ids only, so the same run exports the same triples.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV

from agent.chain import verify

from .rundir import EVENTS_FILE, EVIDENCE_FILE, PROV_FILE, RUN_FILE, read_json, read_lines

ROOT = "urn:thesis-evidence:"
EV = Namespace("urn:thesis-evidence:vocab#")
OA = Namespace("http://www.w3.org/ns/oa#")


def _iri(*parts: str) -> URIRef:
    return URIRef(ROOT + "/".join(quote(p, safe="-") for p in parts))


def build(run_dir: Path | str) -> Graph:
    run_dir = Path(run_dir)
    record = read_json(run_dir / RUN_FILE)
    report = verify(run_dir / EVENTS_FILE, head=record.get("chain_head"))
    if not report.ok:
        raise ValueError(f"refusing to export a broken chain: {report.errors}")
    run_id = record["run_id"]
    g = Graph(bind_namespaces="core")
    for prefix, ns in (("prov", PROV), ("oa", OA), ("ev", EV), ("dcterms", DCTERMS), ("xsd", XSD), ("rdfs", RDFS)):
        g.bind(prefix, ns)

    def act(task_id: str) -> URIRef:
        return _iri("run", run_id, task_id)

    protocol = _iri("protocol", record["protocol"]["id"], record["protocol"]["sha256"])
    g.add((protocol, RDF.type, PROV.Entity))
    g.add((protocol, RDF.type, EV.Protocol))
    g.add((protocol, EV.sha256, Literal(record["protocol"]["sha256"])))
    run = _iri("run", run_id)
    g.add((run, RDF.type, PROV.Activity))
    g.add((run, EV.mode, Literal(record["mode"])))
    g.add((run, EV.chainHead, Literal(report.head)))
    g.add((run, PROV.used, protocol))
    for ext_id, spec in record.get("extractor_specs", {}).items():
        agent = _iri("extractor", ext_id)
        g.add((agent, RDF.type, PROV.SoftwareAgent))
        g.add((agent, RDFS.label, Literal(ext_id)))
        for key, prop in (("name", EV.name), ("version", EV.version), ("kind", EV.kind), ("code_sha256", EV.codeSha256),
                          ("config_sha256", EV.configSha256), ("determinism", EV.determinism)):
            g.add((agent, prop, Literal(spec[key])))
    documents: dict[str, URIRef] = {}
    merges: dict[tuple[str, str], URIRef] = {}
    for event in read_lines(run_dir / EVENTS_FILE):
        node = act(event["task_id"])
        meta = event["custom_metadata"]
        g.add((node, RDF.type, PROV.Activity))
        g.add((node, EV.subtype, Literal(event["subtype"])))
        g.add((node, DCTERMS.isPartOf, run))
        g.add((node, PROV.startedAtTime, Literal(event["started_at"], datatype=XSD.dateTime)))
        g.add((node, PROV.endedAtTime, Literal(event["ended_at"], datatype=XSD.dateTime)))
        if event["subtype"] in ("locate", "extractor_call", "screen"):
            doc = _iri("document", meta["document"], event["used"][0])
            documents[meta["document"]] = doc
            g.add((doc, RDF.type, PROV.Entity))
            g.add((doc, EV.sha256, Literal(event["used"][0])))
            g.add((node, PROV.used, doc))
        if event["subtype"] == "screen":
            g.add((node, EV.relevant, Literal(bool(meta["relevant"]))))
            g.add((node, EV.reason, Literal(meta["reason"])))
            if meta.get("extractor"):
                g.add((node, PROV.wasAssociatedWith, _iri("extractor", meta["extractor"])))
            for call in meta.get("calls") or []:
                g.add((node, PROV.wasInformedBy, act(call)))
        if event["subtype"] == "extractor_call":
            g.add((node, PROV.used, protocol))
            g.add((node, PROV.wasAssociatedWith, _iri("extractor", event["agent_id"])))
            g.add((node, EV.status, Literal(event["status"])))
            g.add((node, EV.taskSha256, Literal(meta["task_sha256"])))
            g.add((node, EV.outputSha256, Literal(meta["output_sha256"])))
            for ctx_item in event["used"][2:]:
                g.add((node, PROV.used, _iri("item", ctx_item)))
        if event["subtype"] == "merge":
            merges[(meta["document"], meta["evidence_type"])] = node
            for item_id, calls in meta["sources"].items():
                for call in calls:
                    g.add((node, PROV.wasInformedBy, act(call)))
                    g.add((_iri("item", item_id), PROV.wasInfluencedBy, act(call)))  # the calls that found it
        if event["subtype"] == "synthesis":
            answer = _iri("run", run_id, "answer")
            g.add((answer, RDF.type, PROV.Entity))
            g.add((answer, RDF.type, EV.Answer))
            g.add((answer, PROV.wasGeneratedBy, node))
            if "label" in meta:     # effect answers only; the other kinds have no label
                g.add((answer, EV.label, Literal(meta["label"])))
            g.add((answer, EV.sha256, Literal(meta["answer_sha256"])))
            for item_id in event["used"]:
                g.add((node, PROV.used, _iri("item", item_id)))
                g.add((answer, PROV.wasDerivedFrom, _iri("item", item_id)))
    for item in read_lines(run_dir / EVIDENCE_FILE):
        _item(g, item, documents, merges)
    return g


def _item(g: Graph, item: dict[str, Any], documents: dict[str, URIRef], merges: dict[tuple[str, str], URIRef]) -> None:
    node = _iri("item", item["item_id"])
    g.add((node, RDF.type, PROV.Entity))
    g.add((node, EV.evidenceType, Literal(item["evidence_type"])))
    for name, value in sorted(item["fields"].items()):
        if value is not None:
            g.add((node, EV[f"field_{name}"], Literal(value)))
    for name, target in sorted(item["links"].items()):
        g.add((node, EV[f"link_{name}"], _iri("item", target)))
    for ext in item.get("found_by", []):
        g.add((node, PROV.wasAttributedTo, _iri("extractor", ext)))
    by_sha = {str(iri).rsplit("/", 1)[-1]: d for d, iri in documents.items()}
    doc_id = by_sha.get(item["spans"][0]["selector"]["sha256"])
    if doc_id is not None and (doc_id, item["evidence_type"]) in merges:
        g.add((node, PROV.wasGeneratedBy, merges[(doc_id, item["evidence_type"])]))
    for s in item["spans"]:
        sel = s["selector"]
        passage = _iri("passage", sel["sha256"], f"{sel['start']}-{sel['end']}")
        g.add((node, PROV.wasDerivedFrom, passage))
        g.add((passage, RDF.type, PROV.Entity))
        g.add((passage, RDF.type, OA.SpecificResource))
        g.add((passage, EV.role, Literal(s["role"])))
        if doc_id is not None:
            g.add((passage, OA.hasSource, documents[doc_id]))
        quote_sel, pos_sel = URIRef(f"{passage}/quote"), URIRef(f"{passage}/position")
        g.add((passage, OA.hasSelector, quote_sel))
        g.add((passage, OA.hasSelector, pos_sel))
        g.add((quote_sel, RDF.type, OA.TextQuoteSelector))
        g.add((quote_sel, OA.exact, Literal(sel["exact"])))
        g.add((quote_sel, OA.prefix, Literal(sel["prefix"])))
        g.add((quote_sel, OA.suffix, Literal(sel["suffix"])))
        g.add((pos_sel, RDF.type, OA.TextPositionSelector))
        g.add((pos_sel, OA.start, Literal(sel["start"], datatype=XSD.nonNegativeInteger)))
        g.add((pos_sel, OA.end, Literal(sel["end"], datatype=XSD.nonNegativeInteger)))


def export(run_dir: Path | str) -> Path:
    path = Path(run_dir) / PROV_FILE
    path.write_bytes(build(run_dir).serialize(format="turtle").encode("utf-8"))
    return path
