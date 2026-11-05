"""Review Focus: one evidence line crashes, the others finish, the line says "failed: <reason>" and the answer
says "missing: <line>". The main-answer rule is applied by code; a changed decision reaches the query that runs."""
from __future__ import annotations

import pytest

from evidence.plan import Decision, EvidenceLine, Plan, WordList
from evidence.planner.lines import apply_rule, run_lines

Q = "SELECT ?x WHERE { ?x a ev:Claim . FILTER(?n >= $threshold) }"


def plan_of(*lines: EvidenceLine, rule: str = "any_line", threshold: str = "0.01") -> Plan:
    return Plan(question="q", field="cs", lines=list(lines), main_rule=rule, clarifications=[],
                decisions=[Decision(id="d1", type="threshold", value=threshold, reason="r")],
                words=WordList(things={}, cues=[], written_by="fake", ontology_names={}))


def line(lid: str, query: str) -> EvidenceLine:
    return EvidenceLine(id=lid, question=f"question {lid}", query=query, template=None)


def runner(query: str, params: dict) -> list[dict]:
    if query == "BOOM":
        raise ValueError("bad query")
    if query == "SILENT":
        raise RuntimeError()
    return [] if query == "EMPTY" else [{"x": query}]


def test_a_crashing_line_does_not_stop_the_others():
    out = run_lines(plan_of(line("a", "A"), line("b", "BOOM"), line("c", "C")), runner)
    by = {x["id"]: x for x in out["lines"]}
    assert by["a"]["status"] == "done" and by["a"]["rows"] == [{"x": "A"}]
    assert by["c"]["status"] == "done"
    assert by["b"]["status"] == "failed" and by["b"]["text"] == "failed: bad query"
    assert out["answer"]["missing"] == ["missing: question b"]
    assert "missing: question b" in out["answer"]["text"]


def test_an_error_without_a_message_still_gives_a_reason():
    out = run_lines(plan_of(line("a", "SILENT")), runner)
    assert out["lines"][0]["text"] == "failed: RuntimeError"


def test_empty_answer_is_valid():
    out = run_lines(plan_of(line("a", "EMPTY")), runner)
    assert out["lines"][0]["text"] == "No evidence found" and out["lines"][0]["status"] == "done"
    assert out["answer"]["text"] == "No evidence found" and out["answer"]["missing"] == []


def test_a_line_that_could_not_be_planned_is_failed_not_run():
    seen: list[str] = []
    out = run_lines(plan_of(line("a", "")), lambda q, p: seen.append(q) or [])
    assert not seen and out["lines"][0]["text"].startswith("failed:")


def test_the_main_rule_is_applied_by_code():
    lines = (line("a", "A"), line("b", "EMPTY"), line("c", "EMPTY"))
    assert run_lines(plan_of(*lines, rule="any_line"), runner)["answer"]["rule_met"] is True
    assert run_lines(plan_of(*lines, rule="all_lines"), runner)["answer"]["rule_met"] is False
    assert run_lines(plan_of(*lines, rule="majority"), runner)["answer"]["rule_met"] is False
    assert apply_rule("majority", [True, True, False]) and not apply_rule("all_lines", [True, False])
    with pytest.raises(ValueError):
        apply_rule("free text", [True])


def test_a_changed_decision_reaches_the_query_that_runs():
    seen: list[dict] = []
    for threshold in ("0.01", "0.2"):
        run_lines(plan_of(line("a", Q), threshold=threshold), lambda q, p: seen.append(p) or [])
    assert [p["threshold"] for p in seen] == [0.01, 0.2]


def test_a_rank_line_names_the_best_thing_and_its_paper():
    """scilead-07 said only "Yes: ..."; a ranking question's answer names who is best (ties too), then the rule."""
    rows = {"RANK": [{"thing": "T-ConvS2S", "score": 31.89, "paper": "1808.08745v1"},
                     {"thing": "PG", "score": 31.89, "paper": "1704.04368"}, {"thing": "Lead-3", "score": 30.1, "paper": "x"}],
            "BEST": [{"kind": "result", "thing": "BART", "count": 4}, {"kind": "result", "thing": "T5", "count": 2}]}
    ranked = EvidenceLine(id="a", question="best?", query="RANK", template="rank")
    out = run_lines(plan_of(ranked), lambda q, p: rows[q], name_best=True)
    assert out["answer"]["text"] == ("Best: T-ConvS2S in 1808.08745v1, PG in 1704.04368 (score 31.89); "
                                     "Yes: the answer is yes when any line found evidence (1 of 1 lines found evidence)")
    assert out["answer"]["rule_met"] is True
    best = EvidenceLine(id="b", question="wins?", query="BEST", template="best")
    assert run_lines(plan_of(best), lambda q, p: rows[q], name_best=True)["answer"]["text"].startswith("Best: BART (4 wins); Yes:")
    assert run_lines(plan_of(line("c", "C")), runner, name_best=True)["answer"]["text"].startswith("Yes:")   # not a ranking
    assert run_lines(plan_of(ranked), lambda q, p: rows[q])["answer"]["text"].startswith("Yes:")   # v1: as before


def test_the_best_text_comes_from_the_rank_line_even_after_a_list_line():
    rows = {"LIST": [{"item": "SQuAD"}], "RANK": [{"thing": "BART", "score": 0.9, "paper": "P1"}]}
    plan = plan_of(EvidenceLine(id="a", question="which?", query="LIST", template=None),
                   EvidenceLine(id="b", question="best?", query="RANK", template="rank"))
    assert run_lines(plan, lambda q, p: rows[q], name_best=True)["answer"]["text"].startswith("Best: BART in P1")
