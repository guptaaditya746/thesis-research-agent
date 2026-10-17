"""The agentic extractor's conversion, offline with recorded runs (no agent, no model)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.concept import validate_concept
from evidence.agentic.extractor import AgenticExtractor
from evidence.agentic.runner import AgentSettings
from evidence.contract import Extractor, ExtractionResult, Scope

from . import fixtures as fx
from .agentic_fakes import (CONDITION_SCHEMA, LINKS, MEASUREMENT_SCHEMA, Ctx, FakeRunner, claim, context,
                            recorded_run, row, task)


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
    assert base.fields == {"value": 0.62, "dataset": None} and base.links["condition"] == ids["S001.c1"]
    assert sorted(s.selector["exact"] for s in base.spans) == ["0.62", "62%"]
    assert result.model_calls == ("agentic-" + task().task_sha256[:16] + "/task-000001",
                                  "agentic-" + task().task_sha256[:16] + "/task-000004")
    job = runner.jobs[0]
    assert job.files == {"S001.md": fx.S001} and job.budget == {"steps": 30, "tokens": 600_000}
    assert validate_concept(job.concept) == [] and "S001.md" in job.concept["scope"]["paper"]
    assert [c["name"] for c in job.concept["answer_shape"]["columns"]] == ["condition", "metric", "value", "dataset"]
    assert ids["S001.c2"] in job.concept["scope"]["earlier_items"]


def test_code_hash_covers_the_agent_and_its_harness(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review 6: run settings, concept and prompt handling, stopping, spawn and mini-swe-agent change the id."""
    from importlib import metadata

    from evidence.agentic import extractor as ex

    assert {"rundir.py", "concept.py", "stopping.py", "prompts.py", "spawn.py"} <= set(ex.AGENT_FILES)
    before = ex.code_sha256()
    real = metadata.version
    monkeypatch.setattr(metadata, "version", lambda name: "9.9.9" if name == "mini-swe-agent" else real(name))
    assert ex.code_sha256() != before


def test_register_agentic_uses_the_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    from evidence.agentic import factory, register_agentic

    registered: dict = {}
    registry = types.ModuleType("evidence.extractors")
    registry.register = lambda name, f: registered.update({name: f})  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "evidence.extractors", registry)
    register_agentic()
    assert registered == {"agentic": factory}


def test_engine_config_and_recorder() -> None:
    """Built as the engine's registry builds it; the run goes to the engine's recorder for its cache."""
    from evidence.agentic import factory

    extractor = factory({"evidence_type": "measurement", "links": LINKS, "description": "One reported result.",
                         "field_schema": MEASUREMENT_SCHEMA, "roles": ["value"], "sandbox_mode": "unsandboxed",
                         "budget": {"steps": 9, "tokens": 9000}})
    assert extractor.spec.evidence_types == ("measurement",) and extractor.settings.sandbox_mode == "unsandboxed"
    assert extractor.spec.config["links"] == LINKS and extractor.budget == {"steps": 9, "tokens": 9000}
    record = recorded_run()
    record["model_calls"] = [{"task_id": "task-000001", "step_id": 1, "usage": {"prompt_tokens": 100,
                                                                                "completion_tokens": 7}},
                             {"task_id": "task-000004", "step_id": 2, "usage": {"prompt_tokens": 300,
                                                                                "completion_tokens": 9}}]
    extractor.runner = FakeRunner(record)

    recorder = SimpleNamespace(records=[])  # the engine's Recorder, as far as the extractor uses it
    result = extractor.extract(task(), Ctx(fx.S001, context(), MEASUREMENT_SCHEMA, recorder))
    assert [r["id"] for r in recorder.records] == list(result.model_calls) and len(result.model_calls) == 2
    assert [r["usage"] for r in recorder.records] == [{"input_tokens": 100, "output_tokens": 7},
                                                      {"input_tokens": 300, "output_tokens": 9}]
    assert "agent_run" not in recorder.records[0] and recorder.records[1]["agent_run"]["claims"]
    assert "One reported result." in extractor.runner.jobs[0].concept["scope"]["item"]


