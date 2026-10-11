"""The five provenance queries (milestones-1-2.md, row 2.8; provenance-model.md).

All five run on a run's graph.ttl (agent/prov.py): 1, 2, 3 and 5 are SPARQL; 4 gets the anchors
by SPARQL and re-finds each one in the current corpus with agent.anchor.resolve.

1. KG edge -> claim -> step -> exact passage.
2. Which command and which model call produced a fact (or a claim).
3. All claims from one step or one (sub)agent.
4. Claims whose anchor no longer resolves at its offsets (the file hash changed).
5. Answer facts with no claim behind them.

Each query returns a list of plain dicts, one per result row, ordered.
In the baseline, every claim comes from the attach step, so queries 1-3 end there (`phase`
"attach", `attach_activity` set) and never at the research step where the fact was read.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal

from .anchor import Index, Selector, read_text, resolve

PREFIXES = """
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX oa: <http://www.w3.org/ns/oa#>
PREFIX ours: <urn:thesis-agent:vocab#>
PREFIX dcterms: <http://purl.org/dc/terms/>
"""

STEP = """
    ?step ours:stepId ?step_id ; prov:wasAssociatedWith ?agent .
    ?agent ours:agentId ?agent_id .
    OPTIONAL { ?step ours:taskId ?step_task }
    OPTIONAL { ?step ours:subtype ?step_subtype }
    OPTIONAL { ?step ours:phase ?phase }
    OPTIONAL { ?step ours:command ?command }
    OPTIONAL { ?step dcterms:isPartOf ?attach_activity . ?attach_activity a ours:AttachStep }
"""

PASSAGE = """
    ?claim prov:wasDerivedFrom ?anchor .
    ?anchor a oa:SpecificResource ; oa:hasSource ?source ; oa:hasSelector ?quote_sel, ?pos_sel ;
            ours:sha256 ?sha256 .
    ?source ours:fileName ?file .
    ?quote_sel a oa:TextQuoteSelector ; oa:exact ?exact ; oa:prefix ?prefix ; oa:suffix ?suffix .
    ?pos_sel a oa:TextPositionSelector ; oa:start ?start ; oa:end ?end .
