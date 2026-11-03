"""Planner steps. Each model step is one DSPy signature run through `evidence.steps.Step` (docs/prompt-writing.md):
one task, one typed output, and the hard limits checked in code.

Steps, in order (propose):
  1. lines      question -> 1-5 evidence lines (question, kind, saved template or none)
  2. things     question -> the field and the things the question names
  3. rule       question + lines -> the main-answer rule, from the fixed set RULES (code applies it: lines.py)
  4. decisions  one call per line -> the research-policy choices that line needs (type, value, reason)
  5. query      one call per line -> one SPARQL query. Choices stay in the query as `$name` placeholders (the
                decision's own parameter, or the one named by the template header `# decisions: type=param`); code
                fills them from the plan's decisions at run time (`decision_params`), so "Change" changes what runs.
  6. explain    one call per fresh line -> plain sentences (a template line gets its sentences from the template header)
critic (a separate step that never sees the planner's reasons) flags 1-2 decisions; confirm_all confirms all.

Code checks (`check_plan`): at least one line, decision types in the fixed set, template names exist, things
non-empty, rule in RULES, every query parses. A plan with problems is not ready to run (webapp/evplan.py). The word
writer (W1) and the saved SPARQL templates (W4) are injected: this module imports neither.

The model is the recorded model of `evidence.steps.configure`; that process-global is guarded by `using(lm)`, one
re-entrant lock around configure and every Step call, so two requests never record on each other's model."""
from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Literal

import dspy
import pyoxigraph as ox
from pydantic import BaseModel, Field

from evidence.plan import Decision, EvidenceLine, Plan, WordList
from evidence.steps import Step, configure
from evidence.vocab import EV
from modelcall.dspy_lm import RecordedLM

OVERSELL_ID = "oversell"
MAIN_RULE_ID = "main_rule"
NOT_PLANNED = "could not plan"
DECISION_TYPES = ("must_match", "counts_as", "threshold", "include")
MAX_LINES = 5

# The main-answer rules: name -> what it says. `evidence.planner.lines.apply_rule` applies them.
RULES: dict[str, str] = {
    "any_line": "the answer is yes when any line found evidence",
    "all_lines": "the answer is yes when every line found evidence",
    "majority": "the answer is yes when more than half of the lines found evidence",
}
Rule = Literal["any_line", "all_lines", "majority"]
DEFAULT_THRESHOLD = "0.01"

# The oversell line when no saved template is given: firm "improves" claims the paper's own numbers do not back
# (same meaning as W4's oversell.rq; its choices stay as placeholders, filled from the decisions).
OVERSELL_QUESTION = "Do the authors' conclusions match their numbers?"
OVERSELL_QUERY = """# params: threshold
# decisions: threshold=threshold
# Firm claims the paper's own numbers do not back: a firm claim that a thing improves, where the thing is not better by at least the threshold in any comparison of the paper.
SELECT ?paper ?subject ?direction ?strength WHERE {
  ?claim a ev:Claim ; ev:inPaper ?p ; ev:subject ?subject ; ev:direction ?direction ; ev:strength ?strength .
  ?p ev:name ?paper .
  FILTER(?strength = "firm" && ?direction = "improves")
  FILTER NOT EXISTS {
    ?c a ev:Comparison ; ev:better ?bv ; ev:delta ?d ; ev:inExperiment ?e .
    ?e ev:inPaper ?p .
    ?bv ev:of ?t .
    ?t ev:name ?name .
    FILTER(LCASE(STR(?name)) = LCASE(STR(?subject)) && ABS(?d) >= $threshold)
  }
  $include[?paper]
}
ORDER BY ?paper ?subject"""

Writer = Callable[[str, list[str]], WordList]
_KG = "https://w3id.org/thesis-ev/kg#"
_PREFIXES = {"ev": EV, "kg": _KG, "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
             "rdfs": "http://www.w3.org/2000/01/rdf-schema#", "xsd": "http://www.w3.org/2001/XMLSchema#"}
