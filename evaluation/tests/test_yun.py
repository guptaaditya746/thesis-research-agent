"""The Yun et al. 2024 + Evidence Inference 2.0 real-paper check (D42, spec 6.12): A (names, values), B (value -> arm
and outcome) and C (direction against the Evidence Inference label), reported separately.

The fixture `yun_tiny/` is hand-made data (not data of either release) in the real layouts (yun_tiny/provenance.json:
the headers are copied from the files at the commits named there): the llm-meta-analysis checkout's
annotated_rct_dataset.csv (3 records) and two markdown papers, and Evidence Inference's annotations/ (3 prompts).
  record 1  PMC1001, Zelvora vs placebo, response rate, binary 41/120 vs 22/118 (complete), EI 9001 increased
  record 2  PMC1001, pain score, continuous, means 3.1 vs 4.0 without SDs (incomplete), EI 9002 no difference
            (the one other annotation is not valid and is left out)
  record 3  PMC1002, response rate, binary, comparator events missing (incomplete), EI 9003 decreased
Runs are of the drugtoy fixture pack (the real domains/drugtrials pack is a live step still owed)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from evaluation import cli
from evaluation.realpapers.yun import GOLD_FILE, direction_label, score, to_corpus, value_matches
from evaluation.tests.helpers import guard_corpus
from evidence import comparisons, contract
from evidence.contract import Item, Span
from evidence.pack import RoleMap, load_pack, register_pack
from evidence.protocol import load
from evidence.rundir import COMPARISONS_FILE, EVIDENCE_FILE, PROTOCOL_FILE, RUN_FILE, write_lines
from evidence.tests.conftest import regex_run_dir

TINY = Path(__file__).resolve().parent / "data" / "yun_tiny"
REPO, EI = TINY / "llm-meta-analysis", TINY / "evidence-inference" / "annotations"
FIXTURES = Path(__file__).resolve().parents[2] / "evidence" / "tests" / "fixtures"
RESPONSE = FIXTURES / "drugtoy" / "protocols" / "drugtoy-response.yaml"
DOC = {"p1": "PMC1001", "p2": "PMC1002"}
SIDE = {"Zelvora": "drug", "placebo": "placebo"}


@pytest.fixture(autouse=True)
def code_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sealed runs name commit `test` (no `git rev-parse` per run; F54)."""
    monkeypatch.setenv("EVIDENCE_CODE_COMMIT", "test")


@pytest.fixture(autouse=True)
def _registry():
    """Each test leaves the type registry as it found it (as evidence/tests/test_comparisons.py does): the drugtoy
    types are registered for the test and dropped after, so a later test of renamed types does not find them."""
    before = dict(contract.ITEM_PREFIX)
    register_pack(load_pack("drugtoy", root=FIXTURES))
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


def tiny_corpus(tmp: Path) -> Path:
    return to_corpus(REPO, EI, tmp / "corpus")


def measure(paper: str, value: float, *, arm: str, outcome: str) -> list[Item]:
    """An arm, an outcome and a result of `value` linked to both, in paper `paper` (p1, p2)."""
    span = [Span(role="quote", selector={"file": f"papers/{DOC[paper]}.md", "start": 0, "end": 4})]
    a = Item.build("arm", {"label": arm, "role": SIDE.get(arm, "other")}, span)
    o = Item.build("outcome", {"name": outcome, "canonical": "response_rate", "higher_is_better": True}, span)
    r = Item.build("result", {"value": value, "population": None}, span, links={"arm": a.item_id, "outcome": o.item_id})
    return [a, o, r]


def run_of(tmp: Path, items: list[Item]) -> Path:
    """A run directory of the drugtoy response protocol holding `items` and the comparisons plan 2 builds from them."""
    run = tmp / "run"
    run.mkdir(parents=True)
    (run / PROTOCOL_FILE).write_bytes(RESPONSE.read_bytes())
    (run / RUN_FILE).write_text(json.dumps({"settings": {"domains": str(FIXTURES)}}), encoding="utf-8")
    unique = list({i.item_id: i for i in items}.values())
    write_lines(run / EVIDENCE_FILE, [i.model_dump(mode="json") for i in unique])
    by_doc: dict[str, list[Item]] = {}
    for item in unique:
        by_doc.setdefault(Path(item.spans[0].selector["file"]).stem, []).append(item)
    built = comparisons.of_run(load(RESPONSE, FIXTURES), list(DOC.values()), by_doc,
                               RoleMap(load_pack("drugtoy", root=FIXTURES)), None)
    (run / COMPARISONS_FILE).write_text(json.dumps(built.json()), encoding="utf-8")
    return run


