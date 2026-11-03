"""The off-template generality check. Tests that run queries need workstream W4's `evidence.kg` (query runner,
truth_store); they skip on a branch without it. The parse test needs only pyoxigraph."""
from __future__ import annotations

import re
from types import SimpleNamespace

import pyoxigraph as ox
import pytest

from evaluation.offtemplate import check as ot


def test_twelve_questions_with_reference_files() -> None:
    qs = ot.load_questions()
    assert len(qs) == 12 and len({q.id for q in qs}) == 12
    assert all(q.reference.is_file() and q.question.endswith("?") for q in qs)
    assert len(list(ot.REFERENCE.glob("*.rq"))) == 12


def test_reference_queries_parse() -> None:
    for q in ot.load_questions():
        ox.Store().query(q.sparql)           # a malformed query raises; an empty store answers with no rows


def test_reference_queries_parse_and_run() -> None:
    pytest.importorskip("evidence.kg.query")
    from evidence.kg.query import run_query
    from evidence.kg.truthgraph import truth_store
    qs = ot.load_questions()
    store = truth_store(qs[0])               # one answer key: all 12 questions share it
    answers = {q.id: run_query(store, q.sparql, {}) for q in qs}
    assert all(not a.empty for a in answers.values()), [i for i, a in answers.items() if a.empty]


def _shape(sparql: str) -> str:
    """A query without comments, prefixes, variable names or spacing."""
    body = re.sub(r"(?m)^\s*(#.*|PREFIX.*)$", "", sparql)
    body = re.sub(r"\?\w+", "?v", body)
    return re.sub(r"\s+", "", body)


def test_no_question_fits_a_template() -> None:
    pytest.importorskip("evidence.kg.query")
    from evidence.kg.query import template, templates
    saved = {_shape(template(n)): n for n in templates()}
    for q in ot.load_questions():
        assert _shape(q.sparql) not in saved, f"{q.id} equals the saved template {saved[_shape(q.sparql)]}"
        assert q.sparql.strip() != ""


def test_match_when_rows_equal() -> None:
    a = [{"paper": "S1", "gap": 0.1234567}, {"paper": "S2", "gap": 0.5}]
    b = [{"paper": "S2", "gap": 0.5}, {"gap": 0.12345671, "paper": "S1"}]
    assert ot.same_rows(a, b)
    assert not ot.same_rows(a, b[:1]) and not ot.same_rows(a, [{"paper": "S1", "gap": 0.2}, b[0]])
    assert ot.summary([{"fresh": True, "match": True}, {"fresh": False, "match": True},
                       {"fresh": True, "match": False}, {"fresh": True, "match": True}]) == {
        "questions": 4, "fresh_share": 0.75, "match_rate": 0.75}


def test_check_with_a_plan_line() -> None:
    pytest.importorskip("evidence.kg.query")
    from evidence.kg.truthgraph import truth_store
    q = ot.load_questions()[2]
    store = truth_store(q)
    fresh = SimpleNamespace(question=q.question, query=q.sparql, template=None)
    saved = SimpleNamespace(question=q.question, query=q.sparql, template="count")
    wrong = SimpleNamespace(question=q.question, query=ot.load_questions()[10].sparql, template=None)
    assert ot.check(SimpleNamespace(plan=SimpleNamespace(lines=[fresh]), store=store), q) == {"fresh": True, "match": True}
    assert ot.check(SimpleNamespace(plan=SimpleNamespace(lines=[saved]), store=store), q)["fresh"] is False
    assert ot.check(SimpleNamespace(plan=SimpleNamespace(lines=[wrong]), store=store), q)["match"] is False


def test_questions_are_committed_before_use() -> None:
    when = ot.committed_at([ot.QUESTIONS, *ot.REFERENCE.glob("*.rq")])
    if when is None:
        pytest.skip("not committed yet")
    assert when.year >= 2026
