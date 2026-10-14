"""Subagents (row 2.12): `spawn` end to end with scripted models for the parent and its subagents.

Everything but the models' HTTP calls is real: the spawn command in the sandbox and its SPAWN_FD
channel, the SpawnService with its two workers (sub-model-1, sub-model-2), each subagent's
sandboxed commands and claims through the broker (in process and as its own process), the
records, verify, graph, PROV export and query 3. A barrier in the scripted sub-models only lets
two subagents through together, so a test that passes ran them at the same time.
"""
from __future__ import annotations

import dataclasses
import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("minisweagent")
pytest.importorskip("litellm")

from rdflib import Literal  # noqa: E402
from rdflib.namespace import PROV  # noqa: E402

from agent import prompts, prov, queries, sandbox, schema  # noqa: E402
from agent.batch import Batch, Manifest, run_state  # noqa: E402
from agent.broker_client import InProcessBroker  # noqa: E402
from agent.cli import main as cli  # noqa: E402
from agent.loop import POSIX_BROKER, LoopSettings, Outcome, SandboxEnvironment, StepCounter, kept_lines  # noqa: E402
from agent.rundir import SUBAGENTS, RunDir  # noqa: E402
from agent.spawn import SpawnJob, SpawnService, SpawnSettings  # noqa: E402
from agent.verify import verify_run  # noqa: E402

from .test_batch import SAMPLE  # noqa: E402
from .test_loop import (CONCEPT, FENCE, Reply, ScriptedModel, bash, claim_cmd, corpus, final, go,  # noqa: E402, F401
                        posix_only, records, row, unique_quote)

SPAWN = SpawnSettings(enabled=True)


class SubModel(ScriptedModel):
    """A scripted sub-model: its records name the worker's sub-model and the subagent's seed."""

    def __init__(self, replies: list[Reply], slot: dict[str, Any], seed: int) -> None:
        super().__init__(replies)
        self.settings |= {"model": slot["alias"], "model_name": slot["name"], "revision": slot["revision"],
                          "seed": seed}
        self.context_tokens = slot["context_tokens"]


class SubModels:
    """The sub_model factory for research_run: each subagent gets the script of its task."""

    def __init__(self, scripts: dict[str, list[Reply]]) -> None:
        self.scripts = scripts
        self.made: dict[str, tuple[str, int, SubModel]] = {}  # agent id -> (sub-model alias, seed, model)

    def __call__(self, job: SpawnJob, slot: dict[str, Any], seed: int) -> SubModel:
        model = SubModel(self.scripts[job.task], slot, seed)
        self.made[job.agent_id] = (slot["alias"], seed, model)
        return model


def summary(text: str) -> str:
    return f"Done.\n{FENCE}json\n{json.dumps({'summary': text})}\n{FENCE}"


def together(barrier: threading.Barrier, reply: str) -> Any:
    """A reply given only when another subagent's model call is in flight too (else the barrier breaks)."""
    def answer(messages: list[dict[str, Any]]) -> str:
        barrier.wait(timeout=30)
        return reply
    return answer


def results_in(text: str) -> list[dict[str, Any]]:
    """The spawn results printed in a command's output, one JSON object per line."""
    return [json.loads(line) for line in text.splitlines() if line.startswith('{"')]


def cite_sub_claims(messages: list[dict[str, Any]]) -> str:
    """The parent's answer: one fact citing every claim its subagents returned."""
    ids = sorted(c["claim_id"] for r in results_in(messages[-1]["content"]) for c in r.get("claims", []))
    return final([row(ids)], "from two subagents")


def of(run: RunDir, subtype: str) -> list[dict[str, Any]]:
    return [r for r in records(run) if r["subtype"] == subtype]


# --- end to end ---------------------------------------------------------------------------------------

@posix_only
@pytest.mark.parametrize("broker", ["inprocess", pytest.param("process", marks=pytest.mark.skipif(
    not POSIX_BROKER, reason="BrokerProcess needs SEQPACKET and SCM_RIGHTS"))])
