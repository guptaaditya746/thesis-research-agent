"""The Spec step's LLM tasks, one DSPy Signature each. Code (spec/build.py) validates every output.

The Spec step is an independent advisor: these prompts see only the question, the names in it and the user's
answers, never a paper. Examples use drugs and measures that are not in the benchmark questions.

PROMPTS names the version of each prompt. When a prompt changes behaviour, bump its version and keep the old text
in HISTORY below (docs/prompt-writing.md).

History
- v1 (21 Nov 2026): first versions.
- 21 Nov 2026 (new question types effect, trend, list; Aditya):
  ClassifyQuestion v1  new: the question type from the question text only (before: the dataset's type field).
  ReadQuestion v2      subjects may be [] and measure "" (list questions); a second drug after "more than" is the
                       comparator; examples without benchmark names. v1 text in HISTORY.
  Direction v2         also for "does A beat B" (effect) questions; examples without benchmark topics. v1 in HISTORY.
"""
from __future__ import annotations

import dspy

PROMPTS = {"ClassifyQuestion": "v1", "ReadQuestion": "v2", "KnowName": "v1", "OtherNames": "v1", "CheckNames": "v1",
           "ReadUserNames": "v1", "Direction": "v2"}
QUESTION_TYPES = ("lookup", "effect", "best", "trend", "list")


class ClassifyQuestion(dspy.Signature):
    """Say what kind of answer a question about drug trials asks for. Read only the question.

    Contract (docs/prompt-writing.md):
      in   question   the user's question
           feedback   "" on the first call; on a repair call the rejected reply and the check it failed
      out  type       lookup | effect | best | trend | list
           reason     one short line naming the words that decided it
      accepted by code  type is one of the five; best has two options (two drugs, or the doses of one drug);
                        effect has a second option (another drug or a control such as placebo); every type but list
                        names a measure.

    Types:
    - lookup: the value(s) of a measure for a drug ("How much does X lower Y?", "What does X do to Y?"). A question
      that fixes a dose or a time point ("X 10 mg", "at 12 weeks") is still lookup.
    - effect: whether one option beats one other option on a measure: drug A against drug B, or against a control
      such as placebo ("Does A lower Y more than B does?", "Is A better than placebo for Y?").
    - best: which of several options gives the best value: the drugs the question lists, or the doses of one drug
      ("Which drug ... more, A or B?", "Which dose of A works best?").
    - trend: how the measure changes over time or across doses ("How does the effect of A on Y change over time?",
      "... change with the dose?").
    - list: which studies, papers or trials tested something; the answer is a set of studies.
    A name you do not know does not change the type.

    Examples:
    1) normal: "How much does naproxen 500 mg lower pain score at 12 weeks?" -> type "lookup"
    2) confusing (two drugs, but "does A beat B" asks for the difference, not a winner among options):
       "Does budesonide improve FEV1 more than salmeterol does?" -> type "effect"
       while "Which drug improves FEV1 more, budesonide or salmeterol?" -> type "best"
    3) missing (no measure named, unknown name): "Which trials tested trelvanex?" -> type "list"
    """

    question: str = dspy.InputField()
    feedback: str = dspy.InputField(desc="'' or: the rejected reply and the check it failed")
    type: str = dspy.OutputField(desc="lookup | effect | best | trend | list")
    reason: str = dspy.OutputField(desc="one short line")


