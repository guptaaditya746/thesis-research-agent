"""Main loop end to end with a scripted model (rows 1.8, 1.9, 1.11, 1.12).

The model is mocked at LiteLLM's call (`_query`), so everything else is real: the parser, the
sandbox wrapper (mode `unsandboxed`, or `landlock` where the kernel has it), the broker (in process
and as its own process), the claim command over CLAIM_FD, the records, answer.json, verify and
pairs. Commands need bash and descriptor passing, so these tests are POSIX-only.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable

import pytest

pytest.importorskip("minisweagent")
pytest.importorskip("litellm")

import litellm  # noqa: E402

from agent import sandbox  # noqa: E402
from agent.anchor import AnchorError, Index, find  # noqa: E402
from agent.canonical import canonical  # noqa: E402
from agent.chain import verify  # noqa: E402
from agent.cli import main as cli  # noqa: E402
from agent.loop import POSIX_BROKER, OrchestratorModel, is_context_full, research_run  # noqa: E402
from agent.rundir import RunDir  # noqa: E402
from agent.verify import verify_run  # noqa: E402

from .conftest import fixture, papers, write_corpus  # noqa: E402

POSIX = os.name == "posix" and shutil.which("bash") is not None and shutil.which("timeout") is not None
posix_only = pytest.mark.skipif(not POSIX, reason="agent commands need bash, coreutils timeout and pass_fds")
FENCE = "`" * 3
CONCEPT = fixture("concept_table.json")
SETTINGS = dict(temperature=0.7, seed=1234, git_commit="c" * 40, agent_root_manifest_sha256="b" * 64)

Reply = str | Exception | Callable[[list[dict[str, Any]]], str]


class ScriptedModel(OrchestratorModel):
    """OrchestratorModel whose LiteLLM call returns scripted replies (or raises scripted errors)."""

    abort_exceptions = [*OrchestratorModel.abort_exceptions, IndexError]  # script ran out: fail, never retry

    def __init__(self, replies: list[Reply], reasoning: str = "") -> None:
        super().__init__(base_url="http://mock.invalid/v1", temperature=0.7, seed=1234)
        self.replies = list(replies)
        self.reasoning = reasoning
        self.prompts: list[list[dict[str, Any]]] = []

    def _query(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        self.prompts.append(json.loads(json.dumps(messages)))
        assert kwargs == {} and self.config.model_kwargs["seed"] == 1234
        reply = self.replies.pop(0)
        if callable(reply):
            reply = reply(messages)
        if isinstance(reply, Exception):
            raise reply
        prompt = len(canonical(messages)) // 4
        return {"model": "orch-model",
                "choices": [{"message": {"content": reply, "reasoning_content": self.reasoning or None},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": prompt, "completion_tokens": 25, "total_tokens": prompt + 25}}


def bash(command: str, why: str = "Next step.") -> str:
    return f"{why}\n{FENCE}bash\n{command}\n{FENCE}"


def final(rows: list[dict[str, Any]], notes: str = "") -> str:
    return f"Done.\n{FENCE}json\n{json.dumps({'rows': rows, 'notes': notes})}\n{FENCE}"


def unique_quote(name: str = "p1") -> str:
    """A run of plain words (letters only) that occurs once in the corpus file `name`.md."""
    text = papers()[list(papers())[int(name[1:]) - 1]]
    words = text.split()
    index = Index(text)
    for i in range(200, len(words) - 12):
        window = words[i:i + 12]
        if all(re.fullmatch(r"[A-Za-z]+", w) for w in window):
            quote = " ".join(window)
            try:
                find(index, quote)
                return quote
            except AnchorError:
                continue
    raise AssertionError("no plain unique quote")


def claim_cmd(quote: str, file: str = "p1.md", o: str = "a fact") -> str:
    request = json.dumps({"s": "Paper p1", "p": "states", "o": o, "file": file, "quote": quote})
    return f"echo '{request}' | claim"


def row(claims: list[str] | None = None, fid: str = "f1", rid: str = "r1") -> dict[str, Any]:
    fact: dict[str, Any] = {"id": fid, "s": "Ann Lee", "p": "first author of", "o": "p1"}
    if claims is not None:
        fact["claims"] = claims
    return {"id": rid, "cells": {"author": "Ann Lee", "first_author_papers": 1, "papers": ["p1"]}, "facts": [fact]}


def records(run: RunDir) -> list[dict[str, Any]]:
    return [json.loads(line) for line in run.events.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def corpus(tmp_path: Path) -> tuple[Path, Path]:
    return write_corpus(tmp_path)


def go(tmp_path: Path, corpus: tuple[Path, Path], replies: list[Reply], **kw: Any):
    model = kw.pop("model", None) or ScriptedModel(replies)
    run, outcome, head = research_run(
        runs_root=tmp_path / "runs", run_id=kw.pop("run_id", "r1"), concept=kw.pop("concept", CONCEPT),
        corpus=corpus[0], manifest=corpus[1], condition=kw.pop("condition", "claim_on"),
        sandbox_mode=kw.pop("sandbox_mode", "unsandboxed"), broker=kw.pop("broker", "inprocess"),
        model=model, **SETTINGS, **kw)
    return run, outcome, head, model


# --- pure functions (any OS) -----------------------------------------------------------------------

def test_context_full_detection() -> None:
    assert is_context_full(litellm.exceptions.ContextWindowExceededError("too long", "orch-model", "openai"))
    assert is_context_full(litellm.exceptions.BadRequestError(
        "litellm.ContextWindowExceededError: maximum context length is 65536", "orch-model", "openai"))
    assert not is_context_full(litellm.exceptions.BadRequestError("bad seed", "orch-model", "openai"))


def test_model_keeps_the_key_out_of_its_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-not-a-real-key")
    model = OrchestratorModel(temperature=0.2, seed=7)
    kwargs = model.config.model_kwargs
    assert "api_key" not in kwargs and "sk-test" not in json.dumps(model.serialize())
    assert kwargs["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert (kwargs["max_tokens"], kwargs["temperature"], kwargs["seed"]) == (4096, 0.2, 7)
    assert kwargs["api_base"] == "http://127.0.0.1:4000/v1" and model.config.model_name == "openai/orch-model"


def test_wrapper_sets_the_limits() -> None:
    argv = sandbox.wrapper_argv("echo hi", ulimit_v_kib=2097152)
    assert argv[:2] == ["bash", "-c"] and "ulimit -v" in argv[2]
    assert argv[3:] == ["agent-sandbox", "2097152", "echo hi"]


# --- end to end --------------------------------------------------------------------------------------

def main_script(quote: str) -> list[Reply]:
    return [
        bash('grep -c "the" "$CORPUS/p1.md"', "Count lines first."),          # 1 strict
        'ls "$CORPUS" | head -3',                                               # 2 lenient bare command
        "I should think about this.\nLet me consider the papers.\nThen decide.\nMaybe later.",  # 3 unparsed
        bash(claim_cmd("this sentence was retyped and is not in the paper")),   # 4 claim rejected
        bash(claim_cmd(quote)),                                                 # 5 retried: accepted
        bash("python3 -c \"print('x' * 20000)\""),                              # 6 output over the cap
        final([row(["claim-000009"])]),                                         # 7 cites an unknown claim
        final([row(["claim-000001"]), row(None, "f2", "r2")], "f2 has no claim"),  # 8 valid answer
    ]


def check_main_run(run: RunDir, outcome: Any, head: dict[str, Any], model: ScriptedModel, corpus: tuple[Path, Path],
                   quote: str) -> None:
    assert outcome.exit_status == "submitted" and outcome.steps == 8 and outcome.answer_rows == 2
    report = verify(run.events, run.claims)
    assert report.ok and report.head == head["head"] and report.claims == 2
    recs = records(run)
    calls = [r for r in recs if r["subtype"] == "ai_model_invocation"]
    tools = [r for r in recs if r["subtype"] == "agent_tool"]
    claims = [r for r in recs if r["subtype"] == "claim"]
    coverage = [r for r in recs if r["subtype"] == "coverage"]
    assert [c["step_id"] for c in calls] == list(range(1, 9))
    assert {k: calls[0]["used"][k] for k in ("model", "model_name", "revision", "temperature", "seed")} == {
        "model": "orch-model", "model_name": "Qwen/Qwen3.8-27B-FP8", "revision": "017b9c7", "temperature": 0.7,
        "seed": 1234}
    assert re.fullmatch(r"[0-9a-f]{64}", calls[0]["used"]["prompt_sha256"])
    assert calls[0]["generated"]["usage"]["total_tokens"] > 0 and calls[0]["generated"]["parse"] == "strict"
    assert calls[1]["generated"]["parse"] == "lenient_bare_command"
    # Every command's record points at the model call that emitted it, in the same step.
    by_task = {r["task_id"]: r for r in recs}
    for tool in tools:
        parent = by_task[tool["parent_task_id"]]
        assert parent["subtype"] == "ai_model_invocation" and parent["step_id"] == tool["step_id"]
    assert [t["step_id"] for t in tools] == [1, 2, 4, 5, 6]
    assert [(t["used"]["files_read"], t["used"]["corpus_dir_read"]) for t in tools] == [
        (["p1.md"], False), ([], True), (["p1.md"], False), (["p1.md"], False), ([], False)]
    # Only the reply that became answer.json is marked; every loop record has origin research.
    assert [c["step_id"] for c in calls if c["custom_metadata"]["final_answer"]] == [8]
    assert all(r["custom_metadata"]["origin"] == "research" for r in recs if r["subtype"] != "claim")
    assert [c["generated"]["reason"] for c in coverage] == ["unparsed", "invalid_final_answer"]
    assert coverage[0]["step_id"] == 3 and coverage[1]["step_id"] == 7
    # The rejected claim and its retry are claim steps; the others are not.
    assert {t["step_id"]: t["custom_metadata"]["claim_step"] for t in tools} == {
        1: False, 2: False, 4: True, 5: True, 6: False}
    assert [(c["step_id"], c["status"], c["custom_metadata"].get("reason")) for c in claims] == [
        (4, "rejected", "not_found"), (5, "accepted", None)]
    assert claims[1]["generated"] == {"claim_id": "claim-000001"}
    # Output cap: 8 KB in context, the whole output in out/, a pointer in the observation.
    big = tools[4]
    assert big["generated"]["truncated"] and big["generated"]["output_bytes"] == 20001
    assert (run.root / big["generated"]["output_file"]).read_bytes() == b"x" * 20000 + b"\n"
    observation = model.prompts[6][-1]["content"]
    assert "Output cut at 8,192 of 20,001 bytes" in observation and "step-0006.txt" in observation
    assert 8192 <= observation.count("x") < 8300
    # The agent saw the rejection reason, the nudge and the answer problems.
    assert '"reason": "not_found"' in model.prompts[4][-1]["content"]
    assert "Nothing ran" in model.prompts[3][-1]["content"]
    assert "claim-000009 is not an accepted claim" in model.prompts[7][-1]["content"]
    assert "[Budget: 1 of 150 steps" in model.prompts[1][-1]["content"]
    # answer.json, pairs.jsonl, verify
    answer = json.loads(run.answer.read_text(encoding="utf-8"))
    assert [f["claims"] for r in answer["rows"] for f in r["facts"]] == [["claim-000001"], []]
    assert run.validate(complete=True) == []
    pairs = [json.loads(line) for line in (run.root / "pairs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(p["fact_id"], p["claim_id"], p["file"]) for p in pairs] == [("f1", "claim-000001", "p1.md"),
                                                                         ("f2", None, None)]
    assert " ".join(pairs[0]["quote"].split()) == quote and pairs[1]["quote"] is None
    result = verify_run(run, *corpus)
    assert result.ok, result.errors
    assert {k: result.stats[k] for k in ("steps", "commands", "claims_accepted", "claims_rejected", "claim_steps",
                                         "coverage", "facts", "facts_with_claims")} == {
        "steps": 8, "commands": 5, "claims_accepted": 1, "claims_rejected": 1, "claim_steps": 2, "coverage": 2,
        "facts": 2, "facts_with_claims": 1}
    config = run.load_config()
    assert config["sandbox"]["mode"] == "unsandboxed" and config["loop"]["harness"] == "mini-swe-agent 2.4.6"
    assert config["prompt"]["files"]["system-v1.txt"] == config["prompt"]["sha256"]


@posix_only
def test_end_to_end_in_process_broker(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    quote = unique_quote()
    run, outcome, head, model = go(tmp_path, corpus, main_script(quote))
    check_main_run(run, outcome, head, model, corpus, quote)
    # The system prompt is v1 with the budget filled in; the task names the concept.
    assert "150 steps" in model.prompts[0][0]["content"] and "Recording facts with claim" in model.prompts[0][0]["content"]
    assert CONCEPT["title"] in model.prompts[0][1]["content"]
    assert (run.root / "trajectory.json").is_file()


@posix_only
@pytest.mark.skipif(not POSIX_BROKER, reason="BrokerProcess needs SEQPACKET and SCM_RIGHTS")
def test_end_to_end_broker_process(tmp_path: Path, corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    quote = unique_quote()
    run, outcome, head, model = go(tmp_path, corpus, main_script(quote), broker="process")
    check_main_run(run, outcome, head, model, corpus, quote)
    assert f"head={head['head']}" in capsys.readouterr().out
    assert cli(["verify", str(run.root), "--corpus", str(corpus[0])]) == 0
    assert "claims=1 accepted / 1 rejected claim_steps=2" in capsys.readouterr().out


@posix_only
def test_reasoning_field_is_never_run(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    marker = tmp_path / "ran"
    model = ScriptedModel(["Thinking about it.\nNot sure yet.\nLet me reconsider the plan.\nStill thinking.",
                           final([row([])])],
                          reasoning=f"{FENCE}bash\ntouch {marker}\n{FENCE}")
    run, outcome, _, _ = go(tmp_path, corpus, [], model=model)
    assert outcome.exit_status == "submitted" and not marker.exists()
    assert [r["subtype"] for r in records(run)].count("agent_tool") == 0
    assert all(r["generated"].get("reasoning_sha256") for r in records(run) if r["subtype"] == "ai_model_invocation")


@posix_only
def test_repeated_commands_get_notices(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    replies: list[Reply] = [bash('ls "$CORPUS"'), bash('ls   "$CORPUS"'), bash('ls "$CORPUS"'), bash("pwd"),
                            final([row([])])]
    run, outcome, _, model = go(tmp_path, corpus, replies)
    assert outcome.exit_status == "submitted"
    second, third, other = (model.prompts[i][-1]["content"] for i in (2, 3, 4))
    assert "same command in the previous step" in second and "You have" not in second
    assert "same command 3 times in a row. You have 147 steps and" in third
    assert "Notice" not in other
    tools = [r for r in records(run) if r["subtype"] == "agent_tool"]
    assert [t["custom_metadata"]["repeat"] for t in tools] == [1, 2, 3, 1]


@posix_only
def test_step_budget_runs_out_then_the_answer(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    replies: list[Reply] = [bash("echo one"), bash("echo two"), final([row([])], "partial")]
    run, outcome, _, model = go(tmp_path, corpus, replies, budget={"steps": 2, "tokens": 400_000, "announced": True})
    assert outcome.exit_status == "submitted" and outcome.steps == 2 and outcome.model_calls == 3
    assert "Budget used up" in model.prompts[2][-1]["content"]
    assert "2 steps" in model.prompts[0][0]["content"]
    calls = [r for r in records(run) if r["subtype"] == "ai_model_invocation"]
    assert [c["custom_metadata"]["phase"] for c in calls] == ["research", "research", "conclude"]
    assert run.load_config()["budget"]["steps"] == 2


@posix_only
def test_budget_exhausted_without_answer(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    replies: list[Reply] = [bash("echo one"), bash("echo two"), bash("echo three")]
    run, outcome, _, _ = go(tmp_path, corpus, replies, budget={"steps": 1, "tokens": 400_000, "announced": True})
    assert outcome.exit_status == "budget" and outcome.model_calls == 3
    recs = records(run)
    assert [r["generated"]["reason"] for r in recs if r["subtype"] == "coverage"] == [
        "command_not_run", "command_not_run", "no_final_answer"]
    assert [r["step_id"] for r in recs if r["subtype"] == "agent_tool"] == [1]  # conclude replies never run
    answer = json.loads(run.answer.read_text(encoding="utf-8"))
    assert answer["rows"] == [] and "budget" in answer["notes"]
    assert verify_run(run, *corpus).ok
    assert (run.root / "pairs.jsonl").read_bytes() == b""


@posix_only
def test_token_budget(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    replies: list[Reply] = [bash("echo one"), final([row([])])]
    _, outcome, _, model = go(tmp_path, corpus, replies, budget={"steps": 150, "tokens": 10, "announced": True})
    assert outcome.exit_status == "submitted" and outcome.steps == 1
    assert "Budget used up" in model.prompts[1][-1]["content"]


@posix_only
def test_context_full_concludes_without_retry(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    quote = unique_quote()
    overflow = litellm.exceptions.ContextWindowExceededError(
        "litellm.ContextWindowExceededError: 70000 tokens > 65536", "orch-model", "openai")
    replies: list[Reply] = [bash(claim_cmd(quote)), bash("python3 -c \"print('y' * 5000)\""), overflow,
                            final([row(["claim-000001"])])]
    run, outcome, _, model = go(tmp_path, corpus, replies)
    assert outcome.exit_status == "submitted" and len(model.prompts) == 4  # the 400 was not retried
    last = model.prompts[3]
    assert "Context full" in last[-1]["content"]
    outputs = [m["content"] for m in last if m["role"] == "user"][1:-1]
    assert all(o.startswith("[output removed: context full]") for o in outputs)
    assert '"claim_id": "claim-000001"' in outputs[0] and "yyyy" not in "".join(outputs)
    failed = [r for r in records(run) if r["subtype"] == "ai_model_invocation" and r["status"] == "failed"]
    assert len(failed) == 1 and failed[0]["generated"] == {"error": "context_window_exceeded"}
    assert verify_run(run, *corpus).ok


@posix_only
def test_context_full_three_times_ends_the_run(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    def overflow() -> Exception:
        return litellm.exceptions.ContextWindowExceededError("too long", "orch-model", "openai")
    replies: list[Reply] = [bash("echo a"), overflow(), overflow(), overflow()]
    run, outcome, _, model = go(tmp_path, corpus, replies)
    assert outcome.exit_status == "context_full" and len(model.prompts) == 4
    assert json.loads(run.answer.read_text(encoding="utf-8"))["rows"] == []


@posix_only
def test_other_400_is_not_retried_and_fails_the_run(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    replies: list[Reply] = [litellm.exceptions.BadRequestError("unsupported parameter", "orch-model", "openai")]
    with pytest.raises(litellm.exceptions.BadRequestError):
        go(tmp_path, corpus, replies)
    run = RunDir(tmp_path / "runs" / "r1")
    assert [r["generated"]["reason"] for r in records(run) if r["subtype"] == "coverage"] == [
        "run_error", "no_final_answer"]
    assert verify(run.events, run.claims).ok and run.validate(complete=True) == []


@posix_only
def test_claim_off_baseline(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    quote = unique_quote()
    replies: list[Reply] = [bash(claim_cmd(quote)), final([row()])]
    run, outcome, _, model = go(tmp_path, corpus, replies, condition="claim_off")
    assert outcome.exit_status == "submitted"
    assert "claim" not in model.prompts[0][0]["content"].lower()
    out = (run.out / "step-0001.txt").read_text(encoding="utf-8")
    assert "claim" in out and "not found" in out  # bash: claim: command not found
    assert run.claims.read_bytes() == b""
    config = run.load_config()
    assert config["condition"] == "claim_off" and config["prompt"]["files"]["system-v1-baseline.txt"] == config["prompt"]["sha256"]
    assert verify_run(run, *corpus).ok


def test_claim_off_environment_has_no_claim_tool(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """2.4: the baseline sandbox has no claim shim on PATH, no agent code mounted and no CLAIM_FD."""
    from agent.loop import AGENT_DIR, SandboxEnvironment
    from agent.rundir import RunDir as Run
    run = Run.create(tmp_path / "runs", "x", CONCEPT, corpus_manifest=corpus[1], condition="claim_off",
                     prompt_version="v1", prompt_sha256="a" * 64, **SETTINGS)
    on, off = (SandboxEnvironment(run, corpus=corpus[0], mode="unsandboxed", claim=c) for c in (True, False))
    assert str(AGENT_DIR / "bin") in on.path().split(":") and str(AGENT_DIR / "bin") not in off.path().split(":")
    assert str(AGENT_DIR) in on.readonly() and str(AGENT_DIR) not in off.readonly()
    assert "CLAIM_FD" not in off.environment(None) and on.environment(7)["CLAIM_FD"] == "7"
    assert off.path().split(":")[-3:] == on.path().split(":")[-3:]  # otherwise the same tools


@posix_only
def test_claim_off_run_sees_no_claim_and_no_fd(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    probe = 'command -v claim || echo NO_CLAIM; echo "fd=${CLAIM_FD:-unset}"; ls /proc/self/fd | wc -l'
    run, outcome, _, _ = go(tmp_path, corpus, [bash(probe), final([row()])], condition="claim_off")
    out = (run.out / "step-0001.txt").read_text(encoding="utf-8").split()
    assert outcome.exit_status == "submitted" and out[:2] == ["NO_CLAIM", "fd=unset"]
    assert int(out[2]) <= 5  # stdin, stdout, stderr, ls's own directory fd: nothing passed through
    tool = next(r for r in records(run) if r["subtype"] == "agent_tool")
    assert tool["custom_metadata"]["claim_step"] is False and tool["custom_metadata"]["claims"] == 0


@posix_only
def test_conditions_share_model_budget_seed_and_answer_format(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """2.4: claim_on and claim_off differ only in the condition, the system prompt's claim block and the tool."""
    from agent import prompts
    budget = {"steps": 40, "tokens": 90_000, "announced": True}
    runs = {}
    for condition in ("claim_on", "claim_off"):
        runs[condition] = go(tmp_path, corpus, [bash("echo hi"), final([row()])], run_id=condition,
                             condition=condition, budget=budget)
    (on, _, _, m_on), (off, _, _, m_off) = runs["claim_on"], runs["claim_off"]
    c_on, c_off = on.load_config(), off.load_config()
    differ = {k for k in c_on if c_on[k] != c_off[k]}
    assert differ == {"run_id", "created_at", "condition", "prompt"}
    assert c_on["prompt"]["files"]["task-v1.txt"] == c_off["prompt"]["files"]["task-v1.txt"]
    assert c_off["budget"] == budget and c_off["sampling"] == {"temperature": 0.7, "seed": 1234}
    # The prompts the model saw: the same task message, the system prompt minus the claim block only.
    assert m_on.prompts[0][1] == m_off.prompts[0][1]
    assert prompts.baseline_from(m_on.prompts[0][0]["content"]) == m_off.prompts[0][0]["content"]
    assert "40 steps" in m_off.prompts[0][0]["content"] and "90000" in m_off.prompts[0][0]["content"]
    calls = [[r for r in records(run) if r["subtype"] == "ai_model_invocation"] for run in (on, off)]
    keys = ("model", "model_name", "revision", "temperature", "seed", "max_tokens", "thinking")
    assert [{k: c["used"][k] for k in keys} for c in calls[0]] == [{k: c["used"][k] for k in keys} for c in calls[1]]
    # The same answer format: both validate against the concept, every fact unsourced and origin research.
    a_on, a_off = (json.loads(r.answer.read_text(encoding="utf-8")) for r in (on, off))
    assert a_on == a_off and a_off["rows"][0]["facts"][0]["claims"] == [] and a_off["rows"][0]["facts"][0]["origin"] == "research"


