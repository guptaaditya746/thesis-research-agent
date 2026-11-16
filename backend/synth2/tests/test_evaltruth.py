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

OLD_PROTOCOL = DATA / "domains/rag/protocols/rag-factuality.yaml"   # one result per study, no subsets
PROTOCOL = DATA / "domains/rag/protocols/rag-factuality-subsets.yaml"


def raw(corpus: Path) -> dict:
    return json.loads((corpus / "ground_truth.json").read_text(encoding="utf-8"))


def test_each_study_becomes_two_conditions_one_metric_and_a_measurement_per_cell_and_arm(tiny):
    truth = GroundTruth.load(tiny / "ground_truth.json")
    for s in raw(tiny)["studies"]:
        facts = [f for f in truth.facts.values() if f.paper == s["id"]]
        kinds = [f.type for f in facts]
        assert kinds.count("condition") == 2 and kinds.count("metric") == 1
        assert kinds.count("measurement") == 2 * len(s["cells"]) and kinds.count("author_claim") == 1


def test_every_study_carries_an_effect_per_cell_and_its_own_pooled_direction(tiny):
    from synth2.recipe import load_recipe
    from synth2.world import Study, direction, study_delta
    recipe = load_recipe("rag")
    truth = GroundTruth.load(tiny / "ground_truth.json")
    names = {"helps": "supports", "hurts": "contradicts", "no_effect": "neutral"}
    by_id = {s["study_id"]: s for s in truth.studies}
    assert {len(s["cells"]) for s in raw(tiny)["studies"]} == {1, 2}
    for s in raw(tiny)["studies"]:
        study = by_id[s["id"]]
        assert len(study["cells"]) == len(s["cells"])
        for j, (c, cell) in enumerate(zip(s["cells"], study["cells"])):
            delta = c["k_t"] / c["n_t"] - c["k_c"] / c["n_c"]
            assert cell == {"id": f"{s['id']}.e{j}", "subset": c["levels"], "delta": delta,
                            "direction": names[direction(delta, recipe.min_effect)],
                            "treatment": f"{s['id']}.m{j}t", "control": f"{s['id']}.m{j}c"}
            for arm in "tc":   # the measurement says which subset it is of and how many questions are behind it
                fact = truth.facts[f"{s['id']}.m{j}{arm}"]
                assert fact.data["subset"] == c["levels"] and fact.data["total"] == c[f"n_{arm}"]
        pooled = study_delta(Study.parse(s))
        assert study["effect"]["direction"] == names[direction(pooled, recipe.min_effect)]
        assert study["effect"]["delta"] == pooled
        assert (study["effect"]["treatment"], study["effect"]["control"]) == (f"{s['id']}.m0t", f"{s['id']}.m0c")


