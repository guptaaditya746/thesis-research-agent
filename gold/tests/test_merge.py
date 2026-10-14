"""gold/build.py merge rule: table rows by their key column, graph rows by identical edges."""
from __future__ import annotations

from gold.build import count_columns, key_column, merge_rows, norm

from .scripted import graph_concept, table_concept

N = iter(range(1, 1000))


def item(row, paper="p1", chunk=0, extracted_row=0):
    return {"id": f"c{next(N)}", "row": row, "paper_id": paper, "chunk": chunk, "extracted_row": extracted_row}


def cells(dataset, papers, count):
    return {"dataset": dataset, "papers": papers, "paper_count": count}


def test_norm_merges_spelling_variants_only():
    assert norm("Natural Questions") == norm("natural-questions") == norm("NaturalQuestions") == "naturalquestions"
    assert norm("NQ") != norm("Natural Questions")
    assert norm("—") == "—"


def test_key_and_count_columns():
    columns = table_concept()["answer_shape"]["columns"]
    assert key_column(columns) == "dataset"
    assert count_columns(columns) == {"paper_count": "papers"}
    fixture = [{"name": "author", "type": "Person"}, {"name": "first_author_papers", "type": "integer"},
               {"name": "papers", "type": "list<Paper>"}]
    assert count_columns(fixture) == {"first_author_papers": "papers"}
    assert count_columns([{"name": "items", "type": "list<string>"}, {"name": "total", "type": "integer"}]) == \
        {"total": "items"}
    assert count_columns([{"name": "year", "type": "integer"}, {"name": "papers", "type": "list<Paper>"}]) == {}
    assert key_column([{"name": "n", "type": "integer"}, {"name": "xs", "type": "list<string>"}]) is None


def shape(key, listed, list_type, integer):
    return [{"name": key, "type": "string"}, {"name": listed, "type": f"list<{list_type}>"},
            {"name": integer, "type": "integer"}]


def test_count_columns_are_named_as_counts_of_their_list():
    for name in ("paper_count", "papers_count", "num_papers", "n_papers", "number_of_papers", "total_papers",
                 "first_author_papers", "count", "total"):
        assert count_columns(shape("model", "papers", "Paper", name)) == {name: "papers"}, name
    assert count_columns(shape("venue", "studies", "Paper", "study_count")) == {"study_count": "studies"}


def test_integers_that_only_share_a_word_with_a_list_are_not_counts():
    for key, listed, list_type, name in (
            ("language", "tasks", "string", "num_speakers"), ("benchmark", "datasets", "Dataset", "dataset_size"),
            ("model", "papers", "Paper", "num_parameters"), ("benchmark", "measures", "string", "num_tasks"),
            ("model", "papers", "Paper", "paper_year"), ("model", "papers", "Paper", "num_examples"),
            ("model", "papers", "Paper", "total_params"), ("model", "papers", "Paper", "n_samples"),
            ("model", "datasets", "Dataset", "dataset_rank")):
        assert count_columns(shape(key, listed, list_type, name)) == {}, name
    two_lists = [{"name": "a", "type": "string"}, {"name": "xs", "type": "list<string>"},
                 {"name": "ys", "type": "list<string>"}, {"name": "count", "type": "integer"}]
    assert count_columns(two_lists) == {}  # which list? none


def test_a_value_that_is_not_a_count_is_kept_as_extracted():
    concept = {"answer_shape": {"kind": "table", "columns": shape("language", "tasks", "string", "num_speakers")}}
    rows = merge_rows(concept, [item({"language": "Swahili", "tasks": ["NER", "MT"], "num_speakers": 200000000})])
    assert rows[0]["cells"]["num_speakers"] == 200000000 and "conflicts" not in rows[0]
    concept = {"answer_shape": {"kind": "table", "columns": shape("model", "papers", "Paper", "num_parameters")}}
    rows = merge_rows(concept, [item({"model": "Llama-3-8B", "papers": ["p1"], "num_parameters": 8}),
                                item({"model": "llama-3-8b", "papers": ["p2"], "num_parameters": 8})])
    assert rows[0]["cells"] == {"model": "Llama-3-8B", "papers": ["p1", "p2"], "num_parameters": 8}


