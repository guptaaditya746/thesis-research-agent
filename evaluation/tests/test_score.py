"""Scoring on the hand-written corpus (fixtures.py) with known expected numbers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from evaluation import report as rep
from evaluation.score import GroundTruth, match, score, score_answers
from evaluation.truth import Fact
from evidence.contract import Item, Span

from . import fixtures as fx


def row(rows: list[dict[str, Any]], **want: str) -> dict[str, Any]:
    found = [r for r in rows if all(r.get(k) == v for k, v in want.items())]
    assert len(found) == 1, (want, rows)
    return found[0]


def a_row(result: dict[str, Any], kind: str = "all", level: str = "all") -> dict[str, Any]:
    return row(result["extraction"]["rows"], evidence_type=kind, level=level)


def system(result: dict[str, Any], name: str) -> dict[str, Any]:
    return next(s for s in result["synthesis"] if s["system"] == name)


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    return fx.write_corpus(tmp_path)


def run_with(tmp_path: Path, items: dict[str, Item], answer: dict[str, Any] | None = None, **kw: Any) -> Path:
    return fx.write_run(tmp_path / "runs", list(items.values()),
                        fx.engine_answer(items) if answer is None else answer, **kw)


def test_perfect_run_scores_one_everywhere(tmp_path: Path, corpus: Path) -> None:
    items = fx.perfect_items()
    result = score(run_with(tmp_path, items), corpus)
    for r in result["extraction"]["rows"]:
        assert (r["precision"], r["recall"], r["f1"], r["span_accuracy"]) == (1.0, 1.0, 1.0, 1.0), r
    assert (a_row(result)["items"], a_row(result)["facts"]) == (15, 15)
    assert a_row(result, "measurement")["facts"] == 5
    b = row(result["integration"]["rows"], level="all")
    assert (b["matched_measurements"], b["association_accuracy"], b["condition_exact"], b["metric_exact"],
            b["true_pair"]) == (5, 1.0, 1.0, 1.0, 1.0)
    engine = system(result, "evidence-engine")
    assert engine["label_correct"] and row(engine["rows"], level="all")["direction_accuracy"] == 1.0
    assert row(result["locate"]["rows"], evidence_type="all", level="all") == {
        "evidence_type": "all", "level": "all", "placements": 16, "inside": 16, "recall": 1.0}
    cascade = {r["extractor"]: r for r in result["cascade"]["rows"]}
    assert (cascade[fx.REGEX]["found"], cascade[fx.REGEX]["only"]) == (9, 8)
    assert (cascade[fx.LLM]["found"], cascade[fx.LLM]["only"], cascade[fx.LLM]["only_matched"]) == (7, 6, 6)
    assert result["cascade"]["missed_by_all"] == {}
    assert result["cost"]["per_paper"]["calls"] == 8.0 and result["cost"]["total"]["seconds"] == 12.5
    assert result["stability"] is None
    # F4: intervals of a perfect run are the point value with null bounds (no spread); extractor rows exist
    assert row(result["intervals"]["extraction"], evidence_type="all") == {"evidence_type": "all", "point": 1.0,
                                                                            "low": None, "high": None, "method": None,
                                                                            "unit": "row", "n_rows": 2}
    assert result["intervals"]["synthesis"] == [{"system": "evidence-engine", "point": 1.0, "low": None, "high": None,
                                                 "method": None, "unit": "row", "n_rows": 2}]
    assert result["intervals"]["paired"] == [] and engine["flags"] is None
    assert {r["extractor"] for r in result["extractors"]["rows"]} == {fx.REGEX, fx.LLM}
    assert result["extractors"]["cost"] is None   # no calls/ in the hand-written run


def test_a_missing_item_lowers_recall_only(tmp_path: Path, corpus: Path) -> None:
    items = fx.perfect_items()
    del items["S001.m3"]
    result = score(run_with(tmp_path, items), corpus)
    m = a_row(result, "measurement")
    assert (m["items"], m["facts"], m["matched"], m["precision"], m["recall"]) == (4, 5, 4, 1.0, 0.8)
    assert a_row(result, "measurement", "explicit")["recall"] == pytest.approx(2 / 3)
    assert a_row(result, "measurement", "paraphrased")["recall"] == 1.0
    assert result["extraction"]["missed"] == ["S001.m3"]
    assert result["cascade"]["missed_by_all"] == {"measurement": 1}


def test_value_linked_to_wrong_condition_counts_in_a_but_fails_b(tmp_path: Path, corpus: Path) -> None:
    items = fx.perfect_items()
    old = items["S001.m2"]
    wrong = items["S001.c3"].item_id  # the distractor system (role other), not the RAG condition
    items["S001.m2"] = Item.build("measurement", dict(old.fields), list(old.spans),
                                  links={**old.links, "condition": wrong})
    result = score(run_with(tmp_path, items), corpus)
    assert a_row(result, "measurement")["f1"] == 1.0
    b = row(result["integration"]["rows"], level="all")
    assert (b["association_accuracy"], b["condition_role_accuracy"], b["condition_exact"], b["metric_accuracy"]) == (
        0.8, 0.8, 0.8, 1.0)
    assert row(result["integration"]["rows"], level="explicit")["association_accuracy"] == pytest.approx(2 / 3)


def test_wrong_pair_fails_the_true_pair_check(tmp_path: Path, corpus: Path) -> None:
    items = fx.perfect_items()
    answer = fx.engine_answer(items)
    answer["studies"][0]["treatment"]["measurement"] = items["S001.m3"].item_id  # the distractor as RAG
    result = score(run_with(tmp_path, items, answer), corpus)
    assert row(result["integration"]["rows"], level="all")["true_pair"] == 0.5
    assert row(result["integration"]["rows"], level="explicit")["true_pair"] == 0.0
    assert [s["true_pair"] for s in result["integration"]["studies"]] == [False, True]


def test_wrong_direction_fails_c(tmp_path: Path, corpus: Path) -> None:
    items = fx.perfect_items()
    answer = fx.engine_answer(items)
    answer["studies"][1]["direction"] = "supports"
    answer["label"] = "supported"
    result = score(run_with(tmp_path, items, answer), corpus)
    engine = system(result, "evidence-engine")
    assert not engine["label_correct"] and engine["expected_label"] == "mixed"
    assert row(engine["rows"], level="all")["direction_accuracy"] == 0.5
    assert row(engine["rows"], level="paraphrased")["direction_accuracy"] == 0.0
    assert {"expected": "contradicts", "given": "supports", "n": 1} in engine["confusion"]
    assert a_row(result)["f1"] == 1.0  # extraction is untouched


def test_value_tolerance_and_span_accuracy(tmp_path: Path, corpus: Path) -> None:
    items = fx.perfect_items()
    m2, m3 = items["S001.m2"], items["S001.m3"]
    items["S001.m2"] = Item.build("measurement", {**m2.fields, "value": 0.704}, [fx.span("S001", "value", "70%")],
                                  links=dict(m2.links))  # within 0.005, but its span is not the fact's placement
    items["S001.m3"] = Item.build("measurement", {**m3.fields, "value": 0.656 - 0.0001}, list(m3.spans),
                                  links=dict(m3.links))  # 0.0041 off: still matches
    result = score(run_with(tmp_path, items, answer={"system": "evidence-engine", "label": "mixed", "studies": []}),
                   corpus)
    m = a_row(result, "measurement")
    assert (m["matched"], m["span_accuracy"]) == (5, 0.8)
    items["S001.m3"] = Item.build("measurement", {**m3.fields, "value": 0.654}, list(m3.spans), links=dict(m3.links))
    result = score(run_with(tmp_path / "b", items, answer={"system": "x", "studies": []}), corpus)
    m = a_row(result, "measurement")
    assert (m["items"], m["matched"], m["precision"], m["recall"]) == (5, 4, 0.8, 0.8)


def test_matching_is_one_to_one_and_maximal() -> None:
    """Greedy (closest first) would give item A fact X and leave B unmatched; the assignment matches both."""
    truth = GroundTruth("c", "q", [{"paper": "P", "level": "explicit"}], [], {})
    facts = [Fact("P.x", "measurement", "P", "explicit", {"value": 0.624}),
             Fact("P.y", "measurement", "P", "explicit", {"value": 0.617})]

    def item(value: float) -> Item:
        sel = {"file": "P.md", "start": int(value * 1000), "end": int(value * 1000) + 3, "exact": "x", "prefix": "",
               "suffix": "", "sha256": "0"}
        return Item.build("measurement", {"value": value}, [Span(role="value", selector=sel)])

    a, b = item(0.621), item(0.627)
    pairs = {(i.fields["value"], f.id) for i, f in match([a, b], facts, truth)}
    assert pairs == {(0.621, "P.y"), (0.627, "P.x")}
    assert len(match([a, b, item(0.6215)], facts, truth)) == 2  # never more pairs than facts


def test_locate_recall_counts_placements_outside_the_scope(tmp_path: Path, corpus: Path) -> None:
    results = fx.S001.index("## Results")
    locate = [{"document": p, "evidence_type": t, "strategy": "whole", "scope": {"kind": "document"}}
              for p in fx.PAPERS for t in ("condition", "metric", "author_claim")]
    locate += [{"document": "S001", "evidence_type": "measurement", "strategy": "tables",
                "scope": {"kind": "ranges", "ranges": [[results, len(fx.S001)]]}}]  # S002 measurements: no entry
    result = score(run_with(tmp_path, fx.perfect_items(), locate=locate), corpus)
    m = row(result["locate"]["rows"], evidence_type="measurement", level="all")
    assert (m["placements"], m["inside"]) == (6, 3)  # 62% (abstract) and both S002 values are outside
    assert row(result["locate"]["rows"], evidence_type="condition", level="all")["recall"] == 1.0
    assert {o["fact"] for o in result["locate"]["outside"]} == {"S001.m1", "S002.m1", "S002.m2"}


def test_locate_accepts_the_mapping_shape(tmp_path: Path, corpus: Path) -> None:
    locate = {"documents": {p: {t: {"strategy": "whole", "scope": {"kind": "document"}}
                                for t in ("condition", "metric", "measurement", "author_claim")} for p in fx.PAPERS}}
    result = score(run_with(tmp_path, fx.perfect_items(), locate=locate), corpus)
    assert row(result["locate"]["rows"], evidence_type="all", level="all")["recall"] == 1.0


def test_baseline_answers_are_scored_like_the_engine(tmp_path: Path, corpus: Path) -> None:
    rag = fx.baseline_answer("rag-baseline", {"S001": "supports", "S002": "supports"}, "supported")
    agent = fx.baseline_answer("agent-baseline", {"S001": "supports"}, "supported")
    fx.dump(tmp_path / "rag.json", rag)
    fx.dump(tmp_path / "agent.json", agent)
    result = score(run_with(tmp_path, fx.perfect_items()), corpus, [tmp_path / "rag.json", tmp_path / "agent.json"])
    assert [s["system"] for s in result["synthesis"]] == ["evidence-engine", "rag-baseline", "agent-baseline"]
    r, a = system(result, "rag-baseline"), system(result, "agent-baseline")
    assert not r["label_correct"] and row(r["rows"], level="all")["direction_accuracy"] == 0.5
    overall = row(a["rows"], level="all")
    assert (overall["direction_accuracy"], overall["completeness"], overall["accuracy_answered"]) == (0.5, 0.5, 1.0)
    only = score_answers(corpus, [tmp_path / "rag.json"])
    assert only["extraction"] is None and only["synthesis"][0]["system"] == "rag-baseline"
    paired = {p["system"]: p for p in result["intervals"]["paired"]}
    assert paired["rag-baseline"]["point"] == 0.5 and paired["agent-baseline"]["point"] == 0.5   # engine 2/2 vs 1/2
    assert row(result["intervals"]["synthesis"], system="rag-baseline")["point"] == 0.5
    assert only["intervals"]["extraction"] == [] and only["intervals"]["paired"] == []   # no engine to pair with


def test_completeness_and_traceability(tmp_path: Path, corpus: Path) -> None:
    """Part G.1: completeness over the studies with a determined true direction; traceability over the cited
    passages, each against the placements of the paper it cites; null without citations (the engine)."""
    places = {(p["fact"], p["exact"]): p for p in fx.placements()}
    sixty_two = places[("S001.m1", "62%")]
    cited = [{"document": "S001", "start": sixty_two["start"] - 3, "end": sixty_two["start"] + 1},  # overlaps "62%"
             {"document": "S001", "start": 0, "end": 10},                                          # the title: none
             {"document": "S999", "start": 0, "end": 10}]                                          # no such paper
    rag = fx.baseline_answer("rag-baseline", {"S001": "supports"}, "supported") | {"citations": cited}
    fx.dump(tmp_path / "rag.json", rag)
    truth = fx.ground_truth()
    truth["studies"].append({"study_id": "S003", "paper": "S003", "level": "paraphrased", "conditions": [],
                             "metrics": [], "measurements": [], "author_claim": None,
                             "effect": {"direction": "undetermined", "delta": None}})  # not determined: not counted
    fx.dump(corpus / "ground_truth.json", truth)
    result = score(run_with(tmp_path, fx.perfect_items()), corpus, [tmp_path / "rag.json"])
    r = {x["level"]: x for x in system(result, "rag-baseline")["rows"]}
    assert (r["all"]["studies"], r["all"]["completeness"]) == (3, 0.5)              # S001 of S001, S002
    assert (r["all"]["citations"], r["all"]["traceability"]) == (3, pytest.approx(1 / 3))
    assert (r["explicit"]["completeness"], r["explicit"]["citations"], r["explicit"]["traceability"]) == (1.0, 2, 0.5)
    assert (r["paraphrased"]["completeness"], r["paraphrased"]["citations"], r["paraphrased"]["traceability"]) == (
        0.0, 0, None)
    e = row(system(result, "evidence-engine")["rows"], level="all")
    assert (e["completeness"], e["citations"], e["traceability"]) == (1.0, None, None)
    empty = fx.baseline_answer("agent-baseline", {}, "insufficient") | {"citations": []}
    fx.dump(tmp_path / "agent.json", empty)
    a = row(score_answers(corpus, [tmp_path / "agent.json"])["synthesis"][0]["rows"], level="all")
    assert (a["completeness"], a["citations"], a["traceability"]) == (0.0, 0, None)
    # a dropped citation (naming no retrieved passage) is a cited passage that is never traced
    dropped = rag | {"citations": cited[:1], "dropped_citations": [
        {"document": "S001", "start": sixty_two["start"], "end": sixty_two["end"]},  # fabricated: untraced even here
        {"document": "S999", "start": 0, "end": 10}]}
    fx.dump(tmp_path / "dropped.json", dropped)
    d = {x["level"]: x for x in score_answers(corpus, [tmp_path / "dropped.json"])["synthesis"][0]["rows"]}
    assert (d["all"]["citations"], d["all"]["traceability"]) == (3, pytest.approx(1 / 3))
    assert (d["explicit"]["citations"], d["explicit"]["traceability"]) == (2, 0.5)
    only_dropped = rag | {"citations": [], "dropped_citations": [{"document": "S999", "start": 0, "end": 10}]}
    fx.dump(tmp_path / "only.json", only_dropped)
    o = row(score_answers(corpus, [tmp_path / "only.json"])["synthesis"][0]["rows"], level="all")
    assert (o["citations"], o["traceability"]) == (1, 0.0)
    rows = rep.compare([result])["rows"]
    by = {x["system"]: x for x in rows}
    assert (by["rag-baseline"]["completeness"], by["rag-baseline"]["traceability"]) == (0.5, pytest.approx(1 / 3))
    assert (by["evidence-engine"]["completeness"], by["evidence-engine"]["traceability"]) == (1.0, None)
    assert "traceability" in rep.render_compare(rep.compare([result])) and "completeness" in rep.render(result)


def test_stability_from_a_reexec_report(tmp_path: Path, corpus: Path) -> None:
    """The engine's reexec.json shape (evidence/replay.compare): calls name the extractor, not its id."""
    def call(name: str, outcome: str, original: int, reproduced: int) -> dict:
        return {"document": "S001", "evidence_type": "measurement", "extractor": name, "outcome": outcome,
                "items_original": original, "items_reproduced": reproduced}

    reexec = {"calls": [call("regex_measurement", "identical", 3, 3)] * 3
              + [call("llm_measurement", "identical", 2, 2), call("llm_measurement", "items_missing", 2, 1)],
              "summary": {"llm_measurement": {"calls": 2}}, "totals": {"identical": 4, "items_missing": 1}}
    result = score(run_with(tmp_path, fx.perfect_items(), reexec=reexec), corpus)
    rows = {r["extractor"]: r for r in result["stability"]["rows"]}
    assert rows["regex_measurement"]["identical_share"] == 1.0 and rows["llm_measurement"]["identical_share"] == 0.5
    assert rows["llm_measurement"]["item_stability"] == 0.75
    assert rows["llm_measurement"]["outcomes"] == {"identical": 1, "items_missing": 1}
    assert result["stability"]["summary"] == {"llm_measurement": {"calls": 2}}


