"""The agentic extractor's conversion, offline with recorded runs (no agent, no model)."""
from __future__ import annotations

import pytest

from agent.concept import validate_concept
from evidence.agentic.extractor import AgenticExtractor
from evidence.agentic.runner import AgentSettings
from evidence.contract import Extractor, ExtractionResult, Scope

from . import fixtures as fx
from .agentic_fakes import CONDITION_SCHEMA, MEASUREMENT_SCHEMA, Ctx, FakeRunner, context, recorded_run, task


def extract(record=None, scope: Scope | None = None) -> tuple[ExtractionResult, FakeRunner]:
    runner = FakeRunner(recorded_run() if record is None else record)
    extractor = AgenticExtractor(runner)
    result = extractor.extract(task(scope=scope), Ctx(fx.S001, context(), MEASUREMENT_SCHEMA))
    return result, runner


def test_spec_is_an_agent_with_variable_determinism() -> None:
    extractor = AgenticExtractor(FakeRunner({}))
    assert isinstance(extractor, Extractor)
    spec = extractor.spec
    assert (spec.kind, spec.determinism, spec.name) == ("agent", "variable", "agentic")
    assert spec.config["prompt_version"] == "v2" and "system-v2.txt" in spec.config["prompt_files"]
    assert AgenticExtractor(FakeRunner({})).spec.extractor_id == spec.extractor_id
    other = AgenticExtractor(FakeRunner({}), AgentSettings(seed=7))
    assert other.spec.extractor_id != spec.extractor_id  # a config change is a new id


def test_accepted_claims_become_items_with_checked_spans() -> None:
    result, runner = extract()
    items = {i.fields["value"]: i for i in result.items}
    assert result.status == "ok" and set(items) == {0.7, 0.62}
    ids = {k: i.item_id for k, i in fx.perfect_items().items()}
    rag = items[0.7]
    assert rag.links == {"condition": ids["S001.c2"], "metric": ids["S001.k1"]}
    assert sorted(s.role for s in rag.spans) == ["condition_label", "value"]
    value = next(s.selector for s in rag.spans if s.role == "value")
    assert value["file"] == "papers/S001.md" and fx.S001[value["start"]:value["end"]] == "0.70"
    assert value["sha256"] == task().document.sha256
    base = items[0.62]  # rows r2 (label resolved to the id) and r3 (id) are one item with both value spans
    assert base.fields["condition"] == ids["S001.c1"] and base.links["condition"] == ids["S001.c1"]
    assert sorted(s.selector["exact"] for s in base.spans) == ["0.62", "62%"]
    assert result.model_calls == ("agentic-" + task().task_sha256[:16] + "/task-000001",
                                  "agentic-" + task().task_sha256[:16] + "/task-000004")
    job = runner.jobs[0]
    assert job.files == {"S001.md": fx.S001} and job.budget == {"steps": 30, "tokens": 600_000}
    assert validate_concept(job.concept) == [] and "S001.md" in job.concept["scope"]["paper"]
    assert [c["name"] for c in job.concept["answer_shape"]["columns"]] == ["condition", "metric", "value"]
    assert ids["S001.c2"] in job.concept["scope"]["earlier_items"]


def test_bad_quotes_and_bad_rows_are_rejected_with_reasons() -> None:
    result, _ = extract()
    reasons = sorted((r.reason, r.quotes) for r in result.rejected)
    assert reasons == [("dangling_link", ("0.70",)), ("empty_quote", ()), ("not_found", ("R reached 71%",)),
                       ("schema", ("62%",)), ("schema", ("x",))]
    assert all(r.evidence_type == "measurement" for r in result.rejected)


def test_coverage_is_what_the_agent_read() -> None:
    result, _ = extract()
    table, after = fx.S001.index("| System"), fx.S001.index("Retrieval clearly")
    cov = [(c.range, c.status, c.found, c.reason) for c in result.coverage]
    assert cov[0] == ((0, table), "skipped", 0, "not_read")
    assert cov[1][1:3] == ("found", 2) and cov[1][0][0] == table and cov[1][0][1] <= after
    assert cov[-1][1] == "skipped" and cov[-1][0][1] == len(fx.S001)
    assert sum(b - a for (a, b), *_ in cov) == len(fx.S001)  # contiguous over the whole scope


def test_scope_drops_outside_spans_and_rejects_rows_with_none_inside() -> None:
    results = fx.S001.index("## Results")
    result, runner = extract(scope=Scope(kind="ranges", ranges=((results, len(fx.S001)),)))
    base = next(i for i in result.items if i.fields["value"] == 0.62)
    assert [s.selector["exact"] for s in base.spans] == ["0.62"]  # "62%" is in the abstract
    rag = next(i for i in result.items if i.fields["value"] == 0.7)
    assert [s.role for s in rag.spans] == ["value"]  # the condition label quote is outside
    assert all(c.range[0] >= results for c in result.coverage)
    assert f"{results}-{len(fx.S001)}" in runner.jobs[0].concept["scope"]["passages"]


def test_draft_answer_is_partial_and_a_failed_run_is_an_error() -> None:
    record = recorded_run()
    record["outcome"] = {"exit_status": "budget", "answer_from": "draft"}
    result, _ = extract(record)
    assert result.status == "partial" and result.items and result.error.reason == "no_final_answer"
    record["answer"] = {"rows": [], "notes": "harness: no valid final answer"}
    record["outcome"]["answer_from"] = "none"
    assert extract(record)[0].status == "error"
    failed, _ = extract(RuntimeError("proxy down: key sk-abcdefgh1234"))
    assert failed.status == "error" and failed.error.reason == "agent_failed" and "sk-abcd" not in failed.error.detail


def test_same_record_same_result_and_record_kept() -> None:
    runner = FakeRunner(recorded_run())
    extractor = AgenticExtractor(runner)
    ctx = Ctx(fx.S001, context(), MEASUREMENT_SCHEMA)
    first, record = extractor.extract_recorded(task(), ctx)
    second = extractor.extract(task(), ctx)
    assert first.output_sha256 == second.output_sha256
    assert extractor.records[task().task_sha256]["trajectory"] == {"messages": []} and record["concept"]["title"]


@pytest.mark.parametrize("kind,schema,role", [("condition", CONDITION_SCHEMA, "condition_label")])
def test_other_evidence_types_get_their_span_role(kind: str, schema: dict, role: str) -> None:
    record = {"run_id": "r", "outcome": {"answer_from": "final"}, "commands": [], "model_calls": [],
              "claims": [{"step_id": 1, "status": "accepted", "claim_id": "claim-000001", "reason": None, "s": "r1",
                          "p": "label", "o": "x", "quote": "closed-book model (B)", "file": "S001.md", "anchor": None}],
              "answer": {"rows": [{"id": "r1", "cells": {"label": "closed-book model", "role": "baseline"},
                                   "facts": [{"id": "f1", "s": "r1", "p": "label", "o": "x", "claims": ["claim-000001"]}]}]}}
    extractor = AgenticExtractor(FakeRunner(record))
    result = extractor.extract(task(kind), Ctx(fx.S001, [], schema))
    assert [s.role for s in result.items[0].spans] == [role] and result.items[0].fields["role"] == "baseline"