def score_tiny(tmp: Path, items: list[Item] | None = None) -> dict:
    return score(run_of(tmp, items or []), tiny_corpus(tmp))


# --- the brief's tests -----------------------------------------------------------------------------------------

def test_incomplete_record_is_scored_on_names_and_direction_only(tmp_path):
    r = score_tiny(tmp_path)
    assert r["A_values"]["records"] == r["complete"] and r["A_names"]["records"] == r["records"]
    assert (r["records"], r["complete"], r["C"]["records"], r["B"]["records"]) == (3, 1, 3, 1)


def test_count_value_matches_events_over_size(tmp_path):
    assert score_tiny(tmp_path, items=measure("p1", 41 / 120, arm="Zelvora", outcome="response rate"))[
        "A_values"]["matched"] == 1


@pytest.mark.parametrize("delta,neutral,label", [(0.1, False, "significantly increased"),
                                                 (-0.1, False, "significantly decreased"),
                                                 (0.001, True, "no significant difference")])
def test_direction_mapping(delta, neutral, label):
    assert direction_label(delta, neutral) == label


def test_complete_share_is_reported(tmp_path):
    r = score_tiny(tmp_path)
    assert 0 <= r["complete_share"] <= 1 and r["complete_share"] == pytest.approx(1 / 3)


# --- the corpus and the gold ----------------------------------------------------------------------------------

def test_corpus_holds_the_papers_and_the_gold(tmp_path):
    corpus = tiny_corpus(tmp_path)
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    assert [(p["id"], p["file"]) for p in manifest["papers"]] == [("PMC1001", "papers/PMC1001.md"),
                                                                  ("PMC1002", "papers/PMC1002.md")]
    assert (corpus / "papers" / "PMC1001.md").read_bytes() == (
        REPO / "evaluation" / "data" / "no_attributes_markdown_files" / "PMC1001.md").read_bytes()
    gold = json.loads((corpus / GOLD_FILE).read_text(encoding="utf-8"))
    first, second = gold["PMC1001"]
    assert {k: first[k] for k in ("intervention", "comparator", "outcome", "kind", "ei_label", "complete")} == {
        "intervention": "Zelvora", "comparator": "placebo", "outcome": "response rate", "kind": "binary",
        "ei_label": "significantly increased", "complete": True}
    assert first["values"] == {"intervention_events": 41, "intervention_group_size": 120, "comparator_events": 22,
                               "comparator_group_size": 118}
    assert second["kind"] == "continuous" and second["complete"] is False
    assert second["ei_label"] == "no significant difference"   # the annotation marked not valid is left out
    assert second["values"]["intervention_standard_deviation"] is None
    assert gold["PMC1002"][0]["complete"] is False and gold["PMC1002"][0]["ei_label"] == "significantly decreased"