def test_report_files_are_deterministic(tmp_path: Path, corpus: Path) -> None:
    run = run_with(tmp_path, fx.perfect_items())
    js1, md1 = rep.write_report(score(run, corpus), tmp_path / "out1")
    js2, md2 = rep.write_report(score(run, corpus), tmp_path / "out2")
    assert js1.read_bytes() == js2.read_bytes() and md1.read_bytes() == md2.read_bytes()
    text = md1.read_text(encoding="utf-8")
    for heading in ("## A. Extraction", "## B. Integration", "## C. Synthesis", "## Intervals", "## Locate recall",
                    "## Cascade contribution", "## Per extractor", "## Cost"):
        assert heading in text
    assert "1.000 [n/a]" in text   # the perfect run's F1: point value, degenerate bounds


def test_compare_orders_corpora_by_level(tmp_path: Path) -> None:
    reports = []
    for level in ("paraphrased", "explicit"):
        corpus = fx.write_corpus(tmp_path / level, corpus_id=f"c-{level}")
        truth = fx.ground_truth(f"c-{level}")
        for s in truth["studies"]:
            s["level"] = level
        fx.dump(corpus / "ground_truth.json", truth)
        reports.append(score(run_with(tmp_path / level, fx.perfect_items()), corpus))
    rows = rep.compare(reports)["rows"]
    assert [r["level"] for r in rows] == ["explicit", "paraphrased"]
    assert rows[0]["extraction_f1"] == 1.0 and rows[0]["label_correct"] is True
    assert "| explicit" in rep.render_compare(rep.compare(reports))
    assert rows[0]["accuracy_answered"] == 1.0 and "accuracy_answered" in rep.render_compare(rep.compare(reports))
    intervals = rep.compare(reports)["intervals"]
    assert [(r["level"], r["system"]) for r in intervals] == [("explicit", "evidence-engine"), ("paraphrased", "evidence-engine")]
    assert intervals[0]["extraction_f1"] == {"point": 1.0, "low": None, "high": None, "method": None}
    assert intervals[0]["engine_minus_system"] is None
    text = rep.render_compare(rep.compare(reports))
    assert "## Intervals" in text and "1.000 [n/a]" in text


