"""gold/export.py: the decision rule, missing facts anchored with agent/anchor.py, rows in the concept's
shape, and a key.json that validates as an answer once the gold-only fields are stripped."""
from __future__ import annotations

import json
from pathlib import Path

from agent import schema
from agent.concept import answer_schema_for, concept_sha256, validate_answer
from agent.tests.conftest import fixture
from gold import export, review

from .fixtures import ANSWERS, CONCEPT, MISSING_LINES, NQ, OCR_VQA, QID, Env, cid, env, pulled  # noqa: F401


def store_answers(e: Env, answers: dict[str, dict] = ANSWERS, missing: str = MISSING_LINES) -> None:
    review.store(e.root, {
        "review": [pulled(rid, "review", {"aditya": values}) for rid, values in answers.items()],
        "missing": [pulled(f"missing-{QID}", "missing", {"aditya": {"missing": missing, "done": "yes"}})]})


def run(e: Env, **kw) -> export.Export:
    return export.export(e.root, QID, corpus=review.Corpus(e.corpus), concepts=e.concepts, **kw)


def facts_by_candidate(key: dict) -> dict:
    return {f["candidate_id"]: (row, f) for row in key["rows"] for f in row["facts"]}


def test_key_validates_as_an_answer_after_stripping_gold_only_fields(env: Env) -> None:
    store_answers(env)
    done = run(env)
    assert done.key is not None, done.problems
    key = json.loads((env.root / QID / "key.json").read_text(encoding="utf-8"))
    assert key == done.key
    assert (key["qid"], key["version"], key["reviewed"], key["kind"]) == (QID, "v1", True, "graph")
    assert key["concept_sha256"] == concept_sha256(CONCEPT)
    stripped = {"concept_sha256": key["concept_sha256"], "kind": key["kind"], "notes": key["notes"],
                "rows": [{**row, "facts": [{k: v for k, v in f.items()
                                            if k not in ("paper_id", "quote", "vital", "candidate_id")}
                                           for f in row["facts"]]} for row in key["rows"]]}
    assert schema.errors(answer_schema_for(CONCEPT), stripped) == []
    assert validate_answer(stripped, CONCEPT) == []
    assert export.as_answer(key) == stripped


def test_kept_corrected_vital_and_dropped(env: Env) -> None:
    store_answers(env)
    key = run(env).key
    by = facts_by_candidate(key)
    assert set(by) == {cid(1), cid(2), cid(3), cid(4), None}  # c5, c6 incorrect; c7 unsure
    row, fact = by[cid(2)]
    assert (fact["s"], fact["p"], fact["o"]) == ("p1", "evaluatesOn", "BIRD")  # " | | BIRD" fixes the object
    assert row["target"] == "BIRD"  # the row follows the fix
    assert fact["quote"] == "deployable LLMs using benchmark datasets like Spider and Bird"
    assert [by[cid(n)][1]["vital"] for n in (1, 2, 3, 4)] == [True, False, True, False]
    assert all(f["claims"] == [] and f["origin"] == "research" for _, f in by.values())
    assert key["review"]["kept"] == 4 and key["review"]["unsure"] == 1 and key["review"]["complete"]
    report = json.loads((env.root / QID / "export.json").read_text(encoding="utf-8"))
    assert report["unsure"] == [{"candidate_id": cid(7), "user": "aditya", "note": "authorship, not a dataset"}]


def test_missing_facts_are_anchored_or_rejected(env: Env) -> None:
    store_answers(env)
    done = run(env)
    added = [f for row in done.key["rows"] for f in row["facts"] if f["candidate_id"] is None]
    assert [(f["o"], f["paper_id"], f["quote"]) for f in added] == [("NQ", "p6", NQ.text), ("OCR-VQA", "p6", OCR_VQA.text)]
    assert {r["reason"] for r in done.report["rejected"]} == {"not_found", "format", "unknown_file"}
    assert done.key["review"]["added"] == 2 and done.key["review"]["added_rejected"] == 3
    anchors = {a["o"]: a["anchor"] for a in done.report["added"]}
    text = review.Corpus(env.corpus).text("p6.md")
    assert text[anchors["NQ"]["start"]:anchors["NQ"]["end"]] == NQ.text


