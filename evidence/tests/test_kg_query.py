import json
from pathlib import Path

import pytest
from pyoxigraph import Store

from evidence.kg import after
from evidence.kg.build import build
from evidence.kg.query import NO_EVIDENCE, run_query, run_template, templates
from evidence.protocol import load
from evidence.rundir import RunDir

from .kg_support import ROLES, Doc, paper, register, restore

REPO = Path(__file__).resolve().parents[2]
EV2_RUN = REPO / "tests" / "EV2" / "runs" / "cascade-gaps-escalate" / "rag-claude-pilot-complex-escalate"


@pytest.fixture(autouse=True)
def _registry():
    before = register()
    yield
    restore(before)


def graph(*docs: Doc) -> Store:
    return build([paper(d.id) for d in docs], {d.id: d.items for d in docs}, ROLES, None)


def test_every_old_answer_kind_is_a_saved_template():
    assert set(templates()) >= {"effect", "consistency", "best", "rank", "inventory", "list_for", "count",
                                "chaining_path", "builds_on", "oversell"}


def test_rank_matches_leaderboard_fixture():
    board = {"p1": {"Alpha": 0.71, "Beta": 0.64}, "p2": {"Gamma": 0.80, "Alpha": 0.69},
             "p3": {"Delta": 0.55}, "p4": {"Beta": 0.66, "Epsilon": 0.40}}
    docs = []
    for pid, rows in board.items():
        d = Doc(pid)
        for name, x in rows.items():
            d.value(name, x, metric="F1", population="SciERC")
        d.value("Other", 0.99, metric="F1", population="OtherSet")   # another dataset: not on this board
        docs.append(d)
    best: dict[str, float] = {}
    for rows in board.values():
        for name, x in rows.items():
            best[name] = max(best.get(name, 0), x)
    expected = sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))
    answer = run_template(graph(*docs), "rank", {"context": "SciERC", "metric": "F1"})
    assert [(r["thing"], r["score"]) for r in answer.rows] == expected


def test_rank_follows_the_metric_direction():
    d = Doc("p1")
    d.value("Alpha", 0.30, metric="error", higher=False, population="X")
    d.value("Beta", 0.10, metric="error", higher=False, population="X")
    answer = run_template(graph(d), "rank", {"context": "X", "metric": "error"})
    assert [(r["thing"], r["score"]) for r in answer.rows] == [("Beta", 0.1), ("Alpha", 0.3)]


def test_list_for_task():
    docs = []
    for pid, task, data in (("p1", "NER", "SciERC"), ("p2", "NER", "CoNLL"), ("p3", "NER", "SciERC"),
                            ("p4", "RE", "TACRED")):
        d = Doc(pid)
        d.experiment("e1", {"task": task, "dataset": data})
        docs.append(d)
    answer = run_template(graph(*docs), "list_for", {"list_field": "dataset", "for_field": "task", "for_value": "NER"})
    assert [(r["item"], r["papers"]) for r in answer.rows] == [("SciERC", 2), ("CoNLL", 1)]


def chain_doc(pid: str, setting: dict[str, str], a: float | None, b: float, c: float | None, mid: str = "B") -> Doc:
    d = Doc(pid)
    d.experiment("e1", setting)
    if a is not None:
        d.value("A", a, population=None)
    d.value(mid, b, population=None)
    if c is not None:
        d.value("C", c, population=None)
    return d


def test_chaining_conflicting():
    # via B1: A over B1 by 0.3, C under B1 by 0.1 -> A over C by 0.4; via B2: A level with B2, C over B2 by 0.2 -> -0.2
    docs = []
    for mid, a, c in (("B1", 0.8, 0.4), ("B2", 0.5, 0.7)):
        docs.append(chain_doc(f"{mid}a", {"model": "7B"}, a, 0.5, None, mid))
        docs.append(chain_doc(f"{mid}c", {"model": "7B"}, None, 0.5, c, mid))
    answer = run_template(graph(*docs), "chaining_path",
                          {"a": "A", "c": "C", "metric": "acc", "must_match": ["model"], "threshold": 0.05})
    assert sorted((r["via"], round(r["estimate"], 3)) for r in answer.rows) == [("B1", 0.4), ("B2", -0.2)]
    assert {r["label"] for r in answer.rows} == {"conflicting"}


