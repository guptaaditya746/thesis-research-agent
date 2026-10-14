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
from synth.render_llm import LEVEL_INSTRUCTIONS, LlmRenderer, locate, plan_json
from synth.render_template import render

SEED, N = 3, 4


def prompt_of(messages: list[ModelMessage]) -> str:
    parts = [p.content for m in messages for p in getattr(m, "parts", []) if isinstance(p, UserPromptPart)]
    return str(parts[-1]) if parts else ""


def respond(info: AgentInfo, args: dict[str, Any]) -> ModelResponse:
    if info.output_tools:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])
    return ModelResponse(parts=[TextPart(json.dumps(args))])


class Writer:
    def __init__(self, studies: list[truth.Study], *, fail_first: bool = True, error: str | None = None) -> None:
        self.studies = {s.study_id: s for s in studies}
        self.fail_first, self.error = fail_first, error
        self.calls: list[str] = []

    def paper(self, prompt: str) -> str:
        plan = json.loads(prompt.split("Rendering plan:\n", 1)[1].split("\n\nYour previous", 1)[0])
        level = next(lv for lv, text in LEVEL_INSTRUCTIONS.items() if text == plan["level_instructions"])
        s = self.studies[plan["paper"]]
        p = make_plan(s, level, plan_rng(SEED, s.study_id, level))
        text, _, _ = render(p, plan_rng(SEED, s.study_id, level + ":text"))
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


def blind(blind_to: list[str]):
    """A verifier that reads every percent value of an explicit paper, except in the paper that contains
    all of `blind_to`, where it finds nothing."""
    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        text = prompt_of(messages)
        values = [] if all(s in text for s in blind_to) else [float(x) / 100 for x in re.findall(r"(\d+\.\d)%", text)]
        return respond(info, {"measurements": [{"condition": "x", "metric": "y", "dataset": "z", "value": v}
                                               for v in values]})
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
    first = make_plan(studies[0], "explicit", plan_rng(SEED, studies[0].study_id, "explicit"))
    verifier = blind([v.text for v in first.values.values()])
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
        assert rec["checks"][-1]["name"] == "blind_reextraction" and "missing" in rec["checks"][-1]["detail"]
        good = next(r for r in fid["papers"] if r["id"] != bad)
        assert good["ok"] and good["checks"][-1]["name"] == "blind_reextraction"
        gt = json.loads((d / "ground_truth.json").read_text(encoding="utf-8"))
        assert bad not in [s["paper"] for s in gt["studies"]] + [p["paper"] for p in gt["placements"]]


def test_model_errors_are_failed_attempts_with_the_key_redacted(tmp_path: Path, studies: list[truth.Study],
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-secret-key-123")
    writer = Writer(studies, error="auth failed for key sk-test-secret-key-123")
    renderer = LlmRenderer(FunctionModel(writer, model_name="fake-writer"), tmp_path / "cache.jsonl", attempts=2)
    r = renderer.render_all([(studies[0], "explicit")], SEED)[(studies[0].study_id, "explicit")]
    assert not r.fidelity.ok and r.fidelity.attempts == 2
    detail = json.dumps(r.fidelity.json())
    assert "sk-test-secret-key-123" not in detail and "***" in detail and "model_call" in detail