_SPECIAL = re.compile(r"\$(?:include|must_match|must_match_values)\[[^\]]*\]")
_NAME = re.compile(r"\$(\w+)")
_DIRECTIVE = re.compile(r"^#[ \t]*(params|decisions|after):")
_COMMENT_LINE = re.compile(r"^[ \t]*#.*$", re.MULTILINE)

# ---- the model and its lock ---------------------------------------------------------------------------------------

STEP_LOCK = threading.RLock()


@contextmanager
def using(lm: RecordedLM) -> Iterator[None]:
    """Hold the one lock around `configure(lm)` and the Step calls made inside (Step reads a process-global)."""
    with STEP_LOCK:
        configure(lm)
        yield


# ---- signatures ---------------------------------------------------------------------------------------------------

class Clarification(BaseModel):
    question: str
    options: list[str] = Field(min_length=2, max_length=5)


class LineDraft(BaseModel):
    question: str
    kind: Literal["effect", "inventory", "consistency", "best", "other"]
    template: str | None = None


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


class LinesSig(dspy.Signature):
    """List what would prove or disprove the question from papers: 1 to 5 evidence lines, each one checkable thing
    stated as a question. Start a line from a saved template when one fits (copy its name into `template`);
    otherwise leave `template` null. Do not write queries here.

    Example: question "Does method A beat method B on measure M?" -> [{"question": "Is A better than B on M?",
    "kind": "effect", "template": "effect"}, {"question": "Which papers measured A and B together?",
    "kind": "inventory", "template": null}]"""
    question: str = dspy.InputField(desc="the research question")
    clarifications: str = dspy.InputField(desc="JSON list of {question, answer} the person gave; may be empty")
    templates: str = dspy.InputField(desc="JSON object: saved template name -> what it finds")
    problem: str = dspy.InputField(desc="why the last reply was refused; empty on the first call")
    lines: list[LineDraft] = dspy.OutputField(desc="1 to 5 evidence lines")


class ThingsSig(dspy.Signature):
    """Name the things the question is about and the field it belongs to. `things` are short ids, one per thing
    named in the question (a method, a measure, a dataset). `field` is cs, medicine, materials or other.

    Example: "Does method A beat method B on measure M?" -> field "cs", things ["method_a", "method_b", "measure_m"]"""
    question: str = dspy.InputField(desc="the research question")
    problem: str = dspy.InputField(desc="why the last reply was refused; empty on the first call")
    field: Literal["cs", "medicine", "materials", "other"] = dspy.OutputField()
    things: list[str] = dspy.OutputField(desc="short ids of the things the question names; at least one")


class RuleSig(dspy.Signature):
    """Pick the rule that turns the evidence lines into one answer: any_line (yes when any line found evidence),
    all_lines (yes when every line found evidence) or majority (yes when more than half did).

    Example: a question with one effect line and one caveat line -> any_line"""
    question: str = dspy.InputField(desc="the research question")
    lines: str = dspy.InputField(desc="JSON list of the evidence lines' questions")
    rule: Rule = dspy.OutputField()


class DecisionsSig(dspy.Signature):
    """Name the research-policy choices ONE evidence line needs, from these types only: must_match (what settings
    two experiments must share to be compared), counts_as (what counts as the thing asked about, or the unit
    counted), threshold (the smallest difference that matters), include (which papers to include, or "all").
    Give each with a value and a one-sentence reason. Give none the line does not need.

    Example: line "Is A better than B on M?" -> [{"type": "threshold", "value": "0.01", "reason": "smaller gaps are
    within noise"}, {"type": "include", "value": "all", "reason": "the corpus is small"}]"""
    question: str = dspy.InputField(desc="the research question")
    line: str = dspy.InputField(desc="the evidence line's question")
    template_help: str = dspy.InputField(desc="what the line's saved template finds, with its parameters; may be empty")
    decisions: list[DecisionDraft] = dspy.OutputField(desc="the choices this line needs")