def test_the_truth_answer_is_the_synth2_key_with_every_study_grouped(tiny):
    truth = GroundTruth.load(tiny / "ground_truth.json")
    assert truth.answer["key"] == raw(tiny)["key"]
    grouped = sorted(p for g in ("supporting", "contradicting", "neutral") for p in truth.answer[g])
    assert grouped == sorted(s["paper"] for s in truth.studies if not s["duplicate_of"])


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
    studies = raw(tiny)["studies"]
    assert pairs["true_pair"] == 1.0 and pairs["studies"] == len(studies)
    assert pairs["cells"] == sum(len(s["cells"]) for s in studies)
    assert pairs["true_cell_pair"] == 1.0 and pairs["subset_accuracy"] == 1.0
    assert "unscored_studies" not in report
    c = next(r for r in report["synthesis"][0]["rows"] if r["level"] == "all")
    assert c["direction_accuracy"] == 1.0 and c["determined"] == len(studies)
    verdicts = report["synthesis"][0]
    assert verdicts["label_correct"] is True and verdicts["flags"]["counts_correct"] is True
    assert verdicts["key"]["given"] == verdicts["key"]["expected"] == raw(tiny)["key"]
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
    truth = GroundTruth.load(corpus / "ground_truth.json")
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
    answer = {"system": "x", "question": "q", "label": "supported", **groups, "undetermined": [],
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


def test_the_corpus_answer_is_scored_against_the_key_and_a_wrong_one_is_wrong(tiny, tmp_path):
    out = oracle.run(PROTOCOL, tiny, tmp_path / "oracle")
    c = score(out, tiny)["synthesis"][0]
    assert c["errors"] == [] and c["label_correct"] is True and c["flags"]["counts_correct"] is True
    assert (c["label"], c["expected_label"]) == (raw(tiny)["key"]["verdict"],) * 2
    answer = json.loads((out / "answer.json").read_text(encoding="utf-8"))
    answer["conclusion"] = {**answer["conclusion"], "verdict": "depends", "condition": "model_size",
                            "sides": {"small": "supports", "large": "neutral"}}
    (out / "answer.json").write_text(json.dumps(answer), encoding="utf-8")
    wrong = score(out, tiny)["synthesis"][0]
    assert wrong["label_correct"] is False and (wrong["label"], wrong["expected_label"]) == ("depends", "helps")
    assert wrong["key"]["given"]["condition"] == "model_size" and wrong["key"]["verdict_correct"] is False


def test_a_depends_key_is_recovered_by_the_oracle(tmp_path):
    from synth2.corpus import Settings, build_base
    for seed in range(50):
        base = tmp_path / f"s{seed}"
        build_base(base, Settings("rag", seed, 12, "opposed", "table", exact=True))
        if raw(base)["key"]["verdict"] == "depends":
            break
    else:
        raise AssertionError("no seed gives a depends key")
    report = score(oracle.run(PROTOCOL, base, tmp_path / "oracle"), base)
    c = report["synthesis"][0]
    assert c["label_correct"] is True and c["key"]["given"] == raw(base)["key"]
    assert next(r for r in report["integration"]["rows"] if r["level"] == "all")["true_pair"] == 1.0


def test_a_run_without_subsets_is_scored_on_every_study_and_misses_the_second_cells(tiny, tmp_path):
    report = score(oracle.run(OLD_PROTOCOL, tiny, tmp_path / "oracle"), tiny)
    studies = raw(tiny)["studies"]
    row = next(r for r in report["integration"]["rows"] if r["level"] == "all")
    two = sum(len(s["cells"]) == 2 for s in studies)
    assert row["studies"] == len(studies) and row["true_pair"] == (len(studies) - two) / len(studies)
    assert row["true_cell_pair"] == len(studies) / (len(studies) + two) and row["subset_accuracy"] == 0.0
    by_study = {s["study"]: s for s in report["integration"]["studies"]}
    for s in studies:
        assert [c["true_pair"] for c in by_study[s["id"]]["cells"]] == [True, False][:len(s["cells"])]
    assert report["synthesis"][0]["key"]["given"]["condition"] is None   # it can only give one overall label


def test_studies_whose_claim_disagrees_with_their_pooled_direction_are_flagged(tiny):
    truth = GroundTruth.load(tiny / "ground_truth.json")
    said = {"helps": "supports", "hurts": "contradicts", "no_effect": "neutral"}
    by_id = {s["study_id"]: s for s in truth.studies}
    for s in raw(tiny)["studies"]:
        study = by_id[s["id"]]
        disagrees = said[s["claim"]] != study["effect"]["direction"]
        assert ("claim_disagrees" in study["flags"]) == disagrees


def test_the_oracle_flags_the_spun_corpus_overclaims_correctly(tmp_path):
    spun = _spun_corpus(tmp_path)
    c = _oracle_c(spun, tmp_path / "oracle")
    over = sorted(s["id"] for s in raw(spun)["studies"] if s["overclaims"])
    assert {len(s["cells"]) for s in raw(spun)["studies"] if s["overclaims"]} == {1, 2}
    row = next(r for r in c["flags"]["rows"] if r["flag"] == "claim_disagrees")
    assert row["expected"] == over and row["given"] == over
    assert (row["tp"], row["fp"], row["fn"]) == (len(over), 0, 0)
    assert c["label_correct"] is True and c["flags"]["counts_correct"] is True
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


def _with_leftover_item(tiny: Path, tmp_path: Path) -> tuple[Path, Path, str, str]:
    """A copy of `tiny`, the oracle run on it plus one measurement item whose span is S001's first line (standing in
    for a real result left in the paper), that line, and the new item's id."""
    import shutil
    from agent.anchor import selector_at
    from evidence.contract import Item, Span
    from evidence.rundir import EVIDENCE_FILE
    corpus = tmp_path / "corpus"
    shutil.copytree(tiny, corpus)
    out = oracle.run(PROTOCOL, corpus, tmp_path / "oracle")
    rows = [json.loads(line) for line in (out / EVIDENCE_FILE).read_text(encoding="utf-8").splitlines()]
    text = (corpus / "papers" / "S001.md").read_text(encoding="utf-8")
    line = text[:text.index("\n")]
    model = Item.model_validate(next(r for r in rows if r["evidence_type"] == "measurement"
                                     and r["spans"][0]["selector"]["file"].endswith("S001.md")))
    span = Span.of(model.spans[0].role, selector_at(text, 0, len(line), file=model.spans[0].selector["file"]))
    extra = Item.build("measurement", {**model.fields, "value": 0.42}, [span], dict(model.links))
    rows.append(extra.model_dump(mode="json"))
    (out / EVIDENCE_FILE).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n")
    return corpus, out, line, extra.item_id


def test_an_item_on_a_listed_leftover_result_is_excused_not_counted_wrong(tiny, tmp_path):
    corpus, out, line, extra = _with_leftover_item(tiny, tmp_path)

    def a(report: dict) -> dict:
        return next(r for r in report["extraction"]["rows"] if r["evidence_type"] == "all" and r["level"] == "all")

    before = score(out, corpus)
    assert a(before)["precision"] < 1.0 and extra in before["extraction"]["unmatched_items"]
    truth = raw(corpus)
    truth["known_extras"] = [{"study": "S001", "id": "X1", "direction": "helps", "text": line}]
    (corpus / "ground_truth.json").write_text(json.dumps(truth), encoding="utf-8")
    after = score(out, corpus)
    assert a(after)["precision"] == 1.0 and a(after)["recall"] == 1.0
    assert after["extraction"]["excused_items"] == {extra: "X1"}
    assert extra not in after["extraction"]["unmatched_items"]
    per = [r for r in after["extractors"]["rows"] if r["evidence_type"] == "all" and r["level"] == "all"]
    assert per and all(r["precision"] == 1.0 for r in per), per
    assert all(p["items"] == p["matched"] for p in after["extractors"]["papers"])


def test_a_known_extra_whose_text_is_not_in_its_paper_is_refused(tiny, tmp_path):
    import shutil
    corpus = tmp_path / "corpus"
    shutil.copytree(tiny, corpus)
    truth = raw(corpus)
    truth["known_extras"] = [{"study": "S001", "id": "X1", "direction": "helps", "text": "Never in the paper."}]
    (corpus / "ground_truth.json").write_text(json.dumps(truth), encoding="utf-8")
    with pytest.raises(ValueError, match="S001"):
        GroundTruth.load(corpus / "ground_truth.json")


def test_a_synth2_truth_without_corpus_json_is_refused_naming_its_folder(tiny):
    (tiny / "corpus.json").unlink()
    with pytest.raises(ValueError, match=re.escape(str(tiny))):
        GroundTruth.load(tiny / "ground_truth.json")


def test_the_oracle_finds_no_false_copies_on_seed_17(tmp_path):
    # seed 17 once drew two studies with the same rates, and the engine's copy rule took the second for a copy
    from synth2.corpus import Settings, build_base
    base = tmp_path / "base"
    build_base(base, Settings("rag", 17, 6, "opposed", "table", exact=True))
    assert _oracle_c(base, tmp_path / "oracle")["flags"]["duplicates_correct"] is True


def test_the_subsets_protocol_names_the_recipes_conditions_and_thresholds():
    # the engine's candidate conditions and its two thresholds are the ones the answer key is made with
    from evidence import protocol
    from synth2.recipe import load_recipe
    recipe = load_recipe("rag")
    synthesis = protocol.load(PROTOCOL).synthesis
    mods = synthesis.moderators
    assert [c.model_dump(mode="json") for c in mods.conditions] == [c.model_dump(mode="json") for c in recipe.conditions]
    assert (synthesis.min_effect, mods.min_gap) == (recipe.min_effect, recipe.min_gap)
