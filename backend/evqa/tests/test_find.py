"""Find v0 on a tiny fake corpus with a fake model (no network)."""
from __future__ import annotations

import json
import re

import pytest

import evqa.corpus
import evqa.lm
from evqa.contracts import FindConfig, Name, OpenPoint, RunConfig, Spec, StepLLM
from evqa.find import find, run, spec_text
from evqa.find import passages as P
from evqa.find.search import find_term, rank_passages

A1 = """# Drugx added to metformin

## Abstract

Drugx (DX-77) was given once daily to adults on metformin; HbA1c was measured.

## Methods

Adults with type 2 diabetes on metformin took part.

## Results

Table 1: Change in HbA1c at week 12 by dose

| Dose | Time point | HbA1c (percentage points) |
|---|---|---|
| 10 mg | week 12 | -0.5 |

At week 24, the mean difference versus placebo was -0.6 percentage points.
"""
B2 = """# DX 77 in older adults

## Abstract

DX 77 was tested in older adults; HbA1c was measured.

## Results

At week 24, HbA1c fell by -0.4 percentage points with DX-77 in older adults.
"""
C3 = """# Otherdrug with metformin

## Abstract

Otherdrug was tested; HbA1c was measured.

## Results

At week 24, HbA1c fell by -0.3 percentage points with Otherdrug.
"""
CORPUS = {"A-1": A1, "B-2": B2, "C-3": C3}


def spec() -> Spec:
    return Spec(qid="Q-1", question="How much does drugx lower HbA1c?", type="lookup",
                subjects=[Name(label="drugx", known=False)], measure=Name(label="HbA1c"),
                open_points=[OpenPoint(id="time_point", question="Which time?", choice="all"),
                             OpenPoint(id="patient_group", question="Which patients?", choice="all")],
                columns=["time point", "patient group"])


def fields(prompt: str) -> dict[str, str]:
    user = prompt.split("[user]", 1)[-1]
    return {m.group(1): m.group(2).strip() for m in
            re.finditer(r"\[\[ ## (\w+) ## \]\]\n(.*?)(?=\n\n\[\[ ## |\n\nRespond with|\Z)", user, re.S)}


class FakeModel:
    """Screens by name, marks passages with numbers, finds code names in brackets. Counts calls per task."""

    def __init__(self, agent_reply=None, bad_quotes=False, terms=None):
        self.calls: dict[str, int] = {}
        self.agent_reply = agent_reply
        self.bad_quotes = bad_quotes
        self.terms = terms or []

    def __call__(self, prompt: str) -> str:
        f = fields(prompt)
        task = re.search(r"order of fields: `(\w+)`", prompt).group(1)
        self.calls[task] = self.calls.get(task, 0) + 1
        if task == "decision":
            names = ["drugx"] + re.findall(r"names the papers use for it: ([^;\n]+)", f["spec"])
            seen = (f["title"] + f["abstract"] + f["passages"]).lower()
            yes = any(find_term(n.strip(), seen) for n in ",".join(names).split(","))
            return json.dumps({"decision": "yes" if yes else "no", "reason": "named" if yes else "other drug"})
        if task == "marks":
            marks = []
            for m in re.finditer(r"^\[(\d+)\] \(([^)]*)\) (.*?)(?=\n\n\[\d+\] |\Z)", f["passages"], re.M | re.S):
                i, text = int(m.group(1)), m.group(3)
                if "percentage points" in text or "| -0" in text:
                    marks.append({"id": i, "role": "value", "quote": "NOT IN TEXT" if self.bad_quotes else text[:15],
                                  "subjects": ["drugx"], "columns": ["time point"] if "week" in text else []})
                elif "Adults with" in text:
                    marks.append({"id": i, "role": "context", "quote": text[:20], "subjects": [],
                                  "columns": ["patient group"]})
            return json.dumps({"marks": marks})
        if task == "terms":
            return json.dumps({"terms": self.terms})
        if task == "kind":
            if self.agent_reply:
                return json.dumps(self.agent_reply(f, self.calls[task]))
            code = re.search(r"\((DX-\d+)\)", f["text"])
            if "other names" in f["gap"] and code:
                return json.dumps({"kind": "other_name", "term": code.group(1), "reason": "in brackets"})
            return json.dumps({"kind": "stop", "term": "", "reason": "nothing"})
        raise AssertionError(task)


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(evqa.corpus, "papers", lambda domain: dict(CORPUS))
    monkeypatch.setattr(evqa.lm, "CACHE_FILE", tmp_path / "lm.jsonl")

    def make(**kw):
        fake = FakeModel(**kw)
        return fake, evqa.lm.make_lm(StepLLM(), ask=fake)
    return make