class QuerySig(dspy.Signature):
    """Write ONE SPARQL query for the evidence line over the evidence graph (prefixes ev: and kg: are added; classes
    ev:Experiment, ev:Claim, ev:Link, ev:Metric, ev:Value, ev:Comparison). Where a choice belongs (a threshold, the
    papers to include), write its placeholder from `choice_params` (for example $threshold) instead of a value.
    When `template` is given, adapt it: keep its structure, fill every `$name` that is NOT in `choice_params` with a
    literal value for this question, and leave the placeholders in `choice_params` and `$include[...]` as they are.
    Do not write comment lines. Return only the query.

    Example: choice_params ["threshold"], line "Is A better than B on M?" -> SELECT ?paper WHERE { ?c a ev:Comparison ;
    ev:delta ?d . FILTER(ABS(?d) >= $threshold) }"""
    question: str = dspy.InputField(desc="the research question")
    line: str = dspy.InputField(desc="the evidence line's question")
    template: str = dspy.InputField(desc="the saved template's text, or empty for a new query")
    choice_params: str = dspy.InputField(desc="JSON list of the placeholder names the decisions fill")
    problem: str = dspy.InputField(desc="why the last query was refused (parser message); empty on the first call")
    query: str = dspy.OutputField(desc="the SPARQL query")


class ExplainSig(dspy.Signature):
    """Explain in 2 to 4 short plain sentences what the SPARQL query looks for, for a reader who does not know
    SPARQL. Name the kind of record and the condition. Do not write code, variable names or prefixes.

    Example: query "SELECT ?paper WHERE { ?c a ev:Comparison ; ev:delta ?d . FILTER(ABS(?d) >= $threshold) }" ->
    ["It looks at every comparison between two things in the papers.", "It keeps those where the difference is at
    least your threshold."]"""
    query: str = dspy.InputField(desc="the SPARQL query")
    sentences: list[str] = dspy.OutputField(desc="2 to 4 plain sentences, no code")


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
_lines = Step(LinesSig, "planner_lines")
_things = Step(ThingsSig, "planner_things")
_rule = Step(RuleSig, "planner_rule")
_decisions = Step(DecisionsSig, "planner_decisions")
_query = Step(QuerySig, "planner_query")
_explain = Step(ExplainSig, "planner_explain")
_critic = Step(CriticSig, "planner_critic")


# ---- queries: placeholders, parsing, binding ------------------------------------------------------------------------

def decision_map(query: str) -> dict[str, str]:
    """Which parameter each decision type fills (`# decisions: threshold=min_effect`); a type not listed fills the
    parameter of its own name."""
    m = re.search(r"^#[ \t]*decisions:[ \t]*(.*)$", query, re.MULTILINE)
    named = dict(x.split("=", 1) for x in (m.group(1).split(",") if m else []) if "=" in x)
    named = {a.strip(): b.strip() for a, b in named.items()}
    return {t: named.get(t, t) for t in DECISION_TYPES}


def _value(raw: Any) -> Any:
    """A decision's value as the query needs it: numbers and JSON lists parsed, other text kept."""
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def decision_params(plan: Plan, query: str) -> dict[str, Any]:
    """The parameters the run passes with `query`: each placeholder the query holds, filled from the plan's decision
    of that type (the first one, never the main-answer rule). The plan's current values are used, so a changed
    decision changes what runs. `include` of "all" (or empty) is left out: no filter."""
    out: dict[str, Any] = {}
    for kind, param in decision_map(query).items():
        d = next((x for x in plan.decisions if x.type == kind and x.id != MAIN_RULE_ID), None)
        if d is None:
            continue
        value = _value(d.value)
        if kind == "include":
            if value not in ("all", "", None):
                out["include"] = value if isinstance(value, list) else [value]
        else:
            out[param] = value
    return out


