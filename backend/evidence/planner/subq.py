"""The planner steps that also read the sub-questions: new versioned steps (their own names), so plans made
without sub-questions keep running on the old steps and their cached replies."""
from __future__ import annotations

from typing import Literal

import dspy

from evidence.planner.plan import LineDraft
from evidence.steps import Step


class LinesSubSig(dspy.Signature):
    """List what would prove or disprove the main question from papers: 1 to 5 evidence lines, each one checkable
    thing stated as a question. The sub-questions name parts the person also wants looked at: give a line for each
    part they add when it helps answer the main question; never a line the main question does not need. Start a line
    from a saved template when one fits (copy its name into `template`); otherwise leave `template` null. Do not write
    queries here. `sub_questions` may be an empty list.

    Example (normal): question "Does Method K improve Yield compared with the Usual method?", sub_questions
    ["Which studies measured Yield?"] -> [{"question": "Is Method K better than the Usual method on Yield?",
    "kind": "effect", "template": "effect"}, {"question": "Which papers measured Yield for Method K and the Usual
    method?", "kind": "inventory", "template": null}]
    Example (confusing): question "Does Method K improve Yield compared with the Usual method?", sub_questions
    ["Does Method K also cut the Error count?"] -> an effect line for Yield and an effect line "Is Method K better
    than the Usual method on Error count?" (the sub-question adds a measure the lines should look at)
    Example (missing): question "Does Method K improve Yield compared with the Usual method?", sub_questions
    ["Do Small batches differ?"] -> [{"question": "Is Method K better than the Usual method on Yield?", "kind":
    "effect", "template": "effect"}] (a group named only in a sub-question adds no line)"""
    question: str = dspy.InputField(desc="the main research question")
    clarifications: str = dspy.InputField(desc="JSON list of {question, answer} the person gave; may be empty")
    sub_questions: str = dspy.InputField(
        desc="JSON list of the parts of the question the person also wants looked at; may be empty")
    templates: str = dspy.InputField(desc="JSON object: saved template name -> what it finds")
    problem: str = dspy.InputField(desc="why the last reply was refused; empty on the first call")
    lines: list[LineDraft] = dspy.OutputField(desc="1 to 5 evidence lines")


class ThingsSubSig(dspy.Signature):
    """Name the things the main question is about and the field it belongs to. `things` are short ids, one per thing
    named in the question (a method, a measure, a dataset): first the thing the question asks about, then what it
    is compared with, then the rest. The sub-questions may name more things or measures to look for: add those. A
    group named only in a sub-question is not a thing. `measures` repeats the ids of `things` that are measures (a
    score, a rate, a time, a count of outcomes); empty when none is named. `lower_is_better` repeats the ids of
    measures where a lower value is better (an error count, a delay, a cost). `field` is cs, medicine, materials or
    other. `sub_questions` may be an empty list.

    Example (normal): question "Does Method K improve Yield compared with the Usual method?", sub_questions
    ["Which studies measured Yield?"] -> field "cs", things ["method_k", "usual_method", "yield"], measures
    ["yield"], lower_is_better []
    Example (confusing): same question, sub_questions ["Does Method K also cut the Error count?"] -> things
    ["method_k", "usual_method", "yield", "error_count"], measures ["yield", "error_count"], lower_is_better
    ["error_count"]
    Example (missing): same question, sub_questions ["Do Small batches differ?"] -> things ["method_k",
    "usual_method", "yield"], measures ["yield"], lower_is_better [] (Small batches is a group, so it is no thing)"""
    question: str = dspy.InputField(desc="the main research question")
    sub_questions: str = dspy.InputField(
        desc="JSON list of the parts of the question the person also wants looked at; may be empty")
    problem: str = dspy.InputField(desc="why the last reply was refused; empty on the first call")
    field: Literal["cs", "medicine", "materials", "other"] = dspy.OutputField()
    things: list[str] = dspy.OutputField(desc="short ids of the things the question names; at least one")
    measures: list[str] = dspy.OutputField(desc="the ids among things that are measures; may be empty")
    lower_is_better: list[str] = dspy.OutputField(desc="the ids among measures where lower is better; may be empty")


LINES_SUB = Step(LinesSubSig, "planner_lines_sub")
THINGS_SUB = Step(ThingsSubSig, "planner_things_sub")
