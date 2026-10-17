"""A value attached to the wrong condition is a fidelity failure at every level (review item 1).

The paper is the template's, with two value strings swapped, read back as the LLM renderer reads a model's
paper (`locate`). Every presence check still passes; only the association check and the blind
re-extraction (which reports condition and value) can see the swap.
"""
from __future__ import annotations

import asyncio

import pytest

from synth import truth
from synth.fidelity import BlindExtraction, BlindMeasurement, blind_check, check_paper
from synth.levels import LEVELS, Plan, make_plan, plan_rng
from synth.render_llm import locate
from synth.render_template import render

SEED = 1


def paper(s: truth.Study, level: str) -> tuple[Plan, str]:
    plan = make_plan(s, level, plan_rng(SEED, s.study_id, level))
    return plan, render(plan, plan_rng(SEED, s.study_id, level + ":text"))[0]


def swap_pair(s: truth.Study, plan: Plan) -> tuple[str, str]:
    """The rag and baseline measurements, or, where the rag value is relative (complex), the baseline and
    a distractor condition's value; failing that, the baseline and a value of the second dataset."""
    rag, base = s.effect.treatment, s.effect.control
    if plan.values[rag].fmt != "relative":
        return rag, base
    other = next((m.id for m in plan.measurements if m.id not in (rag, base) and m.metric == s.effect.metric
                  and m.dataset == s.datasets[0]), None)
    return other or next(m.id for m in plan.measurements if m.metric == s.effect.metric
                         and m.dataset == s.datasets[1] and m.condition == s.condition("rag").id), base


def swapped(text: str, a: str, b: str) -> str:
    out = text.replace(a, "\0").replace(b, a).replace("\0", b)
    assert out != text
    return out


def blind_reader(plan: Plan, values: dict[str, float]):
    """A blind reader that reports what the swapped paper says: each condition with the value it shows."""
    found = [BlindMeasurement(condition=plan.cond_name[m.condition], metric=plan.metric_name[m.metric],
                              dataset=m.dataset, value=values.get(m.id, m.value)) for m in plan.measurements]

    async def extract(_: str) -> BlindExtraction:
        return BlindExtraction(measurements=found)
    return extract


@pytest.mark.parametrize("level", LEVELS)
def test_swapped_values_fail_the_association_check(level: str) -> None:
    for s in truth.generate(SEED, 6):
        plan, text = paper(s, level)
        a, b = swap_pair(s, plan)
        bad = swapped(text, plan.values[a].text, plan.values[b].text)
        ps, decoys, problems = locate(bad, plan)
        assert problems == []
        failed = {c.name for c in check_paper(bad, plan, ps, decoys) if not c.ok}
        assert "values_associated" in failed, (s.study_id, level, failed)
        ps_ok, decoys_ok, _ = locate(text, plan)
        assert all(c.ok for c in check_paper(text, plan, ps_ok, decoys_ok))


@pytest.mark.parametrize("level", LEVELS)
def test_blind_check_matches_condition_and_value(level: str) -> None:
    s = truth.generate(SEED, 6)[1]
    plan, text = paper(s, level)
    a, b = swap_pair(s, plan)
    swapped_values = {a: s.value_of(b), b: s.value_of(a)}
    def ok(reader) -> bool:          # both checks: every value recovered, and nothing beyond the plan
        return all(c.ok for c in asyncio.run(blind_check(text, plan, reader)))
    assert not ok(blind_reader(plan, swapped_values))
    assert ok(blind_reader(plan, {}))
    codes = BlindExtraction(measurements=[
        BlindMeasurement(condition=(plan.cond_aliases[m.condition] or ("the " + plan.cond_name[m.condition],))[0],
                         metric="m", dataset=m.dataset, value=m.value) for m in plan.measurements])

    async def by_code(_: str) -> BlindExtraction:
        return codes
    assert ok(by_code)


def test_relative_value_must_name_rag_before_and_baseline_after() -> None:
    s = truth.generate(SEED, 6)[0]
    plan, text = paper(s, "complex")
    rag, base = plan.cond_name[s.condition("rag").id], plan.cond_name[s.condition("baseline").id]
    rel = plan.values[s.effect.treatment].text
    start = text.index(rel)
    a, b = text.rindex("\n", 0, start) + 1, text.index("\n", start)
    sentence = text[a:b]
    flipped = sentence.replace(rag, "\0").replace(base, rag).replace("\0", base)
    bad = text[:a] + flipped + text[b:]
    ps, decoys, problems = locate(bad, plan)
    assert problems == []
    assert "values_associated" in {c.name for c in check_paper(bad, plan, ps, decoys) if not c.ok}