# ---------------------------------------------------------------- code parts
def test_regex_is_tolerant_of_case_hyphen_and_space():
    text = "brn 233 and BRN233 and Brn–233 and BRN-2330 and xBRN-233 and BRN-233."
    assert len(find_term("BRN-233", text)) == 4
    assert len(find_term("brn 233", "BRN-233")) == 1
    assert find_term("drugx", "Drugx-based") == [(0, 5)]
    assert find_term("drugx", "drugxy") == []


def test_passages_have_exact_offsets_and_tables_keep_their_caption():
    ps = P.split(A1)
    assert all(P.check(A1, p) and A1[p.start:p.end] == p.text for p in ps)
    assert not any(p.text.startswith("#") for p in ps)
    tables = [p for p in ps if p.kind == "table"]
    assert len(tables) == 1 and tables[0].text.startswith("Table 1:") and tables[0].text.rstrip().endswith("|")
    assert tables[0].section == "Results"
    assert P.title(A1) == "Drugx added to metformin"
    assert "DX-77" in P.abstract(ps)


def test_passages_are_ranked_by_how_many_search_words_they_hold():
    ps = {pid: P.split(t) for pid, t in CORPUS.items()}
    top = rank_passages(ps, ["Otherdrug"], 5)
    assert top and all(ref.paper == "C-3" for ref, _ in top)
    best, n = rank_passages(ps, ["DX-77", "older adults", "HbA1c"], 1)[0]
    assert best.paper == "B-2" and n == 3
    assert rank_passages(ps, ["nothinglikethis"], 5) == []


def test_spec_text_says_all_points_never_drop_a_paper():
    text = spec_text(spec(), {"drugx": ["DX-77"]})
    assert "names the papers use for it: DX-77" in text
    assert "time point, patient group" in text and "never a reason to drop" in text


# ---------------------------------------------------------------- the whole step
def test_find_discovers_the_code_name_and_keeps_its_paper(setup):
    fake, lm = setup()
    res = find(spec(), "medical", RunConfig(), lm=lm)
    kept = {h.paper: h for h in res.hits}
    assert set(kept) == {"A-1", "B-2"}
    assert "agent" in kept["B-2"].sources and "regex" in kept["A-1"].sources
    assert res.aliases == [{"subject": "drugx", "term": "DX-77", "paper": "A-1"}]
    assert res.dropped == []          # C-3 never names drugx or DX-77: not even a candidate
    for h in res.hits:
        assert h.passages
        for p in h.passages:
            assert CORPUS[h.paper][p.start:p.end] == p.text and p.quote.lower() in p.text.lower()
    assert any(p.kind == "table" and p.columns == ["time point"] for p in kept["A-1"].passages)
    assert any(p.role == "context" and p.columns == ["patient group"] for p in kept["A-1"].passages)
    assert res.coverage["gaps_after_agent"] == []
    assert res.agent[0]["kind"] == "other_name" and res.agent[0]["outcome"] == "searched"


def test_agent_off_misses_the_code_name_paper(setup):
    _, lm = setup()
    res = find(spec(), "medical", RunConfig(find=FindConfig(agent=False)), lm=lm)
    assert {h.paper for h in res.hits} == {"A-1"} and res.agent == []


def test_agent_steps_are_capped_by_code(setup):
    words = ["metformin", "adults", "older", "dose", "placebo", "daily", "tested", "measured"]
    fake, lm = setup(agent_reply=lambda f, n: {"kind": "search", "term": words[n - 1], "reason": "try"})
    s = spec().model_copy(update={"columns": ["time point", "patient group", "dose", "region"]})
    res = find(s, "medical", RunConfig(find=FindConfig(agent_max_steps=3)), lm=lm)
    assert len(res.agent) == 3 == fake.calls["kind"] == res.coverage["agent_steps"]
    assert any(g["name"] == "region" for g in res.coverage["gaps_after_agent"])


def test_agent_term_must_be_in_the_papers(setup):
    _, lm = setup(agent_reply=lambda f, n: {"kind": "other_name", "term": "ZZ-999", "reason": "made up"})
    res = find(spec(), "medical", RunConfig(find=FindConfig(agent_max_steps=1)), lm=lm)
    assert res.agent[0]["outcome"] == "term not in any paper" and res.aliases == []


