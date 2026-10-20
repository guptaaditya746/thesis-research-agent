"""Two realistic finished runs for the graph, PROV-O and query tests (rows 2.6-2.8).

Built before the main loop (1.8) and the attach step (2.5); test_attach.py runs the real attach
step and the same queries. These builders drive the real broker (InProcessBroker) as those do: a model call, then the command it emitted (with
`parent_task_id` pointing at the call, LEDGER `informs`), claims sent over the step's claim channel
while the command runs, and a final answer.json that validates against the concept.

- `research_run`: claim on. The main agent claims at steps 1 and 2, spawns `sub-01` at step 3,
  which claims at its step 4; step 5 has a rejected claim. The answer has one fact with no claim.
- `baseline_run`: claim off. Steps 1-3 read the corpus without claiming, step 4 answers; then the
  attach step (steps 5-8, one per fact) finds a quote per fact and claims it with
  origin "attach", or answers "no source found" (fact f4).

The broker has no `attach` record subtype, so the attach step's model calls and commands are
ordinary records with `custom_metadata.origin = "attach"` (the same key the broker sets on attach
claims); agent/prov.py groups them into one attach activity.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from agent import claim_client
from agent.broker_client import InProcessBroker
from jsonio import sha256_hex, write_json
from agent.concept import concept_sha256, validate_answer
from agent.rundir import RunDir

from .conftest import fixture, write_corpus
from .test_rundir import SETTINGS

CONCEPT = "concept_graph.json"


@dataclass(frozen=True)
class Quote:
    file: str
    text: str


# Quotes from the D1 papers as write_corpus names them (p1 = 2025-acl-long-1031, p3 = -625,
# p4 = -935, p5 = -999, p6 = 2025-emnlp-main-1032). Each occurs once in its file.
SPIDER_BIRD = Quote("p1.md", "deployable LLMs using benchmark datasets like Spider and Bird")
AUTHOR = Quote("p1.md", "Hanbing Liu 1 * , Haoyang Li")
GSM8K = Quote("p5.md", "math reasoning using GSM8K")
HOTPOTQA = Quote("p6.md", "and HotpotQA (Yang et al")
MEGAPAIRS = Quote("p4.md", "MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval")
INVENTED = Quote("p3.md", "we evaluate on HellaSwag with exact match")  # not in the paper


@dataclass
class Built:
    run: RunDir
    corpus: Path
    manifest: Path
    head: dict[str, Any]


class Driver:
    """What the main loop does per step, against the real broker core."""

    def __init__(self, run: RunDir, corpus: Path, manifest: Path) -> None:
        self.broker = InProcessBroker(run.root, corpus, manifest)
        self.calls = 0

    def model_call(self, step: int, agent: str = "main", **meta: Any) -> str:
        self.calls += 1
        model = "orch-model" if agent == "main" else "sub-model-1"
        reply = self.broker.record({
            "subtype": "ai_model_invocation", "step_id": step, "agent_id": agent,
            "source_agent_id": None if agent == "main" else "main",
            "used": {"prompt_sha256": sha256_hex(f"prompt {agent} {step}".encode()), "model": model,
                     "revision": "017b9c7" if agent == "main" else "5a5a776", "temperature": 0.7, "seed": 7},
            "generated": {"response_sha256": sha256_hex(f"response {agent} {step}".encode()),
                          "usage": {"prompt_tokens": 1000 + 100 * step, "completion_tokens": 80}},
            "custom_metadata": meta,
        })
        return reply["task_id"]

    def command(self, step: int, parent: str, command: str, files: list[str], agent: str = "main",
                claims: list[tuple[str, str, Any, Quote]] = (), origin: str = "research",
                **meta: Any) -> list[dict[str, Any]]:
        """Run one command: claims go over the step's channel, then the agent_tool record."""
        replies = []
        if origin != "research":
            meta = {"origin": origin, **meta}
        if claims:
            sock = self.broker.claim_channel(step, agent_id=agent, origin=origin)
            with sock:
                for s, p, o, quote in claims:
                    replies.append(claim_client.submit(sock, {"s": s, "p": p, "o": o, "file": quote.file,
                                                              "quote": quote.text}))
        self.broker.record({
            "subtype": "agent_tool", "step_id": step, "agent_id": agent, "parent_task_id": parent,
            "source_agent_id": None if agent == "main" else "main",
            "used": {"command": command, "files_read": files},
            "generated": {"output_sha256": sha256_hex(command.encode()), "output_file": f"out/{agent}-{step}.txt"},
            "custom_metadata": meta,
        })
        return replies

    def spawn(self, step: int, parent: str, child: str, task: str) -> None:
        self.broker.record({"subtype": "spawn", "step_id": step, "parent_task_id": parent,
                            "used": {"task": task}, "generated": {"agent_id": child}})

    def close(self) -> dict[str, Any]:
        return self.broker.close()


def _new_run(tmp: Path, run_id: str, condition: str, corpus: Path, manifest: Path) -> RunDir:
    settings = {**SETTINGS, "condition": condition}
    return RunDir.create(tmp / "runs", run_id, fixture(CONCEPT), corpus_manifest=manifest, **settings)


def _answer(run: RunDir, rows: list[dict[str, Any]]) -> None:
    concept = run.load_concept()
    answer = {"concept_sha256": concept_sha256(concept), "kind": "graph", "rows": rows}
    problems = validate_answer(answer, concept)
    assert not problems, problems
    write_json(run.answer, answer)


def _row(n: int, paper: str, dataset: str, facts: list[dict[str, Any]]) -> dict[str, Any]:
    return {"id": f"r{n}", "source": paper, "source_type": "Paper", "predicate": "evaluatesOn",
            "target": dataset, "target_type": "Dataset", "attributes": {"metric": None}, "facts": facts}


