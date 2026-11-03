"""Review Focus: one evidence line crashes, the others finish, the line says "failed: <reason>" and the answer
says "missing: <line>"."""
from __future__ import annotations

from evidence.plan import EvidenceLine, Plan, WordList
from evidence.planner.lines import run_lines


def plan_of(*lines: EvidenceLine) -> Plan:
    return Plan(question="q", field="cs", lines=list(lines), main_rule="all lines", decisions=[], clarifications=[],
                words=WordList(things={}, cues=[], written_by="fake", ontology_names={}))


def line(lid: str, query: str) -> EvidenceLine:
    return EvidenceLine(id=lid, question=f"question {lid}", query=query, template=None)


def runner(query: str) -> list[dict]:
    if query == "BOOM":
        raise ValueError("bad query")
    return [] if query == "EMPTY" else [{"x": query}]


def test_a_crashing_line_does_not_stop_the_others():
    out = run_lines(plan_of(line("a", "A"), line("b", "BOOM"), line("c", "C")), runner)
    by = {x["id"]: x for x in out["lines"]}
    assert by["a"]["status"] == "done" and by["a"]["rows"] == [{"x": "A"}]
    assert by["c"]["status"] == "done"
    assert by["b"]["status"] == "failed" and by["b"]["text"] == "failed: bad query"
    assert out["answer"]["missing"] == ["missing: question b"]
    assert "missing: question b" in out["answer"]["text"]


def test_empty_answer_is_valid():
    out = run_lines(plan_of(line("a", "EMPTY")), runner)
    assert out["lines"][0]["text"] == "No evidence found" and out["lines"][0]["status"] == "done"
    assert out["answer"]["text"] == "No evidence found" and out["answer"]["missing"] == []


def test_a_line_that_could_not_be_planned_is_failed_not_run():
    seen: list[str] = []
    out = run_lines(plan_of(line("a", "")), lambda q: seen.append(q) or [])
    assert not seen and out["lines"][0]["text"].startswith("failed:")
