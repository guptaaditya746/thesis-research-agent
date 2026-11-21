"""evqa/answer for the question types added on 21 Nov: effect, trend, list, conflicts (any type) and near misses that
must come out "not reported". Hand-made rows, no LLM."""
from __future__ import annotations

from evqa import answer
from evqa.contracts import Answer, Name, Row, Spec, StdValue
from evqa.norm import PP

MET = "adults with type 2 diabetes on metformin"
A, B = Name(label="drug-a"), Name(label="drug-b")
M = Name(label="HbA1c change")


def row(subject, value, dose="10 mg", time="week 24", group=MET, paper="P1", comparator="placebo", ok=True):
    dec = len(value.split(".")[1]) if "." in value else 0
    return Row(paper=paper, subject=subject, comparator=comparator, measure="HbA1c change", patient_group=group,
               dose=dose, time_point=time, std=StdValue(value=value, unit=PP, decimals=dec), raw=value,
               quote=f"{subject} {dose} {time}: {value}", quote_ok=ok)


def spec(qtype, subjects, **kw):
    return Spec(qid="Q", question="", type=qtype, subjects=subjects, measure=M, **kw)


# ---------------------------------------------------------------- effect
def test_effect_head_to_head_rows_give_the_difference_and_verdict():
    rows = [row("drug-a", "-0.30", comparator="drug-b 10 mg", paper="P1"),
            row("drug-b", "0.25", comparator="drug-a", paper="P2", time="week 52"),     # B vs A: sign flipped
            row("drug-a", "-0.01", comparator="drug-b", paper="P3", time="week 12")]    # within rounding
    ans = answer.run(spec("effect", [A, B], higher_is_better=False, columns=["time_point"]), rows)
    got = {e.group["paper"]: (e.basis, e.difference, e.verdict) for e in ans.effects}
    assert got == {"P1": ("head_to_head", "-0.30", "drug-a better"),
                   "P2": ("head_to_head", "-0.25", "drug-a better"),
                   "P3": ("head_to_head", "-0.01", "no clear difference")}
    assert not ans.not_reported and "drug-a better" in ans.sentence


def test_effect_both_against_the_same_comparator_best_dose_each():
    rows = [row("drug-a", "-0.80", dose="10 mg", paper="P1"), row("drug-a", "-1.00", dose="20 mg", paper="P1"),
            row("drug-b", "-0.70", dose="5 mg", paper="P2"),
            row("drug-b", "-0.60", dose="5 mg", paper="P2", time="week 52")]          # A has no week 52 row
    ans = answer.run(spec("effect", [A, B], higher_is_better=False, columns=["dose", "time_point"]), rows)
    (e,) = ans.effects
    assert (e.basis, e.a_value, e.b_value, e.difference, e.verdict) == ("same_comparator", "-1.00", "-0.70",
                                                                         "-0.30", "drug-a better")
    assert e.group == {"comparator": "placebo", "time_point": "24 wk"} and e.papers == ["P1", "P2"]


def test_effect_against_placebo_takes_each_row_as_reported():
    rows = [row("drug-a", "-0.60", paper="P1"), row("drug-a", "0.05", paper="P2")]
    ans = answer.run(spec("effect", [A], comparator=Name(label="placebo"), higher_is_better=False), rows)
    assert [(e.basis, e.b, e.verdict) for e in ans.effects] == [("vs_comparator", "placebo", "drug-a better"),
                                                                 ("vs_comparator", "placebo", "placebo better")]


def test_effect_fixed_dose_binds_drug_a_only():
    rows = [row("drug-a", "-0.80", dose="20 mg"), row("drug-a", "-0.90", dose="40 mg"),
            row("drug-b", "-0.50", dose="5 mg", paper="P2")]
    ans = answer.run(spec("effect", [A, B], higher_is_better=False, fixed={"dose": "20 mg"}), rows)
    (e,) = ans.effects
    assert (e.a_value, e.b_value) == ("-0.80", "-0.50")


def test_effect_with_one_side_missing_is_not_reported():
    ans = answer.run(spec("effect", [A, B], higher_is_better=False), [row("drug-a", "-0.80")])
    assert ans.not_reported and ans.effects == [] and "for drug-b" in ans.sentence


# ---------------------------------------------------------------- trend
def test_trend_over_time_orders_points_and_names_the_direction():
    rows = [row("drug-a", "-0.9", time="week 52"), row("drug-a", "-0.5", time="week 12"),
            row("drug-a", "-0.8", time="6 months"),
            row("drug-a", "-0.4", time="week 12", group="drug-naive adults", paper="P2"),
            row("drug-a", "-0.4", time="week 24", group="drug-naive adults", paper="P2")]
    ans = answer.run(spec("trend", [A], fixed={"dose": "10 mg"}, trend_by="time_point",
                          columns=["time_point", "patient_group"]), rows)
    by = {s.group["patient_group"]: s for s in ans.trend}
    assert [p["at"] for p in by[MET].points] == ["12 wk", "6 mo", "52 wk"]
    assert by[MET].direction == "decreasing" and by["drug-naive adults"].direction == "flat"
    assert "decreasing" in ans.sentence


