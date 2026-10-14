"""Attach step (row 2.5) end to end with a scripted model: a claim_off run, then attach, verify, the
knowledge graph, the PROV-O export and the provenance queries (rows 2.6-2.8) on the real records."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("minisweagent")
pytest.importorskip("litellm")

from rdflib import Literal  # noqa: E402
from rdflib.namespace import PROV  # noqa: E402

import litellm  # noqa: E402

from agent import kg, prov, queries  # noqa: E402
from agent.attach import ATTACH_FILE, RESULT_SCHEMA, AttachError, attach_run, attach_state, load_prompt  # noqa: E402
from agent.canonical import file_sha256  # noqa: E402
from agent.chain import verify  # noqa: E402
from agent.cli import main as cli  # noqa: E402
from agent.prompts import PROMPT_DIR  # noqa: E402
from agent.rundir import RunDir  # noqa: E402
from agent.verify import verify_run  # noqa: E402

from .test_loop import (FENCE, ScriptedModel, bash, claim_cmd, corpus, final, go, posix_only,  # noqa: E402,F401
                        records, unique_quote)

BUDGET = {"steps": 4, "tokens": 400_000, "announced": True}


def result(**block: Any) -> str:
    return f"Result.\n{FENCE}json\n{json.dumps(block)}\n{FENCE}"


def fact(fid: str, o: str) -> dict[str, Any]:
    return {"id": fid, "s": "Paper p1", "p": "states", "o": o}


def answer_rows() -> list[dict[str, Any]]:
    cells = {"author": "Ann Lee", "first_author_papers": 1, "papers": ["p1"]}
    return [{"id": "r1", "cells": cells, "facts": [fact("f1", "a fact"), fact("f2", "fact two")]},
            {"id": "r2", "cells": cells, "facts": [fact("f3", "fact three")]},
            {"id": "r3", "cells": cells, "facts": [fact("f4", "fact four")]}]


def baseline(tmp_path: Path, corpus: tuple[Path, Path]) -> RunDir:
    run, outcome, _, _ = go(tmp_path, corpus, [bash('rg -c "the" "$CORPUS/p1.md"'), final(answer_rows())],
                            condition="claim_off")
    assert outcome.exit_status == "submitted" and attach_state(run) == "pending"
    return run


def attach_script(q1: str, q2: str) -> list[str]:
    return [
        bash(claim_cmd(q1, "p1.md", "a fact")),                     # f1: step 3, claim-000001
        result(claim_id="claim-000001"),                            # step 4: attached
        bash(claim_cmd(q2, "p2.md", "a wrong object")),             # f2: step 5, claim-000002 (wrong o)
        result(claim_id="claim-000002"),                            # step 6: refused, s/p/o differ
        bash(claim_cmd(q2, "p2.md", "fact two")),                   # step 7, claim-000003
        result(claim_id="claim-000003"),                            # step 8: attached
        bash('rg -c "fact three" "$CORPUS/p3.md"'),                 # f3: step 9
        result(no_source="no paper states fact three"),             # step 10
        bash("echo 1"), result(claim_id="claim-000001"), bash("echo 3"), bash("echo 4"),  # f4: steps 11-14
        "Still looking.\nNot done yet.\nOne more search maybe.\nHmm.",  # step 15: conclude reply, unparsed
    ]


@posix_only
def test_attach_end_to_end(tmp_path: Path, corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    run = baseline(tmp_path, corpus)
    research_answer = run.answer.read_bytes()
    head_before = verify(run.events, run.claims).head
    q1, q2 = unique_quote("p1"), unique_quote("p2")
    model = ScriptedModel(attach_script(q1, q2))
    summary = attach_run(run.root, *corpus, model=model, sandbox_mode="unsandboxed", broker="inprocess", budget=BUDGET)
    capsys.readouterr()

    # Per fact: one quote or "no source found".
    got = {f["fact_id"]: (f["status"], f["claim_id"], f["reason"]) for f in summary["facts"]}
    assert got == {"f1": ("attached", "claim-000001", ""), "f2": ("attached", "claim-000003", ""),
                   "f3": ("no_source", None, "no paper states fact three"), "f4": ("no_source", None, "budget")}
    assert (summary["attached"], summary["no_source"], summary["first_step"], summary["last_step"]) == (2, 2, 3, 15)
    answer = json.loads(run.answer.read_text(encoding="utf-8"))
    facts = {f["id"]: f for r in answer["rows"] for f in r["facts"]}
    assert {k: (f["claims"], f["origin"]) for k, f in facts.items()} == {
        "f1": (["claim-000001"], "attach"), "f2": (["claim-000003"], "attach"), "f3": ([], "attach"),
        "f4": ([], "attach")}
    assert (run.root / "answer.research.json").read_bytes() == research_answer
    assert summary["answer_research_sha256"] == file_sha256(run.root / "answer.research.json")
    assert summary["answer_sha256"] == file_sha256(run.answer)

    # config.json: the attach step's own prompt hash (the run's version, v2) and per-fact budget.
    config = run.load_config()["attach"]
    assert config["prompt"]["sha256"] == file_sha256(PROMPT_DIR / "attach-v2.txt") == load_prompt("v2").sha256
    assert config["prompt"]["version"] == "v2" and config["conclude_decoding"] == "structured_outputs"
    assert config["budget_per_fact"] == BUDGET and config["first_step"] == 3 and config["sandbox"] == "unsandboxed"
    assert run.validate(complete=True) == []
    assert [f["how"] for f in summary["facts"]] == ["result", "result", "", ""] and summary["attached_from_claim"] == 0
    # Only the conclude reply (f4, step 15) was decoded under the result schema.
    assert [i for i, k in enumerate(model.kwargs) if k] == [12]
    assert model.kwargs[12]["extra_body"]["structured_outputs"] == {"json": RESULT_SCHEMA}

    # The model: a fresh conversation per fact, the budget announced, the fact's s/p/o given.
    systems = [p[0]["content"] for p in model.prompts]
    assert "Budget for each fact: 4 steps" in systems[0] and len(set(systems)) == 1
    starts = [i for i, p in enumerate(model.prompts) if len(p) == 2]
    assert starts == [0, 2, 6, 8]
    assert '{"s": "Paper p1", "p": "states", "o": "fact two"}' in model.prompts[2][1]["content"]
    assert "Fact f2 (2 of 4)" in model.prompts[2][1]["content"]
    assert "records s/p/o" in model.prompts[4][-1]["content"]
    assert "is not a claim accepted for this fact" in model.prompts[10][-1]["content"]  # f1's claim, cited for f4
    assert "Budget for this fact used up" in model.prompts[12][-1]["content"]

    # Records: one chain continued from the run; every attach record carries origin attach and the fact.
    report = verify(run.events, run.claims)
    assert report.ok and report.claims == 3
    recs = records(run)
    research, attach = recs[:3], recs[3:]
    assert verify(run.events, run.claims).records == len(recs) and research[-1]["hash"] == head_before
    assert all(r["custom_metadata"]["origin"] == "attach" for r in attach)
    # Harness records name the fact; claims (written by the broker) reach it through their step.
    assert all(r["custom_metadata"]["fact_id"] for r in attach if r["subtype"] != "claim")
    assert all(r["custom_metadata"]["origin"] == "research" for r in research)
    claims = [r for r in attach if r["subtype"] == "claim"]
    assert [(c["step_id"], c["status"], c["generated"].get("claim_id")) for c in claims] == [
        (3, "accepted", "claim-000001"), (5, "accepted", "claim-000002"), (7, "accepted", "claim-000003")]
    tools = {r["step_id"]: r for r in attach if r["subtype"] == "agent_tool"}
    assert sorted(tools) == [3, 5, 7, 9, 11, 13, 14]
    assert tools[3]["custom_metadata"]["claim_step"] and not tools[9]["custom_metadata"]["claim_step"]
    coverage = [(r["step_id"], r["generated"]["reason"], r["custom_metadata"]["fact_id"]) for r in attach
                if r["subtype"] == "coverage"]
    assert coverage == [(6, "invalid_attach_result", "f2"), (10, "no_source_found", "f3"),
                        (12, "invalid_attach_result", "f4"), (15, "unparsed", "f4"), (15, "no_source_found", "f4")]
    calls = [r for r in attach if r["subtype"] == "ai_model_invocation"]
    assert [c["custom_metadata"]["phase"] for c in calls][-2:] == ["attach", "conclude"]
    assert {c["used"]["seed"] for c in calls} == {1234}

    # verify: passes, and reports cost with and without the attach step.
    result_ = verify_run(run, *corpus)
    assert result_.ok, result_.errors
    s = result_.stats
    assert s["attach"]["model_calls"] == 13 and s["attach"]["commands"] == 7 and s["attach"]["claims_accepted"] == 3
    assert s["without_attach"]["model_calls"] == 2 and s["without_attach"]["commands"] == 1
    assert s["attach"]["tokens"] + s["without_attach"]["tokens"] == s["tokens"]
    assert summary["cost"]["tokens"] == s["attach"]["tokens"]
    assert cli(["verify", str(run.root), "--corpus", str(corpus[0])]) == 0
    out = capsys.readouterr().out
    assert "attach step: steps=13 model_calls=13 commands=7 claims=3 accepted / 0 rejected" in out
    assert f"without attach: steps=2 tokens={s['without_attach']['tokens']}" in out
    pairs = [json.loads(line) for line in (run.root / "pairs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(p["fact_id"], p["claim_id"], p["origin"]) for p in pairs] == [
        ("f1", "claim-000001", "attach"), ("f2", "claim-000003", "attach"), ("f3", None, "attach"),
        ("f4", None, "attach")]
    assert " ".join(pairs[1]["quote"].split()) == q2

    # Graph, PROV-O, queries: in the baseline everything ends at the attach step.
    kg.write(run, corpus[1])
    prov.write(run)
    g = prov.load(run)
    iri = prov.Iris(run.run_id)
    attach_activity = iri("activity", "attach")
    by_claim = {c["generated"]["claim_id"]: c for c in claims}
    for claim_id, rec in by_claim.items():
        node = iri("claim", claim_id)
        assert (node, PROV.wasGeneratedBy, iri("task", tools[rec["step_id"]]["task_id"])) in g  # its command
        assert (node, PROV.wasInfluencedBy, attach_activity) in g
    q1 = queries.edge_to_passage(g)
    assert [r["claim_id"] for r in q1] == ["claim-000001", "claim-000002", "claim-000003"]
    for row in q1:
        assert row["phase"] == "attach" and row["attach_activity"] == str(attach_activity)
        assert row["step_subtype"] == "agent_tool" and "| claim" in row["command"] and row["origin"] == "attach"
    q2 = queries.fact_producers(g)
    assert [(r["fact_id"], r["claim_id"], r["step_id"]) for r in q2] == [("f1", "claim-000001", 3),
                                                                          ("f2", "claim-000003", 7)]
    for row in q2:
        assert row["phase"] == "attach" and row["attach_activity"] == str(attach_activity)
        assert row["model_call"] == tools[row["step_id"]]["parent_task_id"]
    assert all(queries.claims_from(g, step=s_) == [] for s_ in (1, 2))  # the research steps made no claim
    assert [r["claim_id"] for r in queries.claims_from(g, step=7)] == ["claim-000003"]
    assert [(r["fact_id"], r["origin"]) for r in queries.unsourced_facts(g)] == [("f3", "attach"), ("f4", "attach")]
    assert queries.unresolved_anchors(g, *corpus) == []
    assert (iri("fact", "f3"), prov.OURS.origin, Literal("attach")) in g
    # answer.json is the attach step's; the research answer it was derived from is the final-answer call's.
    final_call = next(r for r in research if r["subtype"] == "ai_model_invocation" and r["custom_metadata"]["final_answer"])
    assert list(g.objects(iri("answer"), PROV.wasGeneratedBy)) == [attach_activity]
    assert (iri("answer"), PROV.wasDerivedFrom, iri("answer-research")) in g
    assert list(g.objects(iri("answer-research"), PROV.wasGeneratedBy)) == [iri("task", final_call["task_id"])]
    assert (iri("answer-research"), prov.OURS.sha256, Literal(summary["answer_research_sha256"])) in g
    assert (attach_activity, PROV.used, iri("answer-research")) in g
    assert {str(o) for o in g.objects(None, prov.OURS.answerSource)} == {"final_answer"}

    # Run once only.
    with pytest.raises(AttachError, match="already done"):
        attach_run(run.root, *corpus, model=ScriptedModel([]), sandbox_mode="unsandboxed", broker="inprocess")
    assert (run.root / ATTACH_FILE).is_file()


@posix_only
def test_attach_through_the_broker_process(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    from agent.loop import POSIX_BROKER
    if not POSIX_BROKER:
        pytest.skip("BrokerProcess needs SEQPACKET and SCM_RIGHTS")
    run = baseline(tmp_path, corpus)
    q1 = unique_quote("p1")
    replies = [bash(claim_cmd(q1, "p1.md", "a fact")), result(claim_id="claim-000001")] + \
        [result(no_source="not looked for")] * 3
    summary = attach_run(run.root, *corpus, model=ScriptedModel(replies), sandbox_mode="unsandboxed", broker="process")
    assert summary["attached"] == 1 and summary["no_source"] == 3
    assert verify_run(run, *corpus).ok and summary["chain_head"] == verify(run.events, run.claims).head


@posix_only
def test_attach_refuses_claim_on_and_runs_without_answer(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    run, _, _, _ = go(tmp_path, corpus, [final([])], run_id="on")
    with pytest.raises(AttachError, match="claim_on"):
        attach_run(run.root, *corpus, model=ScriptedModel([]), sandbox_mode="unsandboxed", broker="inprocess")
    off = RunDir.create(tmp_path / "runs", "off", json.loads(run.concept.read_text(encoding="utf-8")),
                        corpus_manifest=corpus[1], **{**run.load_config()["sampling"], "condition": "claim_off",
                                                      "prompt_version": "v1", "prompt_sha256": "a" * 64,
                                                      "agent_root_manifest_sha256": "b" * 64, "git_commit": "c" * 40})
    with pytest.raises(AttachError, match="no answer.json"):
        attach_run(off.root, *corpus, model=ScriptedModel([]), sandbox_mode="unsandboxed", broker="inprocess")


@posix_only
def test_a_cut_attach_step_is_not_resumed(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    run = baseline(tmp_path, corpus)
    replies: list[Any] = [result(no_source="none")]  # then the script runs out: the model call fails
    with pytest.raises(IndexError):
        attach_run(run.root, *corpus, model=ScriptedModel(replies), sandbox_mode="unsandboxed", broker="inprocess")
    assert attach_state(run) == "cut" and not (run.root / ATTACH_FILE).exists()
    assert verify(run.events, run.claims).ok  # the chain is whole up to the cut
    assert "attach: the attach step started but did not finish (no attach.json)" in verify_run(run, *corpus).errors
    with pytest.raises(AttachError, match="started and cut"):
        attach_run(run.root, *corpus, model=ScriptedModel([]), sandbox_mode="unsandboxed", broker="inprocess")


def tool_call(command: str) -> str:
    """How Qwen3.8 replied in M1-real when asked to conclude (a command, not the result)."""
    return f"<tool_call>\n<function=bash>\n<parameter=command>\n{command}\n</parameter>\n</function>\n</tool_call>"


@posix_only
def test_attach_concludes_under_the_schema_and_from_claims(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """1.13 for the attach step: conclude replies decoded under RESULT_SCHEMA (a refused schema falls back to
    free decoding), and a fact left without a result gets its own matching claim, the last if several."""
    run = baseline(tmp_path, corpus)
    q1, q2 = unique_quote("p1"), unique_quote("p2")
    refused = litellm.exceptions.BadRequestError("xgrammar: unsupported pattern", "orch-model", "openai")
    model = ScriptedModel([
        bash(claim_cmd(q1, "p1.md", "a fact")), bash("echo 1"), '{"claim_id": "claim-000001"}',  # f1: steps 3-5
        bash(claim_cmd(q2, "p2.md", "fact two")), bash(claim_cmd(q2, "p2.md", "fact two")),     # f2: steps 6, 7
        refused, tool_call("ls"),                                                                  # f2: steps 8, 9
        result(no_source="nothing states it"),                                                     # f3: step 10
        bash("echo 1"), bash("echo 2"), tool_call("ls"),                                           # f4: steps 11-13
    ])
    budget = {"steps": 2, "tokens": 400_000, "announced": True}
    summary = attach_run(run.root, *corpus, model=model, sandbox_mode="unsandboxed", broker="inprocess", budget=budget)
    got = {f["fact_id"]: (f["status"], f["claim_id"], f["reason"], f["how"]) for f in summary["facts"]}
    assert got == {"f1": ("attached", "claim-000001", "", "result"), "f2": ("attached", "claim-000003", "", "claim"),
                   "f3": ("no_source", None, "nothing states it", ""), "f4": ("no_source", None, "budget", "")}
    assert (summary["attached"], summary["attached_from_claim"]) == (2, 1)
    # Decoding: guided at f1's and f2's conclusion; free after the refusal, for the rest of the step.
    guided = [i for i, k in enumerate(model.kwargs) if "structured_outputs" in k.get("extra_body", {})]
    assert guided == [2, 5] and model.kwargs[2]["extra_body"]["structured_outputs"] == {"json": RESULT_SCHEMA}
    assert model.prompts[2][-1]["content"].startswith("Budget for this fact used up. Reply now with the result alone, "
                                                      "as one JSON object")
    assert model.prompts[5] == model.prompts[6]  # asked again, without the schema
    assert model.prompts[10][-1]["content"].startswith("Budget for this fact used up. Reply now with your reasoning")
    attach = [r for r in records(run) if r["custom_metadata"].get("origin") == "attach"]
    calls = {r["step_id"]: r for r in attach if r["subtype"] == "ai_model_invocation"}
    assert calls[5]["generated"]["parse"] == "guided_answer" and calls[5]["used"]["decoding"] == "structured_outputs"
    assert calls[8]["status"] == "failed" and calls[8]["generated"] == {"error": "guided_decoding_rejected"}
    assert calls[9]["used"]["decoding"] == "free" and calls[9]["generated"]["parse"] == "lenient_tool_call"
    coverage = [(r["step_id"], r["generated"]["reason"], r["custom_metadata"]["fact_id"]) for r in attach
                if r["subtype"] == "coverage"]
    assert coverage == [(8, "guided_decoding_rejected", "f2"), (9, "command_not_run", "f2"), (9, "attach_from_claim", "f2"),
                        (10, "no_source_found", "f3"), (13, "command_not_run", "f4"), (13, "no_source_found", "f4")]
    taken = next(r for r in attach if r["subtype"] == "coverage" and r["generated"]["reason"] == "attach_from_claim")
    assert taken["generated"]["detail"] == {"row_id": "r1", "claim_id": "claim-000003",
                                            "candidates": ["claim-000002", "claim-000003"], "why": "budget"}
    answer = json.loads(run.answer.read_text(encoding="utf-8"))
    assert [f["claims"] for r in answer["rows"] for f in r["facts"]] == [["claim-000001"], ["claim-000003"], [], []]
    assert verify_run(run, *corpus).ok


@posix_only
def test_attach_of_a_v1_run_is_v1(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """A prompt v1 run (M1-real) attaches with attach-v1 and free decoding, as the M1-real attach did."""
    run, outcome, _, _ = go(tmp_path, corpus, [final(answer_rows())], condition="claim_off", prompt_version="v1")
    assert outcome.exit_status == "submitted"
    model = ScriptedModel([result(no_source="not looked for")] * 4)
    attach_run(run.root, *corpus, model=model, sandbox_mode="unsandboxed", broker="inprocess")
    config = run.load_config()["attach"]
    assert config["prompt"]["version"] == "v1" and config["prompt"]["sha256"] == load_prompt("v1").sha256
    assert config["conclude_decoding"] == "free" and model.kwargs == [{}] * 4
    assert "(p1.md, p2.md, ...)" in model.prompts[0][0]["content"]
    with pytest.raises(AttachError, match="no attach prompt for version v9"):
        attach_run(go(tmp_path, corpus, [final(answer_rows())], run_id="r2", condition="claim_off")[0].root, *corpus,
                   model=ScriptedModel([]), sandbox_mode="unsandboxed", broker="inprocess", prompt_version="v9")


def test_attach_prompt_v2_describes_the_corpus_like_prompt_v2() -> None:
    """The attach step of a v2 run sees v2's corpus description and claim rules, verbatim (not v1's p1.md, p2.md)."""
    assert b"\r" not in (PROMPT_DIR / "attach-v2.txt").read_bytes()
    v2 = (PROMPT_DIR / "system-v2.txt").read_text(encoding="utf-8").splitlines()
    attach = (PROMPT_DIR / "attach-v2.txt").read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(v2) if line.startswith("- Copy the quote"))
    end = next(i for i, line in enumerate(v2) if "corpus_file_hash_mismatch" in line)
    rules = v2[start:end + 1]
    a = attach.index(rules[0])
    assert attach[a:a + len(rules)] == rules
    assert attach[0] == v2[0]  # the same corpus, file names, shell, tools and limits
    text = "\n".join(attach)
    assert "(p1.md, p2.md, ...)" not in text and "2025-acl-long-892.md" in text and "result alone, as one JSON object" in text
    prompt = load_prompt("v2")
    assert prompt.task == load_prompt("v1").task and "{{steps}}" in prompt.system


def test_attach_prompt_quotes_like_prompt_v1() -> None:
    """The attach step quotes under the same rules as the claim_on run: the rules and reasons are v1's, verbatim."""
    for name in ("attach-v1.txt", "attach-task-v1.txt"):
        assert b"\r" not in (PROMPT_DIR / name).read_bytes()
    v1 = (PROMPT_DIR / "system-v1.txt").read_text(encoding="utf-8").splitlines()
    attach = (PROMPT_DIR / "attach-v1.txt").read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(v1) if line.startswith("- Copy the quote"))
    end = next(i for i, line in enumerate(v1) if "corpus_file_hash_mismatch" in line)
    rules = v1[start:end + 1]
    a = attach.index(rules[0])
    assert attach[a:a + len(rules)] == rules
    assert attach[:3] == v1[:3]  # the same shell, tools and limits
    prompt = load_prompt("v1")
    assert set(prompt.files) == {"attach-v1.txt", "attach-task-v1.txt"} and prompt.sha256 == prompt.files["attach-v1.txt"]
    assert "{{steps}}" in prompt.system and "{{spo_json}}" in prompt.task
