"""The SciLead real-paper check (D42, spec 6.12): values found and linked to their metric, "best" per leaderboard and
pairwise order ("chains", F39). The fixture `scilead_tiny/` is hand-made data (not SciLead data) in the release's
layout as the authors' code reads it (tdm_annotations.json, leaderboards.json): four papers, p1 and p2 with arxiv.org
links, the third keyed by its arXiv id ("2103.00003.pdf"), p4 with an ACL link only (not fetchable); one leaderboard
(Question Answering, SQuAD, F1: percent, higher is better per domains/ml/metrics.yaml) with p1 90.0, p2 85.0,
p3 80.0; p1 also reports EM 41.2 on Natural Questions and p4 Accuracy on MNLI (no leaderboard)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from evaluation import cli
from evaluation.realpapers.scilead import gold, ids, matches, no_arxiv, score
from evidence import engine
from evidence.contract import Item, Span
from evidence.pack import protocol_path
from evidence.protocol import load
from evidence.rundir import EVIDENCE_FILE, NAMES_FILE, PROTOCOL_FILE, write_lines
from evidence.tests.conftest import context_id, corpus_of, empty, provider_of, scripted

TINY = Path(__file__).resolve().parent / "data" / "scilead_tiny"
ML_VALUES_PROTOCOL = protocol_path("ml", "values")
KEY = {"p1": "p1", "p2": "p2", "p3": "2103.00003.pdf"}                          # the release's paper keys
ARXIV = {"p1": "2101.00001v1", "p2": "2102.00002v2", "p3": "2103.00003v1"}   # as `evidence fetch` names them
HIGHER = {"p1": "90.0", "p2": "85.0", "p3": "80.0"}
LOWER = {"p1": "15.0", "p2": "10.0", "p3": "20.0"}   # a perplexity: p2 is the best paper
LOWER_METRIC = "Perplexity"                          # lower is better, raw (domains/ml/metrics.yaml)


@pytest.fixture(autouse=True)
def code_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sealed runs name commit `test` (no `git rev-parse` per run; F54)."""
    monkeypatch.setenv("EVIDENCE_CODE_COMMIT", "test")


def data_dir(tmp: Path, *, metric: str = "F1", results: dict[str, str] | None = None) -> Path:
    """A copy of scilead_tiny/ whose SQuAD tuples and leaderboard have metric `metric` and results `results`
    (paper -> result as printed; default HIGHER)."""
    out = tmp / "data"
    shutil.copytree(TINY, out)
    results = results or HIGHER
    tdm = json.loads((out / "tdm_annotations.json").read_text(encoding="utf-8"))
    for short, key in KEY.items():
        for row in tdm[key]["TDMs"]:
            if row["Dataset"] == "SQuAD":
                row["Metric"], row["Result"] = metric, results[short]
    (out / "tdm_annotations.json").write_text(json.dumps(tdm), encoding="utf-8")
    boards = json.loads((out / "leaderboards.json").read_text(encoding="utf-8"))
    boards[0]["Metric"] = metric
    boards[0]["Leaderboard"] = {KEY[p]: float(r) for p, r in results.items()}
    (out / "leaderboards.json").write_text(json.dumps(boards), encoding="utf-8")
    return out


def tiny_corpus(tmp: Path, papers: tuple[str, ...] = ("p1", "p2", "p3")) -> Path:
    return corpus_of(tmp / "corpus", {ARXIV[p]: f"# Tiny paper {p}\n\nWe report F1 on SQuAD." for p in papers})


def run_with_values(tmp: Path, values: dict[str, float], *, metric: str = "F1", dataset: str = "SQuAD",
                    names: dict[str, list[str]] | None = None) -> Path:
    """A run directory holding the ml values protocol and, per paper of `values`, a method, a dataset, a metric
    and a measurement of that value linked to the three; `names` is written as the run's names.json groups."""
    run = tmp / "run"
    run.mkdir(parents=True)
    (run / PROTOCOL_FILE).write_bytes(ML_VALUES_PROTOCOL.read_bytes())
    load(ML_VALUES_PROTOCOL)   # registers the ml types
    built: list[Item] = []
    for paper, value in values.items():
        span = [Span(role="quote", selector={"file": f"papers/{ARXIV[paper]}.md", "start": 0, "end": 4})]
        m = Item.build("method", {"name": f"Model-{paper}"}, span)
        d = Item.build("dataset", {"name": dataset}, span)
        k = Item.build("metric", {"name": metric}, span)
        v = Item.build("measurement", {"value": value}, span,
                       links={"method": m.item_id, "dataset": d.item_id, "metric": k.item_id})
        built += [m, d, k, v]
    write_lines(run / EVIDENCE_FILE, [i.model_dump(mode="json") for i in built])
    if names is not None:
        (run / NAMES_FILE).write_text(json.dumps({"groups": names, "matches": [], "unresolved": []}), encoding="utf-8")
    return run


