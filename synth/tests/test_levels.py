"""Each difficulty level has its defining property; the fidelity checks catch broken papers."""
from __future__ import annotations

import dataclasses
import re

import pytest

from evidence import rules
from synth import fidelity, levelcheck, truth
from synth.levels import LEVELS, make_plan, parse_value, plan_rng, write_value
from synth.render_template import render, render_study


def papers(level: str, seeds=range(1, 9), n: int = 6):
    for seed in seeds:
        for s in truth.generate(seed, n):
            yield s, render_study(s, level, seed)


@pytest.mark.parametrize("level", LEVELS)
def test_template_papers_pass_every_check(level: str) -> None:
    for _, r in papers(level, range(1, 21), 8):
        bad = [c for c in r.fidelity.checks if not c.ok]
        assert not bad, (r.study.study_id, bad)


def test_explicit_one_sentence_names_condition_metric_dataset() -> None:
    for s, r in papers("explicit"):
        values = [p for p in r.placements if p.role == "value"]
        assert len(values) == len(r.plan.measurements) and "|" not in r.text
        for p in values:
            m = next(m for m in r.plan.measurements if m.id == p.fact)
            a, b = levelcheck.sentence_of(r.text, p.start, p.end)
            sentence = r.text[a:b]
            assert next(c.label for c in s.conditions if c.id == m.condition) in sentence
            assert s.primary.name in sentence and m.dataset in sentence and p.exact.endswith("%")


def test_paraphrased_never_uses_labels_and_varies_formats() -> None:
    formats = set()
    for s, r in papers("paraphrased"):
        low = r.text.lower()
        assert not any(re.search(r"(?<!\w)" + re.escape(c.label.lower()) + r"(?!\w)", low) for c in s.conditions)
        assert s.primary.name.lower() not in low
        fmts = {p.fmt for p in r.placements if p.role == "value"}
        assert len(fmts) >= 2
        formats |= fmts
    assert formats == {"pct", "frac", "count"}


def test_distributed_values_only_in_the_table_codes_defined_far_away() -> None:
    for s, r in papers("distributed"):
        lines = r.text.split("\n")
        table = [ln for ln in lines if ln.startswith("|")]
        prose = "\n".join(ln for ln in lines if not ln.startswith("|"))
        for p in (p for p in r.placements if p.role == "value"):
            assert levelcheck.in_table(r.text, p.start)
            assert p.exact not in prose
        assert all(c.label not in "\n".join(table) for c in s.conditions)
        assert table[0] == f"| System | {s.primary.abbr} (%) |"
        first_table = r.text.index("\n|") + 1
        for c in s.conditions:
            definition = r.text.index(f"we denote it by {c.code}.")
            assert first_table - definition > levelcheck.DISTANCE
        assert f"abbreviate it as {s.primary.abbr}" in prose


def test_complex_has_distractors_two_datasets_and_one_relative_value() -> None:
    for s, r in papers("complex"):
        assert len(r.plan.datasets) == 2 and len(r.plan.metrics) >= 2
        assert len(r.plan.measurements) == len(s.measurements)
        rel = [p for p in r.placements if p.fmt == "relative"]
        assert [p.fact for p in rel] == [s.effect.rag] and "percentage points" in rel[0].exact
        base = s.value_of(s.effect.baseline)
        assert parse_value(rel[0].exact, "relative", base) == s.value_of(s.effect.rag)
        assert "see text" in r.text


def test_contradictory_claim_disagrees_with_the_data() -> None:
    decoys = 0
    for s, r in papers("contradictory"):
        assert r.plan.claim == s.false_claim
        assert not rules.claim_agrees(r.plan.claim, s.effect.direction)
        claims = [p.exact for p in r.placements if p.role == "claim"]
        assert claims == list(r.plan.claim_sentences)
        for d in r.decoys:
            decoys += 1
            assert r.text[d.start:d.end] == d.exact and not levelcheck.in_table(r.text, d.start)
            assert abs(d.stated_value - s.value_of(d.measurement)) >= 0.005
    assert decoys > 0


@pytest.mark.parametrize("level", [lv for lv in LEVELS if lv != "contradictory"])
def test_other_levels_claim_agrees(level: str) -> None:
    for s, r in papers(level, range(1, 3)):
        assert rules.claim_agrees(r.plan.claim, s.effect.direction) and not r.decoys


@pytest.mark.parametrize(("fmt", "value", "text"), [
    ("pct", 0.624, "62.4%"), ("frac", 0.624, "0.624"), ("count", 0.624, "624 out of 1,000"),
    ("cell_pct", 0.071, "7.1"), ("cell_raw", 1.24, "1.24")])
def test_value_formats_round_trip(fmt: str, value: float, text: str) -> None:
    assert write_value(value, fmt) == text and parse_value(text, fmt) == value


def test_relative_round_trip() -> None:
    assert write_value(0.694, "relative", 0.624) == "7.0 percentage points higher"
    assert parse_value("0.3 percentage points lower", "relative", 0.624) == 0.621


def _fixture():
    s = truth.generate(2, 2)[0]
    plan = make_plan(s, "explicit", plan_rng(2, s.study_id, "explicit"))
    text, ps, decoys = render(plan, plan_rng(2, s.study_id, "explicit:text"))
    return plan, text, ps, decoys


def failing(plan, text, ps, decoys) -> set[str]:
    return {c.name for c in fidelity.check_paper(text, plan, ps, decoys) if not c.ok}


def test_checks_catch_moved_placement_and_wrong_value() -> None:
    plan, text, ps, decoys = _fixture()
    v = next(i for i, p in enumerate(ps) if p.role == "value")
    moved = [*ps[:v], dataclasses.replace(ps[v], start=ps[v].start + 1, end=ps[v].end + 1), *ps[v + 1:]]
    assert "anchored" in failing(plan, text, moved, decoys)
    p = ps[v]
    wrong = text[:p.start] + "99.9%" + text[p.end:]
    shifted = [dataclasses.replace(q, exact="99.9%") if q is p else q for q in ps]
    assert {"values_match"} <= failing(plan, wrong, shifted, decoys)


def test_checks_catch_stray_number_duplicate_value_and_unrecorded_label() -> None:
    plan, text, ps, decoys = _fixture()
    value = next(p for p in ps if p.role == "value")
    stray = text + f"\nAn earlier system reached {value.exact.rstrip('%')} points.\n"
    assert "stray_numbers" in failing(plan, stray, ps, decoys)
    dup = text + f"\nSee also {value.exact} above.\n"
    assert "values_unique" in failing(plan, dup, ps, decoys)
    label = plan.cond_name[plan.conditions[0].id]
    extra = text + f"\nThe {label} is cheap.\n"
    assert "labels_covered" in failing(plan, extra, ps, decoys)
    assert "facts_rendered" in failing(plan, text, [p for p in ps if p.role != "claim"], decoys)
    assert failing(plan, text, ps, decoys) == set()