def test_compare_shows_direction_intervals_with_bounds(tmp_path: Path) -> None:
    """Six studies, the baseline right on four of them: the direction accuracy has real bounds in compare.md."""
    corpus = fx.write_f_corpus(tmp_path)
    fx.dump(tmp_path / "rag.json", fx.baseline_answer("rag-baseline", {"S001": "supports", "S002": "supports",
                                                                        "S003": "supports", "S006": "contradicts"}, "mixed"))
    fx.dump(tmp_path / "engine.json", fx.f_answer())
    report = score_answers(corpus, [tmp_path / "engine.json", tmp_path / "rag.json"])
    rag = row(report["intervals"]["synthesis"], system="rag-baseline")
    assert rag["point"] == pytest.approx(4 / 6) and rag["low"] is not None and rag["low"] < rag["point"] < rag["high"]
    assert rag["method"] in ("BCa", "percentile")
    text = rep.render(report)
    assert "| method" in text and f"| {rag['method']}" in text and "| determined" in text
    paired = row(report["intervals"]["paired"], system="rag-baseline")
    assert paired["point"] == pytest.approx(2 / 6) and paired["low"] is not None
    line = next(l for l in rep.render_compare(rep.compare([report])).splitlines() if "rag-baseline" in l and "[" in l)
    assert "0.667 [" in line and "0.333 [" in line


