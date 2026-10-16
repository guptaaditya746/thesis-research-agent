"""Test fixtures for the review (C2).

- `build(tmp)`: a gold working directory for question q01 as C1 will write it (contract in
  docs/earlier-work.md, "Gold files, answer key, judge, scores": candidates, pool, strata, triage, screening, doc.json), on the D1
  papers (agent/tests/conftest.py write_corpus), with the graph concept of agent/tests/fixtures.
- `FakeArgilla`: an in-memory stand-in for the Argilla v2 client. Datasets are created from the real
  `argilla_io.settings` (built with the fake as client), and every logged record is checked against the
  dataset's Spec the way the server and SDK would: known keys only, no question name as a key (it would
  become a suggestion), every field a non-empty string, metadata of the declared type. People's answers
  are added with `answer()`.
"""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agent import anchor
from agent.canonical import write_json
from agent.concept import concept_sha256
from agent.tests.conftest import fixture, write_corpus
from agent.tests.runs import AUTHOR, GSM8K, HOTPOTQA, INVENTED, MEGAPAIRS, SPIDER_BIRD, Quote
from gold import argilla_io, review

QID = "q01"
CONCEPT = fixture("concept_graph.json")
# A quote in p6 (2025-emnlp-main-1032) that occurs once, for missing-fact lines.
NQ = Quote("p6.md", "NQ (Kwiatkowski et al., 2019)")
OCR_VQA = Quote("p6.md", "OCR-VQA (Mishra et al., 2019)")

# (n, subject, predicate, object, quote, triage label, in pool)
CANDIDATES = [
    (1, "p1", "evaluatesOn", "Spider", SPIDER_BIRD, "answers", True),
    (2, "p1", "evaluatesOn", "BIRD-SQL", SPIDER_BIRD, "answers", True),
    (3, "p5", "evaluatesOn", "GSM8K", GSM8K, "answers", True),
    (4, "p6", "evaluatesOn", "HotpotQA", HOTPOTQA, "irrelevant", True),
    (5, "p4", "evaluatesOn", "MegaPairs", MEGAPAIRS, "irrelevant", True),
    (6, "p3", "evaluatesOn", "HellaSwag", INVENTED, "context", True),  # the quote is not in p3
    (7, "p1", "authoredBy", "Hanbing Liu", AUTHOR, "context", True),
    (8, "p6", "evaluatesOn", "NQ", NQ, "irrelevant", False),
    (9, "p6", "evaluatesOn", "OCR-VQA", OCR_VQA, "irrelevant", False),
]
# One reviewer's answers on the pool (record id -> values).
ANSWERS = {
    "q01-c000001": {"label": "correct", "vital": "yes"},
    "q01-c000002": {"label": "correct", "correction": " | | BIRD", "vital": "no"},
    "q01-c000003": {"label": "correct", "vital": "yes"},
    "q01-c000004": {"label": "correct"},
    "q01-c000005": {"label": "incorrect", "note": "MegaPairs is a method"},
    "q01-c000006": {"label": "incorrect"},
    "q01-c000007": {"label": "unsure", "note": "authorship, not a dataset"},
}
MISSING_LINES = "\n".join([
    f"p6 | evaluatesOn | NQ | p6.md | {NQ.text}",
    f"p6 | evaluatesOn | OCR-VQA | p6 | {OCR_VQA.text}",
    "p6 | evaluatesOn | SQuAD | p6.md | we evaluate on SQuAD",  # not in the paper
    "p6 evaluatesOn TriviaQA",  # not the format
    "p6 | evaluatesOn | X | p77.md | anything",  # no such file
])


def cid(n: int) -> str:
    return f"{QID}-c{n:06d}"


def rids(e: Env) -> dict[str, str]:
    """Candidate id -> its review record id (candidate id and fact digest) in the built pool."""
    return {item["id"]: review.record_id(item) for item in review.pool(e.root, QID)}


@dataclass
class Env:
    tmp: Path
    root: Path
    corpus: Path
    concepts: Path
    questions: Path

    def args(self, *extra: str) -> list[str]:
        """Path options for a gold subcommand."""
        return ["--gold", str(self.root), *extra]


