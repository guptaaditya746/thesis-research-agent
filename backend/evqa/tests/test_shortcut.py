"""Shortcut test (evqa.shortcut): reply classes, the question as the systems see it, caching by input hash, the
strict rule, the typical-value baseline and the exact intervals. No model is called."""
from __future__ import annotations

import json
import math

import pytest

from evqa import shortcut as sc


def test_question_text_matches_the_systems_form():
    rec = {"qid": "Q-1", "question": "For X, what number is reported for sites?", "type": "lookup",
           "intent_card": [{"point": "other_names", "answer": "None."}, {"point": "papers", "answer": "All."},
                           {"point": "empty", "answer": " "}]}
    assert sc.question_text(rec) == ("For X, what number is reported for sites?\n\nWhat the user wants:\n"
                                     "- other names: None.\n- papers: All.")
    assert sc.question_text({"qid": "Q", "question": "Q?"}) == "Q?"
    assert "type" not in sc.PROMPT.format(question=sc.question_text(rec)).split("Question:")[1]


@pytest.mark.parametrize("text,cls", [
    ("unknown", "unknown"), ("Unknown.", "unknown"), ("", "unknown"), ("  ", "unknown"),
    ("Not reported.", "not_reported"), ("not reported", "not_reported"),
    ("KELAD-4 trial: 24 sites", "answer"), ("The value is unknown to most readers: 12", "answer"),
])
def test_classify(text, cls):
    assert sc.classify(text) == cls


def test_strict_right():
    assert sc.strict_right("lookup", "answer", {"exact": True, "claims": 1})
    assert not sc.strict_right("lookup", "unknown", {"exact": True})
    assert sc.strict_right("absent", "not_reported", {"exact": True, "claims": 0})
    assert not sc.strict_right("absent", "unknown", {"exact": True, "claims": 0})     # scorer-right, strictly wrong
    assert not sc.strict_right("near_miss", "answer", {"exact": False, "claims": 2})


def test_clopper_pearson_known_values():
    lo, hi = sc.clopper_pearson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.3085, abs=1e-3)
    lo, hi = sc.clopper_pearson(5, 10)
    assert lo == pytest.approx(0.1871, abs=1e-3) and hi == pytest.approx(0.8129, abs=1e-3)
    lo, hi = sc.clopper_pearson(10, 10)
    assert lo == pytest.approx(0.6915, abs=1e-3) and hi == 1.0
    assert sc.clopper_pearson(0, 0) == (0.0, 1.0)


def test_typical_baseline_mode_of_other_subjects():
    facts = {
        "R1": {"id": "R1", "what": "attr", "attr": "judges", "unit": "judges", "subject": "D1", "value": "5"},
        "R2": {"id": "R2", "what": "attr", "attr": "judges", "unit": "judges", "subject": "D2", "value": "3"},
        "R3": {"id": "R3", "what": "attr", "attr": "judges", "unit": "judges", "subject": "D3", "value": "3"},
        "R4": {"id": "R4", "what": "attr", "attr": "judges", "unit": "judges", "subject": "D1", "value": "9"},
        "R5": {"id": "R5", "what": "attr", "attr": "pages", "unit": "pages", "subject": "D4", "value": "5"},
    }
    q = {"type": "lookup", "answer": {"table": [{"row": "R1", "value": "5"}]}}
    got = sc.typical_baseline(q, facts)          # the subject's own values (5, 9) are left out: mode 3
    assert got == {"guesses": [3.0], "score": 0.0, "exact": False}
    q2 = {"type": "lookup", "answer": {"table": [{"row": "R2", "value": "3"}]}}
    assert sc.typical_baseline(q2, facts)["exact"]       # others 5, 3, 9 -> tie, smallest = 3
    assert sc.typical_baseline({"type": "list", "answer": {}}, facts) is None


def test_ask_all_caches_by_input_hash(tmp_path):
    calls = []

    def send(model, prompt):
        calls.append(prompt)
        return {"text": "Not reported." if "sites" in prompt.split("Question:")[-1] else "X: 4 judges", "usage": {"prompt_tokens": 7}}
    recs = [{"qid": "Q-1", "question": "For X, what number is reported for sites?"},
            {"qid": "Q-2", "question": "For X, what number is reported for judges?"}]
    cache = sc.Cache(tmp_path / "c.jsonl")
    got = sc.ask_all(recs, "m", send, cache, parallel=2, log=lambda s: None)
    assert got["Q-1"]["class"] == "not_reported" and got["Q-2"]["class"] == "answer"
    assert len(calls) == 2
    again = sc.ask_all(recs, "m", send, sc.Cache(tmp_path / "c.jsonl"), log=lambda s: None)
    assert len(calls) == 2 and again["Q-2"]["text"] == "X: 4 judges"
    other = sc.ask_all(recs[:1], "m2", send, sc.Cache(tmp_path / "c.jsonl"), log=lambda s: None)
    assert len(calls) == 3 and other["Q-1"]["input_sha256"] != got["Q-1"]["input_sha256"]