def test_chaining_indirect_and_settings_must_match():
    d1 = chain_doc("p1", {"model": "7B"}, 0.8, 0.5, None)
    d2 = chain_doc("p2", {"model": "7B"}, None, 0.5, 0.4)
    answer = run_template(graph(d1, d2), "chaining_path",
                          {"a": "A", "c": "C", "metric": "acc", "must_match": ["model"], "threshold": 0.05})
    assert [(r["via"], round(r["estimate"], 3), r["label"]) for r in answer.rows] == [("B", 0.4 - 0.0, "indirect")]
    d2 = chain_doc("p2", {"model": "70B"}, None, 0.5, 0.4)
    assert run_template(graph(d1, d2), "chaining_path",
                        {"a": "A", "c": "C", "metric": "acc", "must_match": ["model"], "threshold": 0.05}).empty


def test_empty_answer_has_reasons():
    d = Doc("p1")
    d.value("Alpha", 0.5)
    d.claim("RAG", "raises")
    d.link("builds_on", "10.1/x")
    store = graph(d)
    answer = run_query(store, "SELECT ?v WHERE { ?v a ev:Value ; ev:number ?n . FILTER(?n > 100) }", {})
    assert answer.empty and answer.rows == [] and answer.message == NO_EVIDENCE
    kinds = {r["kind"]: r["reason"] for r in answer.reasons}
    assert set(kinds) == {"value", "claim", "link"}
    assert "no comparison" in kinds["value"] and "no direction" in kinds["claim"] and "outside the set" in kinds["link"]


def test_a_malformed_query_is_an_error_not_an_empty_answer():
    with pytest.raises(SyntaxError):
        run_query(graph(Doc("p1")), "SELECT WHERE {", {})


def test_builds_on_says_outside_the_set():
    d = Doc("p1")
    d.link("builds_on", "10.1/x")
    d.link("builds_on", "p2 text", object_doc="p2")
    answer = run_template(graph(d, Doc("p2")), "builds_on", {"relation": "builds_on"})
    assert {r["target"] for r in answer.rows} == {"outside the set", "p2"}


def test_best_counts_each_unit_separately():
    docs = []
    for author, per_paper in (("Chen", [3, 3, 2, 2, 2]), ("Rossi", [3, 1, 1, 1, 1, 1, 1])):
        for n, wins in enumerate(per_paper):
            d = Doc(f"{author}{n}")
            for _ in range(wins):
                d.value(author, 0.9)
            d.value("Low", 0.1, side="base")
            docs.append(d)
    store = graph(*docs)
    rows = run_template(store, "best", {"metric": "acc", "counts_as": ["result", "paper"]}).rows
    got = {(r["kind"], r["thing"]): r["count"] for r in rows}
    assert got == {("result", "Chen"): 12, ("result", "Rossi"): 9, ("paper", "Rossi"): 7, ("paper", "Chen"): 5}
    only = run_template(store, "best", {"metric": "acc", "counts_as": ["result"]}).rows
    assert [(r["thing"], r["count"]) for r in only] == [("Chen", 12), ("Rossi", 9)]
    assert run_template(store, "count", {"thing": "Chen", "counts_as": ["result", "paper"]}).rows == [
        {"kind": "paper", "count": 5}, {"kind": "result", "count": 12}]


def test_a_missing_parameter_raises_not_a_free_variable():
    d = Doc("p1")
    d.value("RAG", 0.5)
    d.claim("RAG", "boosts", direction="improves", strength="firm")
    store = graph(d)
    with pytest.raises(ValueError, match="threshold"):
        run_template(store, "oversell", {})
    with pytest.raises(ValueError, match="free variables"):
        run_query(store, "SELECT ?v WHERE { ?v ev:number ?n . FILTER(?n > $cut) }", {})


def test_limitations_template():
    d, e = Doc("p1"), Doc("p2")
    d.value("Zelvora", 0.5)
    d.limitation("Zelvora", "small_sample")
    d.limitation(None, "cost")
    e.value("Zelvora", 0.4)
    e.limitation("Zelvora", "small_sample")
    rows = run_template(graph(d, e), "limitations", {}).rows
    assert [(r["thing"], r["category"], r["papers"]) for r in rows] == [("unlinked", "cost", 1),
                                                                      ("Zelvora", "small_sample", 2)]


def test_all_undetermined_effect_is_no_evidence():
    d = Doc("p1")
    d.value("RAG", 0.5, side="rag")   # no control value
    params = {"sides": ["rag", "baseline"], "metrics": ["acc"], "higher_is_better": {"acc": True},
              "min_effect": 0.01, "order": ["p1"]}
    answer = run_template(graph(d), "effect", params)
    assert answer.empty and answer.message == NO_EVIDENCE and answer.reasons[0]["record"] == "p1"