"""

Q1 = PREFIXES + """
SELECT ?edge_id ?claim_id ?origin ?s ?p ?o ?step_task ?step_subtype ?step_id ?agent_id ?phase ?command
       ?attach_activity ?file ?start ?end ?exact ?sha256 WHERE {
    ?edge a ours:KGEdge ; ours:edgeId ?edge_id ; prov:wasDerivedFrom ?claim .
    ?claim a ours:Claim ; ours:claimId ?claim_id ; ours:origin ?origin ; ours:s ?s ; ours:p ?p ; ours:o ?o ;
           prov:wasGeneratedBy ?step .
""" + STEP + PASSAGE + "%s } ORDER BY ?edge_id"

Q2 = PREFIXES + """
SELECT ?fact_id ?claim_id ?origin ?step_task ?step_subtype ?step_id ?agent_id ?phase ?command
       ?attach_activity ?model_call ?model ?model_revision ?prompt_sha256 WHERE {
    ?claim a ours:Claim ; ours:claimId ?claim_id ; ours:origin ?origin ; prov:wasGeneratedBy ?step .
    OPTIONAL { ?fact a ours:AnswerFact ; ours:factId ?fact_id ; prov:wasDerivedFrom ?claim }
""" + STEP + """
    OPTIONAL {
        ?step prov:wasInformedBy? ?call .
        ?call a ours:ModelInvocation ; ours:taskId ?model_call .
        OPTIONAL { ?call ours:model ?model }
        OPTIONAL { ?call ours:modelRevision ?model_revision }
        OPTIONAL { ?call ours:promptSha256 ?prompt_sha256 }
    }
    %s
} ORDER BY ?fact_id ?claim_id"""

Q3 = PREFIXES + """
SELECT ?claim_id ?origin ?s ?p ?o ?step_task ?step_subtype ?step_id ?agent_id ?phase ?command
       ?attach_activity ?file ?start ?end ?exact WHERE {
    ?claim a ours:Claim ; ours:claimId ?claim_id ; ours:origin ?origin ; ours:s ?s ; ours:p ?p ; ours:o ?o ;
           prov:wasGeneratedBy ?step .
""" + STEP + PASSAGE + "%s } ORDER BY ?claim_id"

ANCHORS = PREFIXES + """
SELECT ?claim_id ?file ?start ?end ?exact ?prefix ?suffix ?sha256 WHERE {
    ?claim a ours:Claim ; ours:claimId ?claim_id .
""" + PASSAGE + "} ORDER BY ?claim_id"

Q5 = PREFIXES + """
SELECT ?fact_id ?row_id ?s ?p ?o ?origin ?cited WHERE {
    ?fact a ours:AnswerFact ; ours:factId ?fact_id ; ours:rowId ?row_id ; ours:s ?s ; ours:p ?p ;
          ours:o ?o ; ours:origin ?origin .
    FILTER NOT EXISTS { ?fact prov:wasDerivedFrom ?c . ?c a ours:Claim }
    OPTIONAL { ?fact prov:wasDerivedFrom ?cited }
} ORDER BY ?fact_id ?cited"""


def _py(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Literal):
        return value.toPython()
    return str(value)


def _select(graph: Graph, query: str) -> list[dict[str, Any]]:
    result = graph.query(query)
    names = [str(v) for v in result.vars]
    return [{name: _py(row[name]) for name in names} for row in result]


def _filter(**values: Any) -> str:
    """FILTER clauses for the given variable values (None = no filter)."""
    return " ".join(f"FILTER(?{name} = {Literal(value).n3()})" for name, value in values.items()
                    if value is not None)


def edge_to_passage(graph: Graph, edge: str | None = None) -> list[dict[str, Any]]:
    """Query 1: every KG edge (or one) with its claim, the step that produced it and the passage."""
    return _select(graph, Q1 % _filter(edge_id=edge))


def fact_producers(graph: Graph, fact: str | None = None, claim: str | None = None) -> list[dict[str, Any]]:
    """Query 2: the command and the model call behind each claim of a fact (or of one claim).

    With neither argument: every claim that some answer fact cites.
    """
    where = _filter(fact_id=fact, claim_id=claim)
    if fact is None and claim is None:
        where = "FILTER(BOUND(?fact_id))"
    return _select(graph, Q2 % where)


def claims_from(graph: Graph, step: int | None = None, agent: str | None = None) -> list[dict[str, Any]]:
    """Query 3: claims produced at one step (of one agent, if given), or by one (sub)agent."""
    if step is None and agent is None:
        raise ValueError("query 3 needs a step, an agent, or both")
    return _select(graph, Q3 % _filter(step_id=step, agent_id=agent))


def unresolved_anchors(graph: Graph, corpus: Path, manifest: Path) -> list[dict[str, Any]]:
    """Query 4: claims whose anchor does not resolve at its offsets in today's corpus.

    status `relocated` (file changed, quote found elsewhere), `ambiguous` or `broken`; claims
    whose anchor is still `ok` are left out.
    """
    data = json.loads(Path(manifest).read_text(encoding="utf-8"))
    hashes = {f"{p['id']}.md": p["markdown_sha256"] for p in data["papers"]}
    indexes: dict[str, Index | None] = {}
    out = []
    for row in _select(graph, ANCHORS):
        name = row["file"]
        selector = Selector(file=name, start=int(row["start"]), end=int(row["end"]), exact=row["exact"],
                            prefix=row["prefix"], suffix=row["suffix"], sha256=row["sha256"])
        if name not in indexes:
            path = Path(corpus) / name
            indexes[name] = Index(read_text(path)) if path.is_file() else None
        index = indexes[name]
        base = {"claim_id": row["claim_id"], "file": name, "start": selector.start, "end": selector.end,
                "anchor_sha256": selector.sha256}
        if index is None or hashes.get(name) is None:
            out.append({**base, "status": "broken", "file_sha256": None, "file_matches_manifest": False,
                        "reason": "file missing from the corpus or the manifest", "new_start": None,
                        "new_end": None})
            continue
        res = resolve(selector, index, hashes[name])
        if res.status == "ok":
            continue
        out.append({**base, "status": res.status, "file_sha256": index.sha256,
                    "file_matches_manifest": res.file_matches_manifest, "reason": res.reason,
                    "new_start": res.selector.start if res.selector else None,
                    "new_end": res.selector.end if res.selector else None})
    return out


def unsourced_facts(graph: Graph) -> list[dict[str, Any]]:
    """Query 5: answer facts that no existing claim supports (`cited` lists unknown claim ids)."""
    facts: dict[str, dict[str, Any]] = {}
    for row in _select(graph, Q5):  # one row per cited IRI; rdflib's GROUP_CONCAT fails on unbound values
        cited = row.pop("cited")
        fact = facts.setdefault(row["fact_id"], {**row, "cited": []})
        if cited:
            fact["cited"].append(cited.rsplit("/claim/", 1)[-1])
    return list(facts.values())


QUERIES = {1: edge_to_passage, 2: fact_producers, 3: claims_from, 4: unresolved_anchors, 5: unsourced_facts}
