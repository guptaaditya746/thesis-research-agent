"""The three model tasks of Find, one DSPy Signature each (docs/prompt-writing.md: one task, typed output, examples,
code-checked acceptance). Code renders the spec as plain text (`pipeline.spec_text`); the model never sees eval data.

- ScreenPaper: is this paper about the spec? yes / no / unsure + one-line reason.
- MarkPassages: which numbered passages hold values for the spec (or a column's value), with a checkable quote.
- NextSearch: the gap-filling agent's one step: propose one search term for an open gap, or stop.
- SearchTerms: other wordings papers may use for the spec's subjects and measure (exact-word search, no index).

Version: find-prompts v2 (21 Nov 2026; v1 had no SearchTerms, BM25 ranked passages instead)."""
from __future__ import annotations

from typing import Literal

import dspy
from pydantic import BaseModel

# v3 (21 Nov 2026): ScreenPaper and MarkPassages take the paper first and the spec last, so vLLM prefix caching
# reuses the paper part across questions. Same words as v2; the v2 field order is kept as ScreenPaperV2 and
# MarkPassagesV2 (defined at the end). The changed prompt text makes the LLM cache miss once for these calls.
PROMPTS_VERSION = "find-prompts-v3"


class ScreenPaper(dspy.Signature):
    """Decide whether one paper can give values for a question's spec.

    Inputs: `spec` (what the user wants: subjects, measure, slots the question fixes, open points), and the paper's
    `title`, `abstract` and some `passages` that a search matched.

    decision:
    - "yes": the paper reports the measure for at least one spec subject (or a name the spec says the papers use for
      it), and it does not contradict a slot the question fixes.
    - "no": the paper is about other drugs/things only, or never reports the measure, or reports only values that
      a fixed slot excludes (for example the spec fixes "24 weeks" and the paper reports only weeks 36 and 52).
    - "unsure": the text shown does not settle it.
    An open point answered "all" never excludes a paper: a paper on the same subject in other patients, at other
    doses or at other time points is "yes" when that point is "all".
    reason: one short line naming the fact that decided it.

    Example: spec subject "drugA", measure "HbA1c", patient group "all"; paper "DrugA in newly diagnosed adults",
    reports HbA1c -> yes, "reports HbA1c for drugA; other patients, but patient group is all".
    Example: spec subject "drugA"; paper about "drugB" only -> no, "about drugB, not drugA".
    Example: spec fixes time point "24 weeks"; paper on drugA reports HbA1c only at weeks 36 and 52 -> no,
    "drugA HbA1c only at weeks 36 and 52, spec fixes 24 weeks".
    Example: spec subject "drugA"; abstract names drugA but does not say which measures were taken -> unsure."""
    title: str = dspy.InputField()
    abstract: str = dspy.InputField()
    passages: str = dspy.InputField(desc="passages of the paper that the search matched")
    spec: str = dspy.InputField(desc="the question's spec in plain text")
    decision: Literal["yes", "no", "unsure"] = dspy.OutputField()
    reason: str = dspy.OutputField(desc="one short line")


class Mark(BaseModel):
    id: int                                  # the passage number shown in brackets
    role: Literal["value", "context"]
    quote: str                               # a short piece copied exactly from that passage
    subjects: list[str] = []                 # spec subject labels the values are for
    columns: list[str] = []                  # spec columns the passage states


class MarkPassages(dspy.Signature):
    """Mark the passages of one paper that a reader needs to fill the spec's answer table.

    Inputs: `spec` (subjects, measure, fixed slots, open points, answer columns) and `passages`, each shown as
    "[number] (section) text".

    Output `marks`, one per useful passage:
    - id: the passage number.
    - role: "value" when the passage states at least one number of the spec's measure for a spec subject (a table
      row or a sentence such as "at week 24 the mean difference was -0.78 percentage points"); "context" when it
      states no such value but states a column's value that the paper's values depend on (for example the methods
      sentence that says which patients took part, or which doses were given).
    - quote: a short piece (a few words up to one sentence) copied exactly from that passage, showing the value or
      the column's value.
    - subjects: the spec subject labels (as written in the spec) whose values the passage holds; [] for context.
    - columns: the spec columns whose value the passage itself states (e.g. "time point" when it says "week 24").
    A paragraph that gives values without naming the measure counts when its section or the sentence before makes
    clear which measure it is. Leave out passages that only describe other measures, other drugs, or plans.
    Return [] when no passage helps.

    Example: [7] (4.1 Change in HbA1c) "At week 24, the mean difference versus placebo was -0.78 percentage points for
    20 mg daily." with measure HbA1c, columns [time point] -> {"id": 7, "role": "value", "quote": "At week 24, the
    mean difference versus placebo was -0.78 percentage points", "subjects": ["drugA"], "columns": ["time point"]}.
    Example: [3] (3.1 Participants) "Adults with newly diagnosed type 2 diabetes took part." with column
    patient group -> {"id": 3, "role": "context", "quote": "Adults with newly diagnosed type 2 diabetes",
    "subjects": [], "columns": ["patient group"]}.
    Example: a table of body weight when the measure is HbA1c -> not marked."""
    passages: str = dspy.InputField(desc="numbered passages of one paper")
    spec: str = dspy.InputField(desc="the question's spec in plain text")
    marks: list[Mark] = dspy.OutputField(desc="one entry per useful passage; [] when none")


