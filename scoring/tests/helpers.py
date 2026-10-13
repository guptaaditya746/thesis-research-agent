"""Shared test helpers: a scripted judge, answer keys for the agent test runs, a finished attach step."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.canonical import file_sha256, write_json
from agent.rundir import ATTACH_FILE, RunDir, utc_now
from scoring.judge import Judge


class FakeJudge:
    """gold.judge's three calls, decided by rules; records every call.

    support: "supports" when the fact's object occurs in the quote as written, "partial" when only
    case-insensitively, else "no". same_fact / same_row: True for the pairs listed in `same`, keyed
    by the run and key objects (facts) or targets/first cells (rows).
    """

    def __init__(self, same_facts: set[tuple[str, str]] = frozenset(), same_rows: set[tuple[str, str]] = frozenset(),
                 fail: bool = False) -> None:
        self.same_facts, self.same_rows, self.fail = set(same_facts), set(same_rows), fail
        self.calls: list[tuple[str, Any, Any]] = []

    def support(self, fact: dict[str, Any], quote: str, *, context: str | None = None) -> dict[str, Any]:
        self.calls.append(("support", fact, quote, context))
        if self.fail:
            raise ConnectionError("judge down")
        o = str(fact["o"])
        label = "supports" if o in quote else "partial" if o.casefold() in quote.casefold() else "no"
        return {"label": label, "rationale": f"{o!r} in quote: {label}", "model": "fake-judge",
                "prompt_sha256": "0" * 64, "cached": False}

    def same_fact(self, run_fact: dict[str, Any], key_fact: dict[str, Any], concept: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("same_fact", run_fact, key_fact))
        return {"match": (str(run_fact["o"]), str(key_fact["o"])) in self.same_facts, "rationale": "rule"}

    def same_row(self, run_row: dict[str, Any], key_row: dict[str, Any], concept: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("same_row", run_row, key_row))
        return {"match": (row_name(run_row), row_name(key_row)) in self.same_rows}

    def asked(self, method: str) -> list[tuple[Any, Any]]:
        return [c[1:] for c in self.calls if c[0] == method]


def row_name(row: dict[str, Any]) -> str:
    return str(row["target"]) if "target" in row else str(next(iter(row["cells"].values())))


def judge(**kw: Any) -> tuple[Judge, FakeJudge]:
    fake = FakeJudge(**kw)
    return Judge(fake, "fake"), fake


def gold_fact(n: int, s: str, p: str, o: Any, vital: bool = False, paper: str | None = None) -> dict[str, Any]:
    return {"id": f"f{n}", "s": s, "p": p, "o": o, "paper_id": paper or s, "quote": f"quote for {s} {p} {o}",
            "vital": vital, "candidate_id": f"q01-c{n:06d}"}


def edge_row(n: int, paper: str, dataset: str, facts: list[dict[str, Any]], metric: str | None = None) -> dict[str, Any]:
    return {"id": f"r{n}", "source": paper, "source_type": "Paper", "predicate": "evaluatesOn", "target": dataset,
            "target_type": "Dataset", "attributes": {"metric": metric}, "facts": facts}


def graph_key(run: RunDir, *, reviewed: bool = True, **extra: Any) -> dict[str, Any]:
    """An answer key for the agent test runs' concept (concept_graph.json: Paper evaluatesOn Dataset).

    Against runs.research_run: f1 Spider and f3 GSM8K match strictly, f2 BIRD matches the key's "Bird"
    once normalised, f4 HotpotQA misses (the key says p6 evaluates on "Hotpot QA dataset", the judge's
    call), f5 HellaSwag is not in the key; the key's p4 MegaPairs fact is vital and missed.
    """
    concept_sha = run.load_config()["hashes"]["concept_sha256"]
    rows = [
        edge_row(1, "p1", "Spider", [gold_fact(1, "p1", "evaluatesOn", "Spider", vital=True)]),
        edge_row(2, "p1", "Bird", [gold_fact(2, "p1", "evaluatesOn", "Bird")]),
        edge_row(3, "p5", "GSM8K", [gold_fact(3, "p5", "evaluatesOn", "GSM8K")]),
        edge_row(4, "p6", "Hotpot QA dataset", [gold_fact(4, "p6", "evaluatesOn", "Hotpot QA dataset")]),
        edge_row(5, "p4", "MegaPairs", [gold_fact(5, "p4", "evaluatesOn", "MegaPairs", vital=True)]),
    ]
    return {"qid": "q01", "concept_sha256": concept_sha, "kind": "graph", "version": "v1" if reviewed else "v1-draft",
            "reviewed": reviewed, "rows": rows, "notes": "test key"} | extra


def write_key(path: Path, key: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(key, indent=1), encoding="utf-8")
    return path


def finish_attach(run: RunDir) -> None:
    """Mark a baseline built by runs.baseline_run as having finished its attach step (row 2.5)."""
    config = run.load_config()
    config["attach"] = {"prompt": {"version": "v1", "sha256": "a" * 64, "files": {}},
                        "budget_per_fact": {"steps": 6, "tokens": 60000, "announced": True},
                        "conclude_replies": 1, "first_step": 5, "started_at": utc_now()}
    write_json(run.config, config)
    write_json(run.root / ATTACH_FILE, {"schema_version": 1, "run_id": run.run_id,
                                        "answer_sha256": file_sha256(run.answer)})