def score_tiny(tmp: Path, values: dict[str, float], higher: bool = True, gold_result: str | None = None,
               metric: str | None = None, **run: Any) -> dict[str, Any]:
    """Score a run with `values` (paper -> its SQuAD value) on the tiny corpus. The board is F1 with HIGHER results,
    or, with `higher=False`, a perplexity board with LOWER results; `gold_result` replaces p1's gold result;
    `metric` is the name of the run's metric items (default: the board's metric)."""
    board = "F1" if higher else LOWER_METRIC
    results = dict(HIGHER if higher else LOWER)
    if gold_result is not None:
        results["p1"] = gold_result
    return score(run_with_values(tmp, values, metric=metric or board, **run), tiny_corpus(tmp),
                 data_dir(tmp, metric=board, results=results))


# --- the brief's tests ----------------------------------------------------------------------------------------


def test_best_matches_when_top_paper_agrees(tmp_path: Path) -> None:
    r = score_tiny(tmp_path, values={"p1": 0.9, "p2": 0.8})
    assert r["best"]["matched"] == 1 and r["best"]["leaderboards"] == 1


def test_lower_is_better_leaderboard(tmp_path: Path) -> None:
    assert score_tiny(tmp_path, values={"p1": 0.2, "p2": 0.1}, higher=False)["best"]["matched"] == 1


def test_pair_order_share(tmp_path: Path) -> None:
    assert score_tiny(tmp_path, values={"p1": 0.9, "p2": 0.8, "p3": 0.85})["chains"]["agree_share"] == pytest.approx(2 / 3)


def test_percent_and_fraction_values_match(tmp_path: Path) -> None:
    assert score_tiny(tmp_path, values={"p1": 0.905}, gold_result="90.5")["values"]["found"] == 1


# --- more ------------------------------------------------------------------------------------------------------


def test_best_misses_when_the_top_paper_differs(tmp_path: Path) -> None:
    r = score_tiny(tmp_path, values={"p1": 0.8, "p2": 0.9})
    assert (r["best"]["matched"], r["best"]["leaderboards"], r["best"]["with_values"]) == (0, 1, 1)
    board = next(iter(r["leaderboards"].values()))
    assert (board["gold_top"], board["engine_top"], board["match"]) == ("p1", "p2", False)


def test_direction_decides_the_engine_top(tmp_path: Path) -> None:
    """The same engine values and gold numbers on a higher-is-better board pick p1 (engine) and p3 (gold)."""
    r = score(run_with_values(tmp_path, {"p1": 0.2, "p2": 0.1}), tiny_corpus(tmp_path),
              data_dir(tmp_path, metric="F1", results=LOWER))
    assert r["best"]["matched"] == 0


def test_tied_engine_top_is_no_match(tmp_path: Path) -> None:
    r = score_tiny(tmp_path, values={"p1": 0.9, "p2": 0.9})
    assert r["best"]["matched"] == 0 and next(iter(r["leaderboards"].values()))["engine_top"] is None
    assert r["chains"]["pairs"] == 1 and r["chains"]["agree"] == 0


def test_a_tied_gold_top_accepts_either_paper(tmp_path: Path) -> None:
    r = score(run_with_values(tmp_path, {"p1": 0.85, "p2": 0.9}), tiny_corpus(tmp_path),
              data_dir(tmp_path, results={"p1": "90.0", "p2": "90.0", "p3": "80.0"}))
    assert r["best"]["matched"] == 1
    assert r["chains"]["pairs"] == 0   # p1-p2 tie in the gold; p3 has no engine value


def test_a_leaderboard_with_no_engine_value_counts_and_has_no_pairs(tmp_path: Path) -> None:
    r = score_tiny(tmp_path, values={"p1": 0.9}, metric="EM")
    assert (r["best"]["matched"], r["best"]["leaderboards"], r["best"]["with_values"]) == (0, 1, 0)
    assert r["chains"] == {"pairs": 0, "agree": 0, "agree_share": None}


def test_value_found_and_link(tmp_path: Path) -> None:
    """Found: the value is a gold result of the paper (half a unit of its last printed digit, x100 for a percent
    metric); linked: its metric item's cleaned name is the gold metric's."""
    r = score_tiny(tmp_path, values={"p1": 0.9, "p2": 0.849, "p3": 80.0})
    assert r["values"] == {"tuples": 5, "in_corpus": 4, "found": 2, "linked": 2, "found_share": 0.5,
                           "linked_share": 0.5}   # p2: 84.9 is not 85.0 (tolerance 0.05)