def test_report_shows_accuracy_on_answered_studies(tmp_path: Path, corpus: Path) -> None:
    """Review 3: a baseline citing only some papers is shown with accuracy on what it answered and its label."""
    fx.dump(tmp_path / "agent.json", fx.baseline_answer("agent-baseline", {"S001": "supports"}, "supported"))
    text = rep.render(score_answers(corpus, [tmp_path / "agent.json"]))
    header = next(line for line in text.splitlines() if line.startswith("| system"))
    assert "direction_accuracy" in header and "accuracy_answered" in header and "label_correct" in header
    assert "determined" in header and "over the determined studies only" in text
    per_level = next(line for line in text.splitlines() if line.startswith("| level"))
    assert "determined" in per_level


def test_missing_gold_label_is_undefined_not_a_match() -> None:
    """An empty gold answer has no label; None == None must not read as a correct label (EV1 probe)."""
    from evaluation.score import score_synthesis
    result = score_synthesis(GroundTruth("empty", "q", [], [], {}), {})
    assert result["label_correct"] is None
    assert "gold answer has no label" in result["errors"]
    labelled = score_synthesis(GroundTruth("c", "q", [], [], {"label": "supported"}), {"label": "supported"})
    assert labelled["label_correct"] is True and labelled["errors"] == []
    text = rep.table([{"label_correct": result["label_correct"]}], ["label_correct"])
    assert "-" in text


def test_paired_interval_reports_its_n() -> None:
    from evaluation.score import score_intervals
    from evaluation.truth import ENGINE
    systems = [
        {"system": ENGINE, "studies": [{"paper": f"S{i}", "correct": True} for i in range(1, 4)]},
        {"system": "base", "studies": [{"paper": "S1", "correct": False}, {"paper": "S2", "correct": True}]},
    ]
    out = score_intervals(None, systems)
    paired = out["paired"][0]
    assert paired["n_rows"] == 2 and paired["excluded_ids"] == ["S3"]
    assert {r["system"]: r["n_rows"] for r in out["synthesis"]} == {ENGINE: 3, "base": 2}
