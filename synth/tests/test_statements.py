"""Atomic Results statements: each prose value is written as one checked sentence before the paper is composed.

The Step-10 fixture (tests/EV1/diagnostics) is the regression case: its count-form sentence never names the
paraphrased metric description, which the whole-paper repair loop failed to fix three times.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic_ai.models.function import FunctionModel

from evidence.protocol import load
from synth import statements, truth, variant
from synth.levels import make_plan, plan_rng
from synth.render_llm import LlmRenderer
from synth.render_template import render, render_study
from synth.tests.test_llm import SEED, N, Writer, sentence_with

REPO = Path(__file__).resolve().parents[2]
DIAG = REPO / "tests" / "EV1" / "diagnostics"


def step10_plan():
    """The plan Step 10 rendered: S002 made to contradict, at the paraphrased level (as review_repro.py builds it)."""
    meta = json.loads((DIAG / "rag-llm-s1-corpus.json").read_text(encoding="utf-8"))
    protocol = load(REPO / "domains" / "rag" / "protocols" / "rag-factuality.yaml")
    studies = variant.base_studies(meta, protocol)
    _, _, after = variant.counterfactual(meta["seed"], studies, "S002", "contradicts", protocol.synthesis)
    return make_plan(after, "paraphrased", plan_rng(meta["seed"], "S002", "paraphrased"))


def test_step10_count_form_sentence_fails_the_statement_contract() -> None:
    plan = step10_plan()
    task = next(t for t in statements.plan_statements(plan) if t.value_text == "662 out of 1,000")
    assert task.metric_phrase == "fraction of answers judged factually correct"
    draft = (DIAG / "step10-final-draft.md").read_text(encoding="utf-8")
    original = sentence_with(draft.split("\n")[12], "662 out of 1,000")
    assert original == "The variant that reads retrieved evidence first yields 662 out of 1,000 answers judged factually correct."
    failed = [c for c in statements.check(task, original) if not c.ok]
    assert "required_strings" in [c.name for c in failed]
    assert "fraction of answers judged factually correct" in next(c for c in failed if c.name == "required_strings").detail
    repaired = ("The variant that reads retrieved evidence first has a fraction of answers judged factually correct "
                "of 662 out of 1,000.")
    checks = statements.check(task, repaired)
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    assert {"required_strings", "values_associated", "added_numbers", "level_paraphrased"} <= {c.name for c in checks}


def test_table_values_get_no_statement_tasks() -> None:
    for s in truth.generate(SEED, N):
        for level in ("distributed", "contradictory"):
            assert statements.plan_statements(make_plan(s, level, plan_rng(SEED, s.study_id, level))) == []
        explicit = make_plan(s, "explicit", plan_rng(SEED, s.study_id, "explicit"))
        assert [t.id for t in statements.plan_statements(explicit)] == [m.id for m in explicit.measurements]
        complex_ = make_plan(s, "complex", plan_rng(SEED, s.study_id, "complex"))
        tasks = statements.plan_statements(complex_)          # only the relative value is written in prose
        assert [t.fmt for t in tasks] == (["relative"] if s.missing is None else [])
        assert all(t.compared_with == complex_.cond_name[s.condition(s.control_role).id] for t in tasks)


def test_template_sentences_pass_the_statement_checks() -> None:
    for s in truth.generate(SEED, N):
        for level in ("explicit", "paraphrased", "complex"):
            plan = make_plan(s, level, plan_rng(SEED, s.study_id, level))
            text, _, _ = render(plan, plan_rng(SEED, s.study_id, level + ":text"))
            for task in statements.plan_statements(plan):
                checks = statements.check(task, sentence_with(text, task.value_text))
                assert all(c.ok for c in checks), (s.study_id, level, [c for c in checks if not c.ok])


def test_paraphrased_statements_keep_paraphrased_wording() -> None:
    s = truth.generate(SEED, N)[0]
    plan = make_plan(s, "paraphrased", plan_rng(SEED, s.study_id, "paraphrased"))
    text, _, _ = render(plan, plan_rng(SEED, s.study_id, "paraphrased:text"))
    task = statements.plan_statements(plan)[0]
    good = sentence_with(text, task.value_text)
    assert all(c.ok for c in statements.check(task, good))
    m = next(x for x in plan.measurements if x.id == task.id)
    label = plan.condition(m.condition).label
    easy = good.replace(task.condition_name, f"{task.condition_name} ({label})", 1)
    failed = {c.name: c.detail for c in statements.check(task, easy) if not c.ok}
    assert "level_paraphrased" in failed and repr(label) in failed["level_paraphrased"]


def test_other_numbers_and_second_sentences_fail() -> None:
    s = truth.generate(SEED, N)[0]
    plan = make_plan(s, "explicit", plan_rng(SEED, s.study_id, "explicit"))
    text, _, _ = render(plan, plan_rng(SEED, s.study_id, "explicit:text"))
    task = statements.plan_statements(plan)[0]
    good = sentence_with(text, task.value_text)
    failed = {c.name for c in statements.check(task, good[:-1] + ", up from 51.0%.") if not c.ok}
    assert "added_numbers" in failed
    failed = {c.name for c in statements.check(task, good + " It is the best result.") if not c.ok}
    assert "one_sentence" in failed


class StatementWriter(Writer):
    """Writes the template's sentences; `bad` maps a task id to a first-round sentence that fails,
    `stubborn` to one written in every round, and `prefix` to a prefix kept in every round (an accepted
    statement the template paper then lacks)."""

    def __init__(self, studies, *, bad: dict[str, str] | None = None, stubborn: dict[str, str] | None = None,
                 prefix: dict[str, str] | None = None, **kw) -> None:
        super().__init__(studies, **kw)
        self.bad, self.stubborn, self.prefix = bad or {}, stubborn or {}, prefix or {}

    def sentence(self, paper: str, task: dict, repair: bool) -> str:
        if task["id"] in self.stubborn:
            return self.stubborn[task["id"]]
        if task["id"] in self.bad and not repair:
            return self.bad[task["id"]]
        text = render_study(self.studies[paper], task["level"], SEED).text
        return self.prefix.get(task["id"], "") + sentence_with(text, task["value"])


def test_a_failed_statement_is_repaired_alone(tmp_path: Path) -> None:
    studies = truth.generate(SEED, N)
    s = studies[0]
    plan = make_plan(s, "explicit", plan_rng(SEED, s.study_id, "explicit"))
    first, second = statements.plan_statements(plan)[:2]
    writer = StatementWriter(studies, fail_first=False, bad={first.id: f"{first.condition_name} did well."})
    renderer = LlmRenderer(FunctionModel(writer, model_name="fake-writer"), tmp_path / "cache.jsonl", attempts=3)
    r = renderer.render_all([(s, "explicit")], SEED)[(s.study_id, "explicit")]
    assert r.fidelity.ok and r.fidelity.statements == {"rounds": 2, "failed": []}
    calls = [c for c in writer.calls if c.startswith("Statement tasks")]
    assert len(calls) == 2 and len(writer.calls) == 3
    repair = json.loads(calls[1].split("\n", 1)[1])
    assert [t["id"] for t in repair["tasks"]] == [first.id]
    assert repair["tasks"][0]["rejected"] == f"{first.condition_name} did well."
    assert any(c.startswith("required_strings") for c in repair["tasks"][0]["failed_checks"])
    assert second.id not in calls[1]
    paper = next(c for c in writer.calls if c.startswith("Rendering plan"))
    assert len(json.loads(paper.split("Rendering plan:\n", 1)[1])["statements"]) == len(plan.measurements)
    assert r.fidelity.json()["statements"] == {"rounds": 2, "failed": []}


def test_a_statement_that_never_passes_is_recorded(tmp_path: Path) -> None:
    studies = truth.generate(SEED, N)
    s = studies[0]
    plan = make_plan(s, "explicit", plan_rng(SEED, s.study_id, "explicit"))
    first = statements.plan_statements(plan)[0]
    writer = StatementWriter(studies, fail_first=False, stubborn={first.id: "Nothing to report."})
    renderer = LlmRenderer(FunctionModel(writer, model_name="fake-writer"), tmp_path / "cache.jsonl", attempts=2)
    r = renderer.render_all([(s, "explicit")], SEED)[(s.study_id, "explicit")]
    assert r.fidelity.statements == {"rounds": 2, "failed": [first.id]}
    paper = next(c for c in writer.calls if c.startswith("Rendering plan"))
    assert len(json.loads(paper.split("Rendering plan:\n", 1)[1])["statements"]) == len(plan.measurements) - 1


def test_accepted_statements_are_required_verbatim_in_the_paper(tmp_path: Path) -> None:
    studies = truth.generate(SEED, N)
    s = studies[0]
    plan = make_plan(s, "explicit", plan_rng(SEED, s.study_id, "explicit"))
    first = statements.plan_statements(plan)[0]
    # the statement is accepted with a prefix; the paper (the template's) keeps the sentence without it
    writer = StatementWriter(studies, fail_first=False, prefix={first.id: "Overall, "})
    renderer = LlmRenderer(FunctionModel(writer, model_name="fake-writer"), tmp_path / "cache.jsonl", attempts=2)
    r = renderer.render_all([(s, "explicit")], SEED)[(s.study_id, "explicit")]
    assert r.fidelity.statements == {"rounds": 1, "failed": []} and not r.fidelity.ok
    failed = [c for c in r.fidelity.checks if not c.ok]
    assert [c.name for c in failed] == ["required_strings"]
    assert f"{first.id}/statement" in failed[0].detail and "not_found" in failed[0].detail


def test_no_statements_keeps_the_old_call_pattern(tmp_path: Path) -> None:
    studies = truth.generate(SEED, N)
    writer = StatementWriter(studies, fail_first=False)
    renderer = LlmRenderer(FunctionModel(writer, model_name="fake-writer"), tmp_path / "cache.jsonl", attempts=2,
                           statements=False)
    r = renderer.render_all([(studies[0], "explicit")], SEED)[(studies[0].study_id, "explicit")]
    assert r.fidelity.ok and r.fidelity.statements is None and "statements" not in r.fidelity.json()
    assert len(writer.calls) == 1 and writer.calls[0].startswith("Rendering plan")
    assert '"statements"' not in writer.calls[0]


def test_cli_statements_flag() -> None:
    import argparse
    from synth.cli import add_renderer_options
    p = argparse.ArgumentParser()
    add_renderer_options(p)
    assert p.parse_args(["--renderer", "llm"]).statements is True
    assert p.parse_args(["--renderer", "llm", "--no-statements"]).statements is False


def test_statement_tasks_carry_no_effect_or_answer() -> None:
    for s in truth.generate(SEED, N):
        plan = make_plan(s, "complex", plan_rng(SEED, s.study_id, "complex"))
        text = statements.prompt(plan, statements.plan_statements(plan))
        assert not re.search(r"supports|contradicts|neutral|improves|worsens|no_effect|\"role\"|\"effect\"", text)


def test_a_built_llm_corpus_records_the_statement_mode(tmp_path: Path) -> None:
    from synth import corpus
    for on in (True, False):
        renderer = LlmRenderer(FunctionModel(Writer(truth.generate(SEED, N), fail_first=False), model_name="fake-writer"),
                               tmp_path / f"cache-{on}.jsonl", attempts=2, statements=on)
        corpus.build(name="m", seed=SEED, studies=N, renderer=renderer, out=tmp_path / str(on), levels=["explicit"])
        for lv in ("explicit", "mixed"):
            models = json.loads((tmp_path / str(on) / f"m-{lv}" / "corpus.json").read_text(encoding="utf-8"))["models"]
            assert (models["statements"], models["paper_prompt"]) == (on, "render-v2.txt" if on else "render.txt")


def test_no_statements_cache_keys_are_unchanged(tmp_path: Path) -> None:
    """--no-statements sends render.txt (as committed before the statement stage) and the old plan: same keys."""
    import hashlib

    import modelcall
    from modelcall.cache import cache_key
    from synth.render_llm import INSTRUCTIONS, PaperReply, plan_json
    assert hashlib.sha256((REPO / "synth" / "prompts" / "render.txt").read_bytes()).hexdigest() == \
        "9e8ff1fedb40b65e2a0e98801e4b8b61605aba1aefe39d45b9f16fa99cc49d9d"
    s = truth.generate(SEED, N)[0]
    renderer = LlmRenderer(FunctionModel(Writer([s], fail_first=False), model_name="fake-writer"),
                           tmp_path / "cache.jsonl", attempts=2, statements=False)
    renderer.render_all([(s, "explicit")], SEED)
    plan = make_plan(s, "explicit", plan_rng(SEED, s.study_id, "explicit"))
    want = cache_key({"prompt_sha256": modelcall.prompt_sha256(INSTRUCTIONS, PaperReply), "model": "fake-writer",
                      "prompt": "Rendering plan:\n" + json.dumps(plan_json(plan), indent=2, ensure_ascii=False),
                      "seed": SEED})
    keys = [json.loads(line)["key"] for line in (tmp_path / "cache.jsonl").read_text(encoding="utf-8").splitlines()]
    assert keys == [want]