def _fact(n: int, s: str, o: str, claims: list[str], origin: str) -> dict[str, Any]:
    return {"id": f"f{n}", "s": s, "p": "evaluatesOn", "o": o, "claims": claims, "origin": origin}


def _accepted(replies: list[dict[str, Any]]) -> list[str]:
    assert all(r["ok"] for r in replies), replies
    return [r["claim_id"] for r in replies]


def research_run(tmp: Path, corpus: Path, manifest: Path, run_id: str = "research-r1") -> Built:
    run = _new_run(tmp, run_id, "claim_on", corpus, manifest)
    d = Driver(run, corpus, manifest)
    call = d.model_call(1)
    c1, c2 = _accepted(d.command(1, call, 'rg -n "Spider" $CORPUS/p1.md', ["p1.md"], claims=[
        ("p1", "evaluatesOn", "Spider", SPIDER_BIRD), ("p1", "evaluatesOn", "BIRD", SPIDER_BIRD)]))
    call = d.model_call(2)
    c3, c4 = _accepted(d.command(2, call, 'rg -n "GSM8K|Hanbing" $CORPUS/p5.md $CORPUS/p1.md',
                                 ["p5.md", "p1.md"], claims=[
        ("p5", "evaluates on", "GSM8K", GSM8K), ("p1", "authored by", "Hanbing Liu", AUTHOR)]))
    call = d.model_call(3)
    d.spawn(3, call, "sub-01", "Find the datasets of p4 and p6")
    sub_call = d.model_call(4, agent="sub-01")
    c5, c6 = _accepted(d.command(4, sub_call, 'rg -n "HotpotQA|MegaPairs" $CORPUS/p4.md $CORPUS/p6.md',
                                 ["p4.md", "p6.md"], agent="sub-01", claims=[
        ("p6", "evaluatesOn", "HotpotQA", HOTPOTQA), ("p4", "proposes", "MegaPairs", MEGAPAIRS)]))
    call = d.model_call(5)
    rejected = d.command(5, call, "sed -n 1,40p $CORPUS/p3.md", ["p3.md"], claims=[
        ("p3", "evaluatesOn", "HellaSwag", INVENTED)])
    assert rejected == [{"ok": False, "reason": "not_found"}]
    d.model_call(6, final_answer=True)
    head = d.close()
    _answer(run, [
        _row(1, "p1", "Spider", [_fact(1, "p1", "Spider", [c1], "research")]),
        _row(2, "p1", "BIRD", [_fact(2, "p1", "BIRD", [c2], "research")]),
        _row(3, "p5", "GSM8K", [_fact(3, "p5", "GSM8K", [c3], "research")]),
        _row(4, "p6", "HotpotQA", [_fact(4, "p6", "HotpotQA", [c5], "research")]),
        _row(5, "p3", "HellaSwag", [_fact(5, "p3", "HellaSwag", [], "research")]),  # no claim behind it
    ])
    assert (c4, c6) == ("claim-000004", "claim-000006")
    return Built(run, corpus, manifest, head)


def baseline_run(tmp: Path, corpus: Path, manifest: Path, run_id: str = "baseline-r1") -> Built:
    run = _new_run(tmp, run_id, "claim_off", corpus, manifest)
    d = Driver(run, corpus, manifest)
    for step, (command, files) in enumerate([
        ('rg -n "Spider|Bird" $CORPUS/p1.md', ["p1.md"]),
        ('rg -n "GSM8K" $CORPUS/p5.md', ["p5.md"]),
        ('rg -n "HotpotQA" $CORPUS/p6.md $CORPUS/p3.md', ["p6.md", "p3.md"]),
    ], 1):
        d.command(step, d.model_call(step), command, files)
    d.model_call(4, final_answer=True)
    # Attach step (2.5): one model call and one command per answer fact.
    facts = [("f1", "p1", "Spider", SPIDER_BIRD), ("f2", "p5", "GSM8K", GSM8K),
             ("f3", "p6", "HotpotQA", HOTPOTQA), ("f4", "p3", "HellaSwag", None)]
    ids: dict[str, list[str]] = {}
    for step, (fact, s, o, quote) in enumerate(facts, 5):
        call = d.model_call(step, origin="attach", fact_id=fact)
        claims = [(s, "evaluatesOn", o, quote)] if quote else []
        file = quote.file if quote else "p3.md"
        ids[fact] = _accepted(d.command(step, call, f'rg -n "{o}" $CORPUS/{file}', [file], claims=claims,
                                        origin="attach", fact_id=fact))
    head = d.close()
    _answer(run, [
        _row(1, "p1", "Spider", [_fact(1, "p1", "Spider", ids["f1"], "attach")]),
        _row(2, "p5", "GSM8K", [_fact(2, "p5", "GSM8K", ids["f2"], "attach")]),
        _row(3, "p6", "HotpotQA", [_fact(3, "p6", "HotpotQA", ids["f3"], "attach")]),
        _row(4, "p3", "HellaSwag", [_fact(4, "p3", "HellaSwag", [], "attach")]),  # no source found
    ])
    return Built(run, corpus, manifest, head)


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# --- pytest fixtures (import them into a test module) ----------------------------------------------

@pytest.fixture
def corpus_env(tmp_path: Path) -> tuple[Path, Path]:
    return write_corpus(tmp_path)


@pytest.fixture
def research(tmp_path: Path, corpus_env: tuple[Path, Path]) -> Built:
    return research_run(tmp_path, *corpus_env)


@pytest.fixture
def baseline(tmp_path: Path, corpus_env: tuple[Path, Path]) -> Built:
    return baseline_run(tmp_path, *corpus_env)