class NextSearch(dspy.Signature):
    """Propose one search term that may close a gap in what the search has found, or stop.

    Inputs: `spec`; `gap` (what is still missing, in plain words); `tried` (terms already searched); `text` (pieces
    of the papers, each starting with its paper id).

    kind:
    - "other_name": the text defines another name for a spec subject right next to it, such as a code name in
      brackets ("drugA (DA-101)") or "also called ...". term = that other name, copied exactly from the text.
    - "search": a word or short phrase, copied from the text, that papers holding the missing values are likely
      to use. term = that phrase.
    - "stop": nothing in the text suggests a new term. term = "".
    Never repeat a term from `tried`. reason: one short line saying where in the text the term comes from.

    Example: text "P-1: Patients took drugA (DA-101) once daily." gap "other names of drugA" -> kind "other_name",
    term "DA-101", reason "P-1 gives DA-101 in brackets after drugA".
    Example: text without any other name for drugA, gap "other names of drugA" -> kind "stop", term "".
    Example: gap "no values for patient group", text "P-2: ... in newly diagnosed adults ..." -> kind "search",
    term "newly diagnosed"."""
    spec: str = dspy.InputField(desc="the question's spec in plain text")
    gap: str = dspy.InputField(desc="what is still missing")
    tried: list[str] = dspy.InputField(desc="terms already searched")
    text: str = dspy.InputField(desc="pieces of the papers, each starting with its paper id")
    kind: Literal["other_name", "search", "stop"] = dspy.OutputField()
    term: str = dspy.OutputField(desc="copied exactly from the text; empty for stop")
    reason: str = dspy.OutputField(desc="one short line")


class Term(BaseModel):
    target: str                              # a spec subject label, or "measure"
    term: str                                # a word or short phrase a paper may write


class SearchTerms(dspy.Signature):
    """List other wordings that research papers may use for the spec's subjects and measure, so that an exact-word
    search can find the papers. You see no papers; use only general knowledge.

    Input: `spec` (subjects with their known other names, the measure, fixed slots).

    Output `terms`, at most 12 entries, each {target, term}:
    - target: a subject label exactly as written in the spec, or "measure".
    - term: a word or short phrase (at most 6 words) a paper may write for that target: an abbreviation, a full
      form, a spelling variant (British/American), a brand or code name you know, or a common lab or plain-word
      name. Not the target itself, not a name the spec already lists, not a class of things (not "diabetes drugs"
      for one drug), not a general word ("level", "change", "effect").
    A subject you do not know (the spec says "no other names known") gets no terms. Return [] when you know no
    other wording.

    Example: subject "metformin", measure "HbA1c" -> [{"target": "measure", "term": "glycated haemoglobin"},
    {"target": "measure", "term": "glycated hemoglobin"}, {"target": "measure", "term": "A1c"},
    {"target": "metformin", "term": "Glucophage"}].
    Example: measure "fasting plasma glucose" (other names: FPG) -> [{"target": "measure", "term":
    "fasting glucose"}, {"target": "measure", "term": "fasting blood glucose"}]; not "glucose" alone (too general).
    Example: subject "zelvoran" (no other names known), measure "body weight" -> [{"target": "measure",
    "term": "bodyweight"}]; nothing for zelvoran."""
    spec: str = dspy.InputField(desc="the question's spec in plain text")
    terms: list[Term] = dspy.OutputField(desc="at most 12 {target, term}; [] when none")


# ---------------------------------------------------------------- predecessors (find-prompts-v2 field order)
def _first(sig: type[dspy.Signature], name: str) -> type[dspy.Signature]:
    """The same signature (instructions and fields) with field `name` moved to the front."""
    order = [name, *(n for n in sig.fields if n != name)]
    return dspy.Signature({n: (sig.fields[n].annotation, sig.fields[n]) for n in order}, sig.instructions)


ScreenPaperV2 = _first(ScreenPaper, "spec")
MarkPassagesV2 = _first(MarkPassages, "spec")
