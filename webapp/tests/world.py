"""A small, complete world for the API tests, built with the agent's own code.

- the D1 corpus (agent/tests/conftest.py write_corpus: p1..p10 and a failed p99);
- two finished runs from agent/tests/runs.py: `research-r1` (claim_on: claims at steps 1, 2, a
  subagent at step 4, a rejected claim at step 5, fact f5 without a claim) and `baseline-r1`
  (claim_off: steps 1-4, then attach steps 5-8, fact f4 "no source found"); both with graph.json
  and graph.ttl, and step 1 of research-r1 with an output file;
- a concept session q01 proposed by a scripted model (brief 1 = the runs' concept, brief 2 a
  table concept), picked or not;
- questions.json with q01 and q02; a draft answer key for q02; score.json for research-r1 and a
  results report.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent import concept_step, kg, prov
from agent.canonical import sha256_hex
from agent.rundir import ORCHESTRATOR, RunDir, utc_now
from agent.tests.conftest import fixture, write_corpus
from agent.tests.runs import Built, baseline_run, research_run
from webapp.settings import Settings

FENCE = "`" * 3
QUESTIONS = {"schema_version": 1, "questions": [
    {"id": "q01", "category": "corpus_wide", "question": "Which benchmarks and datasets do the retrieval-augmented "
     "generation papers in the corpus evaluate on?", "source": "nlp33", "notes": ""},
    {"id": "q02", "category": "corpus_wide", "question": "What kinds of attacks or safety risks do the LLM safety "
     "and red-teaming papers in the corpus evaluate?", "source": "nlp34", "notes": ""},
]}
OUTPUT = "".join(f"p1.md:{n}: deployable LLMs using benchmark datasets like Spider and Bird\n" for n in range(1, 21))
SCORE = {"run_id": "research-r1", "qid": "q01", "condition": "claim_on", "seed": 1234, "exit_status": "submitted",
         "verify_ok": True, "key_version": "v1",
         "rows": {"tp": 3, "fp": 2, "fn": 1, "precision": 0.6, "recall": 0.75, "f1": 0.667},
         "facts": {"strict": {"tp": 2, "fp": 3, "fn": 2, "precision": 0.4, "recall": 0.5, "f1": 0.444},
                   "normalised": {"tp": 3, "fp": 2, "fn": 1, "precision": 0.6, "recall": 0.75, "f1": 0.667},
                   "soft": {"tp": 4, "fp": 1, "fn": 0, "precision": 0.8, "recall": 1.0, "f1": 0.889}},
         "vital_recall": 1.0,
         "support": {"facts": 5, "with_claims": 4, "supports": 3, "partial": 1, "no": 0, "unsourced": 1,
                     "support_share": 0.6},
         "cost": {"steps": 6, "tokens": 10000}}
KEY_DRAFT = {"qid": "q02", "concept_sha256": "0" * 64, "kind": "table", "version": "v1-draft", "reviewed": False,
             "rows": [{"id": "r1", "cells": {"attack": "jailbreak"}, "facts": [
                 {"id": "f1", "s": "p2", "p": "evaluates", "o": "jailbreak", "paper_id": "p2", "quote": "q",
                  "vital": True, "candidate_id": "q02-c000001"}]}], "notes": ""}


class ScriptedConcepts:
    """concept_step's Model protocol: one scripted reply with the given briefs (no LiteLLM)."""

    def __init__(self, briefs: list[dict[str, Any]]) -> None:
        self.settings = {"model": "orch-model", "model_name": ORCHESTRATOR["name"], "revision": ORCHESTRATOR["revision"],
                         "temperature": 0.7, "seed": 1, "max_tokens": 4096, "thinking": False}
        self.content = f"Two readings.\n{FENCE}json\n{json.dumps({'concepts': briefs})}\n{FENCE}"

    def query(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        now = utc_now()
        call = {"prompt_sha256": sha256_hex(json.dumps(messages).encode()), "messages": len(messages),
                "started_at": now, "ended_at": now, "seconds": 0.1,
                "response_sha256": sha256_hex(self.content.encode()), "reasoning_sha256": None,
                "finish_reason": "stop", "usage": {"prompt_tokens": 900, "completion_tokens": 300, "total_tokens": 1200},
                "served_model": "orch-model"}
        return {"role": "assistant", "content": self.content, "extra": {"call": call}}


def briefs() -> list[dict[str, Any]]:
    """Brief 1 is the runs' concept (concept_graph.json, which the harness numbers c1); brief 2 a table."""
    return [{k: v for k, v in fixture(name).items() if k != "id"} for name in ("concept_graph.json", "concept_table.json")]


def propose_q01(concepts: Path, *, pick: int | None = 1) -> Path:
    session, _ = concept_step.propose(concepts, "q01", QUESTIONS["questions"][0]["question"], ScriptedConcepts(briefs()),
                                      temperature=0.7, seed=1, git_commit="c" * 40, base_url="http://mock.invalid/v1")
    if pick:
        concept_step.pick(session.root, pick)
    return session.root


@dataclass
class World:
    root: Path
    corpus: Path
    manifest: Path
    research: Built
    baseline: Built

    @property
    def runs(self) -> Path:
        return self.root / "runs"

    @property
    def settings(self) -> Settings:
        return self.with_settings()

    def copy(self, root: Path) -> World:
        """The same world under `root` (nothing in it names an absolute path); much faster than building."""
        shutil.copytree(self.root, root)
        corpus, manifest = root / "corpus", root / "corpus" / "manifest.json"
        research, baseline = (Built(RunDir(root / "runs" / b.run.run_id), corpus, manifest, b.head)
                              for b in (self.research, self.baseline))
        return World(root, corpus, manifest, research, baseline)

    def with_settings(self, **change: Any) -> Settings:
        return Settings(**({"corpus": self.corpus, "runs": self.runs, "gold": self.root / "gold-data",
                            "concepts": self.root / "concepts", "questions": self.root / "questions.json",
                            "WEBAPP_DIST": self.root / "dist", "WEBAPP_POLL_S": 0.05,
                            "WEBAPP_LIVE_WINDOW_S": 3.0} | change))


def build_world(root: Path, *, pick: int | None = 1) -> World:
    corpus, manifest = write_corpus(root)
    research = research_run(root, corpus, manifest)
    baseline = baseline_run(root, corpus, manifest)
    (research.run.out / "main-1.txt").write_text(OUTPUT, encoding="utf-8")
    for built in (research, baseline):
        kg.write(built.run, manifest)
        prov.write(built.run)
    propose_q01(root / "concepts", pick=pick)
    (root / "questions.json").write_text(json.dumps(QUESTIONS), encoding="utf-8")
    gold = root / "gold-data" / "q02"
    gold.mkdir(parents=True)
    (gold / "key.draft.json").write_text(json.dumps(KEY_DRAFT), encoding="utf-8")
    (gold / "doc.json").write_text(json.dumps({"qid": "q02", "coverage": {"papers": 10, "relevant": 4},
                                               "counts": {"candidates": 7}, "rows": [{"key": "r1"}]}), encoding="utf-8")
    (research.run.root / "score.json").write_text(json.dumps(SCORE), encoding="utf-8")
    (root / "runs" / "report").mkdir()
    (root / "runs" / "report" / "report.json").write_text(json.dumps({"primary": {"p_value": 0.03}}), encoding="utf-8")
    return World(root, corpus, manifest, research, baseline)
