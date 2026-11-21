"""evqa/extract: quote check, sign rule, ambiguous anchors, merge, conflicts and off-spec rows, with a fake LM."""
from __future__ import annotations

import json

import pytest

from evqa import extract
from evqa.contracts import FindHit, Name, Passage, RunConfig, Spec
from evqa.extract import anchor
from evqa.extract.core import spec_text
from evqa.norm import PP
from modelcall.dspy_lm import RecordedLM

PAPER = """# Zelnorin added to metformin

## Abstract

Adults with type 2 diabetes on metformin took Zelnorin. Zelnorin 20 mg gave a mean difference of -0.72 percentage points at week 12.

## 1. Results

At week 12, Zelnorin 10 mg lowered HbA1c by 0.57 percentage points versus placebo.

| Zelnorin dose | Time point | Mean difference vs placebo in HbA1c (percentage points) |
|---|---|---|
| 10 mg daily | week 12 | −0.57 |
| 20 mg daily | week 24 | −0.80 |

Zelnorin 20 mg gave a mean difference of -0.72 percentage points at week 12. At week 24, the 20 mg dose gave -0.85 percentage points.
Fasting plasma glucose fell by 1.1 mmol/L with Zelnorin 10 mg at week 12.
"""
START = PAPER.index("## 1. Results")
PASSAGE = Passage(start=START, end=len(PAPER), text=PAPER[START:])
SPEC = Spec(qid="Q-t", question="How much does zelnorin lower HbA1c?", type="lookup",
            subjects=[Name(label="zelnorin")], comparator=Name(label="placebo"),
            measure=Name(label="HbA1c change", synonyms=["change in HbA1c from baseline"]),
            columns=["dose", "time point", "patient group"])
GROUP = "adults with type 2 diabetes on metformin"


def draft(raw, quote, dose="10 mg daily", time="week 12", subject="Zelnorin", measure="HbA1c", unit="percentage points"):
    return {"subject": subject, "comparator": "placebo", "measure": measure, "patient_group": GROUP, "dose": dose,
            "time_point": time, "statistic": "mean difference vs placebo", "raw": raw, "unit": unit, "quote": quote}


def run_with(drafts, seen=None):
    def ask(prompt):
        if seen is not None:
            seen.append(prompt)
        return json.dumps({"rows": drafts})
    hit = FindHit(paper="P-t", screen="yes", passages=[PASSAGE])
    return extract.run(SPEC, [hit], "medical", RunConfig(), lm=RecordedLM("fake", ask), texts={"P-t": PAPER})


def test_quote_check_passes_and_sign_rule_makes_a_change_negative():
    seen = []
    rows = run_with([draft("lowered HbA1c by 0.57", "At week 12, Zelnorin 10 mg lowered HbA1c by 0.57 percentage "
                                                    "points versus placebo.")], seen)
    assert len(rows) == 1
    r = rows[0]
    assert r.quote_ok and r.std.value == "-0.57" and r.std.unit == PP and r.std.sign_basis == "change"
    assert r.raw == "lowered HbA1c by 0.57"               # the paper's wording is kept
    assert PAPER[r.quote_start:r.quote_end].startswith("At week 12, Zelnorin 10 mg")
    assert r.subject == "zelnorin" and r.measure == "HbA1c change"   # spec words
    assert "zelnorin" in seen[0] and "Adults with type 2 diabetes" in seen[0]   # spec + paper context in the prompt


def test_quote_not_in_paper_is_kept_but_flagged():
    rows = run_with([draft("-0.57", "Zelnorin 10 mg reduced HbA1c by -0.57 points in all patients.")])
    assert len(rows) == 1 and not rows[0].quote_ok and "not found" in rows[0].note and rows[0].std.value == "-0.57"


def test_quote_without_the_value_fails():
    rows = run_with([draft("-0.60", "| 10 mg daily | week 12 | −0.57 |")])
    assert not rows[0].quote_ok and "does not hold" in rows[0].note


def test_unicode_minus_in_paper_matches_ascii_quote():
    rows = run_with([draft("-0.80", "| 20 mg daily | week 24 | -0.80 |", dose="20 mg daily", time="week 24")])
    r = rows[0]
    assert r.quote_ok and r.std.value == "-0.80" and r.std.decimals == 2 and r.std.unit == PP
    assert PAPER[r.quote_start:r.quote_end] == "| 20 mg daily | week 24 | −0.80 |"


def test_ambiguous_anchor_picks_the_occurrence_inside_the_passage():
    q = "Zelnorin 20 mg gave a mean difference of -0.72 percentage points at week 12."
    assert len(anchor.spans(PAPER, q)) == 2
    rows = run_with([draft("-0.72", q, dose="20 mg")])
    r = rows[0]
    assert r.quote_ok and r.quote_start >= START and "found 2 times" in r.note