def _directives(template: str) -> list[str]:
    return [line for line in template.splitlines() if _DIRECTIVE.match(line)]


def with_header(body: str, template: str | None) -> str:
    """`body` with the template's header directives in front (kept in code, not written by the model): `# params:`
    lists only the parameters still left in the query, which the run must pass."""
    if not template:
        return body
    body = _COMMENT_LINE.sub("", body).strip()
    head = []
    for line in _directives(template):
        m = re.match(r"^#[ \t]*params:[ \t]*(.*)$", line)
        if m:
            left = [p.strip() for p in m.group(1).split(",") if p.strip() and f"${p.strip()}" in body]
            if left:
                head.append(f"# params: {', '.join(left)}")
        else:
            head.append(line)
    return "\n".join([*head, body])


def _unfilled(query: str) -> list[str]:
    """`$name` placeholders that no decision fills: they would be free variables matching everything."""
    ok = set(decision_map(query).values()) | set(DECISION_TYPES)
    body = _SPECIAL.sub("", _COMMENT_LINE.sub("", query))
    return sorted({n for n in _NAME.findall(body) if n not in ok})


def query_problem(query: str) -> str | None:
    """Why the query is refused, or None: it must parse (pyoxigraph, placeholders replaced) and hold no placeholder
    that a decision does not fill."""
    if not query.strip():
        return "the query is empty"
    left = _unfilled(query)
    if left:
        return f"these $placeholders have no value: {left}; write a literal value for them"
    body = _SPECIAL.sub("", _COMMENT_LINE.sub("", query))
    body = _NAME.sub('"x"', body)
    head = "".join(f"PREFIX {p}: <{u}>\n" for p, u in _PREFIXES.items())
    try:
        ox.Store().query(head + body)
    except Exception as exc:  # noqa: BLE001 - pyoxigraph raises SyntaxError and others
        return str(exc)[:500]
    return None


def check_plan(plan: Plan, templates: Mapping[str, str] | None = None) -> list[str]:
    """What is wrong with the plan, checked in code; a plan with problems is not ready to run."""
    problems = []
    if not plan.lines:
        problems.append("the plan has no evidence line")
    if len(plan.lines) > MAX_LINES + 1:
        problems.append(f"the plan has more than {MAX_LINES} evidence lines")
    problems += [f"decision {d.id} has the unknown type {d.type!r}" for d in plan.decisions if d.type not in DECISION_TYPES]
    if templates is not None:
        problems += [f"line {x.id} names the unknown template {x.template!r}" for x in plan.lines
                     if x.template and x.template not in templates]
    if not plan.words.things:
        problems.append("the plan names no thing the question is about")
    if plan.main_rule not in RULES:
        problems.append(f"the main-answer rule {plan.main_rule!r} is not one of {sorted(RULES)}")
    for x in plan.lines:
        if x.query:
            why = query_problem(x.query)
            if why:
                problems.append(f"line {x.id}: {why}")
    return problems


# ---- plain sentences for the "how?" of a line ------------------------------------------------------------------------

LABELS = {"must_match": "must-match", "counts_as": "counts-as", "threshold": "threshold", "include": "include"}


def prose(template: str) -> str:
    """The template's header comment as text (its directive lines left out)."""
    lines = [m.lstrip("# \t").strip() for m in template.splitlines()
             if m.lstrip().startswith("#") and not _DIRECTIVE.match(m)]
    return " ".join(x for x in lines if x)


def _used_choices(plan: Plan, query: str) -> list[tuple[str, Any]]:
    wanted = set(_NAME.findall(_COMMENT_LINE.sub("", query))) | ({"include"} if "$include[" in query else set())
    values = decision_params(plan, query)
    return [(k, values[p]) for k, p in decision_map(query).items() if p in wanted and p in values]


