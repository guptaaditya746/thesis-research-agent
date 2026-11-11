import json
import sys
from pathlib import Path

from evaluation import oracle
from evaluation.score import score
from evaluation.tests import fixtures
from evaluation.truth import GroundTruth
from repo_paths import DATA
from synth2.family import make_family

PROTOCOL = DATA / "domains/rag/protocols/rag-factuality.yaml"


def raw(corpus: Path) -> dict:
    return json.loads((corpus / "ground_truth.json").read_text(encoding="utf-8"))


def test_each_study_becomes_two_conditions_one_metric_and_a_measurement_per_cell_and_arm(tiny):
    truth = GroundTruth.load(tiny / "ground_truth.json")
    for s in raw(tiny)["studies"]:
        facts = [f for f in truth.facts.values() if f.paper == s["id"]]
        kinds = [f.type for f in facts]
        assert kinds.count("condition") == 2 and kinds.count("metric") == 1
        assert kinds.count("measurement") == 2 * len(s["cells"]) and kinds.count("author_claim") == 1


def test_one_cell_studies_carry_the_pooled_direction_and_two_cell_studies_are_unscored(tiny):
    from synth2.recipe import load_recipe
    from synth2.world import direction
    recipe = load_recipe("rag")
    truth = GroundTruth.load(tiny / "ground_truth.json")
    names = {"helps": "supports", "hurts": "contradicts", "no_effect": "neutral"}
    by_id = {s["study_id"]: s for s in truth.studies}
    for s in raw(tiny)["studies"]:
        if len(s["cells"]) == 1:
            c = s["cells"][0]
            want = names[direction(c["k_t"] / c["n_t"] - c["k_c"] / c["n_c"], recipe.min_effect)]
            assert by_id[s["id"]]["effect"]["direction"] == want
        else:
            assert "effect" not in by_id[s["id"]]
    assert truth.unscored == [s["id"] for s in raw(tiny)["studies"] if len(s["cells"]) == 2]
    assert truth.unscored


def test_template_placements_cover_every_fact(tiny):
    truth = GroundTruth.load(tiny / "ground_truth.json")
    for fact in truth.facts.values():
        main = truth.placements_of(fact.id, truth.main_role[fact.type])
        assert main, fact.id
        text = (tiny / "papers" / f"{fact.paper}.md").read_text(encoding="utf-8")
        for p in main:
            assert text[p["start"]:p["end"]] == p["exact"]


def test_the_oracle_run_scores_perfectly_on_a_synth2_corpus(tiny, tmp_path):
    out = oracle.run(PROTOCOL, tiny, tmp_path / "oracle")
    report = score(out, tiny)
    all_all = next(r for r in report["extraction"]["rows"] if r["evidence_type"] == "all" and r["level"] == "all")
    assert all_all["f1"] == 1.0 and all_all["span_accuracy"] == 1.0
    pairs = next(r for r in report["integration"]["rows"] if r["level"] == "all")
    assert pairs["true_pair"] == 1.0 and pairs["studies"] == (
        len(GroundTruth.load(tiny / "ground_truth.json").studies) - report["unscored_studies"]["count"])
    c = next(r for r in report["synthesis"][0]["rows"] if r["level"] == "all")
    assert c["direction_accuracy"] == 1.0


def test_an_old_corpus_report_has_no_unscored_key(tmp_path):
    corpus = fixtures.write_corpus(tmp_path)
    items = fixtures.perfect_items()
    run = fixtures.write_run(tmp_path, list(items.values()), fixtures.engine_answer(items))
    assert "unscored_studies" not in score(run, corpus)


def test_a_duplicate_study_keeps_duplicate_of(tiny):
    make_family(tiny)
    truth = GroundTruth.load(tiny.parent / "duplicate" / "ground_truth.json")
    copies = [s for s in truth.studies if s["duplicate_of"]]
    assert len(copies) == 1 and copies[0]["duplicate_of"] == "S001"


def test_two_close_cells_get_two_facts_and_both_match(tiny, tmp_path):
    data = raw(tiny)
    two = next(s for s in data["studies"] if len(s["cells"]) == 2)
    a, b = two["cells"]
    a["n_t"] = b["n_t"] = 1000   # the two rag values now differ by 0.001, less than 0.005
    a["k_t"], b["k_t"] = 500, 501
    (tiny / "ground_truth.json").write_text(json.dumps(data), encoding="utf-8")
    truth = GroundTruth.load(tiny / "ground_truth.json")
    assert len([f for f in truth.facts.values() if f.paper == two["id"] and f.type == "measurement"]) == 4
    out = oracle.run(PROTOCOL, tiny, tmp_path / "oracle")
    report = score(out, tiny)
    row = next(r for r in report["extraction"]["rows"] if r["evidence_type"] == "measurement" and r["level"] == "all")
    assert row["recall"] == 1.0