def candidate(n: int, s: str, p: str, o: str, quote: Quote, corpus: Path) -> dict[str, Any]:
    text = anchor.read_text(corpus / quote.file)
    try:
        sel, status = anchor.find(text, quote.text, file=quote.file).json(), "ok"
    except anchor.AnchorError as exc:
        sel, status = None, exc.reason
    target_type = "Person" if p == "authoredBy" else "Dataset"
    return {"id": cid(n), "qid": QID, "paper_id": s, "file": quote.file,
            "row": {"source": s, "source_type": "Paper", "predicate": p, "target": o, "target_type": target_type,
                    "attributes": {"metric": None}},
            "s": s, "p": p, "o": o, "quote": quote.text, "anchor": sel, "anchor_status": status, "chunk": 0,
            "model": "sub-model-1", "prompt_sha256": "0" * 64}


def build(tmp: Path) -> Env:
    corpus, _ = write_corpus(tmp)
    concepts = tmp / "concepts"
    (concepts / QID).mkdir(parents=True)
    write_json(concepts / QID / "concept.json", CONCEPT)
    questions = tmp / "questions.json"
    questions.write_text(json.dumps({"schema_version": 1, "questions": [
        {"id": "q01", "category": "corpus_wide", "question": "Which benchmarks do the RAG papers evaluate on?",
         "source": "nlp33", "notes": ""},
        {"id": "q02", "category": "ambiguous", "question": "Which paper is the most influential?",
         "source": "nlp48", "notes": ""}]}), encoding="utf-8")
    root = tmp / "gold"
    q = root / QID
    cands = [candidate(n, s, p, o, quote, corpus) for n, s, p, o, quote, _, _ in CANDIDATES]
    review.write_jsonl(q / "candidates.jsonl", cands)
    review.write_jsonl(q / "triage.jsonl", [{"id": cid(n), "label": label, "model": "sub-model-2"}
                                             for n, *_, label, _ in CANDIDATES])
    review.write_jsonl(q / "pool.jsonl", [{"id": cid(n), "stratum": "sample" if label == "irrelevant" else "triaged"}
                                          for n, *_, label, pooled in CANDIDATES if pooled])
    review.write_json(q / "pool.strata.json", {"triaged": True, "reviewed_tiers": 5, "rest": 4, "sampled": 2, "seed": "t"})
    status = {1: "relevant", 2: "not_relevant", 3: "relevant", 4: "relevant", 5: "relevant", 6: "relevant",
              7: "not_relevant", 8: "not_relevant", 9: "not_relevant", 10: "no_text"}
    review.write_jsonl(q / "screening.jsonl", [
        {"paper_id": f"p{n}", "status": s, "chunks_relevant": [0] if s == "relevant" else [], "findings": [],
         "model": "sub-model-1", "prompt_sha256": "0" * 64} for n, s in status.items()])
    review.write_json(q / "doc.json", {
        "qid": QID, "concept_sha256": concept_sha256(CONCEPT),
        "built": {"git_commit": "c" * 40, "models": ["sub-model-1"], "settings": {}, "started_at": "", "ended_at": ""},
        "coverage": {"papers": 10, "relevant": 5, "not_relevant": 4, "no_text": 1, "error": 0},
        "rows": [{"key": f"{c['s']} evaluatesOn {c['o']}", "cells": c["row"], "candidates": [c["id"]]} for c in cands],
        "counts": {"candidates": len(cands)}})
    return Env(tmp, root, corpus, concepts, questions)


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return build(tmp_path)


def pulled(record_id: str, dataset: str, answers: dict[str, dict[str, Any]], *, qid: str = QID,
           status: str = "submitted", **metadata: Any) -> dict[str, Any]:
    """A record as gold pull stores it, with `answers` {user: {question: value}}."""
    return {"id": record_id, "dataset": dataset, "metadata": {"question_id": qid, **metadata},
            "responses": [{"question": k, "value": v, "user": user, "status": status}
                          for user, values in answers.items() for k, v in values.items()]}


# --- an in-memory Argilla ----------------------------------------------------------------------------

class FakeRecords:
    def __init__(self, dataset: FakeDataset) -> None:
        self.dataset = dataset

    def log(self, records: list[dict[str, Any]]) -> FakeRecords:
        for record in records:
            self.dataset.upsert(record)
        return self

    def __call__(self, with_responses: bool = True, with_suggestions: bool = True) -> list[Any]:
        return [SimpleNamespace(id=rid, metadata=dict(row["metadata"]), fields=dict(row["fields"]),
                                responses=list(self.dataset.responses[rid]) if with_responses else [])
                for rid, row in self.dataset.rows.items()]


