"""Spec for the question types added on 21 Nov, with a fake LM: the type comes from the question (never the
record's `type`), a rejected type is repaired with the failed check, effect puts a drug comparator among the
subjects, trend keeps its variable open, list may have no measure or no drug, unknown names get nothing made up."""
from __future__ import annotations

import json
import re

import pytest

from evqa import lm
from evqa.contracts import RunConfig
from evqa.spec import SpecError, build
from evqa.spec import run as spec_run

CARD = [{"point": p, "label": p, "ask": "?", "answer": a} for p, a in (
    ("dose", "Show every dose."), ("time_point", "Only 24 weeks."),
    ("patient_group", "Show every patient group, kept apart."),
    ("measure_variant", "The mean difference vs placebo."),
    ("other_names", "I know no other names. Use the names in the question."))]
KNOWN = {"pain score": "A patient-rated score of pain.", "FEV1": "Air breathed out in one second.",
         "ibuprofen": "A painkiller.", "naproxen": "A painkiller."}

# question -> (fake type replies in order, ReadQuestion reply)
CASES = {
    "Does zorvatinel lower pain score more than naproxen does?": (
        ["effect"], {"subjects": ["zorvatinel"], "comparator": "naproxen", "measure": "pain score"}),
    "Is ibuprofen 400 mg better than placebo for pain score?": (
        ["effect"], {"subjects": ["ibuprofen"], "comparator": "placebo", "measure": "pain score", "dose": "400 mg"}),
    "How does the effect of naproxen on pain score at 12 weeks change with the dose?": (
        ["trend"], {"subjects": ["naproxen"], "measure": "pain score", "time_point": "12 weeks"}),
    "How does the effect of naproxen 500 mg on pain score change over time from 4 weeks?": (
        ["trend"], {"subjects": ["naproxen"], "measure": "pain score", "dose": "500 mg", "time_point": "4 weeks"}),
    "Which trials tested trelvanex?": (
        ["list"], {"subjects": ["trelvanex"], "measure": ""}),
    "Which studies report FEV1 in older adults?": (
        ["list"], {"subjects": [], "measure": "FEV1", "patient_group": "older adults"}),
    "What does naproxen do to pain score?": (            # first reply is a type the code rejects
        ["best", "lookup"], {"subjects": ["naproxen"], "measure": "pain score"}),
    "How much does qelvorin change pain score?": (
        ["effect", "effect", "effect"], {"subjects": ["qelvorin"], "measure": "pain score"}),
}
calls: list[str] = []


def field(prompt: str, name: str) -> str:
    user = prompt.rsplit("[user]\n", 1)[-1].rsplit("\n\nRespond with", 1)[0]
    m = re.findall(rf"\[\[ ## {name} ## \]\]\n(.*?)(?=\n\n\[\[ ## |\Z)", user, re.DOTALL)
    return m[-1].strip() if m else ""


def fake(prompt: str) -> str:
    calls.append(prompt)
    if "Identify dimensions needed" in prompt:      # Spec v2: settings the value depends on, fixed ones quoted
        parse = CASES[field(prompt, "question")][1]
        fixed = {k: parse[k] for k in ("dose", "time_point", "patient_group") if parse.get(k)}
        return json.dumps({"dimensions": [{"key": k, "question": f"Which {k}?", "why": "It can vary.",
            "fixed_value": fixed.get(k, ""), "quote": fixed.get(k, "")}
            for k in ("dose", "time_point", "patient_group")]})
    if "Read the objects, comparison and measure" in prompt:
        parse = CASES[field(prompt, "question")][1]
        return json.dumps({"subjects": parse["subjects"], "comparator": parse.get("comparator", ""),
                           "measure": parse["measure"]})
    if "Say what kind of answer" in prompt:
        replies = CASES[field(prompt, "question")][0]
        n = sum("Say what kind of answer" in c and field(c, "question") == field(prompt, "question") for c in calls)
        return json.dumps({"type": replies[min(n, len(replies)) - 1], "reason": "fake"})
    if "Split a question" in prompt:
        parse = {"comparator": "", "dose": "", "time_point": "", "patient_group": "",
                 **CASES[field(prompt, "question")][1]}
        return json.dumps(parse)
    if "Say whether you know this name" in prompt:
        name = field(prompt, "name")
        return json.dumps({"known": name in KNOWN, "definition": KNOWN.get(name, "")})
    if "List other names that mean exactly" in prompt:
        return json.dumps({"synonyms": []})
    if "The user was asked for other names" in prompt:
        return json.dumps({"names": []})
    if "compares options" in prompt:
        return json.dumps({"higher_is_better": False, "reason": "lower pain is better"})
    raise AssertionError(f"unexpected prompt: {prompt[:300]}")


@pytest.fixture(autouse=True)
def fake_lm(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "CACHE_FILE", tmp_path / "cache.jsonl")
    monkeypatch.setattr(lm, "_caches", {})
    monkeypatch.setattr(build, "make_lm", lambda cfg: lm.make_lm(cfg, ask=fake))
    calls.clear()


def run(question: str, record_type: str = "lookup"):
    return spec_run({"qid": "Q", "type": record_type, "question": question, "intent_card": CARD}, RunConfig())


def test_effect_with_a_drug_comparator_compares_two_subjects():
    s = run("Does zorvatinel lower pain score more than naproxen does?", record_type="near_miss")
    assert s.type == "effect" and [n.label for n in s.subjects] == ["zorvatinel", "naproxen"]
    assert s.comparator is None and s.higher_is_better is False and s.best_by is None
    assert s.subjects[0].known is False and s.subjects[0].synonyms == []      # unknown: nothing made up


def test_effect_against_placebo_keeps_the_control_as_comparator():
    s = run("Is ibuprofen 400 mg better than placebo for pain score?")
    assert [n.label for n in s.subjects] == ["ibuprofen"] and s.comparator.label == "placebo"
    assert s.fixed == {"dose": "400 mg"}


def test_trend_over_dose_is_an_all_column():
    s = run("How does the effect of naproxen on pain score at 12 weeks change with the dose?")
    assert s.type == "trend" and s.trend_by == "dose" and "dose" in s.columns
    assert s.fixed == {"time_point": "12 weeks"} and s.higher_is_better is None


def test_trend_over_time_unfixes_the_time_and_overrides_the_card():
    s = run("How does the effect of naproxen 500 mg on pain score change over time from 4 weeks?")
    assert s.trend_by == "time_point" and "time_point" not in s.fixed and "time_point" in s.columns
    assert {p.id: p.choice for p in s.open_points}["time_point"] == "all"      # card said "Only 24 weeks."


def test_list_without_a_measure_or_without_a_drug():
    s = run("Which trials tested trelvanex?")
    assert s.type == "list" and s.measure.label == "" and [n.label for n in s.subjects] == ["trelvanex"]
    assert not any("Say whether you know this name" in c and field(c, "name") == "" for c in calls)
    s = run("Which studies report FEV1 in older adults?")
    assert s.subjects == [] and s.measure.label == "FEV1" and s.fixed == {"patient_group": "older adults"}


def test_a_rejected_type_gets_a_repair_call_with_the_failed_check():
    s = run("What does naproxen do to pain score?", record_type="best")
    assert s.type == "lookup"
    repair = [c for c in calls if "Say what kind of answer" in c][-1]
    assert "Failed check" in field(repair, "feedback") and "best" in field(repair, "feedback")


def test_no_accepted_type_raises():
    with pytest.raises(SpecError, match="no accepted question type"):
        run("How much does qelvorin change pain score?")