def test_oversell_firm_claim_without_a_win():
    d = Doc("p1")
    d.value("RAG", 0.50)
    d.value("Base", 0.50)
    d.claim("RAG", "boosts", direction="improves", strength="firm")
    d.claim("Base", "hedge", direction="improves", strength="hedged")
    answer = run_template(graph(d), "oversell", {"threshold": 0.01})
    assert [r["subject"] for r in answer.rows] == ["RAG"]


def test_consistency_claim_against_numbers():
    d = Doc("p1")
    d.value("RAG", 0.40)
    d.value("Base", 0.60)
    d.claim("RAG", "boosts", direction="improves")
    [row] = run_template(graph(d), "consistency", {"threshold": 0.01}).rows
    assert (row["data"], row["agrees"]) == ("worsens", False)


@pytest.mark.skipif(not EV2_RUN.is_dir(), reason="committed EV2 run missing")
def test_effect_template_equals_old_effect_answer():
    run = RunDir(EV2_RUN)
    items = run.items()
    pack = run.register_pack()
    from evidence.pack import RoleMap
    protocol = load(EV2_RUN / "protocol.yaml")
    spec = protocol.synthesis
    answer_json = json.loads((EV2_RUN / "answer.json").read_text(encoding="utf-8"))
    order = [s["document"] for s in answer_json["studies"]]
    by_doc: dict[str, list] = {d: [] for d in order}
    for it in items:
        by_doc[Path(it.spans[0].selector["file"]).stem].append(it)
    store = build([paper(d) for d in order], by_doc, RoleMap(pack), None)
    params = {"sides": [spec.compare.treatment, spec.compare.control], "metrics": list(spec.metric_names),
              "higher_is_better": {m.canonical: m.higher_is_better for m in spec.metrics},
              "min_effect": spec.min_effect, "prefer": list(spec.pairing.prefer), "order": order}
    rows = run_template(store, "effect", params).rows
    assert after.counts(rows) == answer_json["counts"]
    by_paper = {r["paper"]: r for r in rows}
    for s in answer_json["studies"]:
        r = by_paper[s["document"]]
        assert (r["direction"], r["delta"]) == (s["direction"], s["delta"])


def test_rank_matches_the_cleaned_context_not_the_exact_string():
    docs = []
    for pid, spelling, name, x in (("p1", "SQuAD", "Alpha", 0.71), ("p2", "squad", "Beta", 0.80),
                                   ("p3", "SQuAD2", "Gamma", 0.99)):
        d = Doc(pid)
        d.value(name, x, metric="F1", population=spelling)
        docs.append(d)
    answer = run_template(graph(*docs), "rank", {"context": "SQuAD", "metric": "F1"})
    assert [(r["thing"], r["paper"]) for r in answer.rows] == [("Beta", "p2"), ("Alpha", "p1")]   # "SQuAD2" is another set


def test_rank_does_not_merge_dataset_versions():
    d = Doc("p1")
    d.value("Alpha", 0.7, metric="F1", population="SQuAD v1.1 dev")
    answer = run_template(graph(d), "rank", {"context": "SQuAD", "metric": "F1"})
    assert answer.empty   # a version is a different literal: cleaning does not merge it (a known gap)


def test_rank_returns_the_paper_of_each_things_best_value():
    docs = []
    for pid, x in (("p1", 0.60), ("p2", 0.75), ("p3", 0.70)):
        d = Doc(pid)
        d.value("Alpha", x, metric="F1", population="X")
        docs.append(d)
    answer = run_template(graph(*docs), "rank", {"context": "X", "metric": "F1"})
    assert [(r["thing"], r["score"], r["paper"]) for r in answer.rows] == [("Alpha", 0.75, "p2")]
    assert list(answer.rows[0]) == ["thing", "score", "paper"]


def test_list_for_matches_the_cleaned_setting_value():
    docs = []
    for pid, task, data in (("p1", "NER", "SciERC"), ("p2", "ner", "CoNLL"), ("p3", "Named-Entity", "WNUT")):
        d = Doc(pid)
        d.experiment("e1", {"task": task, "dataset": data})
        docs.append(d)
    answer = run_template(graph(*docs), "list_for", {"list_field": "dataset", "for_field": "task", "for_value": "NER"})
    assert [r["item"] for r in answer.rows] == ["CoNLL", "SciERC"]   # "Named-Entity" is not the same key
