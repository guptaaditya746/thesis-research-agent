"""The loop after M1-real (rows 1.13, 1.15), end to end with a scripted model.

What the four real runs showed (tests/RESULTS.md, M1-real) and what these tests pin:
- budget notices at 50, 75 and 90 % of either budget, one each;
- conclude replies decoded under the reply schema (extra_body structured_outputs), parsed as
  `guided_answer`, recorded in the call record and config.json;
- the draft answer (scratch/answer-draft.json) taken when the run ends without an answer, and the
  whole chain after it: verify, pairs, graph, PROV export, the five queries;
- proactive output masking (last 8 commands; last 4 after a prompt over 45,000 tokens);
- six identical commands in a row end research (`repeats`);
- prompt v1 runs with the loop and the budget the M1-real runs had;
- `agent run` defaults: 60 steps / 2,000,000 tokens, prompt v2.
And what the review of the branch found: a draft that is valid JSON but no answer never crashes
the harness; a refused schema falls back to free decoding; conclude replies get room for a whole
answer; trajectory.json keeps masked outputs, so every prompt hash can be rebuilt.
Same harness as test_loop: everything but the model's HTTP call is real.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import shlex
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("minisweagent")
pytest.importorskip("litellm")

import litellm  # noqa: E402
from rdflib import Literal  # noqa: E402
from rdflib.namespace import PROV  # noqa: E402

from agent import loop as loop_mod  # noqa: E402
from agent import prov, schema  # noqa: E402
from agent.answer import reply_schema  # noqa: E402
from agent.canonical import canonical_bytes, sha256_hex  # noqa: E402
from agent.cli import main as cli  # noqa: E402
from agent.loop import LEGACY_V1, LoopSettings, Outcome, settings_for  # noqa: E402
from agent.rundir import RunDir  # noqa: E402
from agent.verify import verify_run  # noqa: E402

from .conftest import REPO  # noqa: E402
from .test_loop import (CONCEPT, FENCE, Reply, ScriptedModel, bash, claim_cmd, corpus, final, go,  # noqa: E402, F401
                        posix_only, records, row, unique_quote)

THINKING_OFF = {"chat_template_kwargs": {"enable_thinking": False}}
REPO_M1 = REPO / "tests" / "M1-real"


def tool_call(command: str) -> str:
    """How Qwen3.8 replied in M1-real, also when asked to conclude."""
    return f"<tool_call>\n<function=bash>\n<parameter=command>\n{command}\n</parameter>\n</function>\n</tool_call>"


def bare(rows: list[dict[str, Any]], notes: str = "") -> str:
    """A conclude reply under structured outputs: the answer object and nothing else."""
    return json.dumps({"rows": rows, "notes": notes})


def write_draft(rows: list[dict[str, Any]], notes: str = "draft notes") -> str:
    text = json.dumps({"rows": rows, "notes": notes})
    return bash(f"cat > answer-draft.json <<'EOF'\n{text}\nEOF\necho saved", "Update the draft.")


def calls_of(run: RunDir) -> list[dict[str, Any]]:
    return [r for r in records(run) if r["subtype"] == "ai_model_invocation"]


def coverage_of(run: RunDir) -> list[dict[str, Any]]:
    return [r for r in records(run) if r["subtype"] == "coverage"]


# --- settings and config (any OS) ----------------------------------------------------------------------

def test_settings_and_config_schema() -> None:
    """Both loop settings validate in config.json; the M1-real configs (no 1.13/1.15 keys) still do."""
    assert settings_for("v1") is LEGACY_V1 and settings_for("v2") == LoopSettings()
    base = json.loads((REPO_M1 / "c3-on-2" / "config.json").read_text(encoding="utf-8"))
    assert schema.check("config", base) == []
    for settings in (LoopSettings(), LEGACY_V1):
        config = base | {"loop": {"harness": "mini-swe-agent 2.4.6", "base_url": "x", **settings.config()}}
        assert schema.check("config", config) == []
    assert LoopSettings().config() == {
        "conclude_replies": 2, "conclude_decoding": "structured_outputs", "conclude_max_tokens": 16384,
        "masking": {"keep": 8, "keep_tight": 4, "tight_above_prompt_tokens": 45000},
        "budget_warnings": [50, 75, 90], "repeat_stop": 6, "draft_file": "answer-draft.json", "m1_notices": False}
    assert LEGACY_V1.config() | {"masking": None, "conclude_decoding": "free", "conclude_max_tokens": None,
                                 "m1_notices": True} == LEGACY_V1.config()
    for bad in ({"conclude_decoding": "regex"}, {"mask_keep_tight": 0}, {"mask_keep_tight": 9},
                {"draft_file": "../answer.json"}, {"conclude_max_tokens": 0}):
        with pytest.raises(ValueError):
            LoopSettings(**bad)


def test_agent_defaults_to_its_prompt_versions_settings(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """ResearchAgent built without settings resolves them as research_run does (v1: the M1-real loop)."""
    from agent import prompts
    from agent.broker_client import InProcessBroker
    from agent.loop import ResearchAgent, SandboxEnvironment
    run = RunDir.create(tmp_path / "runs", "x", CONCEPT, corpus_manifest=corpus[1], condition="claim_on",
                        prompt_version="v1", prompt_sha256="a" * 64, temperature=0.7, seed=1, git_commit="c" * 40,
                        agent_root_manifest_sha256="b" * 64)
    env = SandboxEnvironment(run, corpus=corpus[0], mode="unsandboxed", claim=True)
    broker = InProcessBroker(run.root, *corpus)
    try:
        for version, settings in (("v1", LEGACY_V1), ("v2", LoopSettings())):
            agent = ResearchAgent(ScriptedModel([]), env, broker=broker, run=run, concept=CONCEPT,
                                  prompt=prompts.load(version, "claim_on"), budget={"steps": 1, "tokens": 1})
            assert agent.settings == settings
    finally:
        broker.close()


def test_cli_run_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """1.13: `agent run` defaults to the provisional budget and prompt v2; v1 brings the M1-real loop and budget back."""
    import agent.rundir
    seen: list[dict[str, Any]] = []

    def fake_run(**kw: Any) -> tuple[None, Outcome, dict[str, Any]]:
        seen.append(kw)
        return None, Outcome("budget", 60, 62, 2_000_100, 3, "draft"), {"head": "h"}

    monkeypatch.setattr(loop_mod, "research_run", fake_run)
    monkeypatch.setattr(agent.rundir, "git_head", lambda repo: "c" * 40)
    monkeypatch.setattr("agent.cli.stop_on_sigterm", lambda: None)  # keep pytest's own SIGTERM handling
    (tmp_path / "concept.json").write_text(json.dumps(CONCEPT), encoding="utf-8")
    base = ["run", "--concept", str(tmp_path / "concept.json"), "--run-id", "r", "--temperature", "0.7", "--seed", "1",
            "--corpus", str(tmp_path)]
    assert cli(base) == 1
    out = capsys.readouterr().out
    assert "exit=budget" in out and "answer=draft" in out
    assert seen[0]["budget"] == {"steps": 60, "tokens": 2_000_000, "announced": True}
    assert seen[0]["prompt_version"] == "v2" and seen[0]["settings"] == LoopSettings()
    cli([*base, "--prompt-version", "v1"])  # the M1-real runs: their loop and their budget
    assert seen[1]["prompt_version"] == "v1" and seen[1]["settings"] == LEGACY_V1
    assert seen[1]["budget"] == {"steps": 150, "tokens": 400_000, "announced": True}
    cli([*base, "--conclude-decoding", "guided_json", "--steps", "7"])
    assert seen[2]["settings"] == dataclasses.replace(LoopSettings(), conclude_decoding="guided_json")
    assert seen[2]["budget"] == {"steps": 7, "tokens": 2_000_000, "announced": True}
    cli([*base, "--prompt-version", "v1", "--tokens", "9"])
    assert seen[3]["budget"] == {"steps": 150, "tokens": 9, "announced": True}


# --- budget notices ------------------------------------------------------------------------------------

@posix_only
def test_budget_notices_once_each(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """50 / 75 / 90 % of the step budget: one notice each, in the observation of the step that passes it."""
    replies: list[Reply] = [bash(f"echo {n}") for n in range(1, 10)] + [final([row([])])]
    run, outcome, _, model = go(tmp_path, corpus, replies, budget={"steps": 10, "tokens": 10**9, "announced": True})
    assert outcome.exit_status == "submitted"
    shown = [model.prompts[n][-1]["content"] for n in range(1, 10)]  # observation of step n, seen at call n + 1
    notices = {n: s.split("\n")[-2] for n, s in enumerate(shown, 1) if "[Budget notice" in s}
    assert sorted(notices) == [5, 8, 9]
    assert notices[5].startswith("[Budget notice: 50% of the budget is used (5 steps and")
    assert "Bring ./answer-draft.json up to date" in notices[5]
    assert "75%" in notices[8] and "Stop opening new leads" in notices[8] and "update ./answer-draft.json" in notices[8]
    assert "90%" in notices[9] and "Conclude now" in notices[9]
    assert all(s.splitlines()[-1].startswith(f"[Budget: {n} of 10 steps and ") for n, s in enumerate(shown, 1))


@posix_only
def test_token_notices_give_the_highest_threshold_passed(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """A step that passes 50 and 75 % of the token budget at once gives one notice, for 75 %."""
    model = ScriptedModel([bash("echo a"), bash("echo b"), bash("echo c"), final([row([])])],
                          prompt_tokens=[7_975, 1_000, 10, 10])
    _, outcome, _, _ = go(tmp_path, corpus, [], model=model, budget={"steps": 60, "tokens": 10_000, "announced": True})
    assert outcome.exit_status == "submitted"
    first, second, third = (model.prompts[n][-1]["content"] for n in (1, 2, 3))
    assert "[Budget notice: 75%" in first and "50%" not in first  # 8,000 of 10,000 tokens
    assert "[Budget notice: 90%" in second and "Budget notice" not in third


# --- conclusion under the reply schema -------------------------------------------------------------------

@posix_only
@pytest.mark.parametrize("decoding", ["structured_outputs", "guided_json"])
def test_conclude_is_decoded_under_the_reply_schema(tmp_path: Path, corpus: tuple[Path, Path], decoding: str) -> None:
    quote = unique_quote()
    replies: list[Reply] = [bash(claim_cmd(quote)), bare([row(["claim-000001"])], "checked one paper")]
    settings = dataclasses.replace(LoopSettings(), conclude_decoding=decoding)
    run, outcome, _, model = go(tmp_path, corpus, replies, budget={"steps": 1, "tokens": 10**6, "announced": True},
                                settings=settings)
    assert outcome.exit_status == "submitted" and outcome.answer_from == "final" and outcome.answer_rows == 1
    schema_sent = reply_schema(CONCEPT)
    guided = {"structured_outputs": {"json": schema_sent}} if decoding == "structured_outputs" else {"guided_json": schema_sent}
    # research free; conclude guided, with room for a whole answer
    assert model.kwargs == [{}, {"extra_body": THINKING_OFF | guided, "max_tokens": 16_384}]
    conclude = model.prompts[1][-1]["content"]
    assert conclude.startswith("Budget used up.") and "the final answer alone, as one JSON object" in conclude
    calls = calls_of(run)
    assert [c["used"]["decoding"] for c in calls] == ["free", decoding]
    assert [c["used"]["max_tokens"] for c in calls] == [4096, 16_384]
    assert "schema_sha256" not in calls[0]["used"]
    assert calls[1]["used"]["schema_sha256"] == sha256_hex(canonical_bytes(schema_sent))
    assert calls[1]["generated"]["parse"] == "guided_answer" and calls[1]["custom_metadata"]["final_answer"]
    assert run.load_config()["loop"]["conclude_decoding"] == decoding
    answer = json.loads(run.answer.read_text(encoding="utf-8"))
    assert answer["notes"] == "checked one paper" and answer["rows"][0]["facts"][0]["claims"] == ["claim-000001"]
    assert verify_run(run, *corpus).ok


@posix_only
def test_conclude_when_the_server_ignores_the_schema(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """M1-real: both conclude replies were commands. A reply cut inside the JSON is an invalid answer, not a command."""
    replies: list[Reply] = [bash("echo one"), tool_call("ls"), '{"rows": [{"id": "r1", "cells": {"author": "A']
    model = ScriptedModel(replies, finish_reasons=["stop", "stop", "length"])
    run, outcome, _, _ = go(tmp_path, corpus, [], model=model, budget={"steps": 1, "tokens": 10**6, "announced": True})
    assert outcome.exit_status == "budget" and outcome.answer_from == "none"
    assert [c["generated"]["parse"] for c in calls_of(run)] == ["strict", "lenient_tool_call", "guided_answer"]
    reasons = [c["generated"]["reason"] for c in coverage_of(run)]
    assert reasons == ["command_not_run", "invalid_final_answer", "no_final_answer"]
    problems = coverage_of(run)[1]["generated"]["detail"]
    assert "cut at the 16,384-token reply limit" in problems[0] and "not valid JSON" in problems[1]
    assert coverage_of(run)[2]["generated"]["detail"] == {"exit_status": "budget"}  # no draft


@posix_only
def test_a_refused_schema_falls_back_to_free_decoding(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """A 400 on the guided call that is not context-full (the grammar backend refuses the schema) does not
    fail the run: the reply is asked for again, decoded freely, and so are all later conclude replies."""
    refused = litellm.exceptions.BadRequestError("xgrammar: unsupported JSON schema", "orch-model", "openai")
    replies: list[Reply] = [bash("echo one"), refused, tool_call("ls"), bare([row([])], "after the refusal")]
    run, outcome, _, model = go(tmp_path, corpus, replies, budget={"steps": 1, "tokens": 10**6, "announced": True})
    assert outcome.exit_status == "submitted" and outcome.answer_from == "final" and outcome.model_calls == 4
    assert [("structured_outputs" in k.get("extra_body", {}), k.get("max_tokens")) for k in model.kwargs] == [
        (False, None), (True, 16_384), (False, 16_384), (False, 16_384)]
    assert model.prompts[1] == model.prompts[2]  # the same reply asked for again, without the schema
    calls = calls_of(run)
    assert [(c["status"], c["used"]["decoding"]) for c in calls] == [
        ("finished", "free"), ("failed", "structured_outputs"), ("finished", "free"), ("finished", "free")]
    failed = calls[1]
    assert failed["generated"] == {"error": "guided_decoding_rejected"} and "xgrammar" in failed["custom_metadata"]["detail"]
    assert failed["used"]["schema_sha256"] == sha256_hex(canonical_bytes(reply_schema(CONCEPT)))
    assert [c["generated"]["parse"] for c in calls[2:]] == ["lenient_tool_call", "lenient_bare_answer"]
    cov = coverage_of(run)
    assert [c["generated"]["reason"] for c in cov] == ["guided_decoding_rejected", "command_not_run"]
    assert cov[0]["parent_task_id"] == failed["task_id"] and cov[0]["generated"]["detail"]["now"] == "free"
    assert model.prompts[3][-1]["content"].startswith("No more commands run now. Reply with the final answer in one "
                                                      "fenced json block.")
    assert verify_run(run, *corpus).ok


@posix_only
def test_conclude_reply_limit_fits_the_context(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """A conclude reply may use up to 16,384 tokens, but no more than the context leaves, and never less than 4,096."""
    from agent.loop import CONTEXT_MARGIN
    limits = {}
    for last_prompt in (30_000, 55_000, 63_000):
        model = ScriptedModel([bash("echo one"), final([row([])])], prompt_tokens=[last_prompt, 10])
        _, _, _, _ = go(tmp_path / str(last_prompt), corpus, [], model=model,
                        budget={"steps": 1, "tokens": 10**6, "announced": True})
        added = sum(len(m["content"]) for m in model.prompts[1][-2:]) // 3  # the observation and the conclude notice
        limits[last_prompt] = (model.kwargs[1]["max_tokens"], 65_536 - last_prompt - 25 - added - CONTEXT_MARGIN)
    assert limits[30_000][0] == 16_384
    assert limits[55_000][0] == limits[55_000][1] and 4096 < limits[55_000][0] < 16_384
    assert limits[63_000][0] == 4096


# --- the draft answer ----------------------------------------------------------------------------------

@posix_only
def test_answer_from_draft_and_everything_after_it(tmp_path: Path, corpus: tuple[Path, Path],
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    """The M1-real ending (budget, then commands instead of an answer) now leaves the draft as the answer."""
    quote = unique_quote()
    draft_rows = [row(["claim-000001"]), row(None, "f2", "r2")]
    replies: list[Reply] = [bash(claim_cmd(quote)), write_draft(draft_rows), bash("echo three"),
                            tool_call("rg -l x $CORPUS"), tool_call("ls")]
    run, outcome, head, model = go(tmp_path, corpus, replies, budget={"steps": 3, "tokens": 10**6, "announced": True})
    assert outcome == Outcome("budget", 3, 5, outcome.tokens, 2, "draft")
    # The conclude notice showed the draft.
    conclude = model.prompts[3][-1]["content"]
    assert "Your draft ./answer-draft.json:\n{" in conclude and "claim-000001" in conclude
    # answer.json is the draft, completed and checked like a final answer, and says where it came from.
    draft_bytes = (run.scratch / "answer-draft.json").read_bytes()
    answer = json.loads(run.answer.read_text(encoding="utf-8"))
    assert answer["notes"] == "harness: answer taken from the agent's draft file (exit status budget). draft notes"
    assert [f["claims"] for r in answer["rows"] for f in r["facts"]] == [["claim-000001"], []]
    assert all(f["origin"] == "research" for r in answer["rows"] for f in r["facts"])
    cov = coverage_of(run)
    assert [c["generated"]["reason"] for c in cov] == ["command_not_run", "command_not_run", "answer_from_draft"]
    assert cov[-1]["generated"]["detail"] == {"exit_status": "budget", "rows": 2, "draft": {
        "file": "scratch/answer-draft.json", "copy": "answer.draft.json", "bytes": len(draft_bytes),
        "sha256": hashlib.sha256(draft_bytes).hexdigest()}}
    assert (run.root / "answer.draft.json").read_bytes() == draft_bytes  # kept where the sandbox cannot change it
    assert not any(c["custom_metadata"]["final_answer"] for c in calls_of(run))
    # verify, pairs, graph, PROV export and the five queries all work on it.
    report = verify_run(run, *corpus)
    assert report.ok, report.errors
    assert report.stats["facts"] == 2 and report.stats["facts_with_claims"] == 1
    pairs = [json.loads(line) for line in (run.root / "pairs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(p["fact_id"], p["claim_id"]) for p in pairs] == [("f1", "claim-000001"), ("f2", None)]
    root, manifest = str(run.root), str(corpus[1])
    assert cli(["verify", root, "--corpus", str(corpus[0])]) == 0
    assert cli(["graph", root, "--manifest", manifest]) == 0
    assert cli(["export-prov", root]) == 0
    capsys.readouterr()
    for query in (["1"], ["2", "--fact", "f1"], ["3", "--step", "1"],
                  ["4", "--corpus", str(corpus[0]), "--manifest", manifest], ["5"]):
        assert cli(["query", query[0], root, *query[1:]]) == 0, query
    out = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [r["claim_id"] for r in out if "edge_id" in r] == ["claim-000001"]  # query 1
    assert any(r.get("fact_id") == "f1" and r["claim_id"] == "claim-000001" and r["step_id"] == 1 for r in out)
    assert [r["fact_id"] for r in out if "cited" in r] == ["f2"]  # query 5: the unsourced fact
    # PROV: the answer was generated by the harness taking the draft, not by a model call.
    g = prov.load(run)
    iri = prov.Iris(run.run_id)
    assert (iri("answer"), prov.OURS.answerSource, Literal("draft")) in g
    assert (iri("answer"), PROV.wasGeneratedBy, iri("task", cov[-1]["task_id"])) in g
    assert (iri("answer"), PROV.wasDerivedFrom, iri("draft")) in g
    assert (iri("draft"), prov.OURS.sha256, Literal(hashlib.sha256(draft_bytes).hexdigest())) in g
    assert (iri("draft"), prov.OURS.fileName, Literal("answer.draft.json")) in g
    assert (iri("task", cov[-1]["task_id"]), PROV.used, iri("draft")) in g
    # verify holds the copy to the recorded hash.
    (run.root / "answer.draft.json").write_bytes(draft_bytes + b" ")
    assert any("answer.draft.json is not the draft answer_from_draft recorded" in e for e in verify_run(run, *corpus).errors)
    (run.root / "answer.draft.json").unlink()
    assert any("answer.draft.json (answer_from_draft) is missing" in e for e in verify_run(run, *corpus).errors)


def draft_text(text: str) -> str:
    """A command that writes a draft whose bytes are exactly `text`."""
    return bash(f"printf '%s' {shlex.quote(text)} > answer-draft.json")


@posix_only
@pytest.mark.parametrize("make, problem", [
    (lambda: write_draft([row(["claim-000009"])]), "claim-000009 is not an accepted claim of this run"),
    (lambda: write_draft([{"id": "r1", "facts": []}]), "rows/0"),
    (lambda: bash("ln -s ../config.json answer-draft.json"), "not a regular file"),
    (lambda: bash("mkfifo answer-draft.json"), "not a regular file"),
    # JSON that parses but must not crash the harness (review of 1.13): a non-list facts, non-finite numbers, depth
    (lambda: write_draft([{"id": "r1", "facts": 3}]), "rows/0"),
    (lambda: draft_text('{"rows": [{"id": "r1", "facts": [{"id": "f1", "s": "a", "p": "b", "o": NaN}]}], "notes": ""}'),
     "NaN is not a JSON number"),
    (lambda: draft_text('{"rows": [], "notes": "", "x": 1e400}'), "1e400 is not a finite number"),
    (lambda: bash("python3 -c 'print(\"{\\\"rows\\\": \" + \"[\" * 200000 + \"]\" * 200000 + \"}\")' > answer-draft.json"),
     "nested too deeply"),
])
def test_a_bad_draft_is_not_taken(tmp_path: Path, corpus: tuple[Path, Path], make: Any, problem: str) -> None:
    replies: list[Reply] = [make(), tool_call("ls"), tool_call("ls")]
    run, outcome, _, _ = go(tmp_path, corpus, replies, budget={"steps": 1, "tokens": 10**6, "announced": True})
    assert outcome.answer_from == "none" and json.loads(run.answer.read_text(encoding="utf-8"))["rows"] == []
    cov = coverage_of(run)[-1]
    assert cov["generated"]["reason"] == "no_final_answer"
    assert any(problem in p for p in cov["generated"]["detail"]["draft"]["problems"]), cov["generated"]["detail"]
    assert verify_run(run, *corpus).ok


@posix_only
def test_a_final_answer_wins_over_the_draft(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    replies: list[Reply] = [write_draft([row([]), row([], "f2", "r2")]), final([row([])], "final")]
    run, outcome, _, _ = go(tmp_path, corpus, replies)
    assert outcome.answer_from == "final" and outcome.answer_rows == 1
    assert json.loads(run.answer.read_text(encoding="utf-8"))["notes"] == "final"
    assert "answer_from_draft" not in [c["generated"]["reason"] for c in coverage_of(run)]


# --- masking (row 1.15) ----------------------------------------------------------------------------------

@posix_only
def test_old_outputs_become_stubs(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    quote = unique_quote()
    replies: list[Reply] = [bash(claim_cmd(quote) + "; echo FIRST-OUTPUT")]
    replies += [bash(f"echo output-{n}") for n in range(2, 13)] + [final([row(["claim-000001"])])]
    run, outcome, _, model = go(tmp_path, corpus, replies)
    assert outcome.exit_status == "submitted"
    calls = calls_of(run)
    # Before call k there are k - 1 outputs; all but the last 8 are stubs.
    assert [c["custom_metadata"]["masked_observations"] for c in calls] == [0] * 9 + [1, 2, 3, 4]
    observations = [m for m in model.prompts[12] if m["role"] == "user"][1:]
    stubs, whole = observations[:4], observations[4:]
    for n, stub in enumerate(stubs, 1):
        head = stub["content"].splitlines()[0]
        assert head.startswith(f"[Output of step {n} removed to save context (exit 0, ")
        assert head.endswith(f"out/step-{n:04d}.txt]") and str(run.out.resolve()) in head
    assert '"claim_id": "claim-000001"' in stubs[0]["content"] and "FIRST-OUTPUT" not in stubs[0]["content"]
    assert len(stubs[1]["content"].splitlines()) == 1
    assert all(m["content"].startswith("<returncode>0</returncode>") for m in whole)
    # A stub never changes again, so the prompt prefix up to the newest stub stays cached.
    first_stub = [m for m in model.prompts[9] if m["role"] == "user"][1]
    assert first_stub == stubs[0]
    assert model.prompts[12][:4] == model.prompts[11][:4]
    assert cli(["timeline", str(run.root)]) == 0
    assert "4 outputs masked" in (run.root / "timeline.html").read_text(encoding="utf-8")
    # trajectory.json keeps what the model saw before the stub, so every prompt hash can still be checked.
    kept = [m for m in trajectory(run) if m.get("extra", {}).get("masked")]
    assert len(kept) == 4 and "FIRST-OUTPUT" in kept[0]["extra"]["original_content"]
    assert kept[0]["extra"]["original_content"] == [m for m in model.prompts[8] if m["role"] == "user"][1]["content"]
    assert rebuilt_prompt_hashes(run, model) == [c["used"]["prompt_sha256"] for c in calls]


def trajectory(run: RunDir) -> list[dict[str, Any]]:
    return json.loads((run.root / "trajectory.json").read_text(encoding="utf-8"))["messages"]


def rebuilt_prompt_hashes(run: RunDir, model: ScriptedModel) -> list[str]:
    """Each model call's prompt_sha256, from trajectory.json and the call records alone.

    A call's prompt is the first `used.messages` messages; of the command outputs among them the
    oldest `masked_observations` were stubs (as they are now), the rest as first shown.
    """
    messages = trajectory(run)
    out = []
    for call in calls_of(run):
        shown, outputs = [], 0
        for message in messages[:call["used"]["messages"]]:
            extra = message.get("extra") or {}
            content = message["content"]
            if extra.get("kind") == "observation":
                outputs += 1
                if outputs > call["custom_metadata"]["masked_observations"]:
                    content = extra.get("original_content", content)
            shown.append({**message, "content": content})
        out.append(sha256_hex(canonical_bytes(model._prepare_messages_for_api(shown))))
    return out


@posix_only
def test_masking_tightens_after_a_large_prompt(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    replies: list[Reply] = [bash(f"echo {n}") for n in range(1, 8)] + [final([row([])])]
    model = ScriptedModel(replies, prompt_tokens=[1_000] * 5 + [45_001] + [1_000] * 2)
    run, _, _, _ = go(tmp_path, corpus, [], model=model, budget={"steps": 60, "tokens": 10**9, "announced": True})
    # After call 6 (45,001 prompt tokens) only the last 4 outputs stay; stubs stay stubs after that.
    assert [c["custom_metadata"]["masked_observations"] for c in calls_of(run)] == [0] * 6 + [2, 2]
    assert rebuilt_prompt_hashes(run, model) == [c["used"]["prompt_sha256"] for c in calls_of(run)]


@posix_only
def test_a_context_full_overflow_keeps_masked_stubs(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """On a context-full 400 the outputs not yet masked become stubs; a stub already made stays as it was."""
    overflow = litellm.exceptions.ContextWindowExceededError("too long", "orch-model", "openai")
    replies: list[Reply] = [bash(f"echo {n}") for n in range(1, 11)] + [overflow, final([row([])])]
    run, outcome, _, model = go(tmp_path, corpus, replies)
    assert outcome.exit_status == "submitted"
    outputs = [m["content"] for m in model.prompts[11] if m["role"] == "user"][1:-1]
    assert [o.split(" ", 1)[0] for o in outputs] == ["[Output"] * 2 + ["[output"] * 8
    assert all(o.startswith("[output removed: context full] Full output: ") for o in outputs[2:])
    assert outputs[:2] == [m["content"] for m in model.prompts[10] if m["role"] == "user"][1:3]
    answered = [c for c in calls_of(run) if c["status"] == "finished"]
    assert [c["custom_metadata"]["masked_observations"] for c in answered][-1] == 10
    assert all(m["extra"].get("original_content", "").startswith("<returncode>0</returncode>")
               for m in trajectory(run) if m.get("extra", {}).get("kind") == "observation")


@posix_only
def test_v1_keeps_the_m1_wording(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """Prompt v1: the context-full stub and a cut answer read as in the M1-real loop."""
    overflow = litellm.exceptions.ContextWindowExceededError("too long", "orch-model", "openai")
    cut = f"Done.\n{FENCE}json\n{{\"rows\": [\n{FENCE}"
    model = ScriptedModel([bash("echo a"), cut, overflow, final([row([])])], finish_reasons=["stop", "length", "stop"])
    run, outcome, _, _ = go(tmp_path, corpus, [], model=model, prompt_version="v1")
    assert outcome.exit_status == "submitted" and run.load_config()["budget"]["steps"] == 150  # the M1 budget
    problems = coverage_of(run)[0]["generated"]["detail"]
    assert coverage_of(run)[0]["generated"]["reason"] == "invalid_final_answer"
    assert not any("reply limit" in p for p in problems)
    assert [m["content"] for m in model.prompts[3] if m["role"] == "user"][1] == "[output removed: context full]"
    assert all("max_tokens" not in k for k in model.kwargs)


@posix_only
def test_v1_runs_the_m1_loop(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """Prompt v1 reproduces the M1-real runs: no masking, notices, repeat stop, draft or guided conclusion."""
    replies: list[Reply] = [write_draft([row([])])] + [bash("echo same")] * 9 + [tool_call("ls"), tool_call("ls")]
    run, outcome, _, model = go(tmp_path, corpus, replies, prompt_version="v1",
                                budget={"steps": 10, "tokens": 10**6, "announced": True})
    assert outcome.exit_status == "budget" and outcome.answer_from == "none"  # the draft is not v1's
    config = run.load_config()
    assert config["prompt"]["files"]["system-v1.txt"] == config["prompt"]["sha256"]
    assert config["loop"] | {"base_url": None} == {"harness": "mini-swe-agent 2.4.6", "base_url": None,
                                                   **LEGACY_V1.config()}
    assert model.kwargs == [{}] * 12
    assert all(c["custom_metadata"]["masked_observations"] == 0 for c in calls_of(run))
    assert not any("Budget notice" in m["content"] or "removed to save context" in m["content"]
                   for m in model.prompts[-1])
    assert model.prompts[10][-1]["content"].endswith(
        "Reply now with your reasoning and the final answer in EXACTLY ONE fenced json block; no further commands run.")
    assert coverage_of(run)[-1]["generated"]["detail"] == {"exit_status": "budget"}


# --- repeated commands -------------------------------------------------------------------------------------

@posix_only
def test_six_identical_commands_end_research(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """c3-on-3 ran one command 9 times; now the sixth in a row ends research."""
    replies: list[Reply] = [bash("echo other")] + [bash('ls "$CORPUS"')] * 6 + [tool_call("ls"), tool_call("pwd")]
    run, outcome, _, model = go(tmp_path, corpus, replies)
    assert outcome.exit_status == "repeats" and outcome.steps == 7 and outcome.model_calls == 9
    tools = [r for r in records(run) if r["subtype"] == "agent_tool"]
    assert [t["custom_metadata"]["repeat"] for t in tools] == [1, 1, 2, 3, 4, 5, 6]
    assert "At 6 in a row the research ends." in model.prompts[4][-1]["content"]  # after the 3rd
    sixth = model.prompts[7][-2]["content"]  # the last observation, then the conclude notice
    assert "same command 6 times in a row" in sixth and "At 6 in a row" not in sixth
    conclude = model.prompts[7][-1]["content"]
    assert conclude.startswith("Research ended: you ran the same command 6 times in a row.")
    assert [c["custom_metadata"]["phase"] for c in calls_of(run)] == ["research"] * 7 + ["conclude"] * 2
    assert coverage_of(run)[-1]["generated"] == {"reason": "no_final_answer", "detail": {"exit_status": "repeats"}}