def test_two_subagents_at_once_and_their_claims_everywhere(tmp_path: Path, corpus: tuple[Path, Path], broker: str,
                                                           capsys: pytest.CaptureFixture[str]) -> None:
    q1, q5 = unique_quote("p1"), unique_quote("p5")
    barrier = threading.Barrier(2)
    subs = SubModels({
        "Find a fact in p1": [together(barrier, bash(claim_cmd(q1))), summary("p1 states a fact (claim in result)")],
        "Find a fact in p5": [together(barrier, bash(claim_cmd(q5, file="p5.md", o="another fact"))),
                              summary("p5 states another fact")],
    })
    command = ('spawn --task "Find a fact in p1" --files p1.md > a.json & '
               'spawn --task "Find a fact in p5" --files p5 > b.json & wait; cat a.json b.json')
    run, outcome, head, model = go(tmp_path, corpus, [bash(command), cite_sub_claims], broker=broker, spawn=SPAWN,
                                   sub_model=subs)
    assert outcome.exit_status == "submitted" and outcome.answer_rows == 1
    # Two subagents, one on each sub-model replica, run at the same time (the barrier let both through).
    assert sorted(subs.made) == ["sub-01", "sub-02"]
    assert sorted(alias for alias, _, _ in subs.made.values()) == ["sub-model-1", "sub-model-2"]
    assert {seed for _, seed, _ in subs.made.values()} == {1234 + 1, 1234 + 2}  # run seed + subagent number
    # What the parent's spawn commands printed: summary, status and the claims each subagent recorded.
    out = results_in((run.out / "step-0001.txt").read_text(encoding="utf-8"))
    assert [(r["ok"], r["status"]) for r in out] == [(True, "submitted")] * 2
    by_task = {r["summary"]: r for r in out}
    first = by_task["p1 states a fact (claim in result)"]
    assert [(c["s"], c["p"], c["o"], c["file"]) for c in first["claims"]] == [("Paper p1", "states", "a fact", "p1.md")]
    assert by_task["p5 states another fact"]["claims"][0]["file"] == "p5.md"
    # The parent's own cost is its budget's: two model calls; the subagents' tokens are counted apart.
    main_calls = [c for c in of(run, "ai_model_invocation") if c["agent_id"] == "main"]
    assert (outcome.steps, outcome.model_calls, outcome.subagents) == (2, 2, 2)
    assert outcome.tokens == sum(c["generated"]["usage"]["total_tokens"] for c in main_calls)
    sub_calls = [c for c in of(run, "ai_model_invocation") if c["agent_id"] != "main"]
    assert outcome.subagent_tokens == sum(c["generated"]["usage"]["total_tokens"] for c in sub_calls) > 0
    # Records: the subagents' carry their own agent id, the parent and the parent's step.
    assert {c["agent_id"] for c in sub_calls} == {"sub-01", "sub-02"}
    for rec in records(run):
        if rec["agent_id"].startswith("sub-"):
            assert rec["source_agent_id"] == "main" and rec["custom_metadata"]["spawned_by_step"] == 1, rec
    claims = of(run, "claim")
    assert sorted(c["agent_id"] for c in claims) == ["sub-01", "sub-02"]
    assert all(c["status"] == "accepted" and c["source_agent_id"] == "main" for c in claims)
    # Step ids are unique in the run: the parent's two steps come before and after its subagents' four.
    steps = [c["step_id"] for c in of(run, "ai_model_invocation")]
    assert len(steps) == len(set(steps)) == 6 and [c["step_id"] for c in main_calls] == [1, 6]
    assert len(list(run.out.iterdir())) == 3  # out/step-NNNN.txt of the three commands, none overwritten
    # Spawn records: started, then returned, pointing at the parent's model call and at each other.
    spawns = of(run, "spawn")
    assert [(s["status"], s["custom_metadata"]["event"]) for s in spawns][:2] == [("started", "start")] * 2
    assert sorted(s["status"] for s in spawns[2:]) == ["finished", "finished"]
    assert all(s["agent_id"] == "main" and s["step_id"] == 1 for s in spawns)
    assert all(s["parent_task_id"] == main_calls[0]["task_id"] for s in spawns[:2])
    starts = {s["generated"]["agent_id"]: s for s in spawns[:2]}
    for back in spawns[2:]:
        start = starts[back["generated"]["agent_id"]]
        assert back["parent_task_id"] == start["task_id"]
        first_call = next(c for c in sub_calls if c["agent_id"] == back["generated"]["agent_id"])
        assert first_call["parent_task_id"] == start["task_id"]  # a subagent's first event points at its spawn
        assert start["generated"]["model"] == subs.made[back["generated"]["agent_id"]][0]
        assert start["used"]["files"] in (["p1.md"], ["p5.md"])  # `p5` named as the broker names it
    # The parent's spawn command: the subagents it started, the longer time limit, none of their claims.
    tool = next(t for t in of(run, "agent_tool") if t["agent_id"] == "main")
    meta = tool["custom_metadata"]
    assert (meta["spawned"], meta["timeout_s"], meta["claims"], meta["claim_step"]) == (["sub-01", "sub-02"], 1800, 0,
                                                                                          False)
    assert tool["task_id"] > spawns[-1]["task_id"]  # written after its subagents returned
    assert "workdir" not in meta and sorted(t["custom_metadata"]["workdir"] for t in of(run, "agent_tool")
                                            if t["agent_id"] != "main") == ["sub/sub-01/scratch", "sub/sub-02/scratch"]
    # result.json as sent; config; the prompts the models saw.
    for back in spawns[2:]:
        assert (run.root / back["generated"]["result_file"]).is_file()
    config = run.load_config()
    assert config["spawn"]["enabled"] and config["spawn"]["command_timeout_s"] == 1800
    assert config["spawn"]["budget"] == {"steps": 15, "tokens": 300_000, "announced": True}
    assert config["spawn"]["models"] == ["sub-model-1", "sub-model-2"] and config["spawn"]["claim"]
    assert "spawn-v2.txt" in config["prompt"]["files"]
    assert sorted(config["spawn"]["prompt"]["files"]) == ["sub-task-v1.txt", "sub-v1.txt"]
    assert schema.check("config", config) == []
    system = model.prompts[0][0]["content"]
    assert "Subagents with spawn:" in system and "15 steps" in system and "30 minutes" in system and "{{" not in system
    sub_prompt = subs.made["sub-01"][2].prompts[0]
    assert sub_prompt[0]["content"].startswith("You are a subagent") and "{{" not in sub_prompt[0]["content"]
    assert "Start with these corpus files: p" in sub_prompt[1]["content"] and CONCEPT["title"] in sub_prompt[1]["content"]
    # verify: the run's total and each agent's cost; graph, PROV and query 3 see sub-01's claim.
    report = verify_run(run, *corpus)
    assert report.ok, report.errors
    s = report.stats
    assert s["subagents"] == 2 and sorted(s["agents"]) == ["main", "sub-01", "sub-02"]
    assert s["tokens"] == outcome.tokens + outcome.subagent_tokens == sum(a["tokens"] for a in s["agents"].values())
    assert s["agents"]["main"]["tokens"] == outcome.tokens and s["agents"]["main"]["claims_accepted"] == 0
    assert s["agents"]["sub-01"]["claims_accepted"] == 1 and s["steps"] == 6
    root, manifest = str(run.root), str(corpus[1])
    assert cli(["verify", root, "--corpus", str(corpus[0])]) == 0
    assert "agent sub-01: steps=2 model_calls=2 commands=1 claims=1 accepted" in capsys.readouterr().out
    assert cli(["graph", root, "--manifest", manifest]) == 0
    graph = json.loads((run.root / "graph.json").read_text(encoding="utf-8"))
    assert sorted(e["agent_id"] for e in graph["edges"]) == ["sub-01", "sub-02"]
    assert cli(["export-prov", root]) == 0
    g = prov.load(run)
    iri = prov.Iris(run.run_id)
    assert (iri("agent", "sub-01"), PROV.actedOnBehalfOf, iri("agent", "main")) in g
    sub01_model = SUBAGENTS[[s["alias"] for s in SUBAGENTS].index(subs.made["sub-01"][0])]
    assert (iri("agent", "sub-01"), prov.OURS.model, Literal(f"{sub01_model['name']}@{sub01_model['revision']}")) in g
    sub01 = queries.claims_from(g, agent="sub-01")
    claim01 = next(c for c in claims if c["agent_id"] == "sub-01")
    assert [(r["claim_id"], r["agent_id"], r["step_subtype"]) for r in sub01] == [
        (claim01["generated"]["claim_id"], "sub-01", "agent_tool")]
    capsys.readouterr()
    assert cli(["query", "3", root, "--agent", "sub-01"]) == 0
    assert [json.loads(line)["agent_id"] for line in capsys.readouterr().out.splitlines()] == ["sub-01"]
    assert cli(["timeline", root]) == 0
    page = (run.root / "timeline.html").read_text(encoding="utf-8")
    assert "spawn start sub-01" in page and "<span class=tag>sub-02</span>" in page