def test_ask_all_records_a_failed_call(tmp_path):
    def send(model, prompt):
        raise RuntimeError("down")
    got = sc.ask_all([{"qid": "Q-1", "question": "Q?"}], "m", send, sc.Cache(None), log=lambda s: None)
    assert got["Q-1"]["class"] == "error" and got["Q-1"]["text"] is None and "down" in got["Q-1"]["error"]


def test_summarize_chance_for_not_reported_types():
    def q(t, cls, right, exact=False, score=0.0):
        return {"type": t, "answers": {"m": {"class": cls, "strict_right": right, "exact": exact, "score": score}}}
    qs = [q("lookup", "not_reported", False), q("lookup", "answer", True, True, 1.0),
          q("lookup", "answer", False), q("lookup", "unknown", False),
          q("absent", "not_reported", True, True, 1.0), q("absent", "unknown", False, True, 1.0)]
    rows = {r["type"]: r for r in sc.summarize(qs, ["m"])}
    assert rows["lookup"]["right"] == 1 and rows["lookup"]["guess"] == 0.0 and rows["lookup"]["abstain"] == 1
    assert rows["absent"]["guess"] == 0.25           # 1 of the 4 answerable replies said "Not reported."
    assert rows["absent"]["right"] == 1 and rows["absent"]["scorer_right"] == 2
    assert math.isclose(rows["absent"]["scorer_mean"], 1.0)


def test_score_answers_uses_the_project_scorer(tmp_path, monkeypatch):
    """A paperfactory gold file through thesis_scorer.text with a fake reader: a right number is exact, a wrong one
    is not, and "unknown" on an absent question is scorer-right."""
    from thesis_scorer.schema import TextClaim
    from thesis_scorer.text import ClaimList

    from evqa import scoring
    gold = {"domain": "pf_x", "kind": "paperfactory", "split": "test", "units": {}, "papers": ["P-1"],
            "entities": {},
            "questions": [
                {"qid": "Q-1", "type": "lookup", "split": "test", "question": "For X, what number is reported?",
                 "slots": {"subject": ["X"]}, "row_ids": ["R1"],
                 "answer": {"columns": [], "table": [{"row": "R1", "paper": "P-1", "papers": ["P-1"], "cells": {},
                                                      "value": "24", "unit": "sites"}]}},
                {"qid": "Q-2", "type": "lookup", "split": "test", "question": "For Y, what number is reported?",
                 "slots": {"subject": ["Y"]}, "row_ids": ["R2"],
                 "answer": {"columns": [], "table": [{"row": "R2", "paper": "P-1", "papers": ["P-1"], "cells": {},
                                                      "value": "7", "unit": "sites"}]}},
                {"qid": "Q-3", "type": "absent", "split": "test", "question": "For Z, what number is reported?",
                 "slots": {"subject": ["Z"]}, "row_ids": [], "answer": {"columns": [], "table": []}}],
            "data": {}}
    monkeypatch.setattr(scoring, "gold_file", lambda d, s: gold)

    class Reader:
        name, calls = "fake", 0

        def ask(self, instructions, inputs, out):
            ans = inputs["answer"]
            if ans.strip() in ("unknown", "Not reported."):
                return ClaimList(claims=[])
            return ClaimList(claims=[TextClaim(value_text=ans.split(": ")[1], subject=ans.split(": ")[0],
                                               quote=ans)])
    answers = {"Q-1": {"text": "X: 24 sites", "class": "answer"}, "Q-2": {"text": "Y: 8 sites", "class": "answer"},
               "Q-3": {"text": "unknown", "class": "unknown"}}
    got = sc.score_answers("pf_x", answers, "m", Reader(), None, parallel=2)
    assert got["Q-1"]["exact"] and got["Q-1"]["score"] == 1.0
    assert not got["Q-2"]["exact"] and got["Q-2"]["score"] == 0.0
    assert got["Q-3"]["exact"] and not sc.strict_right("absent", "unknown", got["Q-3"])


def test_cache_seeded_from_an_earlier_report(tmp_path):
    cache = sc.Cache(None, {"abc": {"model": "m", "text": "unknown", "usage": {}}})
    assert cache.get("abc")["text"] == "unknown"
    cache.put("def", {"model": "m", "text": "x"})
    assert cache.calls == 1 and json.dumps(cache.get("def"))
