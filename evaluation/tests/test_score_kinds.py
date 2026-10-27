"""A/B/C per question kind (evaluation/score.py: score_kind, integration_kind, score(question_id=...))."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from evaluation import canon
from evaluation import report as rep
from evaluation.cli import main as evaluate
from evaluation.expected import expected
from evaluation import shift as sh
from evaluation.score import (Matching, integration_kind, same_metric, score, score_answers, score_extraction,
                              score_kind)
from evaluation.truth import GroundTruth, paper_ids, read_json
from evidence import protocol as protocol_module
from evidence.contract import Item
from evidence.questions import load as load_questions

from . import fixtures as fx

ROOT = Path(__file__).resolve().parents[2]
EV2 = ROOT / "tests" / "EV2"
MIXED = EV2 / "corpora" / "rag-claude-s1-mixed" / "ground_truth.json"
HARD = EV2 / "corpora" / "rag-tpl-hard-complex" / "ground_truth.json"
DATA = Path(__file__).resolve().parent / "data"
QUESTIONS = {q.id: q for q in load_questions()}


def _q(qid: str) -> Any:
    return QUESTIONS[qid]


def _protocol(qid: str) -> protocol_module.Protocol:
    return protocol_module.load(ROOT / str(_q(qid).protocol))


@pytest.fixture(scope="module")
def mixed() -> GroundTruth:
    return GroundTruth.load(MIXED)


@pytest.fixture(scope="module")
def hard() -> GroundTruth:
    return GroundTruth.load(HARD)


def _expected(truth: GroundTruth, qid: str, system: str = "evidence-engine") -> dict[str, Any]:
    q = _q(qid)
    answer = expected(truth, q.kind, q.truth, _protocol(qid))
    answer["system"] = system
    return answer


def _c(truth: GroundTruth, qid: str, answer: dict[str, Any]) -> dict[str, Any]:
    q = _q(qid)
    return score_kind(truth, q.kind, q.truth, _protocol(qid), answer)


# --- C: inventory ---------------------------------------------------------------------------------------------

def test_inventory_unknown_name_is_false_positive(hard: GroundTruth) -> None:
    answer = _expected(hard, "inv-metrics", "rag-baseline")
    answer["entries"].append({"name": "MagicScore", "aliases": [], "papers": ["S001"], "items": []})
    c = _c(hard, "inv-metrics", answer)
    assert c["precision"] < 1.0 and c["recall"] == 1.0
    assert "MagicScore" in c["false_positives"]
    assert c["paper_precision"] < 1.0 and c["paper_recall"] == 1.0


@pytest.mark.parametrize("qid", ["inv-metrics", "inv-methods", "inv-datasets"])
def test_inventory_perfect_answer(hard: GroundTruth, qid: str) -> None:
    c = _c(hard, qid, _expected(hard, qid))
    assert (c["precision"], c["recall"], c["f1"], c["paper_precision"], c["paper_recall"]) == (1.0,) * 5


def test_inventory_maps_names_through_canon_and_ignores_paper_order(hard: GroundTruth) -> None:
    exp = _expected(hard, "inv-metrics")
    answer = copy.deepcopy(exp)
    for entry in answer["entries"]:   # the engine names an entry by the form it met first, papers in manifest order
        if entry["aliases"]:
            entry["name"], entry["aliases"] = entry["aliases"][0], [entry["name"], *entry["aliases"][1:]]
        entry["papers"] = list(reversed(entry["papers"]))
    c = _c(hard, "inv-metrics", answer)
    assert (c["precision"], c["recall"], c["paper_precision"], c["paper_recall"]) == (1.0,) * 4


def test_inventory_unkeyed_truth_names_match_by_folded_name(hard: GroundTruth) -> None:
    exp = _expected(hard, "inv-methods")
    unkeyed = [e for e in exp["entries"] if canon.key("condition", e["name"]) is None]
    assert unkeyed, "the hard corpus has ablation conditions vocab does not know"
    answer = copy.deepcopy(exp)
    for entry in answer["entries"]:
        if canon.key("condition", entry["name"]) is None:
            entry["name"] = "  " + entry["name"].upper() + " "
    c = _c(hard, "inv-methods", answer)
    assert (c["precision"], c["recall"]) == (1.0, 1.0)


def test_inventory_missing_entry_lowers_recall(hard: GroundTruth) -> None:
    answer = _expected(hard, "inv-metrics")
    dropped = answer["entries"].pop(0)
    c = _c(hard, "inv-metrics", answer)
    assert c["precision"] == 1.0 and c["recall"] < 1.0
    assert dropped["name"] in c["missed"]


# --- C: best --------------------------------------------------------------------------------------------------

def test_best_winner_correct(mixed: GroundTruth) -> None:
    exp = _expected(mixed, "best-accuracy")
    c = _c(mixed, "best-accuracy", exp)
    assert c["winner_correct"] is True and c["per_study_accuracy"] == 1.0
    wrong = copy.deepcopy(exp)
    wrong["winner"] = "rag" if exp["winner"] != "rag" else "no-retrieval"
    assert _c(mixed, "best-accuracy", wrong)["winner_correct"] is False


def test_best_per_study_accuracy_counts_a_wrong_paper(mixed: GroundTruth) -> None:
    exp = _expected(mixed, "best-accuracy")
    answer = copy.deepcopy(exp)
    won = next(s for s in answer["studies"] if s["winner"])
    won["winner"] = "fine-tuned" if won["winner"] != "fine-tuned" else "rag"
    c = _c(mixed, "best-accuracy", answer)
    counted = len(c["studies"])
    assert c["per_study_accuracy"] == pytest.approx((counted - 1) / counted)
    assert not next(s for s in c["studies"] if s["paper"] == won["document"])["correct"]


def test_best_duplicates_are_not_counted_and_engine_duplicates_are_not_hidden() -> None:
    truth = GroundTruth.load(HARD)
    exp = _expected(truth, "best-accuracy")
    dups = {s["paper"] for s in truth.studies if s.get("duplicate_of")}
    assert dups, "the hard corpus has duplicates"
    c = _c(truth, "best-accuracy", exp)
    assert not dups & {s["paper"] for s in c["studies"]}


# --- C: consistency -------------------------------------------------------------------------------------------

def test_consistency_scores_disagreements(mixed: GroundTruth) -> None:
    exp = _expected(mixed, "cons-accuracy")
    perfect = _c(mixed, "cons-accuracy", exp)
    assert (perfect["per_study_accuracy"], perfect["disagreeing_precision"], perfect["disagreeing_recall"],
            perfect["agreeing_precision"], perfect["agreeing_recall"]) == (1.0,) * 5
    answer = copy.deepcopy(exp)
    flipped = answer["disagreeing"][0]
    for s in answer["studies"]:
        if s["document"] == flipped:
            s["agrees"] = True
    answer["disagreeing"].remove(flipped)
    answer["agreeing"].append(flipped)
    # the engine lists every document; one truth does not list (not on the claim metric) is ignored
    answer["studies"].append({"document": "S999", "claim": "improves", "direction": "contradicts", "agrees": False,
                              "reason": None})
    answer["disagreeing"].append("S999")
    c = _c(mixed, "cons-accuracy", answer)
    n = len(exp["disagreeing"])
    assert c["disagreeing_precision"] == 1.0 and c["disagreeing_recall"] == pytest.approx((n - 1) / n)
    assert c["agreeing_precision"] < 1.0
    assert c["per_study_accuracy"] == pytest.approx((len(exp["studies"]) - 1) / len(exp["studies"]))


# --- C: effect ------------------------------------------------------------------------------------------------

def test_effect_question_of_another_metric_is_scored_against_its_own_expected_answer(mixed: GroundTruth) -> None:
    exp = _expected(mixed, "rag-hallucination")
    c = _c(mixed, "rag-hallucination", exp)
    assert c["label_correct"] is True
    assert next(r for r in c["rows"] if r["level"] == "all")["direction_accuracy"] == 1.0


# --- A: dataset items, role-less conditions, metric names through canon ---------------------------------------

def _matching(items: list[Item], corpus: Path) -> Matching:
    truth = GroundTruth.load(corpus / "ground_truth.json")
    return Matching(items, truth, paper_ids(read_json(corpus / "manifest.json")))


def _a(m: Matching, kind: str) -> dict[str, Any]:
    return next(r for r in score_extraction(m)["rows"] if r["evidence_type"] == kind and r["level"] == "all")


def test_dataset_items_match_by_name(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    span = fx.span("S001", "dataset_label", "Results")       # not where the dataset is named: no usable span
    nq = Item.build("dataset", {"name": " nq "}, [span])
    other = Item.build("dataset", {"name": "MagicQA"}, [fx.span("S001", "dataset_label", "Abstract")])
    m = _matching([nq, other], corpus)
    row = _a(m, "dataset")
    assert (row["items"], row["facts"], row["matched"]) == (2, 2, 1)
    assert row["span_accuracy"] is None                       # dataset facts have no placements
    assert m.fact_of[nq.item_id] == "S001.d:NQ"


def test_runs_without_dataset_items_keep_dataset_facts_out(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    m = _matching(list(fx.perfect_items().values()), corpus)
    assert not any(r["evidence_type"] == "dataset" for r in score_extraction(m)["rows"])


def test_roleless_condition_matches_by_name_or_span(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    by_name = Item.build("condition", {"label": "Closed-Book  Model", "kind": "no-retrieval"},
                         [fx.span("S001", "condition_label", "Results")])
    by_span = Item.build("condition", {"label": "R", "kind": "rag"}, fx.fact_spans("S001.c2"))
    m = _matching([by_name, by_span], corpus)
    assert m.fact_of[by_name.item_id] == "S001.c1" and m.fact_of[by_span.item_id] == "S001.c2"


def test_question_metric_matches_through_canon(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    latency = Item.build("metric", {"name": "Latency (ms)", "canonical": "latency", "higher_is_better": False},
                         fx.fact_spans("S001.k2"))
    m = _matching([latency], corpus)
    assert m.fact_of[latency.item_id] == "S001.k2"


# --- B per kind -----------------------------------------------------------------------------------------------

def test_inventory_integration_counts_split_and_merged(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    items = fx.perfect_items()
    conds = [items[k] for k in ("S001.c1", "S001.c2", "S001.c3", "S002.c1", "S002.c2")]
    m = _matching(conds, corpus)
    ids = [i.item_id for i in conds]
    answer = {"kind": "inventory", "system": "evidence-engine", "target": "condition", "entries": [
        {"name": "a", "aliases": [], "papers": ["S001"], "items": [ids[0], ids[1]]},   # two keys: merged
        {"name": "b", "aliases": [], "papers": ["S001"], "items": [ids[2]]},
        {"name": "c", "aliases": [], "papers": ["S002"], "items": [ids[3]]},
        {"name": "d", "aliases": [], "papers": ["S002"], "items": [ids[4]]}]}
    b = integration_kind(m, "inventory", answer)
    assert b["merged"] == 1 and b["split"] == 0
    answer["entries"].append({"name": "e", "aliases": [], "papers": ["S002"], "items": [ids[2]]})
    b = integration_kind(m, "inventory", answer)
    assert b["split"] == 1
    assert 0.0 <= b["clean_share"] < 1.0


@pytest.mark.parametrize(("kind", "accuracy"), [("no-retrieval", 1.0), ("rag", 0.0)])
def test_best_integration_kind_accuracy(tmp_path: Path, kind: str, accuracy: float) -> None:
    corpus = fx.write_corpus(tmp_path)
    closed = Item.build("condition", {"label": "closed-book model", "kind": kind}, fx.fact_spans("S001.c1"))
    unknown = Item.build("condition", {"label": "retrieval-augmented variant", "kind": "rag"}, fx.fact_spans("S001.c2"))
    m = _matching([closed, unknown], corpus)
    answer = {"kind": "best", "system": "evidence-engine", "metric": "factual_accuracy", "studies": [], "wins": {},
              "winner": None, "tied": []}
    b = integration_kind(m, "best", answer)
    assert b["conditions"] == 1 and b["kind_accuracy"] == accuracy   # a label vocab gives no kind is not scored


def test_consistency_integration_claim_accuracy(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    right = Item.build("author_claim", {"direction": "improves"}, fx.fact_spans("S001.a1"))
    wrong = Item.build("author_claim", {"direction": "improves"}, fx.fact_spans("S002.a1"))
    m = _matching([right, wrong], corpus)
    answer = {"kind": "consistency", "system": "evidence-engine", "metric": "factual_accuracy", "studies": [],
              "agreeing": [], "disagreeing": [], "undetermined": []}
    b = integration_kind(m, "consistency", answer)
    assert b["claims"] == 2 and b["claim_accuracy"] == 0.5
    assert "rows" in b


# --- score(): dispatch and today's effect numbers -------------------------------------------------------------

GOLDEN = {"pilot-complex": ("cascade-gaps/rag-claude-pilot-complex", "rag-claude-pilot-complex",
                            ["rag-baseline/rag-claude-pilot-complex/answer.json"]),
          "tpl-s1-mixed": ("cascade-gaps/rag-tpl-s1-mixed", "rag-tpl-s1-mixed", [])}


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_effect_scores_unchanged(name: str) -> None:
    """Captured with the scorer before the per-kind change (evaluation/tests/data/score-golden-*.json)."""
    run, corpus, baselines = GOLDEN[name]
    result = score(EV2 / "runs" / run, EV2 / "corpora" / corpus, [EV2 / "runs" / b for b in baselines])
    assert (result.pop("question_id"), result.pop("kind")) == ("rag-factuality", "effect")
    golden = json.loads((DATA / f"score-golden-{name}.json").read_text(encoding="utf-8"))
    assert json.loads(rep.dumps(result)) == golden


def test_score_answers_dispatches_by_question() -> None:
    result = score_answers(HARD.parent, [], question_id="inv-datasets")
    assert (result["kind"], result["question_id"], result["synthesis"]) == ("inventory", "inv-datasets", [])


def test_score_answers_scores_an_inventory_baseline(tmp_path: Path, hard: GroundTruth) -> None:
    answer = _expected(hard, "inv-datasets", "rag-baseline")
    path = tmp_path / "answer.json"
    path.write_text(json.dumps(answer), encoding="utf-8")
    result = score_answers(HARD.parent, [path], question_id="inv-datasets")
    (c,) = result["synthesis"]
    assert c["system"] == "rag-baseline" and c["f1"] == 1.0
    assert result["attribution"] is None
    md = rep.render(result)
    assert "## C. Inventory" in md


def test_unknown_question_id_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no-such-question"):
        score_answers(HARD.parent, [], question_id="no-such-question")


def test_cli_score_takes_question_id(tmp_path: Path, hard: GroundTruth) -> None:
    answer = _expected(hard, "best-accuracy", "rag-baseline")
    path = tmp_path / "answer.json"
    path.write_text(json.dumps(answer), encoding="utf-8")
    out = tmp_path / "out"
    assert evaluate(["score", "--corpus", str(HARD.parent), "--baseline", str(path), "--question-id", "best-accuracy",
                     "--out", str(out)]) == 0
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["kind"] == "best" and report["question_id"] == "best-accuracy"
    assert report["synthesis"][0]["winner_correct"] is True
    assert "## C. Best" in (out / "report.md").read_text(encoding="utf-8")


def test_score_refuses_a_run_of_another_kind(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    run = fx.write_run(tmp_path / "runs", list(fx.perfect_items().values()), fx.engine_answer(fx.perfect_items()))
    (run / "protocol.yaml").write_bytes((ROOT / str(_q("rag-factuality").protocol)).read_bytes())
    with pytest.raises(ValueError, match="kind"):
        score(run, corpus, question_id="inv-metrics")


def test_compare_leaves_out_reports_of_other_kinds(tmp_path: Path, hard: GroundTruth) -> None:
    answer = _expected(hard, "inv-metrics", "rag-baseline")
    path = tmp_path / "answer.json"
    path.write_text(json.dumps(answer), encoding="utf-8")
    report = score_answers(HARD.parent, [path], question_id="inv-metrics")
    comparison = rep.compare([report])
    assert comparison["rows"] == [] and any("inventory" in n for n in comparison["notes"])


# --- fix round 1 ----------------------------------------------------------------------------------------------

def test_consistency_document_left_out_is_wrong_even_when_truth_is_undetermined(hard: GroundTruth) -> None:
    exp = _expected(hard, "cons-accuracy")
    assert exp["undetermined"], "the hard corpus has undetermined consistency studies"
    left_out = exp["undetermined"][0]
    answer = copy.deepcopy(exp)
    answer["studies"] = [s for s in answer["studies"] if s["document"] != left_out]
    answer["undetermined"].remove(left_out)
    c = _c(hard, "cons-accuracy", answer)
    n = len(exp["studies"])
    assert c["per_study_accuracy"] == pytest.approx((n - 1) / n)
    row = next(s for s in c["studies"] if s["paper"] == left_out)
    assert (row["answered"], row["correct"]) == (False, False)
    # listed as undetermined without a studies entry: answered, and right
    answer["undetermined"].append(left_out)
    assert _c(hard, "cons-accuracy", answer)["per_study_accuracy"] == 1.0


def test_consistency_integration_counts_a_claim_item_once(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    truth = fx.ground_truth()
    second = copy.deepcopy(truth["studies"][1])       # a second study in paper S001 whose claim overlaps S001.a1's
    second.update(study_id="S003", paper="S001", conditions=[], metrics=[], measurements=[],
                  author_claim={"id": "S003.a1", "direction": "no_effect"}, effect=None)
    truth["studies"].append(second)
    start = fx.S001.index("Retrieval clearly")
    truth["placements"].append({"fact": "S003.a1", "role": "claim", "paper": "S001", "start": start,
                                "end": start + len("Retrieval clearly"), "exact": "Retrieval clearly"})
    fx.dump(corpus / "ground_truth.json", truth)
    item = Item.build("author_claim", {"direction": "improves"}, fx.fact_spans("S001.a1"))
    b = integration_kind(_matching([item], corpus), "consistency", {"kind": "consistency", "studies": []})
    assert (b["claims"], b["claim_correct"], b["claim_accuracy"]) == (1, 1, 1.0)   # on S001.a1, the larger overlap


def test_metric_canon_fallback_only_for_facts_outside_the_question_metrics() -> None:
    assert same_metric({"canonical": "latency"}, {"canonical": "other", "name": "latency"})
    assert not same_metric({"canonical": "latency"}, {"canonical": "factual_accuracy", "name": "latency"})
    assert not same_metric({"canonical": "latency"}, {"canonical": "hallucination_rate", "name": "Lat."})
    assert same_metric({"canonical": "factual_accuracy"}, {"canonical": "factual_accuracy", "name": "x"})


def test_cli_refuses_an_unknown_question_id(tmp_path: Path, hard: GroundTruth) -> None:
    path = tmp_path / "answer.json"
    path.write_text(json.dumps(_expected(hard, "inv-metrics", "rag-baseline")), encoding="utf-8")
    with pytest.raises(SystemExit, match="no-such-question"):
        evaluate(["score", "--corpus", str(HARD.parent), "--baseline", str(path), "--question-id", "no-such-question",
                  "--out", str(tmp_path / "out")])


def test_shift_skips_reports_of_other_kinds(tmp_path: Path, hard: GroundTruth) -> None:
    path = tmp_path / "answer.json"
    path.write_text(json.dumps(_expected(hard, "cons-accuracy", "rag-baseline")), encoding="utf-8")
    report = score_answers(HARD.parent, [path], question_id="cons-accuracy")
    spec = {"base_corpus_id": report["corpus_id"], "corpus_id": report["corpus_id"], "study": "S001",
            "from": "supports", "to": "contradicts", "expected": {}}
    result = sh.shift(report, report, spec)
    assert result["systems"] == [] and result["unmatched_systems"] == []
    assert any("consistency" in n for n in result["notes"])
    assert "Not compared" in sh.render(result)


# --- the question of a run, without --question-id (final review, finding 2) ------------------------------------

TPL = EV2 / "corpora" / "rag-tpl-s1-mixed"


def _regex_run(qid: str, corpus: Path, out: Path) -> Path:
    from evidence import engine
    return engine.run(ROOT / str(_q(qid).protocol), corpus, out, cache=out / "cache.jsonl", selection="regex-only",
                      run_id=qid)


def test_a_hallucination_run_scores_against_its_own_truth(tmp_path: Path) -> None:
    run = _regex_run("rag-hallucination", TPL, tmp_path / "runs")
    inferred = score(run, TPL)
    assert (inferred["question_id"], inferred["kind"]) == ("rag-hallucination", "effect")
    assert json.loads(rep.dumps(inferred)) == json.loads(rep.dumps(score(run, TPL, question_id="rag-hallucination")))
    factual = score(run, TPL, question_id="rag-factuality")   # the old default: another truth, other numbers
    assert rep.dumps(factual["integration"]) != rep.dumps(inferred["integration"])


def test_an_inventory_run_scores_without_a_question_id(tmp_path: Path) -> None:
    run = _regex_run("inv-metrics", HARD.parent, tmp_path / "runs")
    out = tmp_path / "score"
    assert evaluate(["score", "--run", str(run), "--corpus", str(HARD.parent), "--out", str(out)]) == 0
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert (report["question_id"], report["kind"]) == ("inv-metrics", "inventory")


def test_a_run_of_no_listed_question_is_refused_without_a_question_id(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    run = fx.write_run(tmp_path / "runs", list(fx.perfect_items().values()), fx.engine_answer(fx.perfect_items()))
    text = (ROOT / str(_q("rag-factuality").protocol)).read_text(encoding="utf-8")
    (run / "protocol.yaml").write_text(text.replace(_q("rag-factuality").question, "Does anything help at all?"),
                                       encoding="utf-8")
    with pytest.raises(ValueError, match="cannot tell which question"):
        score(run, corpus)
    with pytest.raises(SystemExit, match="--question-id"):
        evaluate(["score", "--run", str(run), "--corpus", str(corpus), "--out", str(tmp_path / "out")])
    assert score(run, corpus, question_id="rag-factuality")["question_id"] == "rag-factuality"


def test_baseline_answers_score_for_the_question_they_ask(tmp_path: Path, hard: GroundTruth) -> None:
    answer = _expected(hard, "inv-datasets", "rag-baseline") | {"question_id": "inv-datasets"}
    path = tmp_path / "answer.json"
    path.write_text(json.dumps(answer), encoding="utf-8")
    assert score_answers(HARD.parent, [path])["question_id"] == "inv-datasets"
    with pytest.raises(ValueError, match="cannot tell which question"):
        score_answers(HARD.parent, [])


# --- pre-EV3 scoring fixes --------------------------------------------------------------------------------------

def _all_all(extraction: dict[str, Any]) -> dict[str, Any]:
    return next(r for r in extraction["rows"] if r["evidence_type"] == "all" and r["level"] == "all")


def test_a_counts_only_the_types_the_protocol_extracts(tmp_path: Path) -> None:
    """Finding 1: an inventory protocol that extracts metrics only is not charged with conditions, measurements
    and claims; perfect extraction of its own types is A F1 = 1.0, and report.json names the types scored."""
    corpus = fx.write_corpus(tmp_path)
    metrics = [i for i in fx.perfect_items().values() if i.evidence_type == "metric"]
    run = fx.write_run(tmp_path / "runs", metrics, None)
    (run / "protocol.yaml").write_text((ROOT / str(_q("inv-metrics").protocol)).read_text(encoding="utf-8"),
                                       encoding="utf-8")
    extraction = score(run, corpus, question_id="inv-metrics")["extraction"]
    assert extraction["scored_types"] == ["metric"]
    assert {r["evidence_type"] for r in extraction["rows"]} == {"metric", "all"}
    row = _all_all(extraction)
    assert (row["items"], row["facts"], row["matched"], row["f1"]) == (3, 3, 3, 1.0)


@pytest.mark.parametrize("qid", ["inv-methods", "inv-metrics"])
def test_perfect_inventory_extraction_is_a_f1_one_on_the_hard_corpus(hard: GroundTruth, qid: str) -> None:
    from evaluation.oracle import items_from_truth
    from evaluation.score import protocol_matching
    protocol = _protocol(qid)
    items, _ = items_from_truth(hard, HARD.parent)
    own = [i for doc in items.values() for i in doc if i.evidence_type in protocol.evidence_types]
    m = protocol_matching(own, hard, paper_ids(read_json(HARD.parent / "manifest.json")), protocol)
    assert _all_all(score_extraction(m))["f1"] == 1.0