@posix_only
def test_a_third_spawn_waits_for_a_free_sub_model(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    barrier = threading.Barrier(2)
    slow = [together(barrier, bash("sleep 3; echo read")), summary("done")]  # still running when "three" asks
    subs = SubModels({"one": list(slow), "two": list(slow), "three": [bash("echo three"), summary("three done")]})
    command = ('spawn --task one > 1.json & spawn --task two > 2.json & sleep 1.5; '
               'spawn --task three > 3.json & wait; cat 1.json 2.json 3.json')
    run, outcome, _, _ = go(tmp_path, corpus, [bash(command), final([row([])])], spawn=SPAWN, sub_model=subs,
                            condition="claim_off")
    assert outcome.exit_status == "submitted" and outcome.subagents == 3
    assert [r["status"] for r in results_in((run.out / "step-0001.txt").read_text(encoding="utf-8"))] == ["submitted"] * 3
    spawns = of(run, "spawn")
    start = {s["generated"]["agent_id"]: s for s in spawns if s["custom_metadata"]["event"] == "start"}
    back = {s["generated"]["agent_id"]: s for s in spawns if s["custom_metadata"]["event"] == "return"}
    assert sorted(start) == sorted(back) == ["sub-01", "sub-02", "sub-03"]
    # sub-03 started only when one of the first two had returned, on the replica that one freed.
    assert start["sub-03"]["ended_at"] >= min(back["sub-01"]["ended_at"], back["sub-02"]["ended_at"])
    assert start["sub-03"]["custom_metadata"]["queued_seconds"] > 0.1
    intervals = [(start[a]["ended_at"], back[a]["ended_at"]) for a in start]
    assert max(sum(s <= t < e for s, e in intervals) for t, _ in intervals) == 2  # never more than two at once
    # claim_off: no claims in the results, and subagents had no claim command either.
    assert all("claims" not in r for r in results_in((run.out / "step-0001.txt").read_text(encoding="utf-8")))
    assert not run.load_config()["spawn"]["claim"]
    assert verify_run(run, *corpus).ok


@posix_only
def test_refused_requests_and_a_lower_step_budget(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    subs = SubModels({"short": [bash("echo a"), bash("echo b")], "fine": [summary("ok")]})
    command = ('spawn --task x --files p999.md; echo "exit=$?"; spawn --task x --steps 0; echo "exit=$?"; '
               'spawn --task short --steps 1; echo "exit=$?"; spawn --task fine; spawn --task late; echo "exit=$?"')
    settings = dataclasses.replace(SPAWN, max_subagents=2)
    run, outcome, _, _ = go(tmp_path, corpus, [bash(command), final([row([])])], spawn=settings, sub_model=subs)
    assert outcome.exit_status == "submitted"
    out = (run.out / "step-0001.txt").read_text(encoding="utf-8")
    shown = results_in(out)
    assert shown[0] == {"ok": False, "reason": "unknown_file: p999.md"} and "exit=1" in out
    assert shown[1] == {"ok": False, "reason": "bad_request: --steps must be a positive number"}
    # --steps 1: the subagent's budget is one step; it ended at its budget with no summary.
    assert (shown[2]["ok"], shown[2]["status"], shown[2]["summary"], shown[2]["steps"]) == (True, "budget", "", 1)
    assert shown[3]["status"] == "submitted" and shown[3]["summary"] == "ok"
    assert shown[4]["ok"] is False and shown[4]["reason"].startswith("spawn_limit")
    refused = [s for s in of(run, "spawn") if s["status"] == "refused"]
    assert [s["generated"]["reason"].split(":")[0] for s in refused] == ["unknown_file", "bad_request", "spawn_limit"]
    assert all(s["custom_metadata"]["event"] == "refused" and "agent_id" not in s["generated"] for s in refused)
    start = next(s for s in of(run, "spawn") if s["status"] == "started")
    assert start["used"]["steps"] == 1 and start["used"]["steps_requested"] == 1
    assert verify_run(run, *corpus).ok


@posix_only
def test_a_subagent_left_running_is_cancelled_when_the_command_ends(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """No `wait`: the command ends, its subagent's running command is killed and the subagent stops.

    (A spawn left in the background that still holds the command's output keeps the command
    open until it returns, as any background process does: the harness reads output to its end.)
    """
    subs = SubModels({"slow": [bash("sleep 60; echo late"), summary("never")]})
    t0 = time.monotonic()
    run, outcome, _, _ = go(tmp_path, corpus, [bash("spawn --task slow > s.json 2>&1 & sleep 2; echo done"),
                                               final([row([])])], spawn=SPAWN, sub_model=subs)
    assert outcome.exit_status == "submitted" and time.monotonic() - t0 < 30
    back = next(s for s in of(run, "spawn") if s["custom_metadata"]["event"] == "return")
    assert (back["status"], back["generated"]["exit_status"]) == ("cancelled", "cancelled")
    sub_tool = next(t for t in of(run, "agent_tool") if t["agent_id"] == "sub-01")
    assert sub_tool["custom_metadata"]["cleanup"] == "cancelled" and sub_tool["generated"]["exit_code"] == 137
    assert not sub_tool["generated"]["timed_out"]
    parent_tool = next(t for t in of(run, "agent_tool") if t["agent_id"] == "main")
    assert parent_tool["custom_metadata"]["spawned"] == ["sub-01"] and parent_tool["task_id"] > back["task_id"]
    result = json.loads((run.root / back["generated"]["result_file"]).read_text(encoding="utf-8"))
    assert result["ok"] is True and result["status"] == "cancelled"  # it ran: ok, and the status says how it ended
    assert verify_run(run, *corpus).ok


@posix_only
def test_a_subagent_that_fails_after_a_claim(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """Its model fails after one claim: the parent gets ok, status error and the claim (exit 0) and cites
    it; the run is finished for the batch runner (subagent_error is not the run's run_error)."""
    subs = SubModels({"t": [bash(claim_cmd(unique_quote()))]})  # the script ends: its next model call fails
    run, outcome, _, _ = go(tmp_path, corpus, [bash('spawn --task t --files p1.md; echo "exit=$?"'), cite_sub_claims],
                            spawn=SPAWN, sub_model=subs)
    assert outcome.exit_status == "submitted"
    out = (run.out / "step-0001.txt").read_text(encoding="utf-8")
    result = results_in(out)[0]
    assert (result["ok"], result["status"], [c["claim_id"] for c in result["claims"]]) == (True, "error", ["claim-000001"])
    assert "reason" not in result and "exit=0" in out
    assert [r["generated"]["reason"] for r in of(run, "coverage") if r["agent_id"] == "sub-01"] == ["subagent_error"]
    back = next(s for s in of(run, "spawn") if s["custom_metadata"]["event"] == "return")
    assert back["status"] == "error" and back["generated"]["claims"] == ["claim-000001"]
    assert json.loads(run.answer.read_bytes())["rows"][0]["facts"][0]["claims"] == ["claim-000001"]
    assert verify_run(run, *corpus).ok and run_state(run, *corpus) == ("finished", "")


@posix_only
def test_a_request_that_fails_unexpectedly_still_gets_a_reply(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """A file name with a NUL byte makes the corpus lookup raise ValueError: the request is refused
    (record and reply), not dropped with the requester blocked until its time limit."""
    run = RunDir.create(tmp_path / "runs", "x", CONCEPT, corpus_manifest=corpus[1], condition="claim_on",
                        prompt_version="v2", prompt_sha256="a" * 64, temperature=0.7, seed=1, git_commit="c" * 40,
                        agent_root_manifest_sha256="b" * 64)
    broker = InProcessBroker(run.root, *corpus)
    service = SpawnService(run, broker, SPAWN, concept=CONCEPT, corpus=corpus[0], manifest=corpus[1],
                           condition="claim_on", sandbox_mode="unsandboxed", base_url="http://mock.invalid/v1",
                           temperature=0.7, seed=1, loop=LoopSettings(), next_step=StepCounter())
    channel = service.channel(1, None)
    try:
        read_end, write_end = os.pipe()
        body = {"task": "x", "files": [f"{corpus[0]}\x00/p1.md"], "steps": None}
        socket.send_fds(channel.sandbox_end, [json.dumps(body).encode("utf-8")], [write_end])
        os.close(write_end)
        with os.fdopen(read_end, "rb") as pipe:  # EOF once the harness wrote and closed its copy
            reply = json.loads(pipe.read())
    finally:
        channel.sandbox_end.close()
        channel.finish()
        service.close()
        broker.close()
    assert reply["ok"] is False and reply["reason"].startswith("bad_request: ValueError"), reply
    assert [(s["status"], s["generated"]["reason"]) for s in of(run, "spawn")] == [("refused", reply["reason"])]


@posix_only
@pytest.mark.skipif(sandbox.landlock_abi() is None, reason="kernel without Landlock")
def test_spawn_under_landlock(tmp_path: Path, corpus: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """Under Landlock and seccomp the client makes no socket (a pipe goes over the inherited channel), and a
    subagent can claim but not touch its parent's scratch directory."""
    import agent.loop
    code = tmp_path / "agent-code"  # Landlock rules do not hold on WSL's /mnt/c (drvfs): copy the sandbox side
    (code / "bin" / "spawn-only").mkdir(parents=True)
    for name in ("sandbox.py", "claim_client.py", "spawn_client.py", "bin/claim", "bin/spawn", "bin/spawn-only/spawn"):
        (code / name).write_bytes((agent.loop.AGENT_DIR / name).read_bytes())
        (code / name).chmod(0o755)
    monkeypatch.setattr(agent.loop, "AGENT_DIR", code)
    probe = "; touch ../../../scratch/x 2>/dev/null && echo PARENT_WRITABLE || echo PARENT_SCRATCH_CLOSED"
    subs = SubModels({"t": [bash(claim_cmd(unique_quote()) + probe), summary("one fact")]})
    run, outcome, _, _ = go(tmp_path, corpus, [bash("spawn --task t --files p1.md"), cite_sub_claims],
                            sandbox_mode="landlock", spawn=SPAWN, sub_model=subs)
    assert outcome.exit_status == "submitted"
    result = results_in((run.out / "step-0001.txt").read_text(encoding="utf-8"))[0]
    assert result["ok"] and [c["claim_id"] for c in result["claims"]] == ["claim-000001"]
    sub_tool = next(t for t in of(run, "agent_tool") if t["agent_id"] == "sub-01")
    assert "PARENT_SCRATCH_CLOSED" in (run.root / sub_tool["generated"]["output_file"]).read_text(encoding="utf-8")
    assert not (run.scratch / "x").exists() and verify_run(run, *corpus).ok


@posix_only
def test_masking_shortens_a_spawn_result_alike_in_both_conditions(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """An old spawn result keeps its agent id and status (and in claim_on its claim ids), never its summary."""
    settings = LoopSettings(mask_keep=1, mask_keep_tight=1)
    stubs = {}
    for condition in ("claim_on", "claim_off"):
        work = bash(claim_cmd(unique_quote())) if condition == "claim_on" else bash("echo read")
        subs = SubModels({"t": [work, summary("SUMMARY-TEXT " * 200)]})
        run, outcome, _, model = go(tmp_path / condition, corpus, [
            bash("spawn --task t --files p1.md"), bash("echo next"), bash("echo again"), final([row([])])],
            condition=condition, settings=settings, spawn=SPAWN, sub_model=subs)
        assert outcome.exit_status == "submitted"
        assert "SUMMARY-TEXT" in model.prompts[1][3]["content"]  # the next call sees the whole result
        stub = model.prompts[2][3]["content"]  # the call after that: step 1's output is a stub
        assert stub.startswith("[Output of step 1 removed") and "SUMMARY-TEXT" not in stub
        stubs[condition] = json.loads(stub.splitlines()[1])
    assert stubs["claim_off"] == {"agent_id": "sub-01", "status": "submitted"}
    assert stubs["claim_on"] == stubs["claim_off"] | {"claims": ["claim-000001"]}


def test_kept_lines_of_spawn_results_and_claim_replies() -> None:
    result = json.dumps({"agent_id": "sub-02", "claims": [{"claim_id": "claim-000003", "s": 'a "agent_id": "sub-09"'}],
                         "ok": True, "status": "budget", "summary": 'says "claim_id": "claim-000009"'})
    reply = '{"ok": true, "claim_id": "claim-000004"}'
    short = '{"agent_id": "sub-02", "status": "budget", "claims": ["claim-000003"]}'
    assert kept_lines(f"{result}\nnoise\n{reply}") == [short, reply]
    assert kept_lines("a.json:" + result[:40]) == ['{"agent_id": "sub-02", "status": null, "claims": []}']  # cut by the 8 KB cap
    assert kept_lines(json.dumps({"agent_id": "sub-01", "ok": True, "status": "error", "summary": "s"})) == [
        '{"agent_id": "sub-01", "status": "error"}']  # claim_off: no claims key


# --- spawn off --------------------------------------------------------------------------------------------

@posix_only
def test_spawn_off_is_refused_or_not_found(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """Off by default: claim_on runs see a spawn that refuses, claim_off runs none at all."""
    probe = 'spawn --task "read p1"; echo "exit=$?"; echo "fd=${SPAWN_FD:-unset}"'
    run, outcome, _, model = go(tmp_path / "on", corpus, [bash(probe), final([row([])])])
    out = (run.out / "step-0001.txt").read_text(encoding="utf-8")
    assert '"reason": "spawn is not available here' in out and "exit=2" in out and "fd=unset" in out
    assert run.load_config()["spawn"] == {"enabled": False} and not of(run, "spawn")
    assert "spawn" not in model.prompts[0][0]["content"]
    tool = of(run, "agent_tool")[0]
    assert "spawned" not in tool["custom_metadata"] and "timeout_s" not in tool["custom_metadata"]
    run, _, _, _ = go(tmp_path / "off", corpus, [bash("command -v spawn || echo NO_SPAWN"), final([row([])])],
                      condition="claim_off")
    assert (run.out / "step-0001.txt").read_text(encoding="utf-8").strip() == "NO_SPAWN"


@posix_only
def test_baseline_with_spawn_has_no_claim_command(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    probe = "command -v claim || echo NO_CLAIM; command -v spawn"
    run, _, _, model = go(tmp_path, corpus, [bash(probe), final([row([])])], condition="claim_off", spawn=SPAWN,
                          sub_model=SubModels({}))
    out = (run.out / "step-0001.txt").read_text(encoding="utf-8").split()
    assert out[0] == "NO_CLAIM" and out[1].endswith("/bin/spawn-only/spawn")
    system = model.prompts[0][0]["content"]
    assert "Subagents with spawn:" in system and "claim" not in system.lower()
    assert run.load_config()["prompt"]["files"]["spawn-v2-baseline.txt"]


# --- pieces (any OS) --------------------------------------------------------------------------------------

def test_spawn_commands_get_the_longer_time_limit(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    run = RunDir.create(tmp_path / "runs", "x", CONCEPT, corpus_manifest=corpus[1], condition="claim_on",
                        prompt_version="v2", prompt_sha256="a" * 64, temperature=0.7, seed=1, git_commit="c" * 40,
                        agent_root_manifest_sha256="b" * 64)
    service = type("Service", (), {"settings": SPAWN})()
    on = SandboxEnvironment(run, corpus=corpus[0], mode="unsandboxed", claim=True, spawn=service)
    off = SandboxEnvironment(run, corpus=corpus[0], mode="unsandboxed", claim=True)
    for command, limit in (('spawn --task "x"', 1800), ('a=1; x | spawn --task y & wait', 1800), ("echo spawned", 120),
                           ("python3 spawn.py", 120), ("respawn", 120), ("rg spawn-only", 120)):
        assert on.timeout_for(command) == limit, command
        assert off.timeout_for(command) == 120
    assert "--timeout" in on.argv("spawn --task x", 1800) and "1800" in on.argv("spawn --task x", 1800)
    assert on.environment(None, 9)["SPAWN_FD"] == "9" and "SPAWN_FD" not in off.environment(None)
    assert on.config == {"mode": "unsandboxed", "claim": True, "spawn": True} and "spawn" not in off.config


def test_claim_channel_request_with_the_subagent_fields() -> None:
    """The broker's claim_channel op takes a subagent's parent and spawning step, checked like the rest."""
    from agent.broker import Channel, channel_of
    assert channel_of({"step_id": 3}) == Channel(3)
    assert channel_of({"step_id": 4, "agent_id": "sub-01", "source_agent_id": "main", "spawned_by_step": 2}) == Channel(
        4, "sub-01", "research", "main", 2)
    for bad in ({"step_id": "3"}, {"step_id": True}, {"step_id": 3, "spawned_by_step": "2"}, {"step_id": 3, "agent_id": ""},
                {"step_id": 3, "source_agent_id": 7}):
        assert channel_of(bad) is None, bad


def test_spawn_settings_and_config_schema() -> None:
    loop = LoopSettings()
    assert SpawnSettings().config("claim_on", loop) == {"enabled": False} and SpawnSettings().template_vars() == {}
    for condition in ("claim_on", "claim_off"):
        config = SPAWN.config(condition, loop)
        name = "sub-v1.txt" if condition == "claim_on" else "sub-v1-baseline.txt"
        assert config["prompt"]["sha256"] == config["prompt"]["files"][name] and config["claim"] == (condition == "claim_on")
        assert config["loop"]["conclude_decoding"] == "structured_outputs" and config["loop"]["draft_file"] is None
        assert config["loop"]["masking"] == {"keep": 4, "keep_tight": 2, "tight_above_prompt_tokens": 20000}
        assert schema.errors(schema.load("config")["properties"]["spawn"] | {"$defs": schema.load("config")["$defs"]},
                             config) == []
    assert SPAWN.template_vars() == {"spawn_steps": 15, "spawn_tokens": 300_000, "spawn_max": 20, "spawn_concurrent": 2,
                                     "spawn_minutes": 30, "spawn_context": 32_768}
    for bad in ({"max_concurrent": 3}, {"max_concurrent": 0}, {"steps": 0}, {"command_timeout_s": 0}):
        with pytest.raises(ValueError):
            SpawnSettings(enabled=True, **bad)


def test_spawn_prompts() -> None:
    """The spawn block sits before the draft paragraph; the baseline's is the block minus its claim lines."""
    for condition in ("claim_on", "claim_off"):
        plain, spawn = prompts.load("v2", condition), prompts.load("v2", condition, spawn=True)
        block = (prompts.PROMPT_DIR / prompts._for(condition, "spawn-v2")).read_text(encoding="utf-8")
        assert spawn.system == plain.system.replace("\nDraft answer:", "\n" + block + "Draft answer:", 1)
        assert spawn.sha256 == plain.sha256 and set(spawn.files) - set(plain.files) == {prompts._for(condition, "spawn-v2")}
        assert spawn.task == plain.task
    on = (prompts.PROMPT_DIR / "spawn-v2.txt").read_text(encoding="utf-8").splitlines()
    off = (prompts.PROMPT_DIR / "spawn-v2-baseline.txt").read_text(encoding="utf-8").splitlines()
    assert off == [line for line in on if "claim" not in line] and len(off) == len(on) - 1
    assert "claim" not in prompts.load("v2", "claim_off", spawn=True).system.lower()
    with pytest.raises(ValueError, match="spawn needs prompt v2"):
        prompts.load("v1", "claim_on", spawn=True)
    # The subagent's prompts: the baseline is the prompt minus the claim block; the result is a summary.
    sub_on, sub_off = prompts.load_sub("v1", "claim_on"), prompts.load_sub("v1", "claim_off")
    assert prompts.baseline_from(sub_on.system) == sub_off.system and "claim" not in sub_off.system.lower()
    assert sub_on.task == sub_off.task and '{"summary": "..."}' in sub_on.system
    for name in ("spawn-v2.txt", "spawn-v2-baseline.txt", "sub-v1.txt", "sub-v1-baseline.txt", "sub-task-v1.txt"):
        data = (prompts.PROMPT_DIR / name).read_bytes()
        assert b"\r" not in data and b"{%" not in data and b"{#" not in data, name


def test_broker_reasons_are_all_in_the_subagent_prompt() -> None:
    import re
    source = "".join((prompts.PROMPT_DIR.parent / f).read_text(encoding="utf-8") for f in ("broker.py", "anchor.py"))
    reasons = set(re.findall(r'Rejected\(f?"([a-z_]+)', source)) | set(re.findall(r'AnchorError\("([a-z_]+)"', source))
    system = (prompts.PROMPT_DIR / "sub-v1.txt").read_text(encoding="utf-8")
    assert sorted(r for r in reasons if r not in system) == []


def test_batch_manifest_spawn_switch(tmp_path: Path) -> None:
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    assert data["spawn"] == "off"  # the 72 runs keep it off
    for value in ("on", "off"):
        (tmp_path / "m.json").write_text(json.dumps(data | {"spawn": value}), encoding="utf-8")
        batch = Batch(Manifest.load(tmp_path / "m.json"), deadline=None, corpus=tmp_path)
        argv = batch.run_argv(batch.manifest.plan()[0], "x")
        assert argv[argv.index("--spawn") + 1] == value
        assert "--spawn" not in batch.attach_argv(RunDir(tmp_path / "runs" / "x"))
    (tmp_path / "m.json").write_text(json.dumps(data | {"spawn": "maybe"}), encoding="utf-8")
    with pytest.raises(ValueError, match="spawn"):
        Manifest.load(tmp_path / "m.json")


def test_cli_run_spawn_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import agent.loop
    import agent.rundir
    seen: list[dict[str, Any]] = []

    def fake_run(**kw: Any) -> tuple[None, Outcome, dict[str, Any]]:
        seen.append(kw)
        return None, Outcome("submitted", 5, 5, 1_000, 1, "final", subagents=2, subagent_tokens=500), {"head": "h"}

    monkeypatch.setattr(agent.loop, "research_run", fake_run)
    monkeypatch.setattr(agent.rundir, "git_head", lambda repo: "c" * 40)
    monkeypatch.setattr("agent.cli.stop_on_sigterm", lambda: None)
    (tmp_path / "concept.json").write_text(json.dumps(CONCEPT), encoding="utf-8")
    base = ["run", "--concept", str(tmp_path / "concept.json"), "--run-id", "r", "--temperature", "0.7", "--seed", "1",
            "--corpus", str(tmp_path)]
    assert cli(base) == 0 and seen[0]["spawn"] == SpawnSettings()  # off by default
    assert "subagents" not in capsys.readouterr().out
    assert cli([*base, "--spawn", "on"]) == 0 and seen[1]["spawn"] == SpawnSettings(enabled=True)
    assert "subagents=2 run_tokens=1500" in capsys.readouterr().out
    assert cli([*base, "--spawn", "on", "--prompt-version", "v1"]) == 1  # the M1-real prompt has no spawn block
    assert "spawn needs prompt v2" in capsys.readouterr().out and len(seen) == 2