def test_marks_with_a_quote_outside_the_passage_are_rejected(setup):
    _, lm = setup(bad_quotes=True)
    res = find(spec(), "medical", RunConfig(find=FindConfig(agent=False)), lm=lm)
    a1 = next(h for h in res.hits if h.paper == "A-1")
    assert all(p.role == "context" for p in a1.passages)
    assert a1.details["marks_rejected"] and a1.details["marks_rejected"][0]["why"] == "quote not in the passage"


def test_closed_book_finds_nothing(setup):
    fake, lm = setup()
    assert run(spec(), "medical", RunConfig(closed_book=True), lm=lm) == [] and fake.calls == {}


def test_an_absent_drug_cannot_borrow_another_drugs_name(setup):
    """A drug no paper names: the agent proposes a name it saw in the text (Otherdrug); code rejects the alias,
    because no paper writes that name next to the drug's own name (21 Nov: absent questions stay not reported)."""
    _, lm = setup(agent_reply=lambda f, n: {"kind": "other_name", "term": "Otherdrug", "reason": "seen"})
    s = spec().model_copy(update={"subjects": [Name(label="zelvoran", known=False)],
                                  "question": "How much does zelvoran lower HbA1c?"})
    res = find(s, "medical", RunConfig(find=FindConfig(agent_max_steps=2)), lm=lm)
    assert res.aliases == [] and all(e.get("alias_accepted") is not True for e in res.agent)


def test_spec_without_subject_or_measure_runs():
    s = spec().model_copy(update={"type": "list", "subjects": [], "measure": Name(label="", known=False)})
    text = spec_text(s)
    assert "Subject: any drug" in text and "Measure: any measure" in text


def test_a_quote_shortened_with_an_ellipsis_checks_piece_by_piece():
    """'At week 24, ... -0.55 percentage points for 20 mg' is a fair quote when both pieces are in the passage."""
    from evqa.find.pipeline import _Find
    f = _Find.__new__(_Find)
    text = "At week 24, the mean difference was -0.37 for 10 mg and -0.55 percentage points for 20 mg daily."
    assert f._quote_part("At week 24, ... -0.55 percentage points for 20 mg", text) == "-0.55 percentage points for 20 mg"
    assert f._quote_part("At week 24, the mean difference", text) == "At week 24, the mean difference"
    assert f._quote_part("-0.55 percentage points ... At week 24", text) is None          # pieces out of order
    assert f._quote_part("At week 24, ... -0.99 percentage points", text) is None         # a piece not there


def test_search_terms_are_checked_by_code_and_never_become_names(setup):
    """The model's wordings: a kept subject term makes a candidate the screen then judges; a term no paper writes,
    a target outside the spec and a general word are dropped with a reason."""
    fake, lm = setup(terms=[{"target": "drugx", "term": "Otherdrug"}, {"target": "measure", "term": "A1c"},
                            {"target": "measure", "term": "glycated haemoglobin"},
                            {"target": "metformin", "term": "Glucophage"}, {"target": "measure", "term": "change"}])
    res = find(spec(), "medical", RunConfig(find=FindConfig(agent=False)), lm=lm)
    why = {t["term"]: t["why"] for t in res.coverage["search_terms"]}
    assert why == {"Otherdrug": "", "A1c": "not in any paper", "glycated haemoglobin": "not in any paper",
                   "Glucophage": "target not in the spec", "change": "too general"}
    assert [h.paper for h in res.dropped] == ["C-3"] and res.dropped[0].sources == ["terms"]
    assert res.dropped[0].screen == "no" and {h.paper for h in res.hits} == {"A-1"}
    assert res.aliases == [] and fake.calls["terms"] == 1


def test_without_a_subject_the_measure_words_find_the_papers(setup):
    _, lm = setup()
    s = spec().model_copy(update={"type": "list", "subjects": [], "question": "Which studies report HbA1c?"})
    res = find(s, "medical", RunConfig(find=FindConfig(agent=False)), lm=lm)
    assert {h.paper for h in res.hits + res.dropped} == {"A-1", "B-2", "C-3"}


def test_search_terms_off_makes_no_call(setup):
    fake, lm = setup()
    find(spec(), "medical", RunConfig(find=FindConfig(agent=False, search_terms=False)), lm=lm)
    assert "terms" not in fake.calls