def test_table_row_and_sentence_with_the_same_value_merge():
    rows = run_with([draft("-0.57", "| 10 mg daily | week 12 | −0.57 |", dose="10 mg daily", time="week 12"),
                     draft("lowered HbA1c by 0.57", "At week 12, Zelnorin 10 mg lowered HbA1c by 0.57 percentage "
                                                    "points versus placebo.", dose="10 mg", time="12 weeks")])
    assert len(rows) == 1 and rows[0].quote_ok and len(rows[0].also) == 1


def test_different_values_for_the_same_key_are_both_kept():
    rows = run_with([draft("-0.80", "| 20 mg daily | week 24 | −0.80 |", dose="20 mg daily", time="week 24"),
                     draft("-0.85", "At week 24, the 20 mg dose gave -0.85 percentage points.", dose="20 mg",
                           time="week 24")])
    assert sorted(r.std.value for r in rows) == ["-0.80", "-0.85"]
    assert all("conflict" in r.note for r in rows)


def test_rows_outside_the_spec_are_dropped_with_a_reason():
    rows = run_with([draft("fell by 1.1", "Fasting plasma glucose fell by 1.1 mmol/L with Zelnorin 10 mg at week 12.",
                           measure="fasting plasma glucose", unit="mmol/L"),
                     draft("-0.57", "| 10 mg daily | week 12 | −0.57 |", subject="Metformin")])
    assert len(rows) == 2 and all(r.dropped for r in rows)
    assert "measure" in rows[0].dropped and "subject" in rows[1].dropped


def test_bad_reply_is_retried_then_skipped():
    calls = []

    def ask(prompt):
        calls.append(prompt)
        return "not json"
    hit = FindHit(paper="P-t", passages=[PASSAGE])
    rows = extract.run(SPEC, [hit], "medical", RunConfig(), lm=RecordedLM("fake", ask), texts={"P-t": PAPER})
    assert rows == [] and len(calls) >= 2


def test_a_failed_model_service_fails_the_step_instead_of_skipping_the_passage():
    # a skipped passage would leave a short rows.jsonl that a rerun takes as done (silent data loss)
    calls = []

    def ask(prompt):
        calls.append(prompt)
        raise ConnectionRefusedError(111, "Connection refused")
    hit = FindHit(paper="P-t", passages=[PASSAGE])
    with pytest.raises(ConnectionRefusedError):
        extract.run(SPEC, [hit], "medical", RunConfig(), lm=RecordedLM("fake", ask), texts={"P-t": PAPER})
    assert len(calls) == 1   # not asked again as if the reply were bad


def test_spec_text_names_fixed_slots_and_columns():
    s = SPEC.model_copy(update={"fixed": {"time_point": "24 weeks"}})
    text = spec_text(s)
    assert "time point = 24 weeks" in text and "dose, time point, patient group" in text


def test_list_spec_without_subject_or_measure_keeps_any_row_as_written():
    from evqa.contracts import Row
    from evqa.extract.core import to_spec
    spec = SPEC.model_copy(update={"type": "list", "subjects": [], "comparator": None,
                                   "measure": Name(label="", known=False)})
    r = to_spec(Row(paper="P", subject="Zelnorin", measure="fasting plasma glucose", raw="-1.1", quote="q"), spec)
    assert r.dropped is None and (r.subject, r.measure) == ("Zelnorin", "fasting plasma glucose")
    text = spec_text(spec)
    assert "subjects: any treatment" in text and "measure: any measure" in text


def test_a_subject_the_paper_never_names_is_dropped():
    """A paper on zelnorin read for a question on quarivo: the model wrote 'quarivo' on zelnorin's value."""
    spec = SPEC.model_copy(update={"subjects": [Name(label="quarivo")]})
    hit = FindHit(paper="P-t", screen="yes", passages=[PASSAGE])
    ask = lambda prompt: json.dumps({"rows": [draft("-0.57", "| 10 mg daily | week 12 | −0.57 |", subject="quarivo")]})  # noqa: E731
    rows = extract.run(spec, [hit], "medical", RunConfig(), lm=RecordedLM("fake", ask), texts={"P-t": PAPER})
    assert len(rows) == 1 and rows[0].dropped == "subject 'quarivo' is not named in the paper"


def test_a_code_name_find_found_counts_as_naming_the_subject():
    spec = SPEC.model_copy(update={"subjects": [Name(label="quarivo")]})
    hit = FindHit(paper="P-t", screen="yes", passages=[PASSAGE], details={"agent": ["Zelnorin"]})
    ask = lambda prompt: json.dumps({"rows": [draft("-0.57", "| 10 mg daily | week 12 | −0.57 |", subject="quarivo")]})  # noqa: E731
    rows = extract.run(spec, [hit], "medical", RunConfig(), lm=RecordedLM("fake", ask), texts={"P-t": PAPER})
    assert len(rows) == 1 and rows[0].dropped is None