def test_table_rows_merge_by_key_with_lists_unioned_and_counts_recomputed():
    concept = table_concept()
    items = [item(cells("Natural Questions", ["p1"], 1), "p1"),
             item(cells("HotpotQA", ["p1"], 1), "p1", extracted_row=1),
             item(cells("natural-questions", ["p2", "p1"], 2), "p2"),
             item(cells("NaturalQuestions", ["P2"], None), "p2", chunk=3)]
    rows = merge_rows(concept, items)
    assert [r["key"] for r in rows] == ["naturalquestions", "hotpotqa"]
    nq = rows[0]
    assert nq["cells"] == {"dataset": "Natural Questions", "papers": ["p1", "p2"], "paper_count": 2}
    assert nq["candidates"] == [items[0]["id"], items[2]["id"], items[3]["id"]]
    assert nq["papers"] == ["p1", "p2"] and "conflicts" not in nq  # 1 and 2 differ only by the merge


def test_a_count_that_disagrees_with_its_own_row_is_kept_as_a_conflict():
    rows = merge_rows(table_concept(), [item(cells("MMLU", ["p1"], 5), "p1"), item(cells("mmlu", ["p2"], 1), "p2")])
    assert rows[0]["cells"]["paper_count"] == 2
    assert rows[0]["conflicts"] == {"paper_count": [2, 5]}
    alone = merge_rows(table_concept(), [item(cells("GSM8K", ["p1", "p2"], 3), "p1")])
    assert alone[0]["cells"]["paper_count"] == 2 and alone[0]["conflicts"] == {"paper_count": [2, 3]}
    unlisted = merge_rows(table_concept(), [item(cells("NQ", ["p1"], 1), "p1"), item(cells("nq", [], 4), "p2")])
    assert unlisted[0]["conflicts"] == {"paper_count": [1, 4]}  # listed nothing, counted 4


def test_other_cells_keep_the_first_value_and_list_conflicts():
    concept = {"answer_shape": {"kind": "table", "columns": [
        {"name": "model", "type": "string"}, {"name": "size", "type": "number"}, {"name": "open", "type": "boolean"}]}}
    rows = merge_rows(concept, [item({"model": "Llama", "size": None, "open": True}),
                                item({"model": "llama", "size": 8.0, "open": True}),
                                item({"model": "LLaMA", "size": 70.0, "open": None})])
    assert len(rows) == 1
    assert rows[0]["cells"] == {"model": "Llama", "size": 8.0, "open": True}
    assert rows[0]["conflicts"] == {"size": [8.0, 70.0]}


def test_count_without_list_values_is_kept():
    rows = merge_rows(table_concept(), [item(cells("X", [], 3)), item(cells("x", [], 3))])
    assert rows[0]["cells"]["paper_count"] == 3


def test_rows_without_a_key_are_never_merged_but_keep_their_facts_together():
    a = item(cells(None, ["p1"], 1), "p1", 0, 0)
    a2 = {**item(cells(None, ["p1"], 1), "p1", 0, 0)}
    b = item(cells(None, ["p2"], 1), "p2", 0, 0)
    rows = merge_rows(table_concept(), [a, a2, b])
    assert [r["candidates"] for r in rows] == [[a["id"], a2["id"]], [b["id"]]]
    assert all(r["key"] is None for r in rows)


def edge(source, target, metric=None):
    return {"source": source, "source_type": "Paper", "predicate": "evaluatesOn", "target": target,
            "target_type": "Dataset", "attributes": {"metric": metric}}


def test_identical_edges_merge():
    concept = graph_concept()
    items = [item(edge("p6", "HotpotQA"), "p6"), item(edge("p6", "hotpot-qa", "exact match"), "p6", 1),
             item(edge("p5", "HotpotQA"), "p5"), item(edge("p6", "HotpotQA", "F1"), "p6", 2)]
    rows = merge_rows(concept, items)
    assert len(rows) == 2
    first = rows[0]
    assert first["key"] == "Paper:p6 evaluatesOn Dataset:hotpotqa"
    assert first["cells"] == edge("p6", "HotpotQA", "exact match")
    assert first["conflicts"] == {"metric": ["exact match", "F1"]}
    assert first["candidates"] == [items[0]["id"], items[1]["id"], items[3]["id"]]
    assert rows[1]["cells"] == edge("p5", "HotpotQA")
