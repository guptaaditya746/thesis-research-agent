"""The four engine seams (stages.py): with none registered a run is byte-identical to before; a registered
stage can change what the engine records, in registration order."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import dspy
import pytest
from pydantic import BaseModel
from pydantic_ai.models.function import FunctionModel

from evidence import engine, stages
from evidence.contract import Item
from evidence.plan import Plan, WordList, write_plan
from evidence.replay import replay
from evidence.rundir import RunDir
from jsonio import sha256_hex
from evidence.tests.conftest import PROTOCOL, make_corpus, provider_of, respond

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "golden" / "regex_run_outputs.json"


@pytest.fixture(autouse=True)
def clean_registry() -> Iterator[None]:
    with stages.registered():   # empty inside, import-time registrations of other modules restored after
        yield


def _run(tmp_path: Path, strategy: str = "all", **kw) -> Path:
    kw = {"provider": None, **kw}
    corpus = make_corpus(tmp_path / "corpus")
    return engine.run(PROTOCOL, corpus, tmp_path / "runs", selection="regex-only", strategy=strategy,
                      cache=tmp_path / "cache", **kw)


def _outputs(root: Path) -> dict[str, str]:
    return json.loads((root / "run.json").read_text(encoding="utf-8"))["outputs"]


@pytest.mark.parametrize("strategy", ["all", "gaps"])
def test_no_stages_run_is_byte_identical(tmp_path: Path, strategy: str) -> None:
    # golden hashes were recorded with the engine as it was before the seams (committed fixture)
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))[strategy]
    root = _run(tmp_path, strategy)
    outputs = _outputs(root)
    assert outputs == golden
    for name, digest in outputs.items():
        assert sha256_hex((root / name).read_bytes()) == digest


def test_after_run_output_is_hashed(tmp_path: Path) -> None:
    stages.register("demo", "after_run", lambda run, ctx: {"x": 1})
    root = _run(tmp_path)
    outputs = _outputs(root)
    assert "demo.json" in outputs
    assert json.loads((root / "demo.json").read_text(encoding="utf-8")) == {"x": 1}
    assert outputs["demo.json"] == sha256_hex((root / "demo.json").read_bytes())
    assert (root / "manifest.json").exists()
    assert json.loads((root / "run.json").read_text(encoding="utf-8"))["stages"] == {"after_run": ["demo"]}


def test_no_stages_run_json_has_no_stages_key(tmp_path: Path) -> None:
    assert "stages" not in json.loads((_run(tmp_path) / "run.json").read_text(encoding="utf-8"))


def test_registered_restores_what_was_registered_before() -> None:
    stages.register("keep", "after_run", lambda run, ctx: {})
    with stages.registered():
        assert stages.names() == {}
        stages.register("inner", "after_run", lambda run, ctx: {})
    assert stages.names() == {"after_run": ["keep"]}


@pytest.mark.parametrize("name", ["Bad", "a.b", "", "answer", "graph", "funnel", "run", "manifest", "evidence",
                                  "plan", "reason", "comparisons", "names", "locate", "events", "calls"])
def test_register_rejects_bad_and_reserved_names(name: str) -> None:
    with pytest.raises(ValueError):
        stages.register(name, "after_run", lambda run, ctx: {})


def test_stages_are_called_in_registration_order(tmp_path: Path) -> None:
    seen: list[str] = []
    for name in ("a", "b", "c"):
        stages.register(name, "before_extract", lambda doc, ctx, n=name: seen.append(n))
    _run(tmp_path)
    assert seen[:3] == ["a", "b", "c"] and len(seen) == 15   # five documents


def test_context_reaches_every_seam(tmp_path: Path) -> None:
    got: list[stages.StageContext] = []
    stages.register("b", "before_extract", lambda doc, ctx: got.append(ctx))
    stages.register("t", "after_type", lambda doc, etype, merged, ctx: got.append(ctx) or merged)
    stages.register("d", "after_document", lambda doc, ctx: got.append(ctx) or [])
    stages.register("r", "after_run", lambda run, ctx: got.append(ctx) or {})
    root = _run(tmp_path)
    assert got and all(c.mode == "run" and c.plan is None and c.run_dir == root and c.calls is not None for c in got)


def test_after_type_drops_items_and_after_document_extras_reach_evidence(tmp_path: Path) -> None:
    calls: list[str] = []

    def drop_all(doc, etype, merged, ctx):
        calls.append(etype)
        return []

    stages.register("drop", "after_type", drop_all)
    root = _run(tmp_path / "dropped")
    assert calls and (root / "evidence.jsonl").read_text(encoding="utf-8").strip() == ""
    stages.clear()
    base = _run(tmp_path / "base")
    template = json.loads((base / "evidence.jsonl").read_text(encoding="utf-8").splitlines()[0])

    def extra(doc, ctx):
        if doc.doc.id != "S001":
            return []
        return [Item.model_validate({**template, "item_id": "extra-1"})]

    stages.register("extra", "after_document", extra)
    root = _run(tmp_path / "extra")
    ids = [json.loads(x)["item_id"] for x in (root / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "extra-1" in ids


def test_a_failing_after_run_stage_writes_failed_json_and_the_run_continues(tmp_path: Path) -> None:
    def boom(run, ctx):
        raise RuntimeError("no graph today")

    stages.register("boom", "after_run", boom)
    stages.register("fine", "after_run", lambda run, ctx: {"ok": True})
    root = _run(tmp_path)
    outputs = _outputs(root)
    assert json.loads((root / "boom.json").read_text(encoding="utf-8")) == {"failed": "RuntimeError: no graph today"}
    assert outputs["boom.json"] == sha256_hex((root / "boom.json").read_bytes()) and "fine.json" in outputs


def test_a_failing_before_extract_stage_fails_the_run(tmp_path: Path) -> None:
    def boom(doc, ctx):
        raise RuntimeError("bad")

    stages.register("boom", "before_extract", boom)
    with pytest.raises(RuntimeError, match="bad"):
        _run(tmp_path)


def _plan() -> Plan:
    return Plan(question="q", field="cs", lines=[], main_rule="r", decisions=[], clarifications=[],
                words=WordList(things={}, cues=[], written_by="test", ontology_names={}))


def test_plan_goes_to_the_context_and_is_copied_into_the_run(tmp_path: Path) -> None:
    plan = _plan()
    path = tmp_path / "plan.json"
    write_plan(plan, path)
    got: list[object] = []
    stages.register("p", "before_extract", lambda doc, ctx: got.append(ctx.plan))
    stages.register("r", "after_run", lambda run, ctx: got.append(ctx.plan) or {})
    root = _run(tmp_path / "out", plan=str(path))
    assert got[0] == plan and got[-1] == plan
    assert (root / "plan.json").read_bytes() == path.read_bytes()
    assert _outputs(root)["plan.json"] == sha256_hex(path.read_bytes())


def test_a_planned_run_replays_to_identical_outputs_from_its_own_plan_copy(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    write_plan(_plan(), path)
    stages.register("demo", "after_run", lambda run, ctx: {"plan_q": ctx.plan.question})
    root = _run(tmp_path / "out", plan=str(path))
    path.unlink()   # the original is gone: the replay reads the run folder's copy
    new, report = replay(root)
    assert report["ok"] and report["mismatched"] == []
    assert _outputs(new) == _outputs(root)


def test_replay_with_a_different_stage_set_is_refused(tmp_path: Path) -> None:
    stages.register("demo", "after_run", lambda run, ctx: {"x": 1})
    root = _run(tmp_path)
    stages.clear()
    with pytest.raises(stages.StagesMismatch, match="demo"):
        replay(root)
    stages.register("demo", "after_run", lambda run, ctx: {"x": 1})
    new, report = replay(root)
    assert report["ok"]


# --- a stage's model calls are logged like the engine's own ---------------------------------------------------------

class Echo(BaseModel):
    answer: str


def _provider(fail: bool = False, text: str = "hi there"):
    def reply(messages, info):
        if fail:
            raise RuntimeError("provider down")
        return respond(info, {"answer": text, "text": text})
    return provider_of(FunctionModel(reply, model_name="echo"))


def _ask_stage():
    def stage(run, ctx):
        out = ctx.ask("Echo the word.", "say hi", output_type=Echo, purpose="demo-echo")
        return {"answer": out.answer}
    return stage


def _lines(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_a_stage_model_call_is_logged_counted_and_replays_without_a_model(tmp_path: Path) -> None:
    base = _run(tmp_path / "base", provider=None)
    stages.register("echo", "after_run", _ask_stage())
    root = _run(tmp_path / "with", provider=_provider())
    assert json.loads((root / "echo.json").read_text(encoding="utf-8")) == {"answer": "hi there"}
    rows = _lines(root / "calls.jsonl")
    assert len(rows) == 1 and rows[0]["extractor_id"] == "stage:demo-echo" and rows[0]["evidence_type"] == "stage"
    assert rows[0]["status"] == "ok" and len(rows[0]["model_calls"]) == 1
    calls = {n for n in _outputs(root) if n.startswith("calls/")}
    assert len(calls) == len({n for n in _outputs(base) if n.startswith("calls/")}) + 1
    cost, base_cost = (json.loads((r / "run.json").read_text(encoding="utf-8"))["cost"] for r in (root, base))
    assert cost["calls"] == base_cost["calls"] + 1 and cost["model_calls"] == 1 and cost["made_model_calls"] == 1
    assert any(e["subtype"] == "stage_call" and e["custom_metadata"]["purpose"] == "demo-echo"
               for e in _lines(root / "events.jsonl"))
    new, report = replay(root)
    assert report["ok"] and _outputs(new) == _outputs(root)
    replay_cost = json.loads((new / "run.json").read_text(encoding="utf-8"))["cost"]
    assert replay_cost["made_model_calls"] == 0 and replay_cost["cached_calls"] == replay_cost["calls"]


def test_a_failed_stage_model_call_is_a_failed_call(tmp_path: Path) -> None:
    stages.register("echo", "after_run", _ask_stage())
    root = _run(tmp_path, provider=_provider(fail=True))
    assert "StageCallError" in json.loads((root / "echo.json").read_text(encoding="utf-8"))["failed"]
    assert RunDir(root).failed_calls() == 1


def test_a_stage_gets_a_recorded_dspy_lm(tmp_path: Path) -> None:
    def stage(run, ctx):
        lm = ctx.dspy_lm("demo-dspy")
        return {"out": list(lm("hello"))}

    stages.register("dsp", "after_run", stage)
    root = _run(tmp_path, provider=_provider())
    assert json.loads((root / "dsp.json").read_text(encoding="utf-8")) == {"out": ["hi there"]}
    assert len(_lines(root / "calls.jsonl")) == 1
    _, report = replay(root)
    assert report["ok"]


def test_a_dspy_retry_through_ctx_is_a_new_recorded_call(tmp_path: Path) -> None:
    def stage(run, ctx):
        lm = ctx.dspy_lm("demo-retry")
        return {"out": [list(lm("same words", attempt=0)), list(lm("same words", attempt=1))]}

    stages.register("dsp", "after_run", stage)
    root = _run(tmp_path, provider=_provider())
    assert len(_lines(root / "calls.jsonl")) == 2
    assert len({r["key"] for r in _lines(root / "calls.jsonl")}) == 2
    _, report = replay(root)
    assert report["ok"]


class EchoSig(dspy.Signature):
    """Echo the text."""
    text: str = dspy.InputField()
    echo: str = dspy.OutputField()


def test_a_step_with_a_bad_first_reply_succeeds_on_attempt_1_and_replays_without_calls(tmp_path: Path) -> None:
    from evidence import steps
    asked: list[str] = []

    def reply(messages, info):
        asked.append("x")
        return respond(info, {"text": "not json at all" if len(asked) == 1 else '{"echo": "ok"}'})

    def stage(run, ctx):
        steps.configure(ctx.dspy_lm("demo-step"))
        try:
            return {"echo": steps.Step(EchoSig, "echo")(text="hi").echo}
        finally:
            steps._LM = None

    stages.register("stp", "after_run", stage)
    root = _run(tmp_path, provider=provider_of(FunctionModel(reply, model_name="echo")))
    assert json.loads((root / "stp.json").read_text(encoding="utf-8")) == {"echo": "ok"}
    assert len(asked) == 2 and len(_lines(root / "calls.jsonl")) == 2
    new, report = replay(root)
    assert report["ok"] and len(asked) == 2
    assert json.loads((new / "run.json").read_text(encoding="utf-8"))["cost"]["made_model_calls"] == 0