class ReadQuestion(dspy.Signature):
    """Split a question about drug trials into its parts. Copy every part exactly as the question writes it.

    Parts:
    - subjects: the drug(s) the question asks about. For "which drug ... A or B" give both A and B. [] when the
      question names no drug ("Which studies report pain score?").
    - comparator: what the drug is compared with, only when the question names it (e.g. "versus placebo", or the
      drug after "more than"); else "".
    - measure: the outcome the question asks about (e.g. "pain score"), without verbs like "lower"; "" when the
      question names no outcome ("Which trials tested naproxen?").
    - dose: a dose the question fixes (e.g. "500 mg"); "" when the question names no dose amount.
    - time_point: a time the question fixes (e.g. "12 weeks"); "" when none.
    - patient_group: the patients the question fixes (e.g. "older adults"); "" when none.

    Examples:
    1) normal: "How much does naproxen 500 mg lower pain score at 12 weeks?"
       -> subjects ["naproxen"], comparator "", measure "pain score", dose "500 mg", time_point "12 weeks",
          patient_group ""
    2) confusing: "Which drug improves FEV1 more in older adults, budesonide or zorvatinel?"
       -> subjects ["budesonide", "zorvatinel"], comparator "", measure "FEV1", dose "", time_point "",
          patient_group "older adults"
       and "Does budesonide improve FEV1 more than salmeterol does?"
       -> subjects ["budesonide"], comparator "salmeterol", measure "FEV1", dose "", time_point "", patient_group ""
    3) missing: "Which dose of budesonide works best on FEV1?"
       -> subjects ["budesonide"], comparator "", measure "FEV1", dose "" (no amount is named), time_point "",
          patient_group ""
       and "Which trials tested trelvanex?"
       -> subjects ["trelvanex"], comparator "", measure "" (no outcome is named), dose "", time_point "",
          patient_group ""
    """

    question: str = dspy.InputField()
    subjects: list[str] = dspy.OutputField(desc="drug names, copied exactly from the question; [] when none")
    comparator: str = dspy.OutputField(desc='copied from the question, or ""')
    measure: str = dspy.OutputField(desc='the outcome, copied from the question, or ""')
    dose: str = dspy.OutputField(desc='copied from the question, or ""')
    time_point: str = dspy.OutputField(desc='copied from the question, or ""')
    patient_group: str = dspy.OutputField(desc='copied from the question, or ""')


class KnowName(dspy.Signature):
    """Say whether you know this name from your own knowledge, and if so define it in one plain line.

    Questions often contain new or made-up drug names. A name you cannot place is unknown, even when it sounds like
    a drug (for example it ends in -gliptin, -mab or -oxin). known = true only when you can say a specific true fact
    about this exact name: what it is and what it is used for. When unknown, give definition "".

    Examples:
    1) name "metformin", role "drug" -> known true, definition "A tablet for type 2 diabetes that lowers blood sugar."
    2) name "zorvatinel", role "drug" -> known false, definition "" (it sounds like a drug, but you cannot place it)
    3) name "LDL cholesterol", role "measure" -> known true,
       definition "The amount of low-density lipoprotein cholesterol in the blood; high levels raise heart risk."
    """

    name: str = dspy.InputField()
    role: str = dspy.InputField(desc="drug | comparator | measure")
    question: str = dspy.InputField(desc="the question the name comes from")
    known: bool = dspy.OutputField()
    definition: str = dspy.OutputField(desc='one plain line, or "" when unknown')


class OtherNames(dspy.Signature):
    """List other names that mean exactly the same thing as this name: spellings, abbreviations, full forms,
    brand or chemical names that papers use for it. Give only names you are sure of. A broader or narrower thing is
    not another name (LDL cholesterol is not "cholesterol"). Give [] when you know none.

    Examples:
    1) name "systolic blood pressure" -> ["SBP", "systolic BP"]
    2) name "LDL cholesterol" -> ["LDL-C", "low-density lipoprotein cholesterol", "LDL"]
       (not "cholesterol" or "total cholesterol": those are different measures)
    3) name "placebo" -> []
    """

    name: str = dspy.InputField()
    definition: str = dspy.InputField()
    synonyms: list[str] = dspy.OutputField(desc="other names, at most 8; [] when none")


class CheckNames(dspy.Signature):
    """Check each candidate: is it another name for exactly the same thing as `name`? Answer one true or false per
    candidate, in the same order. A broader thing, a narrower thing, a related test or a unit is false.

    Examples:
    1) name "LDL cholesterol", candidates ["LDL-C", "total cholesterol"] -> [true, false]
    2) name "systolic blood pressure", candidates ["SBP", "blood pressure", "diastolic blood pressure"]
       -> [true, false, false]
    3) name "fasting glucose", candidates [] -> []
    """

    name: str = dspy.InputField()
    definition: str = dspy.InputField()
    candidates: list[str] = dspy.InputField()
    same: list[bool] = dspy.OutputField(desc="one per candidate, same order")


