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
    renamed = [{"p": "S1", "g": 0.1234567}, {"p": "S2", "g": 0.5}]            # other variable names: still a match
    assert ot.same_rows(renamed, a)
    extra = [{**r, "n": 1} for r in a]                                           # an extra column is reported only
    assert ot.same_rows(extra, a) and ot.extra_columns(extra, a) == ["n"]
    assert ot.same_rows([], []) and not ot.same_rows([], a)
    results = [{"fresh": True, "match_on_key": True, "match_on_run": False},
               {"fresh": False, "match_on_key": True, "match_on_run": None},
               {"fresh": True, "match_on_key": False, "match_on_run": True},
               {"fresh": True, "match_on_key": True, "match_on_run": True}]
    assert ot.summary(results) == {"questions": 4, "fresh_share": 0.75, "match_rate": 0.75,
                                   "match_on_run_rate": 2 / 3}


def _plan_of(line):
    from evidence.tests.test_plan_run import make_plan
    return make_plan().model_copy(update={"lines": [line]})


def _line(q, query, template=None):
    from evidence.plan import EvidenceLine
    return EvidenceLine(id="l1", question=q.question, query=query, template=template)


def test_check_with_a_plan_line() -> None:
    pytest.importorskip("evidence.kg.query")
    from evidence.kg.truthgraph import truth_store
    qs = ot.load_questions()
    q = qs[2]
    key = truth_store(q)
    run = lambda line, store=key: SimpleNamespace(plan=_plan_of(line), store=store)   # noqa: E731
    fresh = _line(q, q.sparql)
    saved = _line(q, q.sparql, "count")
    wrong = _line(q, qs[10].sparql)
    got = ot.check(run(fresh), q)
    assert got["fresh"] is True and got["match_on_key"] is True and got["match_on_run"] is True
    assert ot.check(run(saved), q)["fresh"] is False
    assert ot.check(run(wrong), q)["match_on_key"] is False
    empty = ox.Store()                                   # extraction lost everything: planning is still right
    lost = ot.check(run(fresh, empty), q)
    assert lost["match_on_key"] is True and lost["match_on_run"] is False


def test_questions_are_committed_before_the_checker() -> None:
    questions = ot.committed_at([ot.QUESTIONS, *ot.REFERENCE.glob("*.rq")])
    checker = ot.committed_at([ot.HERE / "check.py"])
    if questions is None or checker is None:
        pytest.skip("not committed yet")
    assert questions <= checker      # the questions were committed no later than (here: before) the checker


def test_check_fills_the_plans_choices_in_a_planner_shaped_query() -> None:
    """The planner keeps choices as placeholders ($threshold, $sides); check fills them from the plan (C1)."""
    pytest.importorskip("evidence.kg.query")
    from evidence.kg.truthgraph import truth_store
    q = ot.load_questions()[2]
    query = q.sparql.replace("WHERE {", "WHERE {\n  VALUES ?side { $sides }\n  FILTER($threshold > 0)\n", 1)
    query = "# params: threshold, sides\n" + query
    run = SimpleNamespace(plan=_plan_of(_line(q, query)), store=truth_store(q))
    got = ot.check(run, q)
    assert got["match_on_key"] is True and got["match_on_run"] is True


def test_offtemplate_command_loads_records_and_reports_a_failed_question(tmp_path) -> None:
    pytest.importorskip("evidence.kg.query")
    from evaluation import wholerun_cmd
    from evidence.kg.build import serialize
    from evidence.kg.truthgraph import truth_store
    from evidence.plan import write_plan
    first, second = ot.load_questions()[:2]
    runs = tmp_path / "runs"
    for q, query in ((first, first.sparql), (second, "SELECT ?x WHERE { ?x $nope ?y }")):
        (runs / q.id).mkdir(parents=True)
        write_plan(_plan_of(_line(q, query)), runs / q.id / "plan.json")
    (runs / first.id / "records.nq").write_bytes(serialize(truth_store(first)))
    report = wholerun_cmd.offtemplate(runs, tmp_path / "o")
    assert report["questions"][first.id]["match_on_run"] is True
    assert report["questions"][second.id]["failed"].startswith("failed: ")
    assert report["summary"]["questions"] == 2 and report["summary"]["match_rate"] == 0.5