def test_trend_over_dose_mixed_and_one_point():
    rows = [row("drug-a", "-0.5", dose="5 mg"), row("drug-a", "-0.9", dose="10 mg"), row("drug-a", "-0.6", dose="20 mg"),
            row("drug-a", "-0.7", dose="10 mg", group="drug-naive adults", paper="P2")]
    ans = answer.run(spec("trend", [A], fixed={"time_point": "24 weeks"}, trend_by="dose",
                          columns=["dose", "patient_group"]), rows)
    by = {s.group["patient_group"]: s.direction for s in ans.trend}
    assert by == {MET: "mixed", "drug-naive adults": "one point"}


def test_trend_with_two_papers_disagreeing_at_one_point_is_unclear_and_a_conflict():
    rows = [row("drug-a", "-0.5", time="week 12"), row("drug-a", "-0.9", time="week 24"),
            row("drug-a", "-0.3", time="week 24", paper="P2")]
    ans = answer.run(spec("trend", [A], trend_by="time_point", columns=["time_point"]), rows)
    (s,) = ans.trend
    assert s.direction == "unclear" and "24 wk" in s.note
    assert len(ans.conflicts) == 1 and "Conflict" in ans.sentence


# ---------------------------------------------------------------- list
def test_list_gives_each_paper_with_rows_quotes_and_design():
    rows = [row("drug-a", "-0.5", paper="P2", dose="20 mg"), row("drug-a", "-0.4", paper="P1"),
            row("drug-a", "-0.6", paper="P1", dose="20 mg daily", time="week 52"),
            row("drug-b", "-0.6", paper="P3")]
    ans = answer.run(Spec(qid="Q", question="", type="list", subjects=[A], measure=Name(label="", known=False)), rows)
    assert [p.paper for p in ans.papers] == ["P1", "P2"]
    p1 = ans.papers[0]
    assert p1.rows == [1, 2] and p1.design["dose"] == ["10 mg", "20 mg"] and p1.design["time point"] == ["24 wk", "52 wk"]
    assert len(p1.quotes) == 2 and ans.sentence.startswith("2 studies report drug-a")


def test_list_without_a_subject_lists_papers_of_the_measure_in_the_group():
    rows = [row("drug-a", "-0.5", paper="P1"), row("drug-b", "-0.4", paper="P2", group="drug-naive adults")]
    ans = answer.run(Spec(qid="Q", question="", type="list", subjects=[], measure=M, fixed={"patient_group": MET}), rows)
    assert [p.paper for p in ans.papers] == ["P1"]


# ---------------------------------------------------------------- conflict (any type)
def test_lookup_flags_two_papers_that_disagree_beyond_rounding_and_keeps_both():
    rows = [row("drug-a", "-0.78", paper="P1"), row("drug-a", "-0.52", paper="P2"),
            row("drug-a", "-0.77", paper="P3", time="week 12"), row("drug-a", "-0.78", paper="P4", time="week 12")]
    ans = answer.run(spec("lookup", [A], fixed={"dose": "10 mg"}, columns=["time_point"]), rows)
    (c,) = ans.conflicts
    assert c.cells["time point"] == "24 wk" and c.spread == "0.26" and c.step == "0.01"
    assert [v["paper"] for v in c.values] == ["P1", "P2"]
    assert {a.value for a in ans.table if a.cells["time_point"] == "24 wk"} == {"-0.78", "-0.52"}
    assert "Conflict" in ans.sentence and "P1" in ans.sentence and "P2" in ans.sentence


def test_values_within_rounding_are_not_a_conflict_and_old_json_stays_the_same():
    rows = [row("drug-a", "-0.78", paper="P1"), row("drug-a", "-0.8", paper="P2")]
    ans = answer.run(spec("lookup", [A], columns=["time_point"]), rows)
    assert ans.conflicts == []
    dumped = ans.model_dump_json()
    assert all(k not in dumped for k in ('"conflicts"', '"effects"', '"trend"', '"papers"'))
    assert Answer.model_validate_json(dumped) == ans


# ---------------------------------------------------------------- near miss / absent -> not reported
def test_near_miss_dose_or_group_is_not_used_to_answer():
    rows = [row("drug-a", "-0.5", dose="20 mg"), row("drug-a", "-0.9", dose="40 mg")]
    for qtype in ("lookup", "trend", "list"):
        ans = answer.run(spec(qtype, [A], fixed={"dose": "30 mg"}, trend_by="time_point"), rows)
        assert ans.not_reported and ans.table == [] and ans.sentence == "Not reported in the papers.", qtype
    ans = answer.run(spec("lookup", [A], fixed={"patient_group": "elderly adults with type 2 diabetes"}), rows)
    assert ans.not_reported
    ans = answer.run(spec("effect", [A], comparator=Name(label="placebo"), fixed={"time_point": "16 weeks"}), rows)
    assert ans.not_reported and ans.effects == []
