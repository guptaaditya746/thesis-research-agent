"""LLM renderer and its fidelity loop with pydantic-ai FunctionModels (no network).

The scripted writer answers each plan with the template renderer's paper for that study and level (the
plan's required strings are the template's), but its first attempt for every paper drops one required
value, so every paper needs exactly two attempts and records why the first failed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agent.anchor import read_text
from synth import corpus, truth
from synth.levels import make_plan, plan_rng
from synth.render_llm import LEVEL_INSTRUCTIONS, LlmRenderer, locate, plan_json, title_of
from synth.render_template import render, render_study

SEED, N = 3, 4


def prompt_of(messages: list[ModelMessage]) -> str:
    parts = [p.content for m in messages for p in getattr(m, "parts", []) if isinstance(p, UserPromptPart)]
    return str(parts[-1]) if parts else ""


def respond(info: AgentInfo, args: dict[str, Any]) -> ModelResponse:
    if info.output_tools:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])
    return ModelResponse(parts=[TextPart(json.dumps(args))])


class Writer:
    def __init__(self, studies: list[truth.Study], *, fail_first: bool = True, error: str | None = None,
                 copy_title: bool = False) -> None:
        self.studies = {s.study_id: s for s in studies}
        self.fail_first, self.error, self.copy_title = fail_first, error, copy_title
        self.calls: list[str] = []

    def paper(self, prompt: str) -> str:
        plan = json.loads(prompt.split("Rendering plan:\n", 1)[1].split("\n\nYour previous", 1)[0])
        level = next(lv for lv, text in LEVEL_INSTRUCTIONS.items() if text == plan["level_instructions"])
        s = self.studies[plan["paper"]]
        text = render_study(s, level, SEED).text
        if self.copy_title and "title" in plan:      # a duplicate that ignores the plan and keeps the title
            text = "# " + plan["title"]["must_differ_from"] + "\n" + text.split("\n", 1)[1]
        if self.fail_first and "previous paper was rejected" not in prompt:
            value = next(v for v in plan["results"] if v["write_exactly"] != "see text")["write_exactly"]
            text = text.replace(value, "[value missing]")
        return text

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt = prompt_of(messages)
        self.calls.append(prompt)
        if self.error:
            raise RuntimeError(self.error)
        return respond(info, {"markdown": self.paper(prompt)})


def blind(studies: list[truth.Study], blind_to: str, extra_in: str | None = None):
    """A verifier for explicit papers that reports each condition with its value, read from the plan of
    the study whose value strings the paper holds; in study `blind_to` it finds nothing, and in
    `extra_in` it also reports a value the plan does not have."""
    plans = [make_plan(s, "explicit", plan_rng(SEED, s.study_id, "explicit")) for s in studies]

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        text = prompt_of(messages)
        plan = next(p for p in plans if all(v.text in text for v in p.values.values()))
        found = [] if plan.paper == blind_to else [
            {"condition": plan.cond_name[m.condition], "metric": plan.metric_name[m.metric], "dataset": m.dataset,
             "value": m.value} for m in plan.measurements]
        if plan.paper == extra_in:
            found.append({"condition": plan.cond_name[plan.conditions[0].id], "metric": "BLEU",
                          "dataset": plan.datasets[0], "value": 0.123})
        return respond(info, {"measurements": found})
    return FunctionModel(reply, model_name="fake-verifier")

@pytest.fixture
def studies() -> list[truth.Study]:
    return truth.generate(SEED, N)


def test_one_bad_attempt_then_a_good_one(tmp_path: Path, studies: list[truth.Study]) -> None:
    writer = Writer(studies)
    renderer = LlmRenderer(FunctionModel(writer, model_name="fake-writer"), tmp_path / "cache.jsonl", attempts=3)
    out = corpus.build(name="l", seed=SEED, studies=N, renderer=renderer, out=tmp_path / "c",
                       levels=["explicit", "distributed", "complex", "contradictory"])
    assert out["excluded"] == {} and len(writer.calls) == 2 * N * 4
    for lv in ("explicit", "distributed", "complex", "contradictory", "mixed"):
        d = tmp_path / "c" / f"l-{lv}"
        fid = json.loads((d / "fidelity.json").read_text(encoding="utf-8"))
        for rec in fid["papers"]:
            assert rec["ok"] and rec["attempts"] == 2
            assert rec["history"][0]["attempt"] == 1
            assert rec["history"][0]["failed"][0]["name"] == "required_strings"
            assert "not_found" in rec["history"][0]["failed"][0]["detail"]
        gt = json.loads((d / "ground_truth.json").read_text(encoding="utf-8"))
        for p in gt["placements"]:
            assert read_text(d / "papers" / f"{p['paper']}.md")[p["start"]:p["end"]] == p["exact"]
        meta = json.loads((d / "corpus.json").read_text(encoding="utf-8"))
        assert meta["renderer"] == "llm"
        assert meta["models"] == {"renderer": "fake-writer", "verifier": None, "served": ["fake-writer"]}
    # every second prompt carries the reasons the first paper was rejected
    retries = [c for c in writer.calls if "rejected for these reasons" in c]
    assert len(retries) == N * 4 and all("not_found" in c for c in retries)

    # a rebuild from the cache makes no model call and writes the same bytes
    again = Writer(studies)
    renderer = LlmRenderer(FunctionModel(again, model_name="fake-writer"), tmp_path / "cache.jsonl", attempts=3)
    corpus.build(name="l", seed=SEED, studies=N, renderer=renderer, out=tmp_path / "c2",
                 levels=["explicit", "distributed", "complex", "contradictory"])
    assert again.calls == []
    for f in (tmp_path / "c").rglob("*"):
        if f.is_file():
            assert f.read_bytes() == (tmp_path / "c2" / f.relative_to(tmp_path / "c")).read_bytes()


def test_llm_placements_equal_template_placements(studies: list[truth.Study]) -> None:
    for s in studies:
        for lv in ("explicit", "paraphrased", "distributed", "complex", "contradictory"):
            plan = make_plan(s, lv, plan_rng(SEED, s.study_id, lv))
            text, ps, decoys = render(plan, plan_rng(SEED, s.study_id, lv + ":text"))
            got, got_decoys, problems = locate(text, plan)
            assert problems == []
            key = lambda p: (p.start, p.end, p.fact, p.role)  # noqa: E731
            assert sorted(map(key, got)) == sorted(map(key, ps))
            assert [(d.start, d.end) for d in got_decoys] == [(d.start, d.end) for d in decoys]


def test_plan_never_tells_the_effect_or_the_answer(studies: list[truth.Study]) -> None:
    for s in studies:
        text = json.dumps(plan_json(make_plan(s, "complex", plan_rng(SEED, s.study_id, "complex"))))
        assert not re.search(r"supports|contradicts|neutral|improves|worsens|no_effect|\"role\"|\"effect\"", text)


def test_paper_that_never_passes_is_reported_and_excluded_everywhere(tmp_path: Path,
                                                                     studies: list[truth.Study]) -> None:
    verifier = blind(studies, studies[0].study_id)

    renderer = LlmRenderer(FunctionModel(Writer(studies, fail_first=False), model_name="fake-writer"),
                           tmp_path / "cache.jsonl", attempts=2, verify_model=verifier)
    out = corpus.build(name="x", seed=SEED, studies=N, renderer=renderer, out=tmp_path / "c", levels=["explicit"])
    bad = studies[0].study_id
    assert out["excluded"] == {bad: ["explicit"]}
    for lv in ("explicit", "mixed"):
        d = tmp_path / "c" / f"x-{lv}"
        ids = [p["id"] for p in json.loads((d / "manifest.json").read_text(encoding="utf-8"))["papers"]]
        assert bad not in ids and len(ids) == N - 1
        fid = json.loads((d / "fidelity.json").read_text(encoding="utf-8"))
        rec = next(r for r in fid["papers"] if r["id"] == bad)
        assert not rec["ok"] and rec["attempts"] == 2 and "excluded_reason" in rec and fid["excluded"] == [bad]
        checks = {c["name"]: c for c in rec["checks"]}
        assert not checks["blind_reextraction"]["ok"] and "missing" in checks["blind_reextraction"]["detail"]
        assert checks["blind_extra"]["ok"]
        good = next(r for r in fid["papers"] if r["id"] != bad)
        assert good["ok"] and [c["name"] for c in good["checks"]][-2:] == ["blind_reextraction", "blind_extra"]
        gt = json.loads((d / "ground_truth.json").read_text(encoding="utf-8"))
        assert bad not in [s["paper"] for s in gt["studies"]] + [p["paper"] for p in gt["placements"]]


def test_duplicate_is_told_the_original_title_and_must_differ(tmp_path: Path) -> None:
    """F2: a duplicate paper carries another title; the LLM renderer learns the original's title from the
    original's rendering (originals first) and `title_differs` enforces it."""
    studies = truth.generate(SEED, N, duplicates=1)
    dup = studies[-1]
    writer = Writer(studies, fail_first=False)
    renderer = LlmRenderer(FunctionModel(writer, model_name="fake-writer"), tmp_path / "cache.jsonl", attempts=2)
    out = corpus.build(name="d", seed=SEED, studies=N, renderer=renderer, out=tmp_path / "c", levels=["explicit"], duplicates=1)
    assert out["excluded"] == {}
    d = tmp_path / "c" / "d-explicit"
    original = title_of((d / "papers" / f"{dup.duplicate_of}.md").read_text(encoding="utf-8"))
    assert title_of((d / "papers" / f"{dup.study_id}.md").read_text(encoding="utf-8")) != original
    prompts = [c for c in writer.calls if f'"paper": "{dup.study_id}"' in c]
    assert len(prompts) == 1 and json.loads(prompts[0].split("Rendering plan:\n", 1)[1])["title"]["must_differ_from"] == original
    assert all('"title"' not in c for c in writer.calls if f'"paper": "{dup.study_id}"' not in c)
    fid = json.loads((d / "fidelity.json").read_text(encoding="utf-8"))
    rec = next(r for r in fid["papers"] if r["id"] == dup.study_id)
    assert rec["ok"] and "title_differs" in [c["name"] for c in rec["checks"]]
    # a writer that keeps the original's title fails the check and the duplicate is excluded
    stubborn = LlmRenderer(FunctionModel(Writer(studies, fail_first=False, copy_title=True), model_name="fake-writer"),
                           tmp_path / "cache2.jsonl", attempts=2)
    out = corpus.build(name="d", seed=SEED, studies=N, renderer=stubborn, out=tmp_path / "c2", levels=["explicit"], duplicates=1)
    assert out["excluded"] == {dup.study_id: ["explicit"]}
    fid = json.loads((tmp_path / "c2" / "d-explicit" / "fidelity.json").read_text(encoding="utf-8"))
    rec = next(r for r in fid["papers"] if r["id"] == dup.study_id)
    assert not rec["ok"] and next(c for c in rec["checks"] if c["name"] == "title_differs")["detail"]


