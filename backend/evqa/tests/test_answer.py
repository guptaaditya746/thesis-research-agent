"""evqa/answer: lookup table with columns, best per group, tie, not reported, direction, canonical slot values."""
from __future__ import annotations

from evqa import answer
from evqa.answer import canon
from evqa.contracts import Name, Row, Spec, StdValue
from evqa.norm import PP

MET = "adults with type 2 diabetes on metformin"
NEW = "adults with newly diagnosed type 2 diabetes, no prior drug"
BREN, KAV = Name(label="brenoxalin"), Name(label="kavolemin")
HBA1C = Name(label="HbA1c change")


def row(subject, value, dose, time, group=MET, paper="P1", ok=True, unit=PP, dropped=None):
    dec = len(value.split(".")[1]) if "." in value else 0
    return Row(paper=paper, subject=subject, comparator="placebo", measure="HbA1c change", patient_group=group,
               dose=dose, time_point=time, std=StdValue(value=value, unit=unit, decimals=dec), raw=value,
               quote=f"| {dose} | {time} | {value} |", quote_ok=ok, dropped=dropped)


ROWS = [row("brenoxalin", "-0.57", "10 mg daily", "week 24"),
        row("brenoxalin", "-0.72", "20 mg daily", "week 12"),
        row("brenoxalin", "-0.78", "20 mg", "24 weeks"),
        row("brenoxalin", "-0.91", "40 mg daily", "week 24"),
        row("brenoxalin", "-0.78", "20 mg daily", "week 36", paper="P2"),
        row("brenoxalin", "-0.99", "20 mg daily", "week 24", group=NEW, paper="P4"),
        row("brenoxalin", "-1.16", "40 mg daily", "week 24", group=NEW, paper="P4"),
        row("kavolemin", "-0.58", "5 mg daily", "week 24", paper="P3"),
        row("kavolemin", "-0.64", "10 mg daily", "week 24", paper="P3"),
        row("brenoxalin", "-5.00", "20 mg daily", "week 52", paper="P2", ok=False),            # quote check failed
        row("brenoxalin", "-9.00", "20 mg daily", "week 52", paper="P2", dropped="other measure")]


def test_canonical_time_dose_and_group():
    assert canon.time("week 24") == canon.time("24 weeks") == canon.time("24-week") == canon.time("24 wk") == "24 wk"
    assert canon.dose("20 mg daily") == canon.dose("20mg") == "20 mg"
    assert canon.group("Adults with type 2 diabetes who are taking metformin") == canon.group(MET)
    assert canon.group(NEW) != canon.group(MET)
    assert canon.sort_key("time_point", "12 wk") < canon.sort_key("time_point", "36 wk") \
        < canon.sort_key("time_point", "12 mo")


def test_lookup_table_has_the_columns_and_fixed_dose_only():
    spec = Spec(qid="Q1", question="", type="lookup", subjects=[BREN], measure=HBA1C, fixed={"dose": "20 mg"},
                columns=["time point", "patient group"])
    ans = answer.run(spec, ROWS)
    assert ans.columns == ["time point", "patient group"] and not ans.not_reported
    got = [(a.cells["time point"], a.cells["patient group"], a.value) for a in ans.table]
    assert got == [("12 wk", MET, "-0.72"), ("24 wk", NEW, "-0.99"), ("24 wk", MET, "-0.78"), ("36 wk", MET, "-0.78")]
    assert all(9 not in a.rows and 10 not in a.rows for a in ans.table)     # unchecked and dropped rows are skipped
    assert "4 value(s)" in ans.sentence


def test_lookup_same_cells_same_value_share_a_row_different_values_stay():
    extra = [row("brenoxalin", "-0.78", "20 mg", "week 24", paper="P9"), row("brenoxalin", "-0.70", "20 mg", "week 24",
                                                                              paper="P8")]
    spec = Spec(qid="Q1", question="", type="lookup", subjects=[BREN], measure=HBA1C,
                fixed={"dose": "20 mg", "patient_group": MET, "time_point": "24 weeks"})
    ans = answer.run(spec, ROWS + extra)
    assert sorted(a.value for a in ans.table) == ["-0.70", "-0.78"]
    assert next(a for a in ans.table if a.value == "-0.78").rows == [2, 11]


def test_lookup_nothing_found_is_not_reported():
    spec = Spec(qid="Q", question="", type="lookup", subjects=[Name(label="veloranide")], measure=HBA1C)
    ans = answer.run(spec, ROWS)
    assert ans.not_reported and ans.sentence == "Not reported in the papers." and ans.table == []


def test_best_dose_of_one_drug_lower_is_better():
    spec = Spec(qid="Q3", question="", type="best", subjects=[BREN], measure=HBA1C, higher_is_better=False,
                fixed={"time_point": "24 weeks", "patient_group": MET})
    ans = answer.run(spec, ROWS)
    assert len(ans.groups) == 1
    g = ans.groups[0]
    assert (g.status, g.winner, g.margin) == ("winner", "40 mg", "0.13")
    assert [e["candidate"] for e in g.ranking] == ["40 mg", "20 mg", "10 mg"]


def test_best_direction_higher_is_better_flips_the_winner():
    spec = Spec(qid="Q3", question="", type="best", subjects=[BREN], measure=HBA1C, higher_is_better=True,
                fixed={"time_point": "24 weeks", "patient_group": MET})
    assert answer.run(spec, ROWS).groups[0].winner == "10 mg"


def test_best_drugs_split_by_shared_group_dose_not_split():
    spec = Spec(qid="Q4", question="", type="best", subjects=[BREN, KAV], measure=HBA1C, higher_is_better=False,
                fixed={"time_point": "24 weeks"}, columns=["dose", "patient group"])
    ans = answer.run(spec, ROWS)
    by = {g.group["patient group"]: g for g in ans.groups}
    assert set(by) == {MET, NEW}
    assert (by[MET].status, by[MET].winner, by[MET].margin) == ("winner", "brenoxalin", "0.27")
    assert by[MET].ranking[0]["cells"] == {"dose": "40 mg"} and by[MET].ranking[1]["cells"] == {"dose": "10 mg"}
    assert (by[NEW].status, by[NEW].missing) == ("not_reported", ["kavolemin"])
    assert "not reported for kavolemin" in ans.sentence and "brenoxalin" in ans.sentence
    assert ans.columns == ["subject", "dose", "patient group"] and len(ans.table) == 7


def test_best_tie_when_margin_is_within_rounding():
    rows = [row("brenoxalin", "-0.91", "40 mg", "week 24"), row("kavolemin", "-0.90", "10 mg", "week 24"),
            row("kavolemin", "-0.9", "20 mg", "week 24")]
    spec = Spec(qid="Q", question="", type="best", subjects=[BREN, KAV], measure=HBA1C, higher_is_better=False,
                columns=["dose"])
    g = answer.run(spec, rows).groups[0]
    assert g.status == "tie" and g.winner is None and g.margin == "0.01"


def test_best_with_no_rows_is_not_reported():
    spec = Spec(qid="Q", question="", type="best", subjects=[BREN, KAV], measure=HBA1C, higher_is_better=False,
                fixed={"time_point": "100 weeks"})
    ans = answer.run(spec, ROWS)
    assert ans.not_reported and ans.groups == []