def test_the_tolerance_follows_the_gold_precision_and_scale() -> None:
    assert matches(0.905, "90.5", percent=True) and matches(90.5, "0.905", percent=True)
    assert not matches(0.905, "90.5", percent=False)       # a raw metric is never scaled
    assert not matches(90.4, "90.5", percent=True)         # half of 0.1, not half a point
    assert matches(90.0, "90", percent=True) and matches(90.4, "90", percent=True)   # "90": half a unit
    assert not matches(20.3, "20.7", percent=False)        # perplexity 20.3 is not 20.7
    assert not matches(1.05, "1.08", percent=False)        # bits per character stay apart
    assert matches(85.0, "85.0 ± 0.3", percent=True) and not matches(85.0, "n/a", percent=True)


def test_a_perplexity_is_compared_as_printed(tmp_path: Path) -> None:
    assert score_tiny(tmp_path, values={"p1": 20.3}, higher=False, gold_result="20.7")["values"]["found"] == 0
    assert score_tiny(tmp_path / "b", values={"p1": 20.7}, higher=False, gold_result="20.7")["values"]["found"] == 1


def test_raw_values_on_both_sides_of_one_rank_right(tmp_path: Path) -> None:
    """A lower-is-better raw metric (a table naming it) with 0.98 and 1.02: never scaled, so 0.98 is best."""
    table = tmp_path / "metrics.yaml"
    table.write_text("default: {direction: higher, scale: raw}\nmetrics:\n  BPC: {direction: lower, scale: raw}\n",
                     encoding="utf-8")
    data = data_dir(tmp_path, metric="BPC", results={"p1": "0.98", "p2": "1.02", "p3": "1.10"})
    run = run_with_values(tmp_path, {"p1": 0.98, "p2": 1.02}, metric="BPC")
    r = score(run, tiny_corpus(tmp_path), data, table)
    assert (r["best"]["matched"], r["chains"]["agree"], r["chains"]["pairs"]) == (1, 1, 1)
    assert r["values"]["found"] == 2 and r["metrics_by_default"] == {"count": 0, "metrics": []}
    unknown = score(run, tiny_corpus(tmp_path / "u"), data)   # the pack's table: BPC is not listed
    assert unknown["metrics_by_default"] == {"count": 1, "metrics": ["BPC"]} and unknown["best"]["matched"] == 0


def test_a_value_linked_to_another_metric_is_found_not_linked(tmp_path: Path) -> None:
    r = score_tiny(tmp_path, values={"p1": 0.9}, metric="Exact Match")
    assert (r["values"]["found"], r["values"]["linked"]) == (1, 0)


def test_the_name_group_links_a_metric_written_otherwise(tmp_path: Path) -> None:
    r = score_tiny(tmp_path, values={"p1": 0.9, "p2": 0.85}, metric="F1-measure",
                   names={"F1": ["F1", "F1-measure"]})
    assert r["values"]["linked"] == 2 and r["best"]["matched"] == 1
    assert score_tiny(tmp_path / "b", values={"p1": 0.9}, metric="F1-measure")["values"]["linked"] == 0


def test_dataset_name_must_match_for_best(tmp_path: Path) -> None:
    r = score_tiny(tmp_path, values={"p1": 0.9, "p2": 0.85}, dataset="SQuAD 2.0")
    assert r["best"]["with_values"] == 0 and r["values"]["linked"] == 2   # the link score asks only for the metric
    assert r["best"]["with_metric_values"] == 1   # a naming loss, not a ranking loss


def test_ids_and_papers_with_no_arxiv_id() -> None:
    """From an arxiv.org link (abs or pdf, version dropped), else from a key that is an arXiv id."""
    assert ids(TINY) == ["2101.00001", "2102.00002", "2103.00003"]
    assert no_arxiv(TINY) == ["p4"]


def test_gold_tuples_and_leaderboards() -> None:
    g = gold(TINY)
    assert g["tuples"]["p1"] == [("Question Answering", "SQuAD", "F1", "90.0"),
                                 ("Question Answering", "Natural Questions", "EM", "41.2")]
    assert g["leaderboards"] == [{"task": "Question Answering", "dataset": "SQuAD", "metric": "F1",
                                  "ranking": ["p1", "p2", "2103.00003.pdf"], "higher_is_better": True}]


def test_gold_ranking_follows_the_metric_direction(tmp_path: Path) -> None:
    board = gold(data_dir(tmp_path, metric=LOWER_METRIC, results=LOWER))["leaderboards"][0]
    assert (board["ranking"], board["higher_is_better"]) == (["p2", "p1", "2103.00003.pdf"], False)


