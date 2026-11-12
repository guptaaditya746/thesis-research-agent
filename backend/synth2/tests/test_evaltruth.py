import json
import re
import sys
from pathlib import Path

import pytest

from evaluation import oracle
from evaluation.score import score, score_flags
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
    from synth2.recipe import load_recipe
    recipe = load_recipe("rag")
    truth = GroundTruth.load(tiny / "ground_truth.json")
    cells = {s["id"]: s["cells"] for s in raw(tiny)["studies"]}
    for fact in truth.facts.values():
        main = truth.placements_of(fact.id, truth.main_role[fact.type])
        assert main, fact.id
        text = (tiny / "papers" / f"{fact.paper}.md").read_text(encoding="utf-8")
        for p in main:
            assert text[p["start"]:p["end"]] == p["exact"]
            if fact.type == "condition":
                assert p["exact"] == (recipe.treatment.label if fact.data["role"] == "rag" else recipe.control.label)
            elif fact.type == "metric":
                assert p["exact"] == recipe.metric
        if fact.type == "measurement":   # S001.m0t: cell 0, treatment arm
            cell, arm = cells[fact.paper][int(fact.id.split(".m")[1][:-1])], fact.id[-1]
            assert [text[p["start"]:p["end"]] for p in truth.placements_of(fact.id, "value")] == [str(cell[f"k_{arm}"])]
            assert [text[p["start"]:p["end"]] for p in truth.placements_of(fact.id, "value_total")] == [
                str(cell[f"n_{arm}"])]


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
    verdicts = report["synthesis"][0]
    assert verdicts["label_correct"] is not False and verdicts["flags"]["counts_correct"] is not False
    assert verdicts["flags"]["duplicates_correct"] is True
    assert all(r["fp"] == 0 and r["fn"] == 0 for r in verdicts["flags"]["rows"]), verdicts["flags"]["rows"]


def test_an_old_corpus_report_has_no_unscored_key(tmp_path):
    corpus = fixtures.write_corpus(tmp_path)
    items = fixtures.perfect_items()
    run = fixtures.write_run(tmp_path, list(items.values()), fixtures.engine_answer(items))
    assert "unscored_studies" not in score(run, corpus)


def test_a_duplicate_study_keeps_duplicate_of(tmp_path):
    from synth2.corpus import Settings, build_base
    for seed in range(50):   # a base whose first study (the one copied) has one cell, so the copy is scored
        base = tmp_path / f"s{seed}" / "base"
        build_base(base, Settings("rag", seed, 6, "uniform", "table", exact=True))
        if len(raw(base)["studies"][0]["cells"]) != 1:
            continue
        try:
            make_family(base)
        except ValueError:
            continue
        break
    else:
        raise AssertionError("no seed gives a one-cell first study and a valid family")
    corpus = base.parent / "duplicate"
    data = raw(corpus)   # every other study cut to its first cell, so the corpus-level counts are scored
    for s in data["studies"]:
        s["cells"] = s["cells"][:1]
    (corpus / "ground_truth.json").write_text(json.dumps(data), encoding="utf-8")
    truth = GroundTruth.load(corpus / "ground_truth.json")
    assert truth.unscored == []
    copies = [s for s in truth.studies if s["duplicate_of"]]
    assert len(copies) == 1 and copies[0]["duplicate_of"] == "S001" and "effect" in copies[0]
    copy = copies[0]["paper"]
    count = lambda paper: sorted(f.type for f in truth.facts.values() if f.paper == paper)
    assert count(copy) == count("S001")
    assert truth.answer["duplicates"] == [copy]
    # the engine-shaped answer: the copy set aside, everything else grouped by direction
    groups = {k: truth.answer[k] for k in ("supporting", "contradicting", "neutral")}
    assert copy not in sum(groups.values(), [])
    entries = [{"document": s["paper"], "direction": s["effect"]["direction"] if "effect" in s else "undetermined",
                "duplicate_of": s["duplicate_of"]} for s in truth.studies]
    answer = {"system": "x", "question": "q", "label": truth.answer["label"], **groups, "undetermined": [],
              "duplicates": [copy], "counts": {**{k: len(v) for k, v in groups.items()}, "undetermined": 0,
                                               "duplicates": 1},
              "studies": entries, "flags": {}}
    flags = score_flags(truth, answer)
    assert flags["counts_correct"] is True and flags["duplicates_correct"] is True


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


def _spun_corpus(tmp_path: Path) -> Path:
    """The `spun` member of the first family whose base has overclaiming one-cell and two-cell studies."""
    from synth2.corpus import Settings, build_base
    for seed in range(50):
        base = tmp_path / f"s{seed}" / "base"
        build_base(base, Settings("rag", seed, 6, "uniform", "table", exact=True))
        try:
            make_family(base)
        except ValueError:
            continue
        studies = raw(base.parent / "spun")["studies"]
        if {len(s["cells"]) for s in studies if s["overclaims"]} == {1, 2}:
            return base.parent / "spun"
    raise AssertionError("no seed gives a spun corpus with overclaiming one-cell and two-cell studies")


