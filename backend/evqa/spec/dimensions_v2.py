"""Question-specific, domain-free setting dimensions (prompt v2)."""
from __future__ import annotations

import re
import dspy
from pydantic import BaseModel
from evqa.contracts import Dimension
from evqa.llm import service_failed


class DraftDimension(BaseModel):
    key: str
    question: str
    why: str
    fixed_value: str = ""
    quote: str = ""


class SelectDimensions(dspy.Signature):
    """Identify dimensions needed to describe the settings of results answering the question.

    Input: question is the user's question. Output: dimensions is a list of objects with key (snake_case),
    question (one short question to ask the user), why (one line), fixed_value and quote. If the question fixes a
    dimension, fixed_value and quote are exact substrings of the question; otherwise both are empty. Do not invent
    a fixed value. Include dimensions relevant to the question even when their value is missing.

    Medicine: "What was the effect of aspirin in children?" -> [{"key":"population", "question":"Which
    population?", "why":"Results can differ by population.", "fixed_value":"children", "quote":"children"}].
    Materials: "What strength did alloy Z reach at 500 C?" -> [{"key":"temperature", "question":"At what
    temperature?", "why":"Strength depends on temperature.", "fixed_value":"500 C", "quote":"500 C"},
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
        seen.add(d.key)
        kept.append(Dimension.model_validate(d.model_dump()))
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
    empty; measure is the asked outcome or empty. Do not include a contextual setting as a subject.
    Example: "Does aspirin reduce fever?" -> subjects ["aspirin"], comparator "", measure "fever".
    Example: "Does alloy X have more strength than alloy Y?" -> subjects ["alloy X", "alloy Y"], comparator "",
    measure "strength". Example: "Which models were studied?" -> subjects [], comparator "", measure "".
    """
    question: str = dspy.InputField()
    subjects: list[str] = dspy.OutputField()
    comparator: str = dspy.OutputField()
    measure: str = dspy.OutputField()
