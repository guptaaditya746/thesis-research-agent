"""compare: the Selection table (corpus.json `selection`), the Matched table (template vs LLM on the common
study ids only) and the diagnostic marking."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluation import report as rep
from evaluation.truth import ENGINE

SELECTION = {"requested_studies": 4, "records": 4, "retained_studies": 3,
             "per_level": {"explicit": {"passed": 3, "failed_checks": {"value_present": 1}, "mean_attempts": 1.5}},
             "excluded": {"S004": ["explicit"]}}


def study(paper: str, correct: bool, given: str = "supports", determined: bool = True) -> dict[str, Any]:
    return {"study": paper, "paper": paper, "level": "explicit", "expected": "supports", "given": given,
            "correct": correct, "determined": determined}


def report(tmp_path: Path, name: str, studies: list[dict[str, Any]], *, selection: dict | None = None,
           system: str = "rag-baseline", papers: list[dict[str, Any]] | None = None,
           write_corpus: bool = True) -> dict[str, Any]:
    corpus = tmp_path / name
    corpus.mkdir()
    if write_corpus:
        (corpus / "corpus.json").write_text(json.dumps({"selection": selection} if selection else {}), encoding="utf-8")
    n = len(studies)
    row = {"level": "all", "studies": n, "determined": n, "direction_accuracy": sum(s["correct"] for s in studies) / n,
           "completeness": 1.0, "accuracy_answered": 1.0}
    out: dict[str, Any] = {"corpus_id": f"{name}-abc123", "corpus_dir": str(corpus), "levels": ["explicit"],
                           "run_id": None, "extraction": None, "integration": None, "intervals": None,
                           "synthesis": [{"system": system, "label": "supported", "expected_label": "supported",
                                          "label_correct": True, "rows": [row], "studies": studies}]}
    if papers is not None:
        out["extractors"] = {"rows": [], "papers": papers}
    return out


def test_selection_table_reads_corpus_json(tmp_path: Path) -> None:
    r = report(tmp_path, "rag-llm-s1-explicit", [study("S001", True)], selection=SELECTION)
    old = report(tmp_path, "rag-tpl-s1-explicit", [study("S001", True)])      # built before C3: no selection
    comparison = rep.compare([r, old])
    assert [row["corpus_id"] for row in comparison["selection"]] == ["rag-llm-s1-explicit-abc123"]
    row = comparison["selection"][0]
    assert (row["requested"], row["retained"], row["level"], row["passed"]) == (4, 3, "explicit", 3)
    assert row["failed_checks"] == "value_present: 1"
    assert "## Selection" in rep.render_compare(comparison)


def test_a_report_without_a_corpus_path_or_corpus_json_does_not_crash(tmp_path: Path) -> None:
    r = report(tmp_path, "rag-llm-s1-explicit", [study("S001", True)], write_corpus=False)
    bare = {k: v for k, v in r.items() if k != "corpus_dir"}
    comparison = rep.compare([r, bare])
    assert comparison["selection"] == []
    rep.render_compare(comparison)


def test_matched_uses_the_intersection_and_lists_the_rest(tmp_path: Path) -> None:
    tpl = report(tmp_path, "rag-tpl-s1-explicit", [study("S001", True), study("S002", True), study("S003", False)])
    llm = report(tmp_path, "rag-llm-s1-explicit", [study("S001", True), study("S002", False), study("S004", True)])
    comparison = rep.compare([tpl, llm])
    assert len(comparison["matched"]) == 1
    m = comparison["matched"][0]
    assert m["system"] == "rag-baseline" and m["pair"] == "rag/s1-explicit"
    assert m["n_common"] == 2 and m["common"] == ["S001", "S002"]
    assert m["tpl_only"] == ["S003"] and m["llm_only"] == ["S004"]
    assert (m["tpl_direction_accuracy"], m["llm_direction_accuracy"]) == (1.0, 0.5)
    md = rep.render_compare(comparison)
    assert "## Matched" in md and "S003" in md and "S004" in md


def test_matched_extraction_is_recomputed_on_common_papers(tmp_path: Path) -> None:
    def papers(**counts: tuple[int, int, int]) -> list[dict[str, Any]]:
        return [{"extractor": "x", "paper": p, "cluster": p, "items": i, "matched": m, "facts": f}
                for p, (i, m, f) in counts.items()]

    tpl = report(tmp_path, "rag-tpl-s1-explicit", [study("S001", True), study("S002", True)], system=ENGINE,
                 papers=papers(S001=(4, 4, 4), S002=(2, 1, 4)))
    llm = report(tmp_path, "rag-llm-s1-explicit", [study("S001", True), study("S003", True)], system=ENGINE,
                 papers=papers(S001=(5, 4, 8), S003=(9, 9, 9)))
    comparison = rep.compare([tpl, llm])
    (row,) = comparison["matched_extraction"]
    assert row["extractor"] == "x" and row["n_common"] == 1
    assert (row["tpl_precision"], row["tpl_recall"]) == (1.0, 1.0)
    assert (row["llm_precision"], row["llm_recall"]) == (0.8, 0.5)


def test_unpaired_corpora_have_no_matched_table(tmp_path: Path) -> None:
    comparison = rep.compare([report(tmp_path, "rag-tpl-s1-explicit", [study("S001", True)])])
    assert comparison["matched"] == []
    assert "## Matched" not in rep.render_compare(comparison)


def test_diagnostic_systems_are_marked(tmp_path: Path) -> None:
    rows = [report(tmp_path, f"rag-llm-s1-{i}", [study("S001", True)], system=s)
            for i, s in enumerate(("rag-baseline", "oracle-synthesis", "rag-oracle-passages"))]
    comparison = rep.compare(rows)
    flags = {r["system"]: r["diagnostic"] for r in comparison["rows"]}
    assert flags == {"rag-baseline": False, "oracle-synthesis": True, "rag-oracle-passages": True}
    md = rep.render_compare(comparison)
    assert "oracle-synthesis (diagnostic)" in md and "rag-baseline (diagnostic)" not in md
