"""S4 Spec step with a fake LM: code keeps only question substrings, unknown names get no synonyms, open points and
columns follow the question and the intent card, the dialogue stops at 3 questions."""
from __future__ import annotations

import ast
import json
import re

import dspy
import pytest

from evqa import lm
from evqa.contracts import RunConfig, Spec
from evqa.paths import BACKEND_EVQA
from evqa.spec import advisor_score, build
from evqa.spec import run as spec_run

CARD = {
    "time_point": "Show every time point reported, one per row.",
    "patient_group": "Show every patient group, kept apart.",
    "dose": "Show every dose.",
    "measure_variant": "The change from the start of the trial compared with placebo (the mean difference).",
    "other_names": "I know no other names. Use the names in the question.",
}
KNOWN = {"HbA1c": "Glycated haemoglobin: average blood sugar over about three months.",
         "body weight": "How heavy a person is."}
SYNONYMS = {"HbA1c": ["glycated haemoglobin", "A1c", "HbA1c", "fasting glucose"], "body weight": ["weight"]}


def q(qid: str, qtype: str, text: str, points: list[str]) -> dict:
    return {"qid": qid, "type": qtype, "question": text,
            "intent_card": [{"point": p, "label": p, "ask": "?", "answer": CARD[p]} for p in points]}


Q1 = q("Q1", "lookup", "How much does brenoxalin 20 mg lower HbA1c?",
       ["time_point", "patient_group", "measure_variant", "other_names"])
Q2 = q("Q2", "lookup", "What does kavolemin do to body weight?",
       ["dose", "time_point", "patient_group", "measure_variant", "other_names"])
Q3 = q("Q3", "best", "Which brenoxalin dose lowers HbA1c the most at 24 weeks in patients who already take metformin?",
       ["measure_variant", "other_names"])
Q4 = q("Q4", "best", "Which drug lowers HbA1c more at 24 weeks, brenoxalin or kavolemin?",
       ["dose", "patient_group", "measure_variant", "other_names"])


def field(prompt: str, name: str) -> str:
    """The value of input field `name` in the last user message DSPy rendered."""
    user = prompt.rsplit("[user]\n", 1)[-1].rsplit("\n\nRespond with", 1)[0]
    m = re.findall(rf"\[\[ ## {name} ## \]\]\n(.*?)(?=\n\n\[\[ ## |\Z)", user, re.DOTALL)
    return m[-1].strip() if m else ""


def fake(prompt: str, *, parse: dict | None = None) -> str:
    """A fake model: picks the task from the signature text and answers like a careful model would."""
    calls.append(prompt)
    if "Identify dimensions needed" in prompt:
        question = field(prompt, "question")
        qrec = next(q for q in (Q1, Q2, Q3, Q4) if q["question"] == question)
        fixed = {k: v for k, v in parse[question].items() if k in ("dose", "time_point", "patient_group")
                 and v and v in question and not (k == "dose" and not re.search(r"\d", v))}
        if question == Q4["question"]:
            fixed["time_point"] = "24 weeks"
        keys = [p for p in card_points(qrec) if p in ("dose", "time_point", "patient_group")]
        return json.dumps({"dimensions": [{"key": key, "question": f"Which {key}?", "why": "It can vary.",
            "fixed_value": fixed.get(key, ""), "quote": fixed.get(key, "")} for key in dict.fromkeys([*keys, *fixed])]})
    if "Read the objects, comparison and measure" in prompt:
        question = field(prompt, "question")
        parsed = parse[question]
        return json.dumps({key: parsed[key] for key in ("subjects", "comparator", "measure")})
    if "Say what kind of answer" in prompt:
        question = field(prompt, "question")
        return json.dumps({"type": TYPES[question], "reason": "fake"})
    if "Split a question" in prompt:
        question = field(prompt, "question")
        return json.dumps(parse[question])
    if "Say whether you know this name" in prompt:
        name = field(prompt, "name")
        return json.dumps({"known": name in KNOWN, "definition": KNOWN.get(name, "")})
    if "List other names that mean exactly" in prompt:
        return json.dumps({"synonyms": SYNONYMS.get(field(prompt, "name"), [])})
    if "Check each candidate" in prompt:
        cands = json.loads(field(prompt, "candidates"))
        return json.dumps({"same": [c != "fasting glucose" for c in cands]})
    if "The user was asked for other names" in prompt:
        answer = field(prompt, "answer")
        return json.dumps({"names": ["BRX-233", "made-up-not-in-answer"] if "BRX-233" in answer else []})
    if "compares options" in prompt:
        return json.dumps({"higher_is_better": False, "reason": "lowers"})
    raise AssertionError(f"unexpected prompt: {prompt[:300]}")