def test_overlap_disagreement_listed_then_adjudicated() -> None:
    items = {"c1": {"id": "c1", "s": "p1", "p": "evaluatesOn", "o": "Spider"},
             "c2": {"id": "c2", "s": "p1", "p": "evaluatesOn", "o": "BIRD"}}
    records = [pulled("c1", "overlap", {"ann": {"label": "correct", "vital": "yes"}, "bob": {"label": "incorrect"}}),
               pulled("c2", "overlap", {"ann": {"label": "correct", "vital": "yes"},
                                        "bob": {"label": "correct", "vital": "no"}})]
    plain = export.decide(items, records)
    assert [d["candidate_id"] for d in plain.disagreements] == ["c1"]
    assert [(d.candidate_id, d.keep, d.vital) for d in plain.decisions] == [("c2", True, False)]  # vital only if both
    third = [pulled("c1", "overlap", {"ann": {"label": "correct"}, "bob": {"label": "incorrect"},
                                      "carol": {"label": "correct"}}), records[1]]
    by_third = export.decide(items, third, adjudicator="carol")
    assert by_third.adjudicated == 1 and by_third.adjudicated_by_a_rater == 0
    assert by_third.disagreements[0]["resolved_by"] == "carol"
    assert next(d for d in by_third.decisions if d.candidate_id == "c1").keep
    by_rater = export.decide(items, records, adjudicator="bob")
    assert by_rater.adjudicated_by_a_rater == 1
    assert not next(d for d in by_rater.decisions if d.candidate_id == "c1").keep


def test_different_fixes_are_a_disagreement_and_bad_fix_drops() -> None:
    items = {"c1": {"id": "c1", "s": "p1", "p": "evaluatesOn", "o": "Spider"}}
    fixes = export.decide(items, [pulled("c1", "overlap", {"a": {"label": "correct", "correction": "||Spider 1.0"},
                                                          "b": {"label": "correct", "correction": "||Spider 2.0"}})])
    assert len(fixes.disagreements) == 1 and not fixes.decisions
    bad = export.decide(items, [pulled("c1", "review", {"a": {"label": "correct", "correction": "Spider only"}})])
    assert not bad.decisions[0].keep and "not `s | p | o`" in bad.problems[0]
    assert not export.would_keep({"label": "correct", "correction": "two | parts"})
    assert export.would_keep({"label": "correct", "correction": ""})
    assert not export.would_keep({"label": "unsure"})


def test_unanswered_drafts_do_not_count() -> None:
    items = {"c1": {"id": "c1", "s": "p1", "p": "evaluatesOn", "o": "Spider"}}
    decided = export.decide(items, [pulled("c1", "review", {"a": {"label": "correct"}}, status="draft")])
    assert decided.unreviewed == ["c1"] and not decided.decisions


def test_stale_concept_writes_no_key(env: Env) -> None:
    store_answers(env)
    doc = review.read_json(env.root / QID / "doc.json")
    review.write_json(env.root / QID / "doc.json", {**doc, "concept_sha256": "f" * 64})
    done = run(env)
    assert done.key is None and not (env.root / QID / "key.json").exists()
    assert any("rebuild D" in p for p in done.problems)
    assert (env.root / QID / "export.json").exists()


def test_graph_rows_merge_and_unknown_predicate_is_left_out() -> None:
    def fact(n: int, s: str, p: str, o: str) -> dict:
        return {"s": s, "p": p, "o": o, "paper_id": s, "quote": "q", "vital": n == 2, "candidate_id": f"c{n}"}

    edge = {"source": "p1", "source_type": "Paper", "predicate": "evaluatesOn", "target": "Spider",
            "target_type": "Dataset", "attributes": {"metric": "EM"}}
    rows, merged, problems = export.merge_rows(CONCEPT, [
        (edge, fact(1, "p1", "evaluatesOn", "Spider")),
        ({**edge, "attributes": {}}, fact(2, "p1", "evaluates on", "Spider")),  # same row, same fact (C1's norm)
        ({**edge, "predicate": "cites"}, fact(3, "p1", "cites", "p2")),
        (None, fact(4, "p9", "evaluates on", "MMLU")),  # an added fact: the only edge type fits
        ({**edge, "target": "spider."}, fact(5, "p1", "evaluatesOn", "Spider.")),  # C1's norm: the same row
    ])
    assert [(r["id"], r["source"], r["target"], r["attributes"]) for r in rows] == [
        ("r1", "p1", "Spider", {"metric": "EM"}), ("r2", "p9", "MMLU", {"metric": None})]
    assert len(rows[0]["facts"]) == 1 and rows[0]["facts"][0]["vital"]  # c2 merged into c1, vital from c2
    assert [m["merged"] for m in merged] == ["c2", "c5"] and "no edge type" in problems[0]


