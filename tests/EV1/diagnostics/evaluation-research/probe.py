"""CPU-only research probes; no model calls or product code changes.

Run from the repository root with its dependencies available:
  python tests/EV1/diagnostics/evaluation-research/probe.py
Writes results.json beside this file. Fixtures below are illustrative, not EV1 scores.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import scipy
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from evaluation.score import score_citations, score_intervals, score_synthesis  # noqa: E402
from evaluation.stats import bootstrap_mean  # noqa: E402
from evaluation.truth import ENGINE, GroundTruth  # noqa: E402


def read(path: Path):
    return json.loads(path.read_text())


def main():
    live = ROOT / "tests/EV1/live-rerun"
    report_path = live / "scores/cascade/rag-llm-s1-mixed/report.json"
    report = read(report_path)
    systems = report["synthesis"]
    replay = score_intervals(None, systems)
    # Report serialization rounds floats to four places. Preserve both, compare at that precision.
    reproduced = all(
        [{k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()} for row in replay[key]]
        == report["intervals"][key] for key in ("paired", "synthesis")
    )
    coverage = {}
    for system in systems:
        rows = system["studies"]
        coverage[system["system"]] = {
            "rows": len(rows), "unique_papers": len({r["paper"] for r in rows}),
            "correct": sum(r["correct"] for r in rows),
            "undetermined": sum(r["given"] == "undetermined" for r in rows),
        }
    review_path = live / "corpora/rag-llm-s1-mixed/review/review-s1.csv"
    review = list(csv.DictReader(review_path.open()))
    levels = ("explicit", "paraphrased", "distributed", "complex", "contradictory", "mixed")
    ids = {}
    for level in levels:
        truth = read(live / f"corpora/rag-llm-s1-{level}/ground_truth.json")
        ids[level] = [s["study_id"] for s in truth["studies"]]
    template = read(live / "corpora/rag-tpl-s1-explicit/ground_truth.json")
    llm = read(live / "corpora/rag-llm-s1-explicit/ground_truth.json")
    direction_counts = {name: dict(Counter(s["effect"]["direction"] for s in t["studies"]))
                        for name, t in (("template_full_20", template), ("llm_retained_11", llm))}

    # A deliberately correlated toy fixture: six identical renderings of each of 11 parent studies.
    # Resampling the original study means is the cluster-bootstrap mean for these identical copies.
    toy = [1] * 6 + [0] * 5
    cluster = bootstrap_mean(toy)
    naive = bootstrap_mean([v for v in toy for _ in range(6)])
    # Degenerate bootstrap is honest but not a population interval: exact Bernoulli interval shown
    # only as an illustrative IID assumption, not an interval for these selected EV1 papers.
    degenerate = bootstrap_mean([1] * 11)
    exact = binomtest(11, 11).proportion_ci(confidence_level=0.95, method="exact")

    # Normal scoring expands missing predictions to the full truth denominator.
    fixture_truth = GroundTruth("fixture", "q", [
        {"study_id": f"S{i}", "paper": f"S{i}", "level": "explicit", "effect": {"direction": "supports"}}
        for i in range(1, 4)
    ], [], {"label": "supported"})
    partial = score_synthesis(fixture_truth, {"system": "fixture", "label": "supported", "studies": [
        {"document": "S1", "direction": "supports"}
    ]})
    # Direct malformed scoring inputs expose the helper's implicit denominator contract; these
    # cannot arise from score_synthesis on the same GroundTruth, which enumerates all papers.
    helper = score_intervals(None, [
        {"system": ENGINE, "studies": [{"paper": f"S{i}", "correct": True} for i in range(1, 4)]},
        {"system": "partial-fixture", "studies": [{"paper": "S1", "correct": False}]},
    ])
    empty = score_synthesis(GroundTruth("empty", "q", [], [], {}), {})
    citation_truth = GroundTruth("citation-fixture", "q", [{"paper": "S1", "level": "explicit"}],
                                [{"paper": "S1", "start": 10, "end": 20, "role": "condition_label"}], {})
    citation = score_citations(citation_truth, [{"document": "S1", "start": 0, "end": 1000}])
    output = {
        "evidence_types": {
            "saved_report": "deterministic replay of saved live output; no fresh model calls",
            "retained_ids_and_review": "audit of saved live artifacts",
            "toy_clustering_and_helper_edges": "controlled illustrative fixtures, not EV1 results",
        },
        "environment": {"python": sys.version.split()[0], "scipy": scipy.__version__},
        "report_path": str(report_path.relative_to(ROOT)),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "saved_intervals_reproduced_at_report_precision": reproduced,
        "actual_system_coverage": coverage,
        "actual_direction_mix": direction_counts,
        "replayed_intervals": replay,
        "review_audit": {"rows": len(review), "papers": len({r["paper"] for r in review}),
                         "completed_marks": {k: sum(bool(r[k].strip()) for r in review)
                                             for k in ("present", "states_truth", "unambiguous")}},
        "repeated_study_audit": {"rows_per_level": {k: len(v) for k,v in ids.items()},
                                 "unique_parent_studies": len(set().union(*map(set, ids.values()))),
                                 "total_renderings": sum(map(len, ids.values())),
                                 "ids_identical_across_levels": all(v == ids[levels[0]] for v in ids.values())},
        "illustrative_clustering": {"input_parent_outcomes": toy, "renderings_per_parent": 6,
                                     "naive_rendering_interval": naive, "parent_cluster_interval": cluster},
        "illustrative_perfect_small_sample": {"n": 11, "bootstrap": degenerate,
                                               "iid_exact_binomial_interval": {"low": exact.low, "high": exact.high},
                                               "assumption": "IID representative Bernoulli sample; not established for EV1"},
        "missing_prediction_fixture": {"truth_count": 3, "predictions": 1,
                                        "scored_rows": len(partial["studies"]), "rows": partial["rows"]},
        "helper_partial_overlap_fixture": {"engine_rows": 3, "baseline_rows": 1, "output": helper["paired"],
                                            "scope": "direct helper input, not normal same-truth score path"},
        "empty_truth_fixture": {"synthesis": empty, "intervals": score_intervals(None, [empty])},
        "broad_citation_fixture": {"placement_role": "condition_label", "placement_span": [10, 20],
                                   "citation_span": [0, 1000], "score": citation,
                                   "meaning": "overlap succeeds; claim entailment and quote specificity are not tested"},
    }
    (Path(__file__).parent / "results.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"reproduced": reproduced, "coverage": coverage, "review": output["review_audit"],
                      "repeated": output["repeated_study_audit"], "clustering": output["illustrative_clustering"]}, indent=2))


if __name__ == "__main__":
    main()