calls: list[str] = []
TYPES = {x["question"]: x["type"] for x in (Q1, Q2, Q3, Q4)}   # the fake model's type; the record's type is not read
PARSE = {
    Q1["question"]: {"subjects": ["brenoxalin"], "comparator": "", "measure": "HbA1c", "dose": "20 mg",
                     "time_point": "", "patient_group": ""},
    Q2["question"]: {"subjects": ["kavolemin", "Kavolemin"], "comparator": "", "measure": "body weight", "dose": "",
                     "time_point": "", "patient_group": "adults with diabetes"},   # not in the question: dropped
    Q3["question"]: {"subjects": ["brenoxalin"], "comparator": "", "measure": "HbA1c", "dose": "brenoxalin dose",
                     "time_point": "24 weeks", "patient_group": "patients who already take metformin"},
    Q4["question"]: {"subjects": ["brenoxalin", "kavolemin", "metformin"], "comparator": "", "measure": "HbA1c",
                     "dose": "", "time_point": "", "patient_group": ""},   # metformin not in Q4; time: regex
}


@pytest.fixture(autouse=True)
def fake_lm(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "CACHE_FILE", tmp_path / "cache.jsonl")
    monkeypatch.setattr(lm, "_caches", {})
    monkeypatch.setattr(build, "make_lm", lambda cfg: lm.make_lm(cfg, ask=lambda t: fake(t, parse=PARSE)))
    calls.clear()


CFG = RunConfig()


def card_points(question: dict) -> list[str]:
    return [c["point"] for c in question["intent_card"]]


@pytest.mark.parametrize("question", [Q1, Q2, Q3, Q4], ids=["Q1", "Q2", "Q3", "Q4"])
def test_open_points_match_the_intent_card(question: dict) -> None:
    s = spec_run(question, CFG)
    assert [p.id for p in s.open_points] == card_points(question)
    assert s.columns == [p for p in card_points(question) if p in build.TABLE_POINTS]
    assert s.sha256 and Spec.model_validate(s.model_dump()).seal().sha256 == s.sha256


def test_slots_are_substrings_of_the_question() -> None:
    s1, s2, s3, s4 = (spec_run(x, CFG) for x in (Q1, Q2, Q3, Q4))
    assert s1.fixed == {"dose": "20 mg"}
    assert s2.fixed == {} and [n.label for n in s2.subjects] == ["kavolemin"]       # duplicate and invented dropped
    assert s3.fixed == {"time_point": "24 weeks", "patient_group": "patients who already take metformin"}
    assert s3.best_by == "dose" and s3.higher_is_better is False
    assert [n.label for n in s4.subjects] == ["brenoxalin", "kavolemin"] and s4.best_by == "subject"
    assert s4.fixed == {"time_point": "24 weeks"}                                      # filled by the regex
    assert s1.higher_is_better is None and s1.best_by is None


def test_unknown_names_get_no_synonyms_and_known_ones_are_checked() -> None:
    s = spec_run(Q1, CFG)
    (drug,) = s.subjects
    assert drug.known is False and drug.synonyms == [] and drug.definition == ""
    assert s.measure.known and s.measure.synonyms == ["glycated haemoglobin", "A1c"]   # label and wrong one gone
    assert s.dialogue[0]["point"] == "other_names" and "brenoxalin" in s.dialogue[0]["ask"]


def test_at_most_three_questions_then_defaults() -> None:
    s = spec_run(Q2, CFG)
    assert [t["point"] for t in s.dialogue] == ["other_names", "measure_variant", "dose"]
    src = {p.id: p.source for p in s.open_points}
    assert src == {"dose": "card", "time_point": "default", "patient_group": "default",
                   "measure_variant": "card", "other_names": "card"}
    assert {p.id: p.choice for p in s.open_points}["time_point"] == "all"


def test_presentation_mode_uses_the_hook_and_reads_user_names() -> None:
    asked = []

    def ask(point: str, text: str) -> str:
        asked.append(point)
        return "It is also called BRX-233." if point == "other_names" else "Only 24 weeks." if point == "time_point" \
            else "all of them"

    s = spec_run(Q1, RunConfig(mode="presentation"), ask)
    assert asked == ["other_names", "measure_variant", "time_point"]
    assert s.subjects[0].synonyms == ["BRX-233"]                                         # invented name dropped
    choices = {p.id: (p.choice, p.source) for p in s.open_points}
    assert choices["time_point"] == ("Only 24 weeks.", "user")
    assert s.columns == ["patient_group"]