class FakeDataset:
    def __init__(self, api: FakeArgilla, name: str, settings: Any) -> None:
        self.api, self.name, self.settings = api, name, settings
        self.spec = argilla_io.SPECS[name.rsplit("-", 1)[1]]
        self.rows: dict[str, dict[str, Any]] = {}
        self.responses: dict[str, list[Any]] = defaultdict(list)
        self.records = FakeRecords(self)

    def upsert(self, record: dict[str, Any]) -> None:
        fields = {n for n, _ in self.spec.fields}
        metadata = {n: kind for n, _, kind, _ in self.spec.metadata}
        questions = {n for n, *_ in self.spec.questions}
        keys = set(record) - {"id"}
        assert not keys & questions, f"{self.name}: {keys & questions} would become suggestions"
        assert keys <= fields | set(metadata), f"{self.name}: unknown keys {keys - fields - set(metadata)}"
        assert isinstance(record["id"], str) and record["id"]
        for name in fields:
            assert isinstance(record.get(name), str) and record[name].strip(), f"{self.name}: empty field {name}"
        for name, kind in metadata.items():
            value = record.get(name)
            assert isinstance(value, int if kind == "integer" else str), f"{self.name}: metadata {name}={value!r}"
            assert kind == "integer" or value, f"{self.name}: empty metadata {name}"
        self.rows[record["id"]] = {"fields": {k: record[k] for k in fields},
                                   "metadata": {k: record[k] for k in metadata}}

    def answer(self, record_id: str, user: str, status: str = "submitted", **values: Any) -> None:
        assert record_id in self.rows, record_id
        specs = {n: labels for n, _, labels, _ in self.spec.questions}
        for question, value in values.items():
            assert question in specs, question
            assert specs[question] is None or value in specs[question], (question, value)
        self.responses[record_id] = [r for r in self.responses[record_id]
                                     if not (r.user_id == self.api.user_id(user) and r.question_name in values)]
        self.responses[record_id] += [SimpleNamespace(question_name=q, value=v, status=SimpleNamespace(value=status),
                                                      user_id=self.api.user_id(user)) for q, v in values.items()]


class FakeArgilla:
    def __init__(self) -> None:
        self.api = SimpleNamespace(fields=None, questions=None, metadata=None, vectors=None)
        self.store: dict[tuple[str, str], FakeDataset] = {}
        self._workspaces: set[str] = set()
        self._users: dict[str, uuid.UUID] = {}

    def user_id(self, name: str) -> uuid.UUID:
        return self._users.setdefault(name, uuid.uuid5(uuid.NAMESPACE_URL, name))

    @property
    def users(self) -> list[Any]:
        return [SimpleNamespace(id=i, username=n) for n, i in self._users.items()]

    def workspaces(self, name: str) -> str | None:
        return name if name in self._workspaces else None

    def datasets(self, name: str, workspace: str | None = None) -> FakeDataset | None:
        if workspace not in self._workspaces:  # as argilla 2.8.0: it looks the workspace up and dereferences it
            raise AttributeError("'NoneType' object has no attribute 'datasets'")
        return self.store.get((workspace or "", name))

    def create_dataset(self, api: Any, name: str, workspace: str, settings: Any) -> FakeDataset:
        assert workspace in self._workspaces
        assert [f.name for f in settings.fields] == [n for n, _ in argilla_io.SPECS[name.rsplit("-", 1)[1]].fields]
        self.store[(workspace, name)] = FakeDataset(self, name, settings)
        return self.store[(workspace, name)]

    def dataset(self, suffix: str, name: str = argilla_io.DEFAULT_NAME,
                workspace: str = argilla_io.DEFAULT_WORKSPACE) -> FakeDataset:
        return self.store[(workspace, f"{name}-{suffix}")]


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeArgilla:
    api = FakeArgilla()
    monkeypatch.setattr(argilla_io, "client", lambda: api)
    monkeypatch.setattr(argilla_io, "_create_dataset", api.create_dataset)
    monkeypatch.setattr(argilla_io, "_create_workspace", lambda _, workspace: api._workspaces.add(workspace))
    return api
