"""The one LLM task of Extract: read one passage and write one row per reported value of the asked measure.

Contract (docs/prompt-writing.md):
  in   paper_context  the paper's title and abstract (who the patients are is usually stated there, not in Results)
       passage        the marked passage (a table or text) to read
       question_spec  what is asked, as plain lines made by code from the Spec (subjects, comparator, measure,
                      fixed slots, open columns)
  out  rows           list of RowDraft; [] when the passage reports no value of the measure for the subjects
  accepted by code    quote anchored in paper.md and holding the value (quote_ok); subject and measure in the spec
                      (else the row is kept with a `dropped` reason); value read by norm.py, never by the model.
"""
from __future__ import annotations

import dspy
from pydantic import BaseModel, Field

# v2 (21 Nov 2026): inputs in the order paper_context, passage, question_spec, so the part shared by many calls
# (instructions, then the paper) comes first and vLLM prefix caching can reuse it. Same words as v1; the new order
# changes the prompt text, so Extract's LLM cache misses once. v1 (question_spec first) is kept as ExtractRowsV1.
PROMPT_VERSION = "extract-rows-v2"


class RowDraft(BaseModel):
    subject: str = Field(description="the treatment the value is for; the question's name when it is the same drug")
    comparator: str | None = Field(None, description="what it is compared with, e.g. placebo; null if not stated")
    measure: str = Field(description="the measured quantity; the question's measure words when it is that measure")
    patient_group: str | None = Field(None, description="who was treated, short; question's words when the same group")
    dose: str | None = Field(None, description="dose as written, e.g. '20 mg daily'; null if not stated")
    time_point: str | None = Field(None, description="time point as written, e.g. 'week 24'; null if not stated")
    statistic: str = Field("mean difference vs comparator", description="e.g. 'mean difference vs placebo'")
    raw: str = Field(description="the value exactly as written in the quote, e.g. '-0.78' or 'reduced by 0.57'")
    unit: str = Field("", description="unit as the paper writes it (sentence or table header), e.g. 'kg'; '' if none")
    quote: str = Field(description="the full sentence or the full table row (from | to |) holding the value, copied")


class ExtractRows(dspy.Signature):
    """Write one row for every value in the passage that reports the question's measure for a question subject.

    One row per number. Fill subject, comparator, measure, patient_group, dose, time_point and statistic from the
    passage; take what the passage leaves out (the patients, a table's unit or time point) from the table header,
    the caption or the paper context. Name subject and measure with the question's words when they are the same
    thing; write patient_group with the question's words when it is the same group of patients, otherwise in the
    paper's words. Keep the paper's own wording in raw and quote: raw is the number as printed (with a direction
    word such as "reduced by" when the sentence uses one) and quote is the whole sentence or table row copied
    character for character. Skip values of other measures and other treatments. Return rows = [] when the passage
    has no value of the measure for a question subject.

    Example (sentence): passage "At week 8, Zelnorin 5 mg lowered systolic blood pressure by 4.2 mmHg versus
    placebo." question subjects: Zelnorin; measure: systolic blood pressure change ->
    rows [{subject "Zelnorin", comparator "placebo", measure "systolic blood pressure change", dose "5 mg",
    time_point "week 8", raw "lowered systolic blood pressure by 4.2", unit "mmHg", quote "At week 8, Zelnorin 5 mg
    lowered systolic blood pressure by 4.2 mmHg versus placebo."}]
    Example (table, unit in the header, a row of another measure skipped): passage
    "| Zelnorin dose | Time point | Mean difference vs placebo in SBP (mmHg) |\n| 10 mg daily | week 8 | −6.1 |" and
    a second table on heart rate -> one row with dose "10 mg daily", time_point "week 8", raw "−6.1", unit "mmHg",
    quote "| 10 mg daily | week 8 | −6.1 |"; no row for heart rate.
    Example (nothing to extract): passage "Blood pressure was measured with a validated cuff at each visit." ->
    rows []."""
    paper_context: str = dspy.InputField(desc="title and abstract of the paper")
    passage: str = dspy.InputField(desc="the passage to read (text or a Markdown table)")
    question_spec: str = dspy.InputField(desc="what the question asks: subjects, comparator, measure, fixed slots")
    rows: list[RowDraft] = dspy.OutputField(desc="one row per value; [] when there is none")


def field_first(sig: type[dspy.Signature], name: str) -> type[dspy.Signature]:
    """The same signature (instructions and fields) with field `name` moved to the front."""
    order = [name, *(n for n in sig.fields if n != name)]
    return dspy.Signature({n: (sig.fields[n].annotation, sig.fields[n]) for n in order}, sig.instructions)


ExtractRowsV1 = field_first(ExtractRows, "question_spec")   # the predecessor (v1 field order)