def _oracle_c(corpus: Path, out: Path) -> dict:
    return score(oracle.run(PROTOCOL, corpus, out), corpus)["synthesis"][0]


def test_with_two_subset_studies_the_corpus_label_and_counts_are_not_scored(tiny, tmp_path):
    truth = GroundTruth.load(tiny / "ground_truth.json")
    assert truth.unscored
    assert set(truth.answer) == {"duplicates"}
    c = _oracle_c(tiny, tmp_path / "oracle")
    assert c["label_correct"] is None and c["flags"]["counts_correct"] is None
    assert c["flags"]["duplicates_correct"] is True
    assert c["errors"] == ["label and counts not scored: the corpus has two-subset studies (unscored_studies)"]
    report = score(oracle.run(PROTOCOL, tiny, tmp_path / "o2"), tiny)
    assert "label" in report["unscored_studies"]["reason"] and "counts" in report["unscored_studies"]["reason"]


def test_without_two_subset_studies_the_label_and_counts_are_scored(tiny, tmp_path):
    data = raw(tiny)
    for s in data["studies"]:
        s["cells"] = s["cells"][:1]
    (tiny / "ground_truth.json").write_text(json.dumps(data), encoding="utf-8")
    truth = GroundTruth.load(tiny / "ground_truth.json")
    assert truth.unscored == []
    assert {"label", "supporting", "contradicting", "neutral", "duplicates"} <= set(truth.answer)
    c = _oracle_c(tiny, tmp_path / "oracle")
    assert c["label_correct"] is True and c["flags"]["counts_correct"] is True


def test_one_cell_studies_whose_claim_disagrees_with_their_direction_are_flagged(tiny):
    truth = GroundTruth.load(tiny / "ground_truth.json")
    said = {"helps": "supports", "hurts": "contradicts", "no_effect": "neutral"}
    by_id = {s["study_id"]: s for s in truth.studies}
    for s in raw(tiny)["studies"]:
        study = by_id[s["id"]]
        if len(s["cells"]) == 1:
            disagrees = said[s["claim"]] != study["effect"]["direction"]
            assert study["flags"] == (["claim_disagrees"] if disagrees else [])
        else:
            assert study["flags"] == []


def test_the_oracle_flags_the_spun_corpus_overclaims_correctly(tmp_path):
    spun = _spun_corpus(tmp_path)
    c = _oracle_c(spun, tmp_path / "oracle")
    one_cell = sorted(s["id"] for s in raw(spun)["studies"] if s["overclaims"] and len(s["cells"]) == 1)
    row = next(r for r in c["flags"]["rows"] if r["flag"] == "claim_disagrees")
    assert row["expected"] == one_cell and row["given"] == one_cell
    assert (row["tp"], row["fp"], row["fn"]) == (len(one_cell), 0, 0)
    assert c["label_correct"] is not False and c["flags"]["counts_correct"] is not False
    assert all(r["fp"] == 0 and r["fn"] == 0 for r in c["flags"]["rows"])


def test_an_item_on_a_later_mention_of_a_label_is_span_correct(tiny, tmp_path):
    from agent.anchor import selector_at
    from evidence.contract import Item, Span
    from evidence.rundir import EVIDENCE_FILE, Corpus
    from synth2.recipe import load_recipe
    recipe = load_recipe("rag")
    out = oracle.run(PROTOCOL, tiny, tmp_path / "oracle")
    files = {p.id: p.file for p in Corpus(tiny).papers}
    rows = [json.loads(line) for line in (out / EVIDENCE_FILE).read_text(encoding="utf-8").splitlines()]
    moved = 0
    for row in rows:
        item = Item.model_validate(row)
        if item.evidence_type not in ("condition", "metric"):
            continue
        paper = item.spans[0].selector["file"]
        doc = next(d for d, f in files.items() if f == paper)
        text = (tiny / "papers" / f"{doc}.md").read_text(encoding="utf-8")
        needle = (recipe.metric if item.evidence_type == "metric" else
                  recipe.treatment.label if item.fields["role"] == "rag" else recipe.control.label)
        last = text.rfind(needle)
        assert last > text.find(needle)   # the label is mentioned more than once
        span = Span.of(item.spans[0].role, selector_at(text, last, last + len(needle), file=paper))
        row.update(item.model_copy(update={"spans": [span]}).model_dump(mode="json"))
        moved += 1
    assert moved
    (out / EVIDENCE_FILE).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n")
    report = score(out, tiny)
    for kind in ("condition", "metric"):
        r = next(r for r in report["extraction"]["rows"] if r["evidence_type"] == kind and r["level"] == "all")
        assert r["f1"] == 1.0 and r["span_accuracy"] == 1.0, kind


def test_a_synth2_truth_without_corpus_json_is_refused_naming_its_folder(tiny):
    (tiny / "corpus.json").unlink()
    with pytest.raises(ValueError, match=re.escape(str(tiny))):
        GroundTruth.load(tiny / "ground_truth.json")
