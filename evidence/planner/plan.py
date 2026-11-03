"""Planner steps. Each is one DSPy signature run through `evidence.steps.Step` (docs/prompt-writing.md): one task,
typed output, validated in code.

- clarify(question): 0-2 multiple-choice questions, only when the question is ambiguous.
- propose(question, clarifications): "what would prove it?" evidence lines (each a SPARQL query started from a saved
  template), the four decision types with reasons, the main-answer rule, the field and the word list. Queries are
  parsed by rdflib; a query that does not parse gets ONE repair call with the parser error, and a line that still
  fails is kept as "could not plan" (empty query) so the person sees it. A plan with an effect or consistency line
  also gets the oversell line, which cannot be removed.
- critic(plan): a separate step that sees the lines and the decisions' values but not the planner's reasons; it flags
  1-2 decisions it doubts. A reply with 0 or more than 2 flags is refused and asked again once; still wrong, it is
  clamped to 2 and the rest are dropped and recorded (`record`).
- confirm_all(plan, who): confirms every decision, flagged ones included.

The word writer (W1) and the saved SPARQL templates (W4) are injected as arguments: this module imports neither."""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any, Literal

import dspy
from pydantic import BaseModel, Field
from rdflib.plugins.sparql import prepareQuery

from evidence.plan import Decision, EvidenceLine, Plan, WordList
from evidence.steps import Step
from evidence.vocab import EV

OVERSELL_ID = "oversell"
NOT_PLANNED = "could not plan"
DEFAULT_MAIN_RULE = "answer from the lines that found evidence; say which lines found none"
OVERSELL_QUERY = 'SELECT ?claim ?paper WHERE { ?claim a ev:Claim ; ev:inPaper ?paper ; ev:strength "hedged" . }'
OVERSELL_QUESTION = "Do authors claim more than their numbers show (hedged or unsupported claims)?"
Writer = Callable[..., WordList]


class Clarification(BaseModel):
    question: str
    options: list[str] = Field(min_length=2, max_length=5)


class LineDraft(BaseModel):
    question: str
    kind: Literal["effect", "inventory", "consistency", "best", "other"]
    template: str | None = None
    query: str


class DecisionDraft(BaseModel):
    type: Literal["must_match", "counts_as", "threshold", "include"]
    value: str
    reason: str


class Flag(BaseModel):
    decision_id: str
    reason: str


class ClarifySig(dspy.Signature):
    """Decide whether a research question is too ambiguous to plan. Ask 0 to 2 multiple-choice questions, only
    about what the question leaves open (which systems, which measure, which field). Return an empty list when the
    question is clear. Each question has 2 to 5 short options.

    Example: "Is it better?" -> [{"question": "Better at what?", "options": ["accuracy", "speed", "cost"]}]
    Example: "Does method A beat method B on measure M?" -> []"""
    question: str = dspy.InputField(desc="the research question")
    clarifications: list[Clarification] = dspy.OutputField(desc="0 to 2 multiple-choice questions")


class ProposeSig(dspy.Signature):
    """Plan what would prove or disprove the question from papers. Give 1 to 5 evidence lines: each asks one
    checkable thing and carries one SPARQL query over the evidence graph (prefix ev:, classes ev:Experiment,
    ev:Claim, ev:Link, ev:Metric). Start from a saved template when one fits (its name goes in `template`, the
    query is the template adapted); otherwise leave `template` null. Give one decision per type that matters:
    must_match (what an experiment must share to be compared), counts_as (what counts as the thing asked about),
    threshold (the smallest effect that matters) and include (which papers or results to include), each with a
    one-sentence reason. Give the main-answer rule as one sentence, the field (cs, medicine, materials or other)
    and the things the question names (short ids, e.g. "method_a", "measure_m").

    Example output (shape only): lines=[{"question": "Does method A beat method B on M?", "kind": "effect",
    "template": "effect", "query": "SELECT ?c WHERE {...}"}], decisions=[{"type": "threshold", "value": "0.01",
    "reason": "smaller gaps are within noise"}]"""
    question: str = dspy.InputField(desc="the research question")
    clarifications: str = dspy.InputField(desc="JSON list of {question, answer} the person gave; may be empty")
    templates: str = dspy.InputField(desc="JSON object: saved template name -> its SPARQL text")
    field: Literal["cs", "medicine", "materials", "other"] = dspy.OutputField()
    lines: list[LineDraft] = dspy.OutputField(desc="1 to 5 evidence lines")
    decisions: list[DecisionDraft] = dspy.OutputField(desc="the planner's defaults, with reasons")
    main_rule: str = dspy.OutputField(desc="one sentence: how the answer is made from the lines")
    things: list[str] = dspy.OutputField(desc="short ids of the things the question names")


class RepairSig(dspy.Signature):
    """Fix one SPARQL query so that it parses. Keep its meaning. Return only the corrected query."""
    query: str = dspy.InputField(desc="the query that failed to parse")
    error: str = dspy.InputField(desc="the parser's message")
    fixed_query: str = dspy.OutputField(desc="the corrected SPARQL query")


