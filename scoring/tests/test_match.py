"""scoring/normalise.py and scoring/match.py on hand-built answers and keys (table and graph shapes)."""
from __future__ import annotations

from typing import Any

import pytest

from agent.concept import concept_sha256, validate_answer
from agent.tests.conftest import fixture
from scoring.match import assign, match, prf
from scoring.normalise import fact_norm, norm, paper_id, strict, text

from .helpers import edge_row, gold_fact, judge

TABLE = fixture("concept_table.json")  # author | first_author_papers | papers (list<Paper>)
GRAPH = fixture("concept_graph.json")  # Paper evaluatesOn Dataset, attribute metric


# --- normalisation --------------------------------------------------------------------------------------

@pytest.mark.parametrize("a, b", [
    ("evaluatesOn", "evaluates on"), ("evaluates_on", "Evaluates-On"), ("Natural Questions", "NaturalQuestions"),
    ("GPT-4o", "gpt4o"), ("1,000", 1000), ("12.50", 12.5), (" 2 ", 2), ("2.0", 2), ("85%", "85 percent"),
    ("Résumé", "résumé"), ("−3", "-3"), ("ﬁne-tuning", "fine tuning"), (True, "true"),
    ("p012.md", "p12"), ("$CORPUS/p12.md", "P12"), ("2025.acl-long.892", "2025-acl-long-892.md"),
    (["p12", "p87"], ["p87.md", "p12", "p12"]),
])
def test_normalised_equal(a: Any, b: Any) -> None:
    assert norm(a) == norm(b)


@pytest.mark.parametrize("a, b", [
    ("1 5", "15"), ("-3.2", "3.2"), ("12.5", "125"), ("p12", "p120"), ("Llama 3 8B", "Llama 38B"),
    (2, 3), (["p12"], ["p12", "p87"]), ("GPT-4", "GPT 4o"),
])
def test_normalised_different(a: Any, b: Any) -> None:
    assert norm(a) != norm(b)


def test_strict_is_as_typed() -> None:
    assert strict(2) == strict("2") == strict(" 2 ")
    assert strict("evaluatesOn") != strict("evaluates on")
    assert strict(2.0) != strict(2)  # 2.0 and 2 only meet at the normalised level
    assert paper_id("Spider") is None and paper_id("2025-emnlp-main-1032.md") == "2025-emnlp-main-1032"
    assert text("GPT-4 vs -4") == "gpt<4>vs<-4>"  # a minus only where no word precedes it
    assert fact_norm({"s": "p12.md", "p": "first author", "o": "Author A"}) == ("paper:p12", "firstauthor", "authora")


# --- the assignment --------------------------------------------------------------------------------------

def test_assignment_is_one_to_one_and_prefers_pairs_then_vital_then_strict() -> None:
    # Greedy would give run 0 its strict partner key 0 and leave run 1 without one.
    assert assign(2, 2, {(0, 0): 3, (0, 1): 1, (1, 0): 1}, 1) == [(0, 1, 1), (1, 0, 1)]
    # One run fact, two candidates: the vital gold fact wins over a stricter match ...
    assert assign(1, 2, {(0, 0): 1, (0, 1): 3}, 1, vital=[True, False]) == [(0, 0, 1)]
    # ... and without vital facts the stricter match wins.
    assert assign(1, 2, {(0, 0): 2, (0, 1): 3}, 1) == [(0, 1, 3)]
    assert assign(1, 2, {(0, 0): 2, (0, 1): 3}, 3) == [(0, 1, 3)]
    assert assign(2, 2, {}, 1) == []


def test_prf_conventions() -> None:
    assert prf(0, 0, 4) == {"tp": 0, "fp": 0, "fn": 4, "precision": 0.0, "recall": 0.0, "f1": 0.0}  # empty answer
    assert prf(0, 3, 0)["recall"] is None and prf(0, 3, 0)["f1"] is None  # empty key
    assert prf(2, 4, 4)["f1"] == pytest.approx(0.5)


# --- table answers ---------------------------------------------------------------------------------------

def fact(n: int, s: str, p: str, o: Any) -> dict[str, Any]:
    return {"id": f"f{n}", "s": s, "p": p, "o": o, "claims": [], "origin": "research"}


def table_row(n: int, author: str, count: int, papers: list[str], facts: list[dict[str, Any]]) -> dict[str, Any]:
    return {"id": f"r{n}", "cells": {"author": author, "first_author_papers": count, "papers": papers}, "facts": facts}


