from __future__ import annotations

import os
import subprocess
import sys

import pytest
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, PROV

from agent import kg, prov
from agent.cli import main as cli
from agent.rundir import RunDir

from .conftest import REPO
from .runs import Built, baseline, corpus_env, research, rows  # noqa: F401  (pytest fixtures)

OA, OURS = prov.OA, prov.OURS


def export(built: Built) -> Graph:
    kg.write(built.run, built.manifest)
    return prov.write(built.run)[1]


def task(built: Built, task_id: str) -> URIRef:
    return prov.Iris(built.run.run_id)("task", task_id)


def claim(built: Built, claim_id: str) -> URIRef:
    return prov.Iris(built.run.run_id)("claim", claim_id)


def test_every_record_is_an_activity_with_its_agent(research: Built) -> None:
    g = export(research)
    records = rows(research.run.events)
    for rec in records:
        act = task(research, rec["task_id"])
        assert (act, RDF.type, PROV.Activity) in g
        assert (act, PROV.wasAssociatedWith, prov.Iris(research.run.run_id)("agent", rec["agent_id"])) in g
        assert (act, OURS.recordHash, Literal(rec["hash"])) in g
    activities = set(g.subjects(RDF.type, PROV.Activity))
    assert all(g.value(a, PROV.wasAssociatedWith) is not None for a in activities)


def test_edge_table(research: Built) -> None:
    g = export(research)
    iri = prov.Iris(research.run.run_id)
    records = rows(research.run.events)
    by_task = {r["task_id"]: r for r in records}
    tool = next(r for r in records if r["subtype"] == "agent_tool" and r["step_id"] == 1)
    call = by_task[tool["parent_task_id"]]
    assert call["subtype"] == "ai_model_invocation"
    # informs
    assert (task(research, tool["task_id"]), PROV.wasInformedBy, task(research, call["task_id"])) in g
    # uses
    assert (task(research, tool["task_id"]), PROV.used, prov.corpus_file("p1.md")) in g
    claims = [r for r in rows(research.run.claims) if r["status"] == "accepted"]
    for rec in claims:
        c = claim(research, rec["generated"]["claim_id"])
        anchor = iri("anchor", rec["generated"]["claim_id"])
        step_tool = next(r for r in records if r["subtype"] == "agent_tool" and r["step_id"] == rec["step_id"]
                         and r["agent_id"] == rec["agent_id"])
        assert (c, PROV.wasGeneratedBy, task(research, step_tool["task_id"])) in g  # produces
        assert (c, PROV.wasDerivedFrom, anchor) in g  # supports
        check = task(research, rec["task_id"])  # checked_by
        assert (c, OURS.checkedBy, check) in g
        assert {(check, RDF.type, PROV.Activity), (check, RDF.type, OURS.ClaimCheck),
                (check, PROV.wasAssociatedWith, iri("agent", "broker")), (check, PROV.used, anchor)} <= set(g)
        sel = rec["used"]["anchor"]
        assert (anchor, OA.hasSource, prov.corpus_file(sel["file"])) in g
        quote, pos = iri("anchor", rec["generated"]["claim_id"], "quote"), iri("anchor", rec["generated"]["claim_id"], "position")
        assert (quote, RDF.type, OA.TextQuoteSelector) in g and (pos, RDF.type, OA.TextPositionSelector) in g
        assert str(g.value(quote, OA.exact)) == sel["exact"]
        assert (int(g.value(pos, OA.start)), int(g.value(pos, OA.end))) == (sel["start"], sel["end"])
        assert str(g.value(anchor, OURS.sha256)) == sel["sha256"]
    # subagent acted on behalf of the agent that spawned it
    assert (iri("agent", "sub-01"), PROV.actedOnBehalfOf, iri("agent", "main")) in g
    # KG edge -> claim
    for n in range(1, 7):
        assert (iri("edge", f"edge-{n:06d}"), PROV.wasDerivedFrom, claim(research, f"claim-{n:06d}")) in g