def how_sentences(line: EvidenceLine, plan: Plan, template: str | None, fresh: list[str] | None = None) -> list[str]:
    """Plain sentences for a line, never code: a template line from its template's header (or the oversell line's
    own header), a new query from the explain step's sentences; then the plan's choices the line uses."""
    source = template or (line.query if line.id == OVERSELL_ID else "")
    if source:
        values = decision_params(plan, line.query)
        pieces = [s.strip() for s in re.split(r"(?<=[.:])\s+", prose(source)) if s.strip()]
        out = [_NAME.sub(lambda m: str(values.get(m.group(1), "the chosen value")), s).rstrip(".") + "."
               for s in pieces if not s.startswith("Params")]
    else:
        out = list(fresh or []) or ["This question was written for this plan; it has no explanation yet."]
    for kind, value in _used_choices(plan, line.query):
        out.append(f"It uses your {LABELS[kind]} choice: {value if isinstance(value, str) else json.dumps(value)}.")
    return out


# ---- steps ------------------------------------------------------------------------------------------------------------

def clarify(question: str) -> list[dict[str, Any]]:
    """0 to 2 multiple-choice questions ({question, options}); more than 2 are cut to the first 2."""
    out = _clarify(question=question).clarifications or []
    return [c.model_dump() if isinstance(c, BaseModel) else dict(c) for c in out[:2]]


def _help(name: str, text: str) -> str:
    return prose(text)[:200] or name


def _line_drafts(question: str, clar: list[dict[str, str]], templates: Mapping[str, str]) -> list[LineDraft]:
    shown = json.dumps({n: _help(n, t) for n, t in templates.items()})
    problem = ""
    drafts: list[LineDraft] = []
    for _ in range(2):
        drafts = list(_lines(question=question, clarifications=json.dumps(clar), templates=shown, problem=problem).lines)
        unknown = sorted({d.template for d in drafts if d.template and d.template not in templates})
        if drafts and not unknown:
            break
        problem = ("you gave no line; give 1 to 5" if not drafts else
                   f"these template names do not exist: {unknown}; use one of {sorted(templates)} or null")
    else:  # still wrong after the retry: an unknown template becomes a new query
        drafts = [d.model_copy(update={"template": d.template if d.template in templates else None}) for d in drafts]
    return drafts[:MAX_LINES]


def _things_of(question: str) -> tuple[str, list[str]]:
    problem = ""
    for _ in range(2):
        out = _things(question=question, problem=problem)
        things = [t.strip() for t in out.things if t.strip()]
        if things:
            return out.field, things
        problem = "you named no thing; name at least one"
    return out.field, []


def _query_for(question: str, line: LineDraft, template: str | None, choices: list[str]) -> str | None:
    """The line's query, checked in code: on a problem one repair call with the message; still wrong: None."""
    problem = ""
    for _ in range(2):
        body = _query(question=question, line=line.question, template=template or "",
                      choice_params=json.dumps(choices), problem=problem).query
        query = with_header(body, template)
        why = query_problem(query)
        if why is None:
            return query
        problem = why
    return None