def table_answer() -> dict[str, Any]:
    rows = [
        table_row(1, "author a", 2, ["P12.md", "p087"], [
            fact(1, "p12", "firstAuthor", "Author A"),  # strict -> k1
            fact(2, "p87", "first author", "author a"),  # normalised -> k2
            fact(3, "p12", "published at", "ACL 2025 main"),  # judge -> k3
            fact(4, "p87", "publishedAt", "ACL 2025")]),  # not in the key; rejected by reviewers
        table_row(2, "Author B", 1, ["p40"], [  # the key counts 2 papers: the row is wrong
            fact(5, "p40", "firstAuthor", "Author B"),  # strict -> k4
            fact(6, "p12", "firstAuthor", "Author A")]),  # f1 again: one fact
        table_row(3, "Author A", 2, ["p12", "p87"], [fact(7, "p12", "firstAuthor", "Author A")]),  # r1 again
    ]
    answer = {"concept_sha256": concept_sha256(TABLE), "kind": "table", "rows": rows}
    assert validate_answer(answer, TABLE) == []
    return answer


def table_key() -> dict[str, Any]:
    return {"qid": "q02", "concept_sha256": concept_sha256(TABLE), "kind": "table", "version": "v1", "reviewed": True,
            "rows": [
                table_row(1, "Author A", 2, ["p12", "p87"], [
                    gold_fact(1, "p12", "firstAuthor", "Author A", vital=True),
                    gold_fact(2, "p87", "firstAuthor", "Author A", vital=True),
                    gold_fact(3, "p12", "publishedAt", "ACL 2025")]),
                table_row(2, "Author B", 2, ["p40", "p41"], [
                    gold_fact(4, "p40", "firstAuthor", "Author B", vital=True),
                    gold_fact(5, "p41", "firstAuthor", "Author B")]),
                table_row(3, "Author C", 1, ["p50"], [gold_fact(6, "p50", "firstAuthor", "Author C")]),
            ],
            "rejected": [{"s": "p87", "p": "publishedAt", "o": "ACL 2025", "verdict": "wrong"}]}


def test_table_facts_at_three_levels() -> None:
    j, fake = judge(same_facts={("ACL 2025 main", "ACL 2025")})
    facts = match(table_answer(), table_key(), TABLE, j)["facts"]
    # 5 run facts (f6 is f1 again), 6 gold facts of which 3 vital.
    s, n, soft = facts["levels"]["strict"], facts["levels"]["normalised"], facts["levels"]["soft"]
    assert (s["tp"], s["fp"], s["fn"], s["vital_tp"], s["vital"]) == (2, 3, 4, 2, 3)
    assert (s["precision"], s["recall"]) == (pytest.approx(2 / 5), pytest.approx(2 / 6))
    assert s["f1"] == pytest.approx(2 * 0.4 * (1 / 3) / (0.4 + 1 / 3))
    assert (n["tp"], n["vital_tp"], n["vital_recall"]) == (3, 3, 1.0)
    assert n["f1"] == pytest.approx(2 * 0.6 * 0.5 / 1.1)
    assert (soft["tp"], soft["precision"], soft["recall"]) == (4, pytest.approx(0.8), pytest.approx(4 / 6))
    assert soft["f1"] == pytest.approx(2 * 0.8 * (4 / 6) / (0.8 + 4 / 6))
    levels = {p["run"]["fact"]: (p["key"]["fact"], p["level"]) for p in facts["pairs"]}
    assert levels == {"f1": ("f1", "strict"), "f2": ("f2", "normalised"), "f3": ("f3", "soft"), "f5": ("f4", "strict")}
    assert facts["duplicates"] == 2 and [p["run_same"] for p in facts["pairs"] if p["run"]["fact"] == "f1"] == [
        [{"row": "r2", "fact": "f6"}, {"row": "r3", "fact": "f7"}]]
    assert sorted(m["key"]["fact"] for m in facts["missed"]) == ["f5", "f6"]
    assert [(e["run"]["fact"], e["wrong"]) for e in facts["extra"]] == [("f4", True)]
    assert facts["judged_precision"] == {"correct": 4, "wrong": 1, "precision": 0.8, "coverage": 1.0}
    # The judge sees same-subject pairs where one side is left over after the normalised level, and
    # only {s, p, o}: (f1, k3), (f3, k1), (f3, k3), (f4, k2). f5-k4 are both matched: not asked.
    asked = [(r["o"], k["o"], r["p"], k["p"]) for r, k in fake.asked("same_fact")]
    assert sorted(asked) == sorted([("Author A", "ACL 2025", "firstAuthor", "publishedAt"),
                                    ("ACL 2025 main", "Author A", "published at", "firstAuthor"),
                                    ("ACL 2025 main", "ACL 2025", "published at", "publishedAt"),
                                    ("ACL 2025", "Author A", "publishedAt", "firstAuthor")])
    assert all(set(r) == set(k) == {"s", "p", "o"} for r, k in fake.asked("same_fact"))