def test_unfetched_papers_are_listed_and_the_ranking_uses_the_fetched_ones(tmp_path: Path) -> None:
    """p1 (the gold top) was not fetched: the engine's top is compared with the top of the fetched papers."""
    r = score(run_with_values(tmp_path, {"p2": 0.85, "p3": 0.8}), tiny_corpus(tmp_path, ("p2", "p3")), data_dir(tmp_path))
    assert r["not_fetched"] == {"no_arxiv_id": ["p4"], "not_in_corpus": ["p1"]}
    board = next(iter(r["leaderboards"].values()))
    assert (board["gold_top"], board["gold_top_fetched"], board["match"]) == ("p1", False, True)
    assert r["best"]["gold_top_not_fetched"] == 1


def test_a_run_of_another_corpus_is_refused(tmp_path: Path) -> None:
    run = run_with_values(tmp_path, {"p1": 0.9})
    other = corpus_of(tmp_path / "other", {"2999.99999v1": "# other"})
    with pytest.raises(ValueError, match="no paper of"):
        score(run, other, data_dir(tmp_path))


def test_cli_ids_then_score(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ids_txt, out = tmp_path / "ids.txt", tmp_path / "out"
    assert cli.main(["scilead", "ids", "--data", str(TINY), "--out", str(ids_txt)]) == 0
    assert ids_txt.read_text(encoding="utf-8") == "2101.00001\n2102.00002\n2103.00003\n"
    assert "p4" in capsys.readouterr().out
    run = run_with_values(tmp_path, {"p1": 0.9, "p2": 0.8, "p3": 0.85})
    assert cli.main(["scilead", "score", "--run", str(run), "--corpus", str(tiny_corpus(tmp_path)),
                     "--data", str(TINY), "--out", str(out)]) == 0
    real = json.loads((out / "real.json").read_text(encoding="utf-8"))
    assert real["best"]["report"] == "1 of 1" and real["chains"]["agree"] == 2
    md = (out / "real.md").read_text(encoding="utf-8")
    assert md.startswith("# real-paper check: SciLead (not a synthetic score)")
    assert "best number" in md and "pairwise order" in md and "attachments/2024.emnlp-main.453.data.zip" in md
    assert "metrics.yaml" in md


def test_values_protocol_end_to_end_with_a_scripted_model(tmp_path: Path) -> None:
    """The ml values protocol runs (llm-only, scripted model): the measurement links to its method, dataset and
    metric, and the scorer finds and links the value."""
    text = "# Tiny paper p1\n\nOur model QA-Net reaches 90.0 F1 on SQuAD."
    corpus = corpus_of(tmp_path / "corpus", {ARXIV["p1"]: text})
    names = {"method": "QA-Net", "dataset": "SQuAD", "metric": "F1"}

    def script(etype: str, doc: str, prompt: str) -> dict[str, Any]:
        if etype in names:
            return {"items": [{"fields": {"name": names[etype]}, "quotes": {f"{etype}_label": names[etype]}}]}
        if etype == "measurement":
            return {"items": [{"fields": {"value": 90.0},
                               "links": {t: context_id(prompt, n) for t, n in names.items()},
                               "quotes": {"value": "90.0", "method_label": None, "dataset_label": None,
                                          "metric_label": None}}]}
        return empty(etype, doc, prompt)

    run = engine.run(ML_VALUES_PROTOCOL, corpus, tmp_path / "runs", selection="llm-only",
                     provider=provider_of(scripted(script, [])), model="scripted-alias", strategy="all", workers=1)
    r = score(run, corpus, data_dir(tmp_path))
    assert (r["values"]["found"], r["values"]["linked"]) == (1, 1)
    assert r["leaderboards"]["Question Answering | SQuAD | F1"]["engine_values"] == {"p1": 90.0}


def test_a_bad_release_is_refused(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    tdm = json.loads((data / "tdm_annotations.json").read_text(encoding="utf-8"))
    tdm["p2"]["link"] = "https://arxiv.org/abs/2101.00001v3"   # p1's paper again
    (data / "tdm_annotations.json").write_text(json.dumps(tdm), encoding="utf-8")
    with pytest.raises(ValueError, match="belongs to"):
        ids(data)
    del tdm["p2"]
    (data / "tdm_annotations.json").write_text(json.dumps(tdm), encoding="utf-8")
    (data / "leaderboards.json").write_text(json.dumps([{"Task": "T", "Dataset": "D", "Metric": "M",
                                                         "Leaderboard": {"p1": "n/a"}}]), encoding="utf-8")
    with pytest.raises(ValueError, match="has no score"):
        gold(data)
    (data / "leaderboards.json").write_text(json.dumps([{"Task": "T", "Dataset": "D", "Metric": "M"}]),
                                            encoding="utf-8")
    with pytest.raises(ValueError, match="lacks"):
        gold(data)