class ReadUserNames(dspy.Signature):
    """The user was asked for other names of `name`. List the other names their answer gives, copied exactly from
    the answer. Give [] when the answer gives none.

    Examples:
    1) name "zorvatinel", answer "It is also called ZRV-118." -> ["ZRV-118"]
    2) name "zorvatinel", answer "I know no other names. Use the names in the question." -> []
    3) name "zorvatinel", answer "Some papers call it compound 7, I think." -> ["compound 7"]
    """

    name: str = dspy.InputField()
    answer: str = dspy.InputField()
    names: list[str] = dspy.OutputField(desc="copied from the answer; [] when none")


class Direction(dspy.Signature):
    """For a question that compares options (which one works best, or does one beat another), say whether a higher
    value of the measure is the better result. Use the question's wording first ("lowers the most" means lower is
    better), then your knowledge of the measure.

    Examples:
    1) normal: question "Which drug raises HDL cholesterol the most?", measure "HDL cholesterol"
       -> higher_is_better true
    2) confusing ("more" is about the size of the change, the wording says lowering is wanted):
       question "Does naproxen lower pain score more than ibuprofen does?", measure "pain score" -> false
    3) missing (no direction word; use knowledge): question "Which dose of budesonide works best on FEV1?",
       measure "FEV1" -> true (a higher FEV1 means better breathing)
    """

    question: str = dspy.InputField()
    measure: str = dspy.InputField()
    higher_is_better: bool = dspy.OutputField()
    reason: str = dspy.OutputField(desc="one short line")


# ---------------------------------------------------------------- earlier versions (kept, not used)
HISTORY = {
    'ReadQuestion v1': r'''
class ReadQuestion(dspy.Signature):
    """Split a question about drug trials into its parts. Copy every part exactly as the question writes it.

    Parts:
    - subjects: the drug(s) the question asks about. For "which drug ... A or B" give both A and B.
    - comparator: what the drug is compared with, only when the question names it (e.g. "versus placebo"); else "".
    - measure: the outcome the question asks about (e.g. "fasting glucose"), without verbs like "lower".
    - dose: a dose the question fixes (e.g. "100 mg"); "" when the question names no dose amount.
    - time_point: a time the question fixes (e.g. "12 weeks"); "" when none.
    - patient_group: the patients the question fixes (e.g. "older adults"); "" when none.

    Examples:
    1) "How much does sitagliptin 100 mg lower fasting glucose at 12 weeks?"
       -> subjects ["sitagliptin"], comparator "", measure "fasting glucose", dose "100 mg", time_point "12 weeks",
          patient_group ""
    2) "Which drug lowers systolic blood pressure more in older adults, amlodipine or zorvatinel?"
       -> subjects ["amlodipine", "zorvatinel"], comparator "", measure "systolic blood pressure", dose "",
          time_point "", patient_group "older adults"
    3) "Which dose of atorvastatin works best on LDL cholesterol?"
       -> subjects ["atorvastatin"], comparator "", measure "LDL cholesterol", dose "" (no amount is named),
          time_point "", patient_group ""
    """

    question: str = dspy.InputField()
    subjects: list[str] = dspy.OutputField(desc="drug names, copied exactly from the question")
    comparator: str = dspy.OutputField(desc='copied from the question, or ""')
    measure: str = dspy.OutputField(desc="the outcome, copied from the question")
    dose: str = dspy.OutputField(desc='copied from the question, or ""')
    time_point: str = dspy.OutputField(desc='copied from the question, or ""')
    patient_group: str = dspy.OutputField(desc='copied from the question, or ""')
''',
    'Direction v1': r'''
class Direction(dspy.Signature):
    """For a question that asks which option works best, say whether a higher value of the measure is the better
    result. Use the question's wording first ("lowers the most" means lower is better), then your knowledge of the
    measure.

    Examples:
    1) question "Which drug raises HDL cholesterol the most?", measure "HDL cholesterol" -> higher_is_better true
    2) question "Which dose lowers systolic blood pressure the most?", measure "systolic blood pressure" -> false
    3) question "Which drug works best on pain score?", measure "pain score" -> false (a lower pain score is better)
    """

    question: str = dspy.InputField()
    measure: str = dspy.InputField()
    higher_is_better: bool = dspy.OutputField()
    reason: str = dspy.OutputField(desc="one short line")
''',
}