def test_presentation_without_hook_takes_defaults() -> None:
    s = spec_run(Q1, RunConfig(mode="presentation"))
    assert s.dialogue == [] and all(p.source == "default" for p in s.open_points)
    assert s.columns == ["time_point", "patient_group"]


def test_rerun_makes_no_new_model_call() -> None:
    spec_run(Q4, CFG)
    n = len(calls)
    spec_run(Q4, CFG)
    assert len(calls) == n


def test_advisor_score() -> None:
    s = spec_run(Q1, CFG)
    got = advisor_score(s, {"names": ["brenoxalin", "glycated haemoglobin", "BRX-233"],
                            "slots": {"dose": "20 mg", "time_point": "all", "patient_group": "only adults"}})
    assert got["names"]["missing"] == ["BRX-233"] and got["names"]["share"] == round(2 / 3, 4)
    assert list(got["slots"]["missing"]) == ["patient_group"]
    assert got["share"] == round(4 / 6, 4)


def test_spec_reads_no_papers() -> None:
    """Independent advisor: no corpus papers, no seed, no eval in the spec package."""
    for f in (BACKEND_EVQA / "spec").rglob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in {"evqa.corpus", "evqa.paths"}, f
                assert not (node.module == "evqa" and any(a.name in {"corpus", "paths"} for a in node.names)), f
            if isinstance(node, ast.Import):
                assert not any(a.name.startswith(("evqa.corpus", "evqa.seed", "evqa.eval")) for a in node.names), f


def test_an_empty_reply_is_asked_again(monkeypatch) -> None:
    """Qwen can loop in its reasoning and return nothing; the step asks again (a new recorded attempt)."""
    seen: set[str] = set()

    def flaky(text: str) -> str:
        if "List other names that mean exactly" in text and "OtherNames" not in seen:
            seen.add("OtherNames")
            return ""
        return fake(text, parse=PARSE)

    monkeypatch.setattr(build, "make_lm", lambda cfg: lm.make_lm(cfg, ask=flaky))
    s = spec_run(Q2, CFG)
    assert s.measure.synonyms == ["weight"] and "OtherNames" in seen


def test_an_age_is_never_a_time_point(monkeypatch) -> None:
    """'aged 65 years or older' names patients, not a time point: neither the model's slot nor the regex keeps it."""
    question = "In adults aged 65 years or older with type 2 diabetes, how much does brenoxalin change HbA1c at 12 weeks?"
    parse = {question: {"subjects": ["brenoxalin"], "comparator": "", "measure": "HbA1c", "dose": "",
                        "time_point": "65 years", "patient_group": "adults aged 65 years or older with type 2 diabetes"}}
    monkeypatch.setattr(build, "make_lm", lambda cfg: lm.make_lm(cfg, ask=lambda t: fake(t, parse=parse)))
    with dspy.context(lm=build.make_lm(CFG.llm), adapter=dspy.JSONAdapter()):
        sk = build.skeleton(question)
    assert sk["fixed"] == {"time_point": "12 weeks", "patient_group": "adults aged 65 years or older with type 2 diabetes"}
    assert build.is_age("aged 65 years or older", 5, 13) and not build.is_age("at 24 weeks", 3, 11)


def test_a_background_therapy_is_not_a_subject() -> None:
    q = "Which studies have reported fasting plasma glucose in adults with type 2 diabetes who are taking metformin?"
    assert build.background_span("metformin", q) is not None
    assert build.background_span("brenoxalin", "Does brenoxalin lower HbA1c in adults on metformin?") is None
    assert build.background_span("metformin", "Does metformin lower HbA1c in adults on metformin?") is None


def test_skeleton_moves_a_background_drug_into_the_patient_group(monkeypatch) -> None:
    question = "Which studies have reported fasting plasma glucose in adults aged 65 years or older with type 2 diabetes " \
               "who are taking metformin?"
    parse = {question: {"subjects": ["metformin"], "comparator": "", "measure": "fasting plasma glucose", "dose": "",
                        "time_point": "", "patient_group": "adults aged 65 years or older with type 2 diabetes"}}
    monkeypatch.setattr(build, "make_lm", lambda cfg: lm.make_lm(cfg, ask=lambda t: fake(t, parse=parse)))
    with dspy.context(lm=build.make_lm(CFG.llm), adapter=dspy.JSONAdapter()):
        sk = build.skeleton(question)
    assert sk["subjects"] == [] and sk["fixed"] == {
        "patient_group": "adults aged 65 years or older with type 2 diabetes who are taking metformin"}
