"""Question-specific, domain-free setting dimensions (prompt v2).

History: ReadQuestionCore v2 (21 Nov 2026): new `feedback` input for the one repair call when a part is not written
in the question (Haiku practice run: "body weight reduction" for "reduction in body weight"). v1 had no feedback.
SelectDimensions (21 Nov 2026): new `row_field` per dimension; code renames such a dimension to the Row field
(dose / time_point), so Link never judges a per-row value (Haiku named the time "duration": p22, p8 lost rows).
"""
from __future__ import annotations

import re
import dspy
from typing import Literal

from pydantic import BaseModel
from evqa.contracts import Dimension
from evqa.llm import service_failed

ROW_FIELDS = ("dose", "time_point")    # Row fields (contracts.Row) every value row carries itself


class DraftDimension(BaseModel):
    key: str
    question: str
    why: str
    fixed_value: str = ""
    quote: str = ""
    row_field: Literal["", "dose", "time_point"] = ""


class SelectDimensions(dspy.Signature):
    """Identify dimensions needed to describe the settings of results answering the question.

    Input: question is the user's question. Output: dimensions is a list of objects with key (snake_case),
    question (one short question to ask the user), why (one line), fixed_value and quote. If the question fixes a
    dimension, fixed_value and quote are exact substrings of the question; otherwise both are empty. Do not invent
    a fixed value. Include dimensions relevant to the question even when their value is missing. The named subject
    and the outcome are not settings; do not return a dimension for them.
    row_field: "time_point" when the dimension is when a result was measured (week 24, after 1000 cycles, epoch
    10), "dose" when it is how much of the studied subject was given or applied (25 mg, 2 wt%, 4 bits); else "".
    These two differ between results of one study, so each result states its own value.

    Medicine: "What was the effect of aspirin in children?" -> [{"key":"population", "question":"Which
    population?", "why":"Results can differ by population.", "fixed_value":"children", "quote":"children"}].
    Materials: "What strength did alloy Z reach at 500 C?" -> [{"key":"temperature", "question":"At what
    temperature?", "why":"Strength depends on temperature.", "fixed_value":"500 C", "quote":"500 C", "row_field":""},
    {"key":"processing", "question":"Which processing method?", "why":"Processing affects strength.",
    "fixed_value":"", "quote":""}].
    ML: "How accurate is model X?" -> [{"key":"dataset", "question":"Which dataset?", "why":"Accuracy
    depends on the dataset.", "fixed_value":"", "quote":""}]. Return [] if no dimensions can be identified.
    """
    question: str = dspy.InputField()
    feedback: str = dspy.InputField()
    dimensions: list[DraftDimension] = dspy.OutputField()


def checked(drafts: list[DraftDimension], question: str) -> tuple[list[Dimension], list[str]]:
    kept, errors, seen = [], [], set()
    for d in drafts:
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", d.key) or d.key in seen:
            errors.append(f"invalid or repeated key {d.key!r}")
            continue
        if not d.question.strip() or not d.why.strip():
            errors.append(f"{d.key}: question or why missing")
            continue
        if bool(d.fixed_value) != bool(d.quote) or (d.quote and (d.quote not in question or d.fixed_value not in d.quote)):
            errors.append(f"{d.key}: fixed value and quote must be copied from question")
            continue
        key = d.row_field or d.key          # a per-row dimension takes the Row field's name (Link and Answer use it)
        if key in seen:
            errors.append(f"{d.key}: a second dimension for {key!r}")
            continue
        seen.add(key)
        kept.append(Dimension(key=key, question=d.question, why=d.why, fixed_value=d.fixed_value, quote=d.quote))
    return kept, errors


def select(question: str, lm: dspy.BaseLM) -> list[Dimension]:
    feedback = ""
    accepted: list[Dimension] = []
    for attempt in range(2):
        try:
            with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
                out = dspy.Predict(SelectDimensions)(question=question, feedback=feedback,
                                                       config={"attempt": attempt} if attempt else {})
            drafts = [d if isinstance(d, DraftDimension) else DraftDimension.model_validate(d) for d in out.dimensions]
            accepted, failures = checked(drafts, question)
            if not failures:
                return accepted
            feedback = "Failed checks: " + "; ".join(failures)
        except Exception as exc:
            if service_failed(exc):
                raise
            feedback = f"Output unreadable: {type(exc).__name__}"
    return accepted


class ReadQuestionCore(dspy.Signature):
    """Read the objects, comparison and measure from a question. Copy every name exactly from the question.

    Input: question. Output: subjects is a list of named things being studied; comparator is a named reference or
    empty; measure is the asked outcome or empty. Give only each thing's name, without quantities or settings.
    Do not include a contextual setting as a subject. For "How does aspirin 10 mg affect fever?", subjects is
    ["aspirin"], not ["aspirin 10 mg"].
    Example: "Does aspirin reduce fever?" -> subjects ["aspirin"], comparator "", measure "fever".
    Example: "Does alloy X have more strength than alloy Y?" -> subjects ["alloy X", "alloy Y"], comparator "",
    measure "strength". Example: "Which models were studied?" -> subjects [], comparator "", measure "".
    feedback is "" or lists parts of your last reply that are not written in the question; reply again and copy
    those parts word for word from the question (e.g. question "reduction in body weight", not "body weight
    reduction").
    """
    question: str = dspy.InputField()
    feedback: str = dspy.InputField(desc="'' or: parts of the last reply that are not written in the question")
    subjects: list[str] = dspy.OutputField()
    comparator: str = dspy.OutputField()
    measure: str = dspy.OutputField()
