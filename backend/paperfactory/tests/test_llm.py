"""The model layer with fake backends (#12): parsing, checks, retries, cost, config. No model calls."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperfactory import config, llm, packs, seed
from paperfactory.config import RoleModel
from paperfactory.evaluate import Eval

HERE = Path(__file__).resolve().parents[1]
PILOT = json.loads((HERE / "worlds" / "law-pilot.json").read_text())
LAW = packs.field("law")


def settings(tmp_path: Path, **models) -> config.Settings:
    return config.Settings("law", "argument", out=str(tmp_path / "run"), slot_dir=str(tmp_path / "slots"),
                           models=models or {"default": "claude-haiku-5-5"})


def scripted(*answers, cost=0.001, tokens=(10, 5)):
    """A backend that gives these raw answers in turn and records the prompts it got."""
    seen: list[str] = []

    def backend(rm, system, user, schema):
        seen.append(user)
        raw = answers[min(len(seen), len(answers)) - 1]
        return {"raw": raw, "cost_usd": cost, "served_model": rm.model, "input_tokens": tokens[0],
                "output_tokens": tokens[1]}
    backend.seen = seen
    return backend


def calls(s: config.Settings) -> list[dict]:
    return [json.loads(x) for x in (s.out_dir / "calls.jsonl").read_text().splitlines()]


def evaluator(s: config.Settings, backend) -> Eval:
    _, g = seed.make(PILOT, LAW, per_question=3, seed=1)
    return Eval(s, PILOT, LAW, g, llm.Caller(s, backend=backend))


def test_judge_answer_outside_the_labels_is_a_parse_error_not_a_crash(tmp_path: Path) -> None:
    s = settings(tmp_path)
    b = scripted({"choice": "a"})
    assert evaluator(s, b).judge("Rusk distinguished Marrin.", "K5", "K1", "judge:t") == "parse_error"
    rec = calls(s)[-1]
    assert rec["parse_error"] and rec["attempts"] == 3 and len(b.seen) == 3
    assert "YOUR LAST ANSWER WAS REJECTED" in b.seen[1]
    assert not list((s.out_dir / "cache" / "llm").glob("*.json"))          # a failed answer is never cached


def test_judge_accepts_a_label_after_one_rejection(tmp_path: Path) -> None:
    s = settings(tmp_path)
    b = scripted({"choice": "B"}, {"choice": "distinguishes"})
    assert evaluator(s, b).judge("Rusk distinguished Marrin.", "K5", "K1", "judge:t") == "distinguishes"
    assert calls(s)[-1]["rejections"] and not calls(s)[-1]["parse_error"]


def test_verifier_answering_with_positions_is_rejected_never_shifted(tmp_path: Path) -> None:
    s = settings(tmp_path)
    fa = {"s": "K5", "r": "distinguishes", "o": "K1"}
    positions = {"answers": [{"id": "1", "verdict": "yes"}, {"id": "2", "verdict": "no"}]}
    assert evaluator(s, scripted(positions)).verify([("", "a", fa), ("", "b", fa)], "v") == [None, None]
    ok = {"answers": [{"id": "V2", "verdict": "no"}, {"id": "V1", "verdict": "yes"}]}
    assert evaluator(settings(tmp_path / "2"), scripted(positions, ok)).verify(
        [("", "a", fa), ("", "b", fa)], "v") == [True, False]
    dup = {"answers": [{"id": "V1", "verdict": "yes"}, {"id": "V1", "verdict": "no"}]}
    pairs = [("", "a", fa), ("", "b", fa)]
    assert evaluator(settings(tmp_path / "3"), scripted(dup)).verify(pairs, "v") == [None, None]


def test_unknown_cost_is_none_and_reported_as_unknown(tmp_path: Path) -> None:
    s = settings(tmp_path)
    c = llm.Caller(s, backend=lambda rm, sy, u, sc: {"raw": {"pick": 1}, "cost_usd": None})
    c("leak", "leak:0", "sys", "u", {"type": "object"})
    c2 = llm.Caller(s, backend=scripted({"pick": 2}, cost=0.5))
    c2("leak", "leak:1", "sys", "u2", {"type": "object"})
    assert calls(s)[0]["cost_usd"] is None and calls(s)[0]["cost_source"] == "unknown"
    assert c.cost() == {"usd": "unknown", "usd_known": 0.5, "calls": 2, "calls_unknown_cost": 1}


def test_price_and_local_fill_in_a_missing_cost() -> None:
    got = {"cost_usd": None, "input_tokens": 1_000_000, "output_tokens": 500_000}
    assert llm.price(RoleModel("m", "openai", price_in_per_mtok=1.0, price_out_per_mtok=4.0), got) == (3.0, "price")
    assert llm.price(RoleModel("m", "openai", local=True), got) == (0.0, "local")
    assert llm.price(RoleModel("m", "openai"), got) == (None, "unknown")
    assert llm.price(RoleModel("m"), got | {"cost_usd": 0.2}) == (0.2, "reported")


def test_openai_backend_through_modelcall_with_a_fake_server(tmp_path: Path, monkeypatch) -> None:
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel
    replies = iter(["not json at all", json.dumps({"choice": "rejects"})])
    monkeypatch.setattr(llm, "openai_model", lambda rm: FunctionModel(
        lambda msgs, info: ModelResponse(parts=[TextPart(next(replies))])))
    s = settings(tmp_path, judge={"model": "sub-model-1", "backend": "openai", "local": True})
    got = evaluator(s, None).judge("Pell rejected section 9.", "K4", "S9", "judge:t")
    assert got == "rejects"
    rec = calls(s)[-1]
    assert rec["backend"] == "openai" and rec["cost_usd"] == 0.0 and rec["cost_source"] == "local"
    assert rec["attempts"] == 1 and rec["input_tokens"]      # pydantic-ai asked again inside the call


def test_openai_backend_that_never_gives_json_is_a_parse_error(tmp_path: Path, monkeypatch) -> None:
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel
    monkeypatch.setattr(llm, "openai_model", lambda rm: FunctionModel(
        lambda msgs, info: ModelResponse(parts=[TextPart("I think it is B")])))
    s = settings(tmp_path, judge="qwen:sub-model-1")
    assert evaluator(s, None).judge("Pell rejected section 9.", "K4", "S9", "judge:t") == "parse_error"
    rec = calls(s)[-1]
    assert rec["parse_error"] and rec["attempts"] == 3 and rec["cost_usd"] is None


def test_transport_failure_is_retried_once_then_raises(monkeypatch) -> None:
    n = []

    def down(rm, sy, u, sc):
        n.append(1)
        raise llm.LLMError("connection refused")
    monkeypatch.setitem(llm.BACKENDS, "claude_cli", down)
    with pytest.raises(llm.LLMError):
        llm.run_backend(RoleModel("m"), "s", "u", {})
    assert len(n) == 2


def test_role_settings(tmp_path: Path) -> None:
    s = settings(tmp_path, default="claude-haiku-5-5", qa="qwen:sub-model-1",
                 judge={"model": "m", "backend": "openai", "base_url": "http://h:9/v1", "max_parallel": 1})
    assert s.role("writer") == RoleModel("claude-haiku-5-5", timeout=900)
    assert s.role("qa").backend == "openai" and s.role("qa").model == "sub-model-1"
    assert s.role("judge").url == "http://h:9/v1" and s.model("judge") == "m"
    assert llm.slot_dir(s.slots, s.role("judge")) != llm.slot_dir(s.slots, s.role("writer"))
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"field": "law", "genre": "argument", "models": {"qa": {"model": "m", "colour": 1}}}))
    with pytest.raises(ValueError, match="colour"):
        config.load(p)
    p.write_text(json.dumps({"field": "law", "genre": "argument", "models": {"qa": {"model": "m", "backend": "x"}}}))
    with pytest.raises(ValueError, match="backend"):
        config.load(p)


def test_pydantic_schemas_are_inlined_for_the_backends() -> None:
    from paperfactory.evaluate import VerOut
    sch = llm.json_schema(VerOut)
    assert "$ref" not in json.dumps(sch) and "$defs" not in sch
    assert sch["properties"]["answers"]["items"]["properties"]["verdict"]["enum"] == ["yes", "no"]


# ------------------------------------------------------------------ PaperOrchestra through the same layer
def test_paperorchestra_calls_go_through_the_layer(tmp_path: Path, monkeypatch) -> None:
    import importlib.util
    import sys
    from dataclasses import asdict
    po = HERE.parents[1] / "external" / "paperorchestra"
    spec = importlib.util.spec_from_file_location("po_ccu", po / "utils" / "claude_code_utils.py")
    ccu = importlib.util.module_from_spec(spec)
    sys.modules["po_ccu"] = ccu
    spec.loader.exec_module(ccu)
    monkeypatch.setitem(llm.BACKENDS, "openai", lambda rm, sy, u, sc: {
        "raw": {"markdown": "# T"}, "cost_usd": None, "served_model": rm.model, "input_tokens": 7,
        "output_tokens": 3})
    runner, label = llm.po_runner(asdict(RoleModel("sub-model-1", "openai", base_url="http://h:1/v1")))
    lm = ccu.ClaudeCodeLM(label, cache_dir=tmp_path / "c", lock_dir=tmp_path / "l", log_path=tmp_path / "log.jsonl",
                          runner=runner)
    assert lm("sys", "user", {"type": "object"}, step="outline") == {"markdown": "# T"}
    rec = json.loads((tmp_path / "log.jsonl").read_text().splitlines()[-1])
    assert rec["cost_usd"] is None and rec["model"] == "openai:sub-model-1@http://h:1/v1#max_tokens=8192"


def test_write_passes_the_writer_role_to_paperorchestra(tmp_path: Path, monkeypatch) -> None:
    import subprocess
    from paperfactory import write
    got = {}

    def fake_run(cmd, **kw):
        got["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 1)
    monkeypatch.setattr(write.subprocess, "run", fake_run)
    s = settings(tmp_path, writer={"model": "sub-model-1", "backend": "openai", "max_parallel": 2, "local": True})
    write.write_one(s, "L-01", tmp_path)
    cmd = got["cmd"]
    rm = RoleModel(**json.loads(cmd[cmd.index("--backend_json") + 1]))
    assert rm == s.role("writer")
    assert cmd[cmd.index("--max_parallel") + 1] == "2"
    assert cmd[cmd.index("--lock_dir") + 1] == str(llm.slot_dir(s.slots, rm))
