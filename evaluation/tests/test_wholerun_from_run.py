"""The engine run -> wholerun.Answer adapter (Wave 2 Task 8.1): what a plan run's answer.json and claims say, in the
shape `score` reads."""
from __future__ import annotations

import json
from pathlib import Path

from evaluation.wholerun import Answer, RealQuestion, from_run, score


def run_dir(tmp: Path, lines: list[dict], claims: list[dict] | None = None, synthesis: dict | None = None) -> Path:
    root = tmp / "run"
    root.mkdir()
    answer = {"system": "plan", "lines": lines, "answer": {"text": "x"}, "synthesis": synthesis or {"studies": []}}
    (root / "answer.json").write_text(json.dumps(answer), encoding="utf-8")
    rows = [{"item_id": f"cl-{n}", "evidence_type": "claim", "fields": c, "spans": [], "links": {}}
            for n, c in enumerate(claims or [])]
    (root / "evidence.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return root


def q(kind: str, gold: dict) -> RealQuestion:
    return RealQuestion("q1", "Which?", "cs", Path("."), gold, kind)  # type: ignore[arg-type]


def done(rows: list[dict], lid: str = "l1") -> dict:
    return {"id": lid, "question": "?", "status": "done", "rows": rows, "text": f"{len(rows)} found"}


def test_rank_of_paper_ids_reads_the_paper_column_of_the_first_answered_line(tmp_path: Path) -> None:
    gold = {"ranking": ["P2", "P1"], "papers": ["P1", "P2"]}
    root = run_dir(tmp_path, [{"id": "l0", "question": "?", "status": "failed", "rows": [], "text": "failed: x"},
                              done([{"thing": "m1", "score": 0.9, "paper": "P2"}, {"thing": "m2", "score": 0.8, "paper": "P1"},
                                    {"thing": "m3", "score": 0.7, "paper": "P2"}])])
    answer = from_run(root, q("rank", gold))
    assert answer.ranking == ["P2", "P1"]
    assert score(answer, q("rank", gold))["top1"] == 1


def test_rank_of_paper_ids_never_falls_back_to_another_column(tmp_path: Path) -> None:
    gold = {"ranking": ["P2", "P1"], "papers": ["P1", "P2"]}
    root = run_dir(tmp_path, [done([{"thing": "P2", "score": 0.9}, {"thing": "P1", "score": 0.8}])])
    assert from_run(root, q("rank", gold)).ranking == []


def test_rank_of_names_reads_the_first_column_even_when_a_paper_column_exists(tmp_path: Path) -> None:
    gold = {"ranking": ["GDC", "YSZ"], "papers": ["S1", "S2"]}
    root = run_dir(tmp_path, [done([{"thing": "GDC", "score": 9.0, "paper": "S2"}, {"thing": "YSZ", "score": 8.0, "paper": "S1"}])])
    assert from_run(root, q("rank", gold)).ranking == ["GDC", "YSZ"]


def test_list_takes_the_first_column_once_each(tmp_path: Path) -> None:
    root = run_dir(tmp_path, [done([{"item": "SQuAD", "papers": 2}, {"item": "MNLI", "papers": 1},
                                    {"item": "SQuAD", "papers": 1}])])
    assert from_run(root, q("list", {"items": []})).names == ["SQuAD", "MNLI"]


def test_compare_maps_effect_rows_to_directions_and_a_conclusion(tmp_path: Path) -> None:
    rows = [{"paper": "S1", "direction": "supports"}, {"paper": "S2", "direction": "contradicts"},
            {"paper": "S3", "direction": "supports"}, {"paper": "S4", "direction": "undetermined"}]
    answer = from_run(run_dir(tmp_path, [done(rows)]), q("compare", {"directions": {}}))
    assert answer.directions == {"S1": "improves", "S2": "worsens", "S3": "improves"}
    assert answer.conclusion == "improves"


def test_compare_falls_back_to_the_synthesis_studies(tmp_path: Path) -> None:
    synthesis = {"studies": [{"document": "S1", "direction": "neutral"}, {"document": "S2", "direction": "undetermined"}]}
    answer = from_run(run_dir(tmp_path, [], synthesis=synthesis), q("compare", {"directions": {}}))
    assert answer.directions == {"S1": "no_effect"} and answer.conclusion == "no_effect"


def test_claims_are_about_the_gold_conclusion_ids(tmp_path: Path) -> None:
    claims = [{"subject": "drug", "relation": "lowers", "direction": "improves"},
              {"subject": "drug", "relation": "helps", "direction": "improves"},
              {"subject": "drug", "relation": "hurts", "direction": "worsens"},
              {"subject": "drug", "relation": "is", "direction": None}]
    gold = {"conclusions": [{"id": "CD001", "direction": "improves"}]}
    answer = from_run(run_dir(tmp_path, [], claims=claims), q("claims", gold))
    assert answer.claims == [{"about": "CD001", "direction": "improves"}]
    assert score(answer, q("claims", gold))["recall"] == 1.0


def test_an_empty_run_gives_an_empty_answer(tmp_path: Path) -> None:
    assert from_run(run_dir(tmp_path, []), q("rank", {"ranking": ["a"]})) == Answer()


def test_the_real_rank_template_through_from_run_and_score(tmp_path: Path) -> None:
    """The saved `rank` template on a small store: things are methods, the gold is paper ids, top-1 is right."""
    from evidence.kg.query import run_query, template
    from evidence.tests.kg_support import ROLES, Doc, paper, register, restore
    from evidence.kg.build import build
    before = register()
    try:
        docs = []
        for pid, rows in {"A1": {"Alpha": 0.71, "Beta": 0.64}, "B2": {"Gamma": 0.80, "Alpha": 0.69}, "C3": {"Delta": 0.55}}.items():
            d = Doc(pid)
            for name, x in rows.items():
                d.value(name, x, metric="F1", population="SciERC")
            docs.append(d)
        store = build([paper(d.id) for d in docs], {d.id: d.items for d in docs}, ROLES, None)
    finally:
        restore(before)
    rows = run_query(store, template("rank"), {"context": "scierc", "metric": "F1"}).rows
    assert [(r["thing"], r["paper"]) for r in rows] == [("Gamma", "B2"), ("Alpha", "A1"), ("Beta", "A1"), ("Delta", "C3")]
    gold = {"ranking": ["B2", "A1", "C3"], "papers": ["A1", "B2", "C3"]}
    answer = from_run(run_dir(tmp_path, [done(rows)]), q("rank", gold))
    assert answer.ranking == ["B2", "A1", "C3"]
    result = score(answer, q("rank", gold))
    assert result["top1"] == 1 and result["kendall_tau"] == 1.0


def test_the_key_store_and_the_run_are_split_on_the_paper_column() -> None:
    from evaluation.realpapers.keystore import store
    from evaluation.wholerun import answer_column
    from evidence.kg.query import Answer as KgAnswer, run_query, template
    from evidence.kg.truthgraph import split
    records = [{"paper": p, "thing": p, "metric": "F1", "number": n, "higher_is_better": True, "context": "SQuAD",
                "settings": {"dataset": "SQuAD"}} for p, n in (("P1", 0.7), ("P2", 0.9))]
    gold_q = q("rank", {"ranking": ["P2", "P1"], "papers": ["P1", "P2"]})
    key = run_query(store(records), template("rank"), {"context": "squad", "metric": "F1"})
    ours = KgAnswer(rows=[{"thing": "MethodX", "score": 0.9, "paper": "P2"}, {"thing": "MethodY", "score": 0.7, "paper": "P1"}],
                    empty=False)
    column = answer_column(gold_q)
    assert split(ours, key, ["P2", "P1"], column) == "right"
    wrong = KgAnswer(rows=[{"thing": "MethodY", "score": 0.7, "paper": "P1"}, {"thing": "MethodX", "score": 0.9, "paper": "P2"}],
                     empty=False)
    assert split(wrong, key, ["P2", "P1"], column) == "extraction error"   # the key answers right; the run's order is wrong


def _squad_store():
    from evidence.kg.build import build
    from evidence.tests.kg_support import ROLES, Doc, paper, register, restore
    before = register()
    try:
        docs = []
        for pid, spelling, rows in (("A1", "squad", {"Alpha": 0.71, "Beta": 0.64}), ("B2", "SQuAD", {"Gamma": 0.80}),
                                    ("C3", "SQuAD2", {"Delta": 0.99})):
            d = Doc(pid)
            for name, x in rows.items():
                d.value(name, x, metric="F1", population=spelling)
            d.experiment("e1", {"task": "NER" if pid != "C3" else "QA", "dataset": spelling})
            docs.append(d)
        return build([paper(d.id) for d in docs], {d.id: d.items for d in docs}, ROLES, None)
    finally:
        restore(before)


def _no_header(text: str) -> str:
    """The planner writes no comment lines (the run adds the header)."""
    return chr(10).join(x for x in text.splitlines() if not x.startswith("#"))


def test_a_planner_written_literal_is_cleaned_in_code_rank(tmp_path: Path) -> None:
    """The planner fills the placeholder with the paper's wording, not through params; code cleans it before the run."""
    from evidence.kg.query import run_query, template
    sparql = _no_header(template("rank")).replace("$context_key", '"SQuAD"').replace("$metric", '"F1"')
    rows = run_query(_squad_store(), sparql, {}).rows
    gold = {"ranking": ["B2", "A1"], "papers": ["A1", "B2"]}
    answer = from_run(run_dir(tmp_path, [done(rows)]), q("rank", gold))
    assert answer.ranking == ["B2", "A1"] and score(answer, q("rank", gold))["top1"] == 1


def test_a_planner_written_literal_is_cleaned_in_code_list_for() -> None:
    from evidence.kg.query import run_query, template
    sparql = (_no_header(template("list_for")).replace("$list_field", "ev:setting_dataset").replace("$for_field_key", "kg:key_task")
              .replace("$for_value_key", '"Ner"'))
    rows = run_query(_squad_store(), sparql, {}).rows
    assert sorted(r["item"] for r in rows) == ["SQuAD", "squad"]


def test_include_of_several_papers_is_valid_sparql() -> None:
    from evidence.kg.query import run_query, template
    rows = run_query(_squad_store(), template("rank"), {"context": "SQuAD", "metric": "F1", "include": ["A1", "B2"]}).rows
    assert [r["paper"] for r in rows] == ["B2", "A1", "A1"]


def test_split_counts_a_paper_once_however_many_things_it_ranks() -> None:
    from evidence.kg.query import Answer as KgAnswer
    from evidence.kg.truthgraph import split
    rows = [{"thing": t, "paper": p} for t, p in (("G", "B2"), ("A", "A1"), ("B", "A1"), ("D", "C3"))]
    ours = KgAnswer(rows=rows, empty=False)
    assert split(ours, ours, ["B2", "A1", "C3"], "paper") == "right"
