"""Spec step: the independent advisor. From the question text, the model's general knowledge and the user's answers
(benchmark: the intent card) it builds and locks the Spec. It never sees papers.

Steps (each LLM task is one Signature in prompts.py; code checks every output):
  1. skeleton   LLM splits the question; code keeps only parts that are substrings of the question
  1b. type      LLM names the question type from the question text alone (lookup | effect | best | trend | list;
                the dataset's own type field is never read); code checks it fits the skeleton (best: two options,
                effect: a second option, a measure unless list), one repair call per failed check. Then code shapes
                the skeleton: effect with a drug as comparator -> subjects [A, B] and no comparator (so Find and
                Extract fetch both drugs' rows); trend -> trend_by (dose when the question says dose, else time point)
                is never fixed and is always an "all" column.
  2. open points = the standard list minus what the question fixes (and minus the dose when doses are compared)
  3. gate       does the model know each name? unknown names get no synonyms
  4. names      known names: synonyms (generated, then checked by a second call) and a one-line definition
  5. dialogue   at most 3 questions to the user; unasked points take the default ("all" for table points)
  6. columns    table points answered "all"; best and effect questions: higher_is_better; best: best_by
Unknown names (gate says unknown) get no synonyms and no definition: the advisor never makes up who a name is.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

import dspy

from evqa.contracts import Name, OpenPoint, RunConfig, Spec
from evqa.llm import service_failed
from evqa.lm import make_lm
from evqa.spec import prompts as P
from evqa.spec.dimensions_v3 import ReadQuestionCore, select as select_dimensions

log = logging.getLogger(__name__)

# the standard open points, in asking-table order; the table points become answer columns when answered "all"
TABLE_POINTS = ("dose", "time_point", "patient_group")
POINTS = (*TABLE_POINTS, "measure_variant", "other_names")
ASK = {"dose": "Which dose do you mean?",
       "time_point": "Which time point do you mean?",
       "patient_group": "Which patients do you mean?",
       "measure_variant": "How should the change in {measure} be measured?",
       "other_names": "I do not know {unknown}. Do you know other names for {it}?"}
MAX_QUESTIONS = 3
ASK_ORDER = ("other_names", "measure_variant", *TABLE_POINTS)   # what the advisor cannot guess goes first
MAX_SYNONYMS = 8
ATTEMPTS = 3
DOSE_RE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|µg|g|ml|mL|IU)\b")
TIME_RE = re.compile(r"\b\d+\s?(?:weeks?|wk|months?|days?|years?)\b", re.IGNORECASE)
# "aged 65 years or older", "18 years of age", "over 2 years old": an age, never a time point
AGE_BEFORE_RE = re.compile(r"\b(?:aged?|ages|over|under|older than|younger than|at least|≥|>=|<=|≤)\s*$", re.IGNORECASE)
AGE_AFTER_RE = re.compile(r"^\s*(?:or (?:older|over|more|above|younger|under|less)|and (?:older|over|above)|old\b|of age"
                          r"|of older|-old|\+)", re.IGNORECASE)
ALL_RE = re.compile(r"\b(?:every|all)\b", re.IGNORECASE)
DOSE_WORD_RE = re.compile(r"\bdos(?:e|es|age|ages|ing)\b", re.IGNORECASE)
# a comparator that is a control, not a second drug (effect questions keep it as the comparator)
CONTROL_RE = re.compile(r"\b(?:placebo|controls?|usual care|standard (?:of )?care|no treatment|untreated|vehicle|sham"
                        r"|nothing)\b", re.IGNORECASE)

AskUser = Callable[[str, str], str | None]    # (point id, question text) -> the user's answer, None = no answer


class SpecError(ValueError):
    pass


# ---------------------------------------------------------------- llm helper
def _predict(sig: type[dspy.Signature], **inputs: Any) -> dspy.Prediction:
    """One Predict call under the current dspy.context. A reply that does not parse (or is empty: a reasoning loop
    that used up the tokens) is asked again, up to ATTEMPTS; each retry is a new recorded call that samples
    (evqa.lm), and the bad reply stays in the cache. The last failure is raised."""
    for attempt in range(ATTEMPTS):
        try:
            return dspy.Predict(sig)(**inputs, config={"attempt": attempt} if attempt else {})
        except Exception as e:   # noqa: BLE001 - DSPy raises several parse error types
            if attempt == ATTEMPTS - 1 or service_failed(e):
                raise
            log.warning("spec: %s attempt %d did not parse (%s); asking again", sig.__name__, attempt,
                        str(e).splitlines()[0])
    raise AssertionError("unreachable")


BACKGROUND_RE = r"\b(?:on|tak(?:e|es|ing)|receiv(?:e|es|ing)|treated with|already on|added to|using)\s+(?:background\s+)?"


def background_span(name: str, question: str) -> tuple[int, int] | None:
    """When every mention of `name` in the question is a background therapy ('who are taking metformin', 'on
    insulin'), the span of the last such phrase; else None (the name is asked about)."""
    mentions = list(re.finditer(rf"(?<![a-z0-9]){re.escape(name.lower())}(?![a-z0-9])", question.lower()))
    phrases = list(re.finditer(BACKGROUND_RE + rf"{re.escape(name.lower())}(?![a-z0-9])", question.lower()))
    if not mentions or len(phrases) != len(mentions):
        return None
    return phrases[-1].start(), phrases[-1].end()


def is_age(question: str, start: int, end: int) -> bool:
    """Is question[start:end] (e.g. '65 years') an age rather than a time point?"""
    return bool(AGE_BEFORE_RE.search(question[:start]) or AGE_AFTER_RE.match(question[end:]))


def _in_question(part: str, question: str) -> str | None:
    """The question's own spelling of `part`, or None when `part` is not a substring of the question."""
    part = (part or "").strip().strip('"').strip()
    if not part:
        return None
    i = question.lower().find(part.lower())
    return question[i:i + len(part)] if i >= 0 else None


# ---------------------------------------------------------------- 1. skeleton
def skeleton(question: str) -> dict[str, Any]:
    """{subjects, comparator, measure, fixed}: LLM parse, then code keeps only substrings of the question and fills
    a missed dose or time from a regex."""
    out = _predict(P.ReadQuestion, question=question)
    subjects: list[str] = []
    for s in out.subjects or []:
        got = _in_question(str(s), question)
        if got is None:
            log.warning("spec: dropped subject %r: not in the question", s)
        elif got.lower() not in {x.lower() for x in subjects}:
            subjects.append(got)
    measure = _in_question(out.measure, question)
    if not subjects and measure is None:
        raise SpecError(f"could not read a subject or a measure from {question!r}: {out}")
    comparator = _in_question(out.comparator, question)
    fixed: dict[str, str] = {}
    for slot in TABLE_POINTS:
        got = _in_question(getattr(out, slot), question)
        if slot == "dose" and got is not None and not re.search(r"\d", got):
            log.warning("spec: dropped dose %r: no amount", got)   # "which brenoxalin dose" names no dose
            got = None
        if slot == "time_point" and got is not None:
            i = question.find(got)
            if i >= 0 and is_age(question, i, i + len(got)):
                log.warning("spec: dropped time point %r: it is an age", got)
                got = None
        if got is not None:
            fixed[slot] = got
        elif getattr(out, slot):
            log.warning("spec: dropped %s %r: not in the question", slot, getattr(out, slot))
    for subj in list(subjects):                         # a background therapy is part of the patients, not asked
        span = background_span(subj, question)
        if span is None:
            continue
        subjects.remove(subj)
        log.warning("spec: dropped subject %r: a background therapy of the patients", subj)
        group = fixed.get("patient_group")
        gi = question.lower().find(group.lower()) if group else -1
        if gi >= 0 and 0 <= span[0] - (gi + len(group)) <= 30:   # '... with type 2 diabetes who are taking X'
            fixed["patient_group"] = question[gi:span[1]]
        elif group is None:
            fixed["patient_group"] = question[span[0]:span[1]]
    if not subjects and measure is None:
        raise SpecError(f"could not read a subject or a measure from {question!r}")
    for slot, rx in (("dose", DOSE_RE), ("time_point", TIME_RE)):
        if slot in fixed:
            continue
        m = next((m for m in rx.finditer(question)
                  if not (slot == "time_point" and is_age(question, m.start(), m.end()))), None)
        if m:
            fixed[slot] = m.group(0)
    return {"subjects": subjects, "comparator": comparator, "measure": measure, "fixed": fixed}


# ---------------------------------------------------------------- 1b. type
def type_problem(qtype: str, sk: dict[str, Any], question: str) -> str:
    """'' when the type fits the skeleton, else the failed check in plain words."""
    if qtype not in P.QUESTION_TYPES:
        return f"type {qtype!r} is not one of {', '.join(P.QUESTION_TYPES)}"
    if qtype != "list" and sk["measure"] is None:
        return f"a {qtype} question needs a measure, and the question names none; only a list question has none"
    if qtype != "list" and not sk["subjects"]:
        return f"a {qtype} question needs a drug, and the question names none; only a list question has none"
    if qtype == "best" and len(sk["subjects"]) < 2 and not DOSE_WORD_RE.search(question):
        return "a best question chooses among two or more drugs or doses; the question names one drug and no doses"
    if qtype == "effect" and len(sk["subjects"]) < 2 and not sk["comparator"]:
        return "an effect question compares with a second drug or a control; the question names neither"
    return ""


def question_type(question: str, sk: dict[str, Any]) -> str:
    """ClassifyQuestion with code checks; a rejected reply gets a repair call with the failed check (ATTEMPTS)."""
    feedback, why = "", ""
    for _ in range(ATTEMPTS):
        out = _predict(P.ClassifyQuestion, question=question, feedback=feedback)
        qtype = str(out.type or "").strip().strip('"').lower()
        why = type_problem(qtype, sk, question)
        if not why:
            return qtype
        log.warning("spec: type %r rejected: %s", qtype, why)
        feedback = f'Rejected reply: type "{qtype}". Failed check: {why}. Reply with another type.'
    raise SpecError(f"no accepted question type for {question!r}: {why}")


def shape(qtype: str, sk: dict[str, Any], question: str) -> tuple[dict[str, Any], str | None]:
    """The skeleton made fit for the type (module doc, step 1b), and trend_by."""
    sk = {**sk, "subjects": list(sk["subjects"]), "fixed": dict(sk["fixed"])}
    if qtype == "effect":
        if len(sk["subjects"]) == 1 and sk["comparator"] and not CONTROL_RE.search(sk["comparator"]):
            sk["subjects"].append(sk["comparator"])          # B is a drug: fetch its own rows too
            sk["comparator"] = None
        if len(sk["subjects"]) > 2:
            log.warning("spec: effect question with %d drugs; the first two are compared", len(sk["subjects"]))
            sk["subjects"] = sk["subjects"][:2]
    trend_by = None
    if qtype == "trend":
        trend_by = "dose" if DOSE_WORD_RE.search(question) else "time_point"
        if trend_by in sk["fixed"]:
            log.warning("spec: trend over %s: dropped the fixed %r", trend_by, sk["fixed"].pop(trend_by))
    return sk, trend_by


def best_by(qtype: str, subjects: list[str], question: str) -> str | None:
    """What a best question compares: its subjects (two or more), or the doses of its one subject."""
    if qtype != "best":
        return None
    if len(subjects) >= 2:
        return "subject"
    if DOSE_WORD_RE.search(question):
        return "dose"
    raise SpecError(f"best question with one subject and no dose to compare: {question!r}")


# ---------------------------------------------------------------- 3 + 4. names
def _clean(names: list[Any], label: str) -> list[str]:
    seen, out = {label.lower()}, []
    for n in names or []:
        n = str(n).strip()
        if n and len(n) <= 60 and n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out[:MAX_SYNONYMS]


def name(label: str, role: str, question: str, check_lm: dspy.BaseLM) -> Name:
    """Familiarity gate, then (known names only) synonyms checked by a second call, and the one-line definition.
    An empty label (a list question that names no measure) is no name: no call, known False."""
    if not label:
        return Name(label="", known=False)
    gate = _predict(P.KnowName, name=label, role=role, question=question)
    definition = (gate.definition or "").strip()
    known = gate.known is True and bool(definition)   # a "known" name the model cannot define counts as unknown
    if not known:
        return Name(label=label, known=False)
    cands = _clean(_predict(P.OtherNames, name=label, definition=definition).synonyms, label)
    synonyms = cands
    if cands:
        with dspy.context(lm=check_lm):
            same = _predict(P.CheckNames, name=label, definition=definition, candidates=cands).same
        if isinstance(same, list) and len(same) == len(cands) and all(isinstance(x, bool) for x in same):
            synonyms = [c for c, ok in zip(cands, same, strict=True) if ok]
        else:
            log.warning("spec: synonym check for %r gave %r for %d candidates; keeping none", label, same, len(cands))
            synonyms = []
    return Name(label=label, synonyms=synonyms, definition=definition, known=True)


def user_names(label: str, answer: str) -> list[str]:
    """Names the user's answer gives for `label`, kept only when copied from the answer."""
    if not answer.strip():
        return []
    got = _predict(P.ReadUserNames, name=label, answer=answer).names or []
    return _clean([n for n in got if _in_question(str(n), answer)], label)


# ---------------------------------------------------------------- 5. dialogue
def _answers_from_card(question: dict[str, Any]) -> AskUser:
    card = {c["point"]: c.get("answer", "") for c in question.get("intent_card", [])}
    return lambda point, _ask: card.get(point)


def dialogue(points: list[str], ask_texts: dict[str, str], ask_user: AskUser | None,
             source: str) -> tuple[list[OpenPoint], list[dict[str, str]]]:
    """Ask the first MAX_QUESTIONS points in ASK_ORDER; the others (and unanswered ones) take defaults."""
    asked = [p for p in ASK_ORDER if p in points and p in ask_texts][:MAX_QUESTIONS]
    turns, opened, answers = [], [], {}
    for p in asked if ask_user is not None else []:
        answer = ask_user(p, ask_texts[p])
        if answer is not None:
            answers[p] = answer
            turns.append({"point": p, "ask": ask_texts[p], "answer": answer})
    for p in points:
        answer = answers.get(p)
        if answer is not None:
            choice = "all" if (p in TABLE_POINTS and ALL_RE.search(answer)) else answer.strip()
            opened.append(OpenPoint(id=p, question=ask_texts[p], choice=choice, source=source))
        else:
            default = "all" if p in TABLE_POINTS else "as the papers report it" if p == "measure_variant" else "none"
            opened.append(OpenPoint(id=p, question=ask_texts.get(p, ""), choice=default, source="default"))
    return opened, turns


def not_in_question(core: dspy.Prediction, question: str) -> list[str]:
    """The non-empty parts of a ReadQuestionCore reply that are not written in the question."""
    parts = [str(v) for v in (core.subjects or [])] + [core.comparator or "", core.measure or ""]
    return [p for p in parts if p.strip() and _in_question(p, question) is None]


def read_core(question: str) -> dspy.Prediction:
    """ReadQuestionCore, plus one repair call when a part is not written in the question (code then drops what is
    still not written there)."""
    core = _predict(ReadQuestionCore, question=question, feedback="")
    missing = not_in_question(core, question)
    if missing:
        feedback = "Not written in the question: " + "; ".join(f'"{m}"' for m in missing) + \
                   ". Copy each part word for word from the question."
        log.warning("spec: ReadQuestionCore repair: %s", feedback)
        core = _predict(ReadQuestionCore, question=question, feedback=feedback)
    return core


# ---------------------------------------------------------------- the step
def run(question: dict[str, Any], cfg: RunConfig, ask_user: AskUser | None = None) -> Spec:
    """Build and seal the Spec of one question record (qid, question, intent_card; its `type` is not read).

    Benchmark mode: the user's answers come from the intent card by point id (code lookup). Presentation mode: from
    `ask_user(point_id, ask_text)` (the UI hook); without one, every open point takes its default."""
    text = question["question"]
    lm = make_lm(cfg.llm_for("spec"))
    check_lm = make_lm(cfg.llm_for("spec_check"))
    with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
        dimensions = select_dimensions(text, lm)
        core = read_core(text)
        subjects_raw = [v for item in (core.subjects or []) if (v := _in_question(str(item), text))]
        subjects_raw = list({s.casefold(): s for s in reversed(subjects_raw)}.values())[::-1]
        measure_raw = _in_question(core.measure, text)
        named = {v.casefold() for v in [*subjects_raw, measure_raw] if v}
        dimensions = [d for d in dimensions if not d.fixed_value or d.fixed_value.casefold() not in named]
        sk = {"subjects": subjects_raw, "comparator": _in_question(core.comparator, text), "measure": measure_raw,
              "fixed": {d.key: d.fixed_value for d in dimensions if d.fixed_value}}
        qtype = question_type(text, sk)
        fixed_before = dict(sk["fixed"])
        sk, trend_by = shape(qtype, sk, text)
        unfixed = {v for k, v in fixed_before.items() if k not in sk["fixed"]}   # the trend variable: shown in full
        dimensions = [d.model_copy(update={"fixed_value": "", "quote": ""}) if d.fixed_value in unfixed else d
                      for d in dimensions]
        by = best_by(qtype, sk["subjects"], text)
        subjects = [name(s, "drug", text, check_lm) for s in sk["subjects"]]
        comparator = name(sk["comparator"], "comparator", text, check_lm) if sk["comparator"] else None
        measure = name(sk["measure"] or "", "measure", text, check_lm)

        unknown = [n for n in (*subjects, comparator, measure) if n is not None and n.label and not n.known]
        ask_texts = {p: ASK[p] for p in TABLE_POINTS + ("measure_variant",)}
        ask_texts["measure_variant"] = ASK["measure_variant"].format(measure=measure.label) if measure.label else \
            "How should the change be measured?"
        if unknown:
            ask_texts["other_names"] = ASK["other_names"].format(
                unknown=" or ".join(n.label for n in unknown), it="it" if len(unknown) == 1 else "them")
        if cfg.mode == "benchmark":
            ask_user, source = _answers_from_card(question), "card"
        else:
            source = "user"
        # Name and measurement clarifications are not setting dimensions.
        open_dimensions = [d for d in dimensions if not d.fixed_value]
        prompts = {d.key: d.question for d in open_dimensions}
        meta = ["measure_variant"] if measure.label else []
        if unknown:
            meta.append("other_names")
        prompts.update({p: ask_texts[p] for p in meta})
        ordered = [p for p in ("other_names", "measure_variant") if p in meta] + [d.key for d in open_dimensions]
        answers, turns = {}, []
        for point in ordered:
            if ask_user is None or len(turns) >= MAX_QUESTIONS:
                break
            answer = ask_user(point, prompts[point])
            if answer is not None:
                answers[point] = answer
                turns.append({"point": point, "ask": prompts[point], "answer": answer})
        points = []
        for point in [d.key for d in open_dimensions] + meta:
            answer = answers.get(point)
            if point in meta:
                choice = answer if answer is not None else ("none" if point == "other_names" else "as the papers report it")
            else:
                choice = "all" if answer is None or ALL_RE.search(answer) else answer.strip()
            points.append(OpenPoint(id=point, question=prompts[point], choice=choice,
                                    source=source if answer is not None else "default"))

        other = next((t["answer"] for t in turns if t["point"] == "other_names"), "")
        for n in unknown:
            n.synonyms = user_names(n.label, other)

        higher = None
        if qtype in ("best", "effect"):
            d = _predict(P.Direction, question=text, measure=measure.label)
            if not isinstance(d.higher_is_better, bool):
                raise SpecError(f"higher_is_better is not a bool: {d.higher_is_better!r}")
            higher = d.higher_is_better

    if trend_by:                                   # the trend variable is always shown in full
        for p in points:
            if p.id == trend_by and p.choice != "all":
                log.warning("spec: trend over %s: choice %r taken as 'all'", trend_by, p.choice)
                p.choice = "all"
    dimension_keys = {d.key for d in dimensions}
    columns = [p.id for p in points if p.id in dimension_keys and p.choice == "all"]
    return Spec(qid=question["qid"], question=text, type=qtype, subjects=subjects, comparator=comparator,
                measure=measure, fixed=sk["fixed"], open_points=points, columns=columns, higher_is_better=higher,
                best_by=by, trend_by=trend_by, dialogue=turns, dimensions=dimensions, locked=True).seal()