def test_blind_extra_measurement_fails_the_paper(tmp_path: Path, studies: list[truth.Study]) -> None:
    """G.2: a value the blind reader returns that the plan does not have is added content (`blind_extra`)."""
    bad = studies[1].study_id
    verifier = blind(studies, blind_to="none", extra_in=bad)
    renderer = LlmRenderer(FunctionModel(Writer(studies, fail_first=False), model_name="fake-writer"),
                           tmp_path / "cache.jsonl", attempts=2, verify_model=verifier)
    out = corpus.build(name="x", seed=SEED, studies=N, renderer=renderer, out=tmp_path / "c", levels=["explicit"])
    assert out["excluded"] == {bad: ["explicit"]}
    fid = json.loads((tmp_path / "c" / "x-explicit" / "fidelity.json").read_text(encoding="utf-8"))
    rec = next(r for r in fid["papers"] if r["id"] == bad)
    checks = {c["name"]: c for c in rec["checks"]}
    assert checks["blind_reextraction"]["ok"] and not checks["blind_extra"]["ok"]
    assert "0.123" in checks["blind_extra"]["detail"] and "blind_extra" in json.dumps(rec["history"])
    assert all(r["ok"] for r in fid["papers"] if r["id"] != bad)


def test_blind_check_allows_the_decoy_and_the_relative_difference(studies: list[truth.Study]) -> None:
    import asyncio
    from synth.fidelity import BlindExtraction, BlindMeasurement, blind_check

    async def const(value):
        return value

    def read(plan, text, extra: list[BlindMeasurement]):
        planned = [BlindMeasurement(condition=plan.cond_name[m.condition], metric="m", dataset=m.dataset, value=m.value)
                   for m in plan.measurements]
        return asyncio.run(blind_check(text, plan, lambda _t: const(BlindExtraction(measurements=planned + extra))))

    s = next(s for s in studies if s.decoy is not None)
    plan = make_plan(s, "contradictory", plan_rng(SEED, s.study_id, "contradictory"))
    text, _, _ = render(plan, plan_rng(SEED, s.study_id, "contradictory:text"))
    rag = plan.cond_name[s.conditions[1].id]
    ok = read(plan, text, [BlindMeasurement(condition=rag, metric="m", dataset=s.datasets[0], value=s.decoy)])
    assert all(c.ok for c in ok) and [c.name for c in ok] == ["blind_reextraction", "blind_extra"]
    extra = read(plan, text, [BlindMeasurement(condition=rag, metric="m", dataset=s.datasets[0], value=0.999)])
    assert extra[0].ok and not extra[1].ok and "0.999" in extra[1].detail
    # the complex level's relative difference, read as a value of the treatment condition, is planned content
    plan = make_plan(s, "complex", plan_rng(SEED, s.study_id, "complex"))
    text, _, _ = render(plan, plan_rng(SEED, s.study_id, "complex:text"))
    diff = abs(s.value_of(s.effect.treatment) - s.value_of(s.effect.control))
    assert all(c.ok for c in read(plan, text, [BlindMeasurement(condition=rag, metric="m", dataset=s.datasets[0], value=diff)]))