class CriticSig(dspy.Signature):
    """You review the choices of a research plan you did not write. Pick the 1 or 2 decisions you doubt most (not
    more, not none) and say in one sentence why each could be wrong. Use the decision ids exactly as given.

    Example: [{"decision_id": "d2", "reason": "a 0.01 threshold may hide real gains on a 0-100 scale"}]"""
    question: str = dspy.InputField()
    lines: str = dspy.InputField(desc="JSON list of the evidence lines' questions")
    decisions: str = dspy.InputField(desc="JSON list of {id, type, value}")
    problem: str = dspy.InputField(desc="why the last reply was refused; empty on the first call")
    flags: list[Flag] = dspy.OutputField(desc="1 or 2 flagged decisions")


_clarify = Step(ClarifySig, "planner_clarify")
_propose = Step(ProposeSig, "planner_propose")
_repair = Step(RepairSig, "planner_repair")
_critic = Step(CriticSig, "planner_critic")


def clarify(question: str) -> list[dict[str, Any]]:
    """0 to 2 multiple-choice questions ({question, options}); more than 2 are cut to the first 2."""
    out = _clarify(question=question).clarifications or []
    return [c.model_dump() if isinstance(c, BaseModel) else dict(c) for c in out[:2]]


def _parse_error(query: str) -> str | None:
    try:
        prepareQuery(query, initNs={"ev": EV})
    except Exception as exc:  # rdflib raises several parser exception types
        return str(exc)[:500]
    return None


def _checked_query(query: str) -> str | None:
    """The query when it parses; else one repair call, then None."""
    error = _parse_error(query)
    if error is None:
        return query
    fixed = _repair(query=query, error=error).fixed_query
    return fixed if _parse_error(fixed) is None else None


def propose(question: str, clarifications: list[Mapping[str, str]] | None = None, *,
            write_words: Writer, templates: Mapping[str, str] | None = None) -> Plan:
    """The plan for `question`. `write_words(question, things)` is W1's word writer; `templates` maps a saved
    SPARQL template's name to its text (W4)."""
    clar = [dict(c) for c in clarifications or []]
    templates = dict(templates or {})
    reply = _propose(question=question, clarifications=json.dumps(clar), templates=json.dumps(templates))
    lines: list[EvidenceLine] = []
    for i, draft in enumerate(reply.lines, 1):
        query = _checked_query(draft.query)
        text = draft.question if query is not None else f"{draft.question} ({NOT_PLANNED})"
        lines.append(EvidenceLine(id=f"l{i}", question=text, query=query or "", template=draft.template))
    if any(d.kind in ("effect", "consistency") for d in reply.lines):
        lines.append(EvidenceLine(id=OVERSELL_ID, question=OVERSELL_QUESTION,
                                  query=templates.get(OVERSELL_ID, OVERSELL_QUERY), template=OVERSELL_ID,
                                  removable=False))
    decisions = [Decision(id=f"d{i}", type=d.type, value=d.value, reason=d.reason)
                 for i, d in enumerate(reply.decisions, 1)]
    words = write_words(question, list(reply.things))
    return Plan(question=question, field=reply.field, lines=lines, main_rule=reply.main_rule or DEFAULT_MAIN_RULE,
                words=words, decisions=decisions, clarifications=clar)


def critic(plan: Plan, *, record: Callable[[dict[str, str]], None] | None = None) -> Plan:
    """Flag 1-2 decisions. The critic sees the lines and each decision's type and value, never the planner's
    reasons. Wrong counts (0 or over 2) are refused and asked once more; then clamped to 2, the dropped flags
    passed to `record`."""
    ids = {d.id for d in plan.decisions}
    if not ids:
        return plan
    shown = {"question": plan.question, "lines": json.dumps([line.question for line in plan.lines]),
             "decisions": json.dumps([{"id": d.id, "type": d.type, "value": d.value} for d in plan.decisions])}
    problem = ""
    flags: list[Flag] = []
    for _ in range(2):
        flags = [f for f in _critic(**shown, problem=problem).flags if f.decision_id in ids]
        if 1 <= len(flags) <= 2:
            break
        problem = f"you gave {len(flags)} valid flags; give 1 or 2, using these ids: {sorted(ids)}"
    kept, dropped = flags[:2], flags[2:]
    if record is not None:
        for f in dropped:
            record({"decision_id": f.decision_id, "reason": f.reason})
    why = {f.decision_id: f.reason for f in kept}
    return plan.model_copy(update={"decisions": [
        d.model_copy(update={"flagged": True, "flag_reason": why[d.id]}) if d.id in why else d
        for d in plan.decisions]})


def confirm_all(plan: Plan, who: str) -> Plan:
    """Confirm every decision (flagged ones too), stamped with `who` and the time."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return plan.model_copy(update={"decisions": [
        d if d.confirmed_by else d.model_copy(update={"confirmed_by": who, "confirmed_at": now})
        for d in plan.decisions]})
