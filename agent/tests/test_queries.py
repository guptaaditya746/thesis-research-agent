from __future__ import annotations

import json

import pytest
from rdflib import Graph

from agent import kg, prov, queries
from agent.anchor import read_text
from agent.canonical import write_json
from agent.cli import main as cli

from .runs import GSM8K, Built, baseline, corpus_env, research, rows  # noqa: F401  (pytest fixtures)


def exported(built: Built) -> Graph:
    kg.write(built.run, built.manifest)
    prov.write(built.run)
    return prov.load(built.run)


def tasks(built: Built, subtype: str) -> dict[tuple[str, int], str]:
    return {(r["agent_id"], r["step_id"]): r["task_id"] for r in rows(built.run.events) if r["subtype"] == subtype}


# --- research run (claim on) ----------------------------------------------------------------------

def test_q1_edge_to_passage(research: Built) -> None:
    g = exported(research)
    result = queries.edge_to_passage(g)
    assert [r["edge_id"] for r in result] == [f"edge-{n:06d}" for n in range(1, 7)]
    tools = tasks(research, "agent_tool")
    for row in result:
        text = read_text(research.corpus / row["file"])
        assert text[row["start"]:row["end"]] == row["exact"]  # the exact passage, at its offsets
        assert row["phase"] == "research" and row["attach_activity"] is None
        assert row["step_task"] == tools[(row["agent_id"], row["step_id"])]
        assert row["step_subtype"] == "agent_tool"
    one = queries.edge_to_passage(g, "edge-000006")
    assert len(one) == 1
    assert (one[0]["claim_id"], one[0]["agent_id"], one[0]["step_id"], one[0]["file"], one[0]["p"]) == \
        ("claim-000006", "sub-01", 4, "p4.md", "proposes")
    assert one[0]["command"].startswith('rg -n "HotpotQA|MegaPairs"')


def test_q2_command_and_model_call_behind_a_fact(research: Built) -> None:
    g = exported(research)
    calls = tasks(research, "ai_model_invocation")
    [row] = queries.fact_producers(g, fact="f3")
    assert (row["claim_id"], row["step_id"], row["agent_id"], row["phase"]) == ("claim-000003", 2, "main", "research")
    assert row["command"].startswith('rg -n "GSM8K|Hanbing"')
    assert row["model_call"] == calls[("main", 2)] and row["model"] == "orch-model"
    assert row["model_revision"] == "017b9c7" and len(row["prompt_sha256"]) == 64
    [sub] = queries.fact_producers(g, fact="f4")
    assert (sub["agent_id"], sub["model_call"], sub["model"]) == ("sub-01", calls[("sub-01", 4)], "sub-model-1")
    everything = queries.fact_producers(g)
    assert [r["fact_id"] for r in everything] == ["f1", "f2", "f3", "f4"]  # f5 has no claim
    [by_claim] = queries.fact_producers(g, claim="claim-000004")  # a claim no fact cites
    assert by_claim["fact_id"] is None and by_claim["model_call"] == calls[("main", 2)]


def test_q3_claims_of_a_step_or_subagent(research: Built) -> None:
    g = exported(research)
    assert [r["claim_id"] for r in queries.claims_from(g, step=1)] == ["claim-000001", "claim-000002"]
    assert [r["claim_id"] for r in queries.claims_from(g, agent="sub-01")] == ["claim-000005", "claim-000006"]
    assert [r["claim_id"] for r in queries.claims_from(g, agent="main")] == \
        ["claim-000001", "claim-000002", "claim-000003", "claim-000004"]
    assert queries.claims_from(g, step=4, agent="main") == []
    assert queries.claims_from(g, step=5) == []  # its only claim was rejected
    with pytest.raises(ValueError):
        queries.claims_from(g)


