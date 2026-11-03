"""The two harder generator settings, multi_experiment and messy_tables, and the five old levels unchanged.
They are made with make_plan and render: the fidelity checks (synth/levelcheck.py) know the five old levels only."""
from __future__ import annotations

import hashlib
import json
import re

import pytest

from synth import levelcheck, truth
from synth.levels import ALL_LEVELS, EXTRA_LEVELS, FOOTNOTE_MARKS, LEVELS, make_plan, parse_value, plan_rng, write_value
from synth.render_template import render, text_rng

# sha256 of the plans, texts, placements and decoys of 120 papers (hard and plain, seeds 1-2, six studies, the five
# old levels), taken on the code before these levels were added
OLD_LEVELS_SHA256 = "00615dd1f6a370df5d9e19276663766035b25fed79444cf6f5b925b5d20a6803"


def made(level: str, *, hard: bool, seeds=range(1, 7), n: int = 6):
    for seed in seeds:
        for s in truth.generate(seed, n, hard=hard):
            if s.relevant:
                plan = make_plan(s, level, plan_rng(seed, s.study_id, level))
                text, placements, decoys = render(plan, text_rng(seed, s, level))
                yield s, plan, text, placements


def test_new_levels_are_named_and_the_old_list_is_unchanged() -> None:
    assert EXTRA_LEVELS == ("multi_experiment", "messy_tables")
    assert LEVELS == ("explicit", "paraphrased", "distributed", "complex", "contradictory")
    assert ALL_LEVELS == LEVELS + EXTRA_LEVELS


def test_multi_experiment_lists_all_experiments() -> None:
    seen = 0
    for s, plan, text, placements in made("multi_experiment", hard=True):
        if len(s.experiments) < 2:
            continue
        seen += 1
        assert [e.id for e in plan.experiments] == [e.id for e in s.experiments]
        for e in s.experiments:
            assert f"### {e.name} experiment" in text
        q = s.primary.id
        values = {p.fact: p for p in placements if p.role == "value"}
        assert set(values) == {m.id for m in plan.measurements}          # every measurement of every experiment is written
        for m in plan.measurements:
            in_table = levelcheck.in_table(text, values[m.id].start)
            assert in_table == (m.metric != q)                           # question metric in prose, the others in tables
        assert len({p.fmt for p in values.values() if not levelcheck.in_table(text, p.start)}) >= 2
    assert seen >= 3


def test_multi_experiment_without_hard_has_one_section_per_dataset() -> None:
    for s, plan, text, _ in made("multi_experiment", hard=False, seeds=range(1, 4)):
        for d in plan.datasets:
            assert f"### {d}\n" in text
        # named by synonyms, as the paraphrased level (a recipe synonym may itself contain another condition's label)
        assert all(plan.cond_name[c.id] == c.synonym for c in plan.conditions)


def test_messy_table_values_parse_back() -> None:
    marks_seen, cells = set(), 0
    for hard in (False, True):
        for s, plan, text, placements in made("messy_tables", hard=hard):
            values = [p for p in placements if p.role == "value"]
            assert {p.fact for p in values} == {m.id for m in plan.measurements}
            lines = [ln for ln in text.split("\n") if ln.startswith("|")]
            assert re.fullmatch(r"\| \| .+ \|( \|)+", lines[0])                       # merged group header, covered cells empty
            assert lines[2].startswith("| System |") and "(%)" in lines[2]           # units in the header row
            for p in values:
                m = next(m for m in plan.measurements if m.id == p.fact)
                assert levelcheck.in_table(text, p.start)
                assert parse_value(p.exact, p.fmt) == pytest.approx(m.value, abs=1e-6), (p.exact, m.value)
                marks_seen |= {c for c in FOOTNOTE_MARKS if p.exact.endswith(c)}
                cells += 1
    assert cells > 20 and marks_seen == set(FOOTNOTE_MARKS)


def test_footnote_marks_are_dropped_by_parse_value() -> None:
    assert write_value(0.624, "cell_pct_note", mark="*") == "62.4*"
    assert parse_value("62.4*", "cell_pct_note") == 0.624 and parse_value("62.4†", "cell_pct_note") == 0.624
    assert parse_value("1.20‡", "cell_raw_note") == 1.2 and parse_value("62.4", "cell_pct") == 0.624


def test_existing_levels_unchanged() -> None:
    out = {}
    for hard in (False, True):
        for seed in (1, 2):
            for s in truth.generate(seed, 6, hard=hard):
                for lv in LEVELS:
                    p = make_plan(s, lv, plan_rng(seed, s.study_id, lv))
                    text, pl, dc = render(p, text_rng(seed, s, lv))
                    out[f"{hard}:{seed}:{s.study_id}:{lv}"] = hashlib.sha256(
                        (repr(p) + "\n" + text + repr(pl) + repr(dc)).encode()).hexdigest()[:12]
    assert hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest() == OLD_LEVELS_SHA256
