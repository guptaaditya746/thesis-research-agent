"""What the Workbench dataset pane shows: papers, the seed table, the folder tree and file text. Read-only; everything comes from the files under data/seed."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from rdflib import Graph

from evqa.paths import REPO, SEED, domain_dir
from evqa.seed import pfview
from evqa.seed.check import full_graph
from evqa.seed.rdf import query as locked_query

# Who makes each file (shown as a tag in the folder tree).
MADE_BY = {"blueprint.yaml": "we", "glue.ttl": "we", "shapes.ttl": "we", "names.json": "LLM + code",
           "seed.ttl": "code", "check.json": "code", "mesh-subset.ttl": "downloaded", "qudt-subset.ttl": "downloaded",
           "sources.json": "code", "idea_sparse.md": "code", "experimental_log.md": "code",
           "writer_log.jsonl": "LLM log", "manifest.json": "code"}
WHAT = {"blueprint.yaml": "Hand-written design: papers, doses, weeks, measures and the effect model for values.",
        "names.json": "Made-up drug names: what the LLM proposed and how code checked each against MeSH and ChEBI.",
        "seed.ttl": "The truth in RDF: one ex:Result per fact. Built by code from the blueprint and the names.",
        "check.json": "S1 checks: SHACL shapes, name clashes, split overlap.",
        "glue.ttl": "Our only hand-written schema; the rest is reused (SOSA, QUDT, PROV, SKOS).",
        "shapes.ttl": "SHACL rules every seed must pass.",
        "mesh-subset.ttl": "The MeSH terms the seed links to, with their other names.",
        "qudt-subset.ttl": "The QUDT units the seed uses, with conversion factors.",
        "sources.json": "Which vocab downloads the subsets came from (URL, sha256)."}

ROWS = """
PREFIX ex: <https://w3id.org/evqa/seed#>
PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX qudt: <http://qudt.org/schema/qudt/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?r ?paper ?split ?subject ?comparator ?measure ?context ?dose ?doseUnit ?time ?timeUnit ?stat ?value ?unit
       ?placement WHERE {
  ?r a ex:Result ; ex:reportedIn ?p ; ex:subject/skos:prefLabel ?subject ;
     sosa:observedProperty/skos:prefLabel ?measure ; sosa:hasFeatureOfInterest/skos:prefLabel ?context ;
     ex:statistic/skos:prefLabel ?stat ; sosa:hasResult [ qudt:numericValue ?value ; qudt:unit ?unit ] ;
     ex:placement ?placement .
  ?p ex:split ?split .
  BIND(STRAFTER(STR(?p), "/data/") AS ?paper)
  OPTIONAL { ?r ex:comparator/skos:prefLabel ?comparator }
  OPTIONAL { ?r ex:condition/ex:setting [ qudt:numericValue ?dose ; qudt:unit ?doseUnit ] }
  OPTIONAL { ?r ex:atTime [ qudt:numericValue ?time ; qudt:unit ?timeUnit ] }
} ORDER BY ?r"""


def local(iri: Any) -> str:
    return str(iri).rsplit("/", 1)[-1].rsplit("#", 1)[-1]


@lru_cache(maxsize=8)
def _graph(domain: str, stamp: float) -> Graph:
    return full_graph(domain)


def graph_of(domain: str) -> Graph:
    return _graph(domain, (domain_dir(domain) / "seed.ttl").stat().st_mtime)


def unit_symbols(g: Graph) -> dict[str, str]:
    q = "PREFIX qudt: <http://qudt.org/schema/qudt/> SELECT ?u ?s WHERE { ?u qudt:symbol ?s }"
    return {str(r.u): str(r.s) for r in locked_query(g, q)}


def overview(domain: str) -> dict[str, Any]:
    if pfview.is_pf(domain):
        return pfview.overview(domain)
    g = graph_of(domain)
    sym = unit_symbols(g)
    rows = [{"id": local(r.r), "paper": str(r.paper), "split": str(r.split), "subject": str(r.subject),
             "comparator": str(r.comparator) if r.comparator else None, "measure": str(r.measure),
             "context": str(r.context),
             "condition": f"{r.dose.toPython():g} {sym.get(str(r.doseUnit), local(r.doseUnit))}" if r.dose else None,
             "time": f"{r.time.toPython():g} {sym.get(str(r.timeUnit), local(r.timeUnit))}" if r.time else None,
             "statistic": str(r.stat), "value": str(r.value), "unit": sym.get(str(r.unit), local(r.unit)),
             "placement": str(r.placement)} for r in locked_query(g, ROWS)]
    pq = """PREFIX ex: <https://w3id.org/evqa/seed#> PREFIX dcterms: <http://purl.org/dc/terms/>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            SELECT ?p ?title ?role ?split ?kind WHERE { ?p a ex:Paper ; dcterms:title ?title ; ex:role ?role ;
            ex:split ?split ; ex:evidenceKind/skos:prefLabel ?kind } ORDER BY ?p"""
    papers = [{"id": local(r.p), "title": str(r.title), "role": str(r.role), "split": str(r.split),
               "kind": str(r.kind), "rows": sum(1 for x in rows if x["paper"] == local(r.p))} for r in locked_query(g, pq)]
    check_file = domain_dir(domain) / "check.json"
    return {"domain": domain, "papers": papers, "rows": rows,
            "check": json.loads(check_file.read_text(encoding="utf-8")) if check_file.is_file() else None}


def tree() -> list[dict[str, Any]]:
    """Every file under data/seed (no hidden files), with who makes it and what it is."""
    out = []
    for path in sorted(SEED.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            rel = path.relative_to(REPO).as_posix()
            out.append({"path": rel, "bytes": path.stat().st_size, "made_by": MADE_BY.get(path.name, ""),
                        "what": WHAT.get(path.name, "")})
    return out


def read_file(rel: str, limit: int = 400_000) -> dict[str, Any]:
    allowed = {f["path"] for f in tree()}
    if rel not in allowed:
        raise KeyError(rel)
    path: Path = REPO / rel
    text = path.read_text(encoding="utf-8")
    return {"path": rel, "text": text[:limit], "truncated": len(text) > limit, "made_by": MADE_BY.get(path.name, ""),
            "what": WHAT.get(path.name, "")}