@posix_only
def test_command_timeout(tmp_path: Path, corpus: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    import agent.rundir
    monkeypatch.setitem(agent.rundir.COMMAND_LIMITS, "timeout_s", 1)
    replies: list[Reply] = [bash("sleep 30; echo late"), final([row([])])]
    run, outcome, _, model = go(tmp_path, corpus, replies)
    tool = next(r for r in records(run) if r["subtype"] == "agent_tool")
    assert tool["generated"]["exit_code"] == 124 and tool["generated"]["timed_out"] and tool["status"] == "timeout"
    assert "time limit" in model.prompts[1][-1]["content"]
    assert run.load_config()["command_limits"]["timeout_s"] == 1


@posix_only
@pytest.mark.skipif(not os.path.isdir("/proc"), reason="the session scan reads /proc")
def test_processes_left_behind_are_removed(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """A background process the command leaves (in the command's own process group) goes after the step."""
    replies: list[Reply] = [bash("sleep 300 >/dev/null 2>&1 & echo $!"), final([row([])])]
    run, _, _, _ = go(tmp_path, corpus, replies)
    pid = int((run.out / "step-0001.txt").read_text(encoding="utf-8").strip())
    try:
        state = Path(f"/proc/{pid}/stat").read_bytes().rsplit(b") ", 1)[1][:1]
    except OSError:
        state = b"gone"
    assert state in (b"gone", b"Z")  # killed (at most a zombie waiting for its new parent)
    tool = next(r for r in records(run) if r["subtype"] == "agent_tool")
    assert tool["custom_metadata"]["cleanup"] in ("sigterm", "sigkill")


@posix_only
def test_memory_limit_applies(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    replies: list[Reply] = [bash("ulimit -v"), final([row([])])]
    run, _, _, _ = go(tmp_path, corpus, replies)
    assert (run.out / "step-0001.txt").read_text(encoding="utf-8").strip() == "2097152"


@posix_only
def test_verify_fails_on_tampering(tmp_path: Path, corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    quote = unique_quote()
    run, _, _, _ = go(tmp_path, corpus, [bash(claim_cmd(quote)), final([row(["claim-000001"])])])
    assert cli(["verify", str(run.root), "--corpus", str(corpus[0])]) == 0
    # An answer that cites a claim the run never accepted.
    answer = json.loads(run.answer.read_text(encoding="utf-8"))
    answer["rows"][0]["facts"][0]["claims"] = ["claim-000002"]
    run.answer.write_bytes(canonical(answer).encode("utf-8") + b"\n")
    assert cli(["verify", str(run.root), "--corpus", str(corpus[0])]) == 1
    assert "claim-000002 is not an accepted claim" in capsys.readouterr().out
    # A corpus file changed after the run: the anchor no longer resolves at its offsets.
    answer["rows"][0]["facts"][0]["claims"] = ["claim-000001"]
    run.answer.write_bytes(canonical(answer).encode("utf-8") + b"\n")
    paper = corpus[0] / "p1.md"
    paper.write_bytes(b"inserted line\n" + paper.read_bytes())
    report = verify_run(run, *corpus)
    assert any("anchor" in e for e in report.errors), report.errors
    # A broken chain.
    run.events.write_bytes(run.events.read_bytes().replace(b'"step_id":1', b'"step_id":7', 1))
    assert any(e.startswith("chain:") for e in verify_run(run, *corpus).errors)


@posix_only
def test_pairs_command_rewrites_the_file(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    quote = unique_quote()
    run, _, _, _ = go(tmp_path, corpus, [bash(claim_cmd(quote)), final([row(["claim-000001"])])])
    written = (run.root / "pairs.jsonl").read_bytes()
    (run.root / "pairs.jsonl").unlink()
    assert cli(["pairs", str(run.root)]) == 0
    assert (run.root / "pairs.jsonl").read_bytes() == written and b"\r" not in written


@posix_only
def test_timeline_html(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    quote = unique_quote()
    run, _, _, _ = go(tmp_path, corpus, main_script(quote))
    assert cli(["timeline", str(run.root)]) == 0
    page = (run.root / "timeline.html").read_text(encoding="utf-8")
    assert page.count("<section id=step-") == 8 and "claim rejected: not_found" in page
    assert "claim claim-000001 accepted" in page and "coverage: unparsed" in page and "final answer" in page
    assert "print(&#x27;x&#x27; * 20000)" in page and "more lines" not in page  # escaped; 1-line output
    assert "<script" not in page


@posix_only
@pytest.mark.skipif(sandbox.landlock_abi() is None, reason="kernel without Landlock")
def test_landlock_mode(tmp_path: Path, corpus: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    # Landlock rules do not hold on WSL's /mnt/c (drvfs): copy the sandbox-side files to tmp.
    import agent.loop
    code = tmp_path / "agent-code"
    (code / "bin").mkdir(parents=True)
    for name in ("sandbox.py", "claim_client.py", "bin/claim"):
        (code / name).write_bytes((agent.loop.AGENT_DIR / name).read_bytes())
    (code / "bin" / "claim").chmod(0o755)
    monkeypatch.setattr(agent.loop, "AGENT_DIR", code)
    quote = unique_quote()
    probe = ('touch "$CORPUS/x" 2>/dev/null && echo CORPUS_WRITABLE || echo CORPUS_READONLY; '
             'touch here && echo SCRATCH_OK; '
             'python3 -c "import socket\ntry:\n socket.socket(socket.AF_INET)\n print(\'NET_OPEN\')\n'
             'except OSError:\n print(\'NET_BLOCKED\')"; ' + claim_cmd(quote))
    run, outcome, _, _ = go(tmp_path, corpus, [bash(probe), final([row(["claim-000001"])])], sandbox_mode="landlock")
    out = (run.out / "step-0001.txt").read_text(encoding="utf-8")
    assert "CORPUS_READONLY" in out and "SCRATCH_OK" in out and "NET_BLOCKED" in out, out
    assert '"claim_id": "claim-000001"' in out
    assert run.load_config()["sandbox"]["mode"] == "landlock" and outcome.exit_status == "submitted"


def test_landlock_refused_where_missing(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    if sandbox.landlock_abi() is not None:
        pytest.skip("this kernel has Landlock")
    with pytest.raises(RuntimeError, match="unsandboxed"):
        go(tmp_path, corpus, [], sandbox_mode="landlock")
    assert not (tmp_path / "runs" / "r1").exists()


def test_cli_run_needs_a_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORPUS", raising=False)
    with pytest.raises(SystemExit, match="corpus"):
        cli(["run", "--concept", "x.json", "--run-id", "r", "--temperature", "0", "--seed", "1"])