def test_model_errors_are_failed_attempts_with_the_key_redacted(tmp_path: Path, studies: list[truth.Study],
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-secret-key-123")
    writer = Writer(studies, error="auth failed for key sk-test-secret-key-123")
    renderer = LlmRenderer(FunctionModel(writer, model_name="fake-writer"), tmp_path / "cache.jsonl", attempts=2)
    r = renderer.render_all([(studies[0], "explicit")], SEED)[(studies[0].study_id, "explicit")]
    assert not r.fidelity.ok and r.fidelity.attempts == 2
    detail = json.dumps(r.fidelity.json())
    assert "sk-test-secret-key-123" not in detail and "***" in detail and "model_call" in detail


def test_a_repeated_value_says_how_often_and_where(studies: list[truth.Study]) -> None:
    """EV1: almost every LLM paper repeated a value (e.g. in the Abstract and in Results); the retry must
    learn how often and in which sections, not just "ambiguous"."""
    plan = make_plan(studies[0], "explicit", plan_rng(SEED, studies[0].study_id, "explicit"))
    text, _, _ = render(plan, plan_rng(SEED, studies[0].study_id, "explicit:text"))
    value = next(v.text for v in plan.values.values() if v.fmt != "relative")
    abstract = text.index("## Abstract\n") + len("## Abstract\n")
    text = text[:abstract] + f"The headline value is {value}.\n" + text[abstract:]
    _, _, problems = locate(text, plan)
    said = next(p for p in problems if repr(value) in p)
    assert "is ambiguous: it occurs 2 times (in Abstract, Results); write it exactly once" in said