def test_a_record_without_a_label_or_numbers_has_nulls(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(REPO, repo)
    csv = repo / "evaluation" / "data" / "annotated_rct_dataset.csv"
    lines = csv.read_text(encoding="utf-8").splitlines()
    cells = lines[3].split(",")
    cells[1] = ""                                     # no Evidence Inference prompt
    cells[7:11] = ["", "", "", ""]                   # no numbers at all
    csv.write_text("\n".join(lines[:3] + [",".join(cells)]) + "\n", encoding="utf-8")
    gold = json.loads((to_corpus(repo, EI, tmp_path / "corpus") / GOLD_FILE).read_text(encoding="utf-8"))
    assert gold["PMC1002"][0]["ei_label"] is None and gold["PMC1002"][0]["values"] is None


def test_an_unknown_outcome_type_is_refused(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(REPO, repo)
    csv = repo / "evaluation" / "data" / "annotated_rct_dataset.csv"
    csv.write_text(csv.read_text(encoding="utf-8").replace(",binary,41,", ",ordinal,41,"), encoding="utf-8")
    with pytest.raises(ValueError, match="ordinal"):
        to_corpus(repo, EI, tmp_path / "corpus")


# --- A, B and C -----------------------------------------------------------------------------------------------

def test_names_are_found_by_clean_form(tmp_path):
    items = measure("p1", 0.5, arm="ZELVORA", outcome="Response rates") + measure("p1", 0.4, arm="Placebo",
                                                                                   outcome="response rate")
    names = score_tiny(tmp_path, items)["A_names"]
    assert (names["intervention"], names["comparator"], names["outcome"], names["all"]) == (2, 2, 1, 1)   # no pain score item


def test_continuous_mean_is_matched_within_one_percent():
    assert value_matches(3.12, {"kind": "continuous", "mean": 3.1})
    assert not value_matches(3.2, {"kind": "continuous", "mean": 3.1})
    assert value_matches(0.3392, {"kind": "binary", "events": 41, "size": 120})       # 0.3417 - 0.0025
    assert not value_matches(0.3477, {"kind": "binary", "events": 41, "size": 120})   # 0.006 off


def test_b_needs_the_value_linked_to_the_matched_arm_and_outcome(tmp_path):
    right = score_tiny(tmp_path / "a", measure("p1", 41 / 120, arm="Zelvora", outcome="response rate"))
    wrong = score_tiny(tmp_path / "b", measure("p1", 41 / 120, arm="placebo", outcome="response rate"))
    assert (right["A_values"]["matched"], right["B"]["linked"]) == (1, 1)
    assert (wrong["A_values"]["matched"], wrong["B"]["linked"]) == (1, 0)


def test_c_compares_the_engine_direction_with_the_label(tmp_path):
    items = measure("p1", 0.342, arm="Zelvora", outcome="response rate") + measure(
        "p1", 0.186, arm="placebo", outcome="response rate") + measure(
        "p2", 0.2, arm="Zelvora", outcome="response rate") + measure("p2", 0.205, arm="placebo",
                                                                      outcome="response rate")
    c = score_tiny(tmp_path, items)["C"]
    assert (c["records"], c["compared"], c["agree"]) == (3, 2, 1)
    assert c["by_label"]["significantly increased"] == {"significantly increased": 1}
    assert c["by_label"]["significantly decreased"] == {"no significant difference": 1}   # within min_effect
    assert c["by_label"]["no significant difference"] == {"none": 1}


# --- a real engine run, the gold unread, the command line -----------------------------------------------------

def test_regex_run_on_the_tiny_corpus_never_reads_the_gold(tmp_path, monkeypatch):
    corpus = tiny_corpus(tmp_path)
    attempts = guard_corpus(monkeypatch, corpus)
    run = regex_run_dir(corpus, tmp_path, RESPONSE, domains=FIXTURES)
    monkeypatch.undo()
    assert attempts == []
    r = score(run, corpus)
    assert r["A_values"]["matched"] == 2 and r["B"]["linked"] == 2
    assert r["C"]["agree"] == 2   # record 1 increased, record 3 decreased; the pain score is no drugtoy outcome


def test_cli_writes_real_json_and_md(tmp_path, capsys):
    corpus = tmp_path / "corpus"
    assert cli.main(["yun", "corpus", "--repo", str(REPO), "--ei", str(EI), "--out", str(corpus)]) == 0
    run = run_of(tmp_path, measure("p1", 41 / 120, arm="Zelvora", outcome="response rate"))
    assert cli.main(["yun", "score", "--run", str(run), "--corpus", str(corpus), "--out", str(tmp_path / "d")]) == 0
    real = json.loads((tmp_path / "d" / "real.json").read_text(encoding="utf-8"))
    assert {"records", "complete", "complete_share", "A_names", "A_values", "B", "C"} <= set(real)
    md = (tmp_path / "d" / "real.md").read_text(encoding="utf-8")
    assert md.startswith("# real-paper check: Yun et al. 2024 + Evidence Inference (not a synthetic score)")
    assert "records without complete numbers are scored on names and direction only" in md
    assert "1bc768d4d098c727c9866eeff909297c38a3e84c" in md and "a661e8c14f973398380c8865cf2f27a535aaaf6d" in md


def test_a_run_without_comparisons_is_refused(tmp_path):
    run = run_of(tmp_path, [])
    (run / COMPARISONS_FILE).unlink()
    with pytest.raises(ValueError, match="comparisons.json"):
        score(run, tiny_corpus(tmp_path))