def test_q4_tampered_corpus(research: Built) -> None:
    g = exported(research)
    assert queries.unresolved_anchors(g, research.corpus, research.manifest) == []
    p5 = research.corpus / GSM8K.file
    p5.write_bytes(read_text(p5).replace("math reasoning using GSM8K", "math reasoning using GSM-8K").encode())
    p6 = research.corpus / "p6.md"
    p6.write_bytes(("Inserted line.\n" + read_text(p6)).encode())
    result = {r["claim_id"]: r for r in queries.unresolved_anchors(g, research.corpus, research.manifest)}
    assert sorted(result) == ["claim-000003", "claim-000005"]
    broken, moved = result["claim-000003"], result["claim-000005"]
    assert (broken["status"], broken["file"], broken["file_matches_manifest"]) == ("broken", "p5.md", False)
    assert broken["file_sha256"] != broken["anchor_sha256"]
    assert (moved["status"], moved["new_start"] - moved["start"]) == ("relocated", len("Inserted line.\n"))
    (research.corpus / "p4.md").unlink()
    gone = {r["claim_id"]: r for r in queries.unresolved_anchors(g, research.corpus, research.manifest)}
    assert gone["claim-000006"]["status"] == "broken" and gone["claim-000006"]["file_sha256"] is None


def test_q5_facts_without_a_claim(research: Built) -> None:
    g = exported(research)
    assert queries.unsourced_facts(g) == [
        {"fact_id": "f5", "row_id": "r5", "s": "p3", "p": "evaluatesOn", "o": "HellaSwag", "origin": "research",
         "cited": []}]
    answer = json.loads(research.run.answer.read_text(encoding="utf-8"))
    answer["rows"][4]["facts"][0]["claims"] = ["claim-000099"]  # cites a claim the broker never issued
    write_json(research.run.answer, answer)
    prov.write(research.run)
    [row] = queries.unsourced_facts(prov.load(research.run))
    assert (row["fact_id"], row["cited"]) == ("f5", ["claim-000099"])


# --- baseline run (claim off, attach step) --------------------------------------------------------

def test_baseline_queries_end_at_the_attach_step(baseline: Built) -> None:
    g = exported(baseline)
    attach = str(prov.Iris(baseline.run.run_id)("activity", "attach"))
    calls = tasks(baseline, "ai_model_invocation")
    q1 = queries.edge_to_passage(g)
    assert len(q1) == 3
    assert all(r["phase"] == "attach" and r["attach_activity"] == attach and r["step_id"] >= 5 for r in q1)
    q2 = queries.fact_producers(g)
    assert [r["fact_id"] for r in q2] == ["f1", "f2", "f3"]
    for row in q2:
        assert row["phase"] == "attach" and row["attach_activity"] == attach
        assert row["model_call"] == calls[("main", row["step_id"])]
    # The research steps that read p1, p5 and p6 produced no claim; the attach steps did.
    assert all(queries.claims_from(g, step=s) == [] for s in (1, 2, 3, 4))
    [at5] = queries.claims_from(g, step=5)
    assert (at5["claim_id"], at5["origin"], at5["phase"]) == ("claim-000001", "attach", "attach")
    assert [r["fact_id"] for r in queries.unsourced_facts(g)] == ["f4"]  # attach: no source found
    assert queries.unresolved_anchors(g, baseline.corpus, baseline.manifest) == []


# --- command line -----------------------------------------------------------------------------------

def test_cli_query(research: Built, capsys: pytest.CaptureFixture[str]) -> None:
    root = str(research.run.root)
    assert cli(["query", "1", root]) == 1
    assert "export-prov" in capsys.readouterr().out
    exported(research)
    assert cli(["query", "1", root, "--edge", "edge-000002"]) == 0
    [line] = capsys.readouterr().out.splitlines()
    assert json.loads(line)["claim_id"] == "claim-000002"
    assert cli(["query", "3", root]) == 1
    assert "needs a step" in capsys.readouterr().out
    assert cli(["query", "3", root, "--agent", "sub-01"]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 2
    assert cli(["query", "4", root, "--corpus", str(research.corpus), "--manifest", str(research.manifest)]) == 0
    assert capsys.readouterr().out == ""
    assert cli(["query", "5", root]) == 0
    assert json.loads(capsys.readouterr().out)["fact_id"] == "f5"
    assert cli(["query", "2", root, "--fact", "f1"]) == 0
    assert json.loads(capsys.readouterr().out)["command"].startswith('rg -n "Spider"')