def test_edge_type_follows_the_row_types() -> None:
    """One predicate between two type pairs: the row's types pick the edge, not the name alone."""
    concept = {**CONCEPT, "answer_shape": {**CONCEPT["answer_shape"], "nodes": [
        {"type": "Paper"}, {"type": "Model"}, {"type": "Dataset"}, {"type": "Metric"}], "edges": [
        {"source": "Paper", "predicate": "evaluatesOn", "target": "Dataset", "attributes": []},
        {"source": "Model", "predicate": "evaluatesOn", "target": "Dataset", "attributes": []}]}}
    row = {"source": "GPT-4", "source_type": "Model", "predicate": "evaluatesOn", "target": "MMLU",
           "target_type": "Dataset"}
    fact = {"s": "GPT-4", "p": "evaluatesOn", "o": "MMLU", "paper_id": "p1", "quote": "q", "vital": False,
            "candidate_id": "c1"}
    rows, _, problems = export.merge_rows(concept, [(row, fact), (None, {**fact, "candidate_id": None})])
    assert rows[0]["source_type"] == "Model" and not problems[:-1]
    assert rows[1]["source_type"] == "Paper"  # no types given: the first of the two, said so
    assert "several edge types fit" in problems[-1]
    edge, problem = export.pick_edge(concept["answer_shape"]["edges"], {**row, "source_type": "Person"}, fact)
    assert edge is None and "no edge type Person -evaluatesOn-> Dataset" in problem


def test_table_rows_merge_by_first_column() -> None:
    concept = fixture("concept_table.json")  # author, first_author_papers (integer), papers (list<Paper>)

    def fact(n: int, s: str, p: str, o: str) -> dict:
        return {"s": s, "p": p, "o": o, "paper_id": s, "quote": "q", "vital": False, "candidate_id": f"c{n}"}

    rows, _, problems = export.merge_rows(concept, [
        ({"cells": {"author": "Author A", "first_author_papers": "2", "papers": "p12"}}, fact(1, "p12", "firstAuthor", "Author A")),
        ({"author": "author a", "papers": ["p87"]}, fact(2, "p87", "firstAuthor", "Author A")),
        ({"author": "Author B", "first_author_papers": "many"}, fact(3, "p40", "firstAuthor", "Author B")),
        (None, fact(4, "Author B", "papers", "p41")),  # joins the row its subject names, and adds to its cells
        (None, fact(5, "Author C", "papers", "p50")),  # a new row from the fact
        (None, fact(6, "p88", "papers", "Author A")),  # only its object names a row: it joins that row
    ])
    # C1's rule: the key column normalised (Author A = author a), lists unioned, a count of a list recomputed.
    assert [r["cells"] for r in rows] == [
        {"author": "Author A", "first_author_papers": 3, "papers": ["p12", "p87", "p88"]},
        {"author": "Author B", "first_author_papers": 1, "papers": ["p41"]},
        {"author": "Author C", "first_author_papers": 1, "papers": ["p50"]}]
    assert [len(r["facts"]) for r in rows] == [3, 2, 1] and not problems
    answer = {"concept_sha256": concept_sha256(concept), "kind": "table",
              "rows": [{**r, "facts": [{k: v for k, v in f.items() if k not in export.GOLD_ONLY} for f in r["facts"]]}
                       for r in rows]}
    assert validate_answer(answer, concept) == []


def test_coerce() -> None:
    assert export.coerce("1,024", "integer") == 1024 and export.coerce("2.5", "integer") is None
    assert export.coerce("0.5", "number") == 0.5 and export.coerce(True, "integer") is None
    assert export.coerce("p1", "list<Paper>") == ["p1"] and export.coerce([], "list<Paper>") is None
    assert export.coerce("True", "boolean") is True and export.coerce("", "string") is None


def test_export_needs_a_concept(env: Env, tmp_path: Path) -> None:
    done = export.export(env.root, QID, corpus=review.Corpus(env.corpus), concepts=tmp_path / "none")
    assert done.key is None and "no concept.json" in done.problems[0]