def propose(question: str, clarifications: list[Mapping[str, str]] | None = None, *,
            write_words: Writer, templates: Mapping[str, str] | None = None,
            explain: bool = True) -> tuple[Plan, dict[str, list[str]]]:
    """(the plan, the sentences for each fresh line's "how?"). `write_words(question, things)` is W1's word writer
    (the caller binds its `lm`); `templates` maps a saved SPARQL template's name to its text (W4)."""
    clar = [dict(c) for c in clarifications or []]
    templates = dict(templates or {})
    drafts = _line_drafts(question, clar, templates)
    field, things = _things_of(question)
    rule = _rule(question=question, lines=json.dumps([d.question for d in drafts])).rule if drafts else "any_line"
    if rule not in RULES:
        rule = "any_line"

    decisions: list[Decision] = []
    for d in drafts:
        text = templates.get(d.template or "", "")
        for draft in _decisions(question=question, line=d.question, template_help=_help(d.template or "", text)).decisions:
            if draft.type in DECISION_TYPES and all(x.type != draft.type for x in decisions):
                decisions.append(Decision(id=f"d{len(decisions) + 1}", type=draft.type, value=draft.value,
                                          reason=draft.reason))
    oversell = any(d.kind in ("effect", "consistency") for d in drafts)
    if oversell and all(x.type != "threshold" for x in decisions):
        decisions.append(Decision(id=f"d{len(decisions) + 1}", type="threshold", value=DEFAULT_THRESHOLD,
                                  reason="default: a difference smaller than this does not count as better"))
    decisions.append(Decision(id=MAIN_RULE_ID, type="counts_as", value=rule,
                              reason=f"how the lines add up to one answer ({RULES[rule]})"))

    empty = WordList(things={}, cues=[], written_by="none", ontology_names={})
    lines: list[EvidenceLine] = []
    how: dict[str, list[str]] = {}
    for i, d in enumerate(drafts, 1):
        template = templates.get(d.template) if d.template else None
        choices = sorted(set(decision_map(template or "").values()) | set(DECISION_TYPES))
        query = _query_for(question, d, template, choices)
        lid = f"l{i}"
        lines.append(EvidenceLine(id=lid, question=d.question if query else f"{d.question} ({NOT_PLANNED})",
                                  query=query or "", template=d.template))
        if query and explain and not d.template:
            how[lid] = [s.strip() for s in _explain(query=query).sentences if s.strip()][:4]
    if oversell:
        text = templates.get(OVERSELL_ID)
        query = text if text else OVERSELL_QUERY
        if query_problem(query) is None:
            lines.append(EvidenceLine(id=OVERSELL_ID, question=OVERSELL_QUESTION, query=query,
                                      template=OVERSELL_ID if text else None, removable=False))
    words = write_words(question, things) if things else empty
    plan = Plan(question=question, field=field, lines=lines, main_rule=rule, words=words, decisions=decisions,
                clarifications=clar)
    return plan, how


def critic(plan: Plan, *, record: Callable[[dict[str, str]], None] | None = None) -> Plan:
    """Flag 1-2 decisions. The critic sees the lines and each decision's type and value, never the planner's
    reasons. Duplicate ids are merged; wrong counts (0 or over 2) are refused and asked once more; then clamped to 2,
    the dropped flags (and a still-empty answer) passed to `record`."""
    ids = {d.id for d in plan.decisions}
    if not ids:
        return plan
    shown = {"question": plan.question, "lines": json.dumps([line.question for line in plan.lines]),
             "decisions": json.dumps([{"id": d.id, "type": d.type, "value": d.value} for d in plan.decisions])}
    problem = ""
    flags: list[Flag] = []
    for _ in range(2):
        seen: dict[str, Flag] = {}
        for f in _critic(**shown, problem=problem).flags:
            if f.decision_id in ids:
                seen.setdefault(f.decision_id, f)
        flags = list(seen.values())
        if 1 <= len(flags) <= 2:
            break
        problem = f"you gave {len(flags)} valid flags; give 1 or 2, using these ids: {sorted(ids)}"
    kept, dropped = flags[:2], flags[2:]
    if record is not None:
        for f in dropped:
            record({"decision_id": f.decision_id, "reason": f.reason})
        if not kept:
            record({"decision_id": "", "reason": "the critic flagged nothing after a retry"})
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


def set_rule(plan: Plan, rule: str, who: str) -> Plan:
    """Change the main-answer rule (one of RULES): the plan's rule and its decision row, confirmed by `who`."""
    if rule not in RULES:
        raise ValueError(f"the main-answer rule is one of {sorted(RULES)}, not {rule!r}")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return plan.model_copy(update={"main_rule": rule, "decisions": [
        d.model_copy(update={"value": rule, "confirmed_by": who, "confirmed_at": now}) if d.id == MAIN_RULE_ID else d
        for d in plan.decisions]})