def test_model_reaches_the_spec_config_and_the_runner() -> None:
    """Part G.3: the engine's --model becomes AgentSettings.model, the runner's alias and the recorded model;
    orch-model (the default) and the sub aliases are recorded with their pinned weights, another alias alone."""
    from pathlib import Path

    from agent.rundir import ORCHESTRATOR, SUBAGENTS
    from evidence import engine, protocol
    from evidence.agentic import factory

    base = factory({"evidence_type": "measurement", "sandbox_mode": "unsandboxed"})
    assert base.settings.model == "orch-model" and base.runner.settings.model == "orch-model"
    assert base.spec.config["model"] == {k: ORCHESTRATOR[k] for k in ("alias", "name", "revision")}
    sub = factory({"evidence_type": "measurement", "sandbox_mode": "unsandboxed", "model": "sub-model-1"})
    assert sub.runner.settings.model == "sub-model-1" and sub.spec.extractor_id != base.spec.extractor_id
    assert sub.spec.config["model"] == {"alias": "sub-model-1", "name": SUBAGENTS[0]["name"],
                                        "revision": SUBAGENTS[0]["revision"]}
    other = factory({"evidence_type": "measurement", "sandbox_mode": "unsandboxed", "model": "other-model"})
    assert other.spec.config["model"] == {"alias": "other-model", "name": "other-model", "revision": "unpinned"}
    # through the engine, as `evidence run --model X` builds the cascade of the agentic protocol
    agentic = protocol.load(Path(engine.__file__).resolve().parent / "protocols" / "rag-factuality-agentic.yaml")
    cascades = engine.build_extractors(agentic, "cascade", model="sub-model-2")
    agents = [e for c in cascades.values() for _, e in c if e.spec.kind == "agent"]
    llms = [e for c in cascades.values() for _, e in c if e.spec.kind == "llm"]
    assert agents and all(e.spec.config["model"]["alias"] == "sub-model-2" for e in agents)
    assert all(e.runner.settings.model == "sub-model-2" for e in agents)
    assert llms and all(e.spec.config["model"] == "sub-model-2" for e in llms)
    default = engine.build_extractors(agentic, "cascade", model=None)
    assert {e.spec.config["model"] for c in default.values() for _, e in c if e.spec.kind == "llm"} == {"orch-model"}
    assert {e.spec.config["model"]["alias"] for c in default.values() for _, e in c if e.spec.kind == "agent"} == {
        "orch-model"}


def test_bad_quotes_and_bad_rows_are_rejected_with_reasons() -> None:
    result, _ = extract()
    reasons = sorted((r.reason, r.quotes) for r in result.rejected)
    assert reasons == [("dangling_link", ("0.70",)), ("empty_quote", ()), ("not_found", ("R reached 71%",)),
                       ("schema", ("62%",)), ("schema", ("x",))]
    assert all(r.evidence_type == "measurement" for r in result.rejected)


def test_a_row_cannot_borrow_another_rows_claim() -> None:
    """Review 4: a value 0.704 citing r2's "62%" claim, or its own claim quoting another number, is no item."""
    ids = {k: i.item_id for k, i in fx.perfect_items().items()}
    cells = {"condition": ids["S001.c2"], "metric": ids["S001.k1"], "dataset": None}
    record = recorded_run()
    record["claims"] += [claim(5, "value", 0.62, "62%", s="r7", step=3), claim(6, "dataset", "NQ", "0.70", s="r8"),
                         claim(7, "value", 0.704, "0.70", s="r8")]
    record["answer"]["rows"] = [row("r7", {**cells, "value": 0.704}, [3]),        # r2's claim
                                row("r8", {**cells, "value": 0.704}, [5]),        # its s is r7, not r8
                                row("r9", {**cells, "value": 0.704}, [6]),        # r8's dataset claim
                                row("r8", {**cells, "value": 0.704}, [7])]        # 0.70 states 0.704 (within 0.005)
    result, _ = extract(record)
    assert [(i.fields["value"], [s.selector["exact"] for s in i.spans]) for i in result.items] == [(0.704, ["0.70"])]
    rows = sorted(r.detail for r in result.rejected if r.reason == "not_found" and r.detail.startswith("row r7: no"))
    assert rows == ["row r7: no cited claim states this row"]
    details = " | ".join(r.detail for r in result.rejected)
    assert "claim-000003 is about 'r2', not this row" in details
    assert "claim-000005 is about 'r7', not this row" in details
    record["answer"]["rows"] = [row("r7", {**cells, "value": 0.704}, [5])]  # its own claim, but "62%" is not 0.704
    result, _ = extract(record)
    assert result.items == () and "does not state the value 0.704" in " | ".join(r.detail for r in result.rejected)


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