def test_table_rows_set_f1() -> None:
    j, fake = judge()
    rows = match(table_answer(), table_key(), TABLE, j)["rows"]
    # r3 repeats r1; r2's count differs from the key's (counts compare exactly), so only r1 matches.
    assert rows["duplicates"] == 1
    assert rows["levels"]["normalised"] == {"tp": 1, "fp": 1, "fn": 2, "precision": 0.5, "recall": pytest.approx(1 / 3),
                                            "f1": pytest.approx(0.4)}
    assert rows["levels"]["soft"] == rows["levels"]["normalised"]
    assert rows["pairs"] == [{"run": "r1", "key": "r1", "level": "normalised", "run_same": ["r3"]}]
    assert (rows["missed"], rows["extra"]) == (["r2", "r3"], ["r2"])
    # Only r2 and the key's Author B row share a value; the judge sees the rows without their facts.
    [(run_row, key_row)] = fake.asked("same_row")
    assert run_row["cells"]["author"] == key_row["cells"]["author"] == "Author B" and "facts" not in run_row
    j, _ = judge(same_rows={("Author B", "Author B")})
    soft = match(table_answer(), table_key(), TABLE, j)["rows"]["levels"]["soft"]
    assert (soft["tp"], soft["f1"]) == (2, pytest.approx(2 * (2 / 2) * (2 / 3) / (1 + 2 / 3)))


def test_null_key_cell_is_not_compared() -> None:
    key = table_key()
    key["rows"][1]["cells"]["first_author_papers"] = None  # the gold could not establish the count
    key["rows"][1]["cells"]["papers"] = None
    rows = match(table_answer(), key, TABLE)["rows"]
    assert rows["levels"]["normalised"]["tp"] == 2


def test_no_judge_means_soft_equals_normalised_and_no_rejected_list() -> None:
    key = table_key()
    del key["rejected"]
    facts = match(table_answer(), key, TABLE, None)["facts"]
    assert facts["levels"]["soft"] == facts["levels"]["normalised"]
    assert facts["judged_precision"]["precision"] is None and facts["judged_precision"]["wrong"] is None


# --- graph answers ---------------------------------------------------------------------------------------

def graph_answer() -> dict[str, Any]:
    rows = [
        edge_row(1, "p12", "HotpotQA", [fact(1, "p12", "evaluatesOn", "HotpotQA"),
                                        fact(2, "p12", "reportsMetric", "exact match")], metric="exact match"),
        edge_row(2, "p30.md", "NaturalQuestions", [fact(3, "p30", "evaluates on", "NaturalQuestions")]),
        edge_row(3, "p30", "TQA", [fact(4, "p30", "evaluatesOn", "TQA")]),
        edge_row(4, "p31", "SQuAD", [fact(5, "p31", "evaluatesOn", "SQuAD")]),
    ]
    answer = {"concept_sha256": concept_sha256(GRAPH), "kind": "graph", "rows": rows}
    assert validate_answer(answer, GRAPH) == []
    return answer


def graph_key() -> dict[str, Any]:
    return {"qid": "q01", "concept_sha256": concept_sha256(GRAPH), "kind": "graph", "version": "v1", "reviewed": True,
            "rows": [
                edge_row(1, "p12", "HotpotQA", [gold_fact(1, "p12", "evaluatesOn", "HotpotQA", vital=True),
                                                gold_fact(2, "p12", "reportsMetric", "EM")], metric="EM"),
                edge_row(2, "p30", "Natural Questions", [gold_fact(3, "p30", "evaluatesOn", "Natural Questions")]),
                edge_row(3, "p30", "TriviaQA", [gold_fact(4, "p30", "evaluatesOn", "TriviaQA", vital=True)]),
            ]}


def test_graph_rows_match_on_the_edge() -> None:
    j, fake = judge(same_rows={("TQA", "TriviaQA")}, same_facts={("TQA", "TriviaQA"), ("exact match", "EM")})
    result = match(graph_answer(), graph_key(), GRAPH, j)
    rows = result["rows"]
    # r1 matches although its metric attribute differs (attributes are scored through their facts);
    # r2 once normalised (paper alias, spacing); r3 by the judge; r4 is not in the key.
    assert [(p["run"], p["key"], p["level"]) for p in rows["pairs"]] == [
        ("r1", "r1", "normalised"), ("r2", "r2", "normalised"), ("r3", "r3", "soft")]
    assert rows["levels"]["normalised"]["tp"] == 2 and rows["levels"]["soft"]["tp"] == 3
    assert rows["levels"]["soft"]["precision"] == 0.75 and rows["levels"]["soft"]["recall"] == 1.0
    # The judge is asked about edges with the same source where one side is left over: r3 against the
    # key's p30 rows, and r2 (matched) against the key's left-over p30 row.
    assert sorted((r["target"], k["target"]) for r, k in fake.asked("same_row")) == [
        ("NaturalQuestions", "TriviaQA"), ("TQA", "Natural Questions"), ("TQA", "TriviaQA")]
    facts = result["facts"]["levels"]
    assert (facts["strict"]["tp"], facts["normalised"]["tp"], facts["soft"]["tp"]) == (1, 2, 4)
    assert (facts["strict"]["vital_recall"], facts["soft"]["vital_recall"]) == (0.5, 1.0)
    assert facts["soft"]["precision"] == 0.8 and facts["soft"]["recall"] == 1.0