def test_rejected_claim_is_a_check_without_a_claim(research: Built) -> None:
    g = export(research)
    rejected = [r for r in rows(research.run.claims) if r["status"] == "rejected"]
    assert len(rejected) == 1
    check = task(research, rejected[0]["task_id"])
    assert (check, OURS.reason, Literal("not_found")) in g
    assert (check, OURS.status, Literal("rejected")) in g
    assert g.value(predicate=OURS.checkedBy, object=check) is None


def test_kg_triples_and_answer_facts(research: Built) -> None:
    g = export(research)
    spider = prov.node_iri("entity:spider")
    assert (prov.node_iri("paper:p1"), URIRef("urn:thesis-agent:vocab#evaluatesOn"), spider) in g
    assert (prov.node_iri("paper:p4"), URIRef("https://w3id.org/cskg/ontology#proposes"),
            prov.node_iri("entity:megapairs")) in g
    iri = prov.Iris(research.run.run_id)
    assert (iri("fact", "f1"), PROV.wasDerivedFrom, claim(research, "claim-000001")) in g
    assert g.value(iri("fact", "f5"), PROV.wasDerivedFrom) is None


def test_answer_was_generated_by_its_final_answer_call(research: Built, baseline: Built) -> None:
    """The answer links to the main agent's model call marked final_answer, also after an attach step."""
    for built in (research, baseline):
        g = export(built)
        records = rows(built.run.events)
        final = [r for r in records if r["subtype"] == "ai_model_invocation" and r["custom_metadata"].get("final_answer")]
        assert len(final) == 1
        answer = prov.Iris(built.run.run_id)("answer")
        assert (answer, OURS.answerSource, Literal("final_answer")) in g
        assert list(g.objects(answer, PROV.wasGeneratedBy)) == [task(built, final[0]["task_id"])]
    assert prov.answer_source([]) == ("unknown", None)


def test_attach_claims_come_from_the_attach_activity(baseline: Built) -> None:
    g = export(baseline)
    iri = prov.Iris(baseline.run.run_id)
    attach = iri("activity", "attach")
    assert (attach, RDF.type, OURS.AttachStep) in g and (attach, RDF.type, PROV.Activity) in g
    for rec in rows(baseline.run.claims):
        c = claim(baseline, rec["generated"]["claim_id"])
        assert (c, PROV.wasInfluencedBy, attach) in g
        step = g.value(c, PROV.wasGeneratedBy)
        assert (step, DCTERMS.isPartOf, attach) in g and (step, OURS.phase, Literal("attach")) in g
    research_steps = [task(baseline, r["task_id"]) for r in rows(baseline.run.events) if r["step_id"] <= 4]
    assert all((s, OURS.phase, Literal("research")) in g for s in research_steps)


def test_export_is_deterministic(research: Built) -> None:
    export(research)
    ttl = research.run.root / prov.TTL_FILE
    first = ttl.read_bytes()
    assert b"\r\n" not in first
    prov.write(research.run)
    assert ttl.read_bytes() == first
    for seed in ("0", "12345"):  # a fresh interpreter with another hash seed writes the same bytes
        env = {**os.environ, "PYTHONHASHSEED": seed}
        subprocess.run([sys.executable, "-m", "agent.cli", "export-prov", str(research.run.root)],
                       check=True, cwd=REPO, env=env, capture_output=True)
        assert ttl.read_bytes() == first
    assert isomorphic(prov.load(research.run), prov.build(research.run))


def test_broken_chain_or_missing_graph_refused(research: Built) -> None:
    with pytest.raises(FileNotFoundError, match="agent graph"):
        prov.build(research.run)
    kg.write(research.run, research.manifest)
    events = research.run.events.read_text(encoding="utf-8").replace("rg -n", "rg -l", 1)
    research.run.events.write_bytes(events.encode("utf-8"))
    with pytest.raises(ValueError, match="broken chain"):
        prov.build(research.run)


def test_cli_export_prov(research: Built, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli(["export-prov", str(research.run.root)]) == 1
    assert "agent graph" in capsys.readouterr().out
    assert cli(["graph", str(research.run.root), "--manifest", str(research.manifest)]) == 0
    assert cli(["export-prov", str(research.run.root)]) == 0
    assert "PASS triples=" in capsys.readouterr().out
    assert RunDir(research.run.root).validate(complete=True) == []
