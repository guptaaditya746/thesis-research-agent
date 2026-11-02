"""Cost per system and the losses-first table (evaluation/losses.py; spec 6.16, D41)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evaluation import cli as evaluate
from evaluation import report as rep
from evaluation.losses import CAUSES, REF, headline, loss_cause, losses, read_reports, system_cost, write_losses
from evaluation.truth import ENGINE

RAG = "bm25-answer-baseline"


def rag_answer(**fields: Any) -> dict[str, Any]:
    return {"system": RAG, "label": "supports", "studies": [], **fields}


def report(question_id: str, *, engine: float | None, rag: float | None, missed: list[str] | None = None,
           assoc: float = 1.0, unresolved_names: int | None = None, kind: str = "effect",
           ref: str | None = None, **extra: Any) -> dict[str, Any]:
    """A report.json as `evaluate score` writes it, cut down to what losses() reads; the effect C rows carry the
    headline (direction accuracy over all levels), B the association accuracy."""
    def system(name: str, value: float | None) -> dict[str, Any]:
        return {"system": name, "label": "supports", "expected_label": "supports", "label_correct": True,
                "rows": [{"level": "low", "direction_accuracy": 0.0}, {"level": "all", "direction_accuracy": value}],
                "cost": {"model_calls": 2, "input_tokens": 10, "output_tokens": 5, "tokens": 15}}
    return {"question_id": question_id, "kind": kind, "domain": "rag", "corpus_name": "c", "run_id": "r",
            "extraction": {"rows": [], "scored_types": ["measurement"], "missed": missed or [], "unmatched_items": []},
            "integration": {"rows": [{"level": "all", "association_accuracy": assoc}], "studies": []},
            "unresolved_names": unresolved_names, "synthesis": [system(ENGINE, engine), system(RAG, rag)],
            REF: ref or f"cascade-gaps~{question_id}", **extra}


# --- system_cost ----------------------------------------------------------------------------------------------

def test_baseline_cost_counts_both_calls() -> None:
    c = system_cost(rag_answer(model_call={"input_tokens": 900, "output_tokens": 100},
                               mapping_call={"input_tokens": 50, "output_tokens": 10}), None)
    assert c == {"model_calls": 2, "input_tokens": 950, "output_tokens": 110, "tokens": 1060}


def test_baseline_without_a_mapping_call_made_one_call() -> None:
    c = system_cost(rag_answer(model_call={"input_tokens": 900, "output_tokens": 100}, mapping_call=None), None)
    assert c == {"model_calls": 1, "input_tokens": 900, "output_tokens": 100, "tokens": 1000}


def test_engine_cost_is_the_runs() -> None:
    run = {"cost": {"calls": 7, "model_calls": 3, "made_model_calls": 1, "input_tokens": 300, "output_tokens": 40}}
    assert system_cost({"system": ENGINE}, run) == {"model_calls": 3, "input_tokens": 300, "output_tokens": 40,
                                                    "tokens": 340}


def test_engine_run_without_cost_is_unknown_not_zero() -> None:
    assert system_cost({"system": ENGINE}, {}) == {"model_calls": None, "input_tokens": None, "output_tokens": None,
                                                   "tokens": None}


def test_agent_baseline_tokens_are_not_split() -> None:
    answer = {"system": "agent-baseline", "agent": {"model_calls": 12, "tokens": 5000},
              "mapping_call": {"input_tokens": 50, "output_tokens": 10}}
    assert system_cost(answer, None) == {"model_calls": 13, "input_tokens": None, "output_tokens": None,
                                         "tokens": 5060}


def test_an_answer_that_records_no_call_has_unknown_cost() -> None:
    assert system_cost({"system": "oracle-synthesis", "studies": []}, None)["model_calls"] is None


# --- headline -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind,system,value", [
    ("effect", {"rows": [{"level": "low", "direction_accuracy": 0.1}, {"level": "all", "direction_accuracy": 0.7}]},
     0.7),
    ("inventory", {"f1": 0.5, "precision": 1.0}, 0.5),
    ("best", {"per_study_accuracy": 0.25, "winner_correct": True}, 0.25),
    ("consistency", {"per_study_accuracy": 0.75}, 0.75),
    ("chaining", {"headline": 0.5, "verdict_correct": True}, 0.5),
    ("limitations", {"headline": 0.0}, 0.0),
    ("builds_on", {"headline": 1.0}, 1.0)])
def test_headline_per_kind(kind: str, system: dict[str, Any], value: float) -> None:
    assert headline(kind, system) == value


def test_new_kind_without_headline_is_named() -> None:
    with pytest.raises(KeyError, match="chaining"):
        headline("chaining", {"rows": [{"level": "all"}]})


def test_effect_without_an_all_row_has_no_headline() -> None:
    assert headline("effect", {"rows": []}) is None


# --- losses and their cause -----------------------------------------------------------------------------------

def test_losses_come_first_with_one_cause() -> None:
    out = losses([report("q1", engine=0.9, rag=0.5), report("q2", engine=0.4, rag=0.8, missed=["f1"])])
    rows = out["domains"]["rag"]
    assert [r["question_id"] for r in rows] == ["q2", "q1"] and rows[0]["cause"] == "missed" and rows[1]["cause"] is None
    assert rows[0]["systems"] == {ENGINE: 0.4, RAG: 0.8} and rows[0]["report"] == "cascade-gaps~q2"
    assert rows[0]["cost"][RAG]["tokens"] == 15 and rows[0]["engine_loss"] is True


@pytest.mark.parametrize("fields,cause", [({"assoc": 0.5}, "wrongly linked"), ({"unresolved_names": 3}, "names not grouped"),
                                          ({}, "wrong rule")])
def test_each_cause(fields: dict[str, Any], cause: str) -> None:
    assert loss_cause(report("q", engine=0.1, rag=0.9, **fields)) == cause


def test_causes_in_order() -> None:
    assert CAUSES == ("missed", "wrongly linked", "names not grouped", "wrong rule")
    both = report("q", engine=0.1, rag=0.9, missed=["f1"], assoc=0.5, unresolved_names=2)
    assert loss_cause(both) == "missed"


def test_inventory_split_or_merged_is_names_not_grouped() -> None:
    r = report("q", engine=0.1, rag=0.9, kind="inventory")
    r["integration"] = {"kind": "inventory", "entries": 3, "split": 0, "merged": 1, "clean_share": 0.5}
    assert loss_cause(r) == "names not grouped"


@pytest.mark.parametrize("kind,b", [
    ("chaining", {"comparison_precision": 1.0, "comparison_recall": 0.5}),
    ("limitations", {"items": 4, "linked": 3, "link_share": 0.75}),
    ("builds_on", {"link_precision": 0.5, "link_recall": 1.0})])
def test_a_new_kinds_link_loss_is_wrongly_linked(kind: str, b: dict[str, Any]) -> None:
    """F33: B comes from the report's own B row; the new kinds' rows measure links (B_LINK)."""
    r = report("q", engine=0.1, rag=0.9, kind=kind)
    r["integration"] = {"kind": kind, **b}
    assert loss_cause(r) == "wrongly linked"


def test_null_link_rates_fall_through() -> None:
    """Chaining without comparisons.json: null rates are not a link loss."""
    r = report("q", engine=0.1, rag=0.9, kind="chaining")
    r["integration"] = {"kind": "chaining", "comparisons": None, "comparison_precision": None,
                        "comparison_recall": None}
    assert loss_cause(r) == "wrong rule"


def test_perfect_links_are_not_a_link_loss() -> None:
    r = report("q", engine=0.1, rag=0.9, kind="builds_on")
    r["integration"] = {"kind": "builds_on", "link_precision": 1.0, "link_recall": 1.0}
    assert loss_cause(r) == "wrong rule"


def test_consistency_claim_accuracy_is_its_b_accuracy() -> None:
    r = report("q", engine=0.1, rag=0.9, kind="consistency")
    r["integration"] = {"kind": "consistency", "claim_accuracy": 0.5, "rows": [{"level": "all",
                                                                                "association_accuracy": 1.0}]}
    assert loss_cause(r) == "wrongly linked"


def test_a_wrong_label_is_a_loss_even_when_the_engine_scores_higher() -> None:
    r = report("q", engine=0.9, rag=0.5)
    r["synthesis"][0]["label_correct"] = False
    (row,) = losses([r])["domains"]["rag"]
    assert row["engine_loss"] and row["cause"] == "wrong rule"


def test_a_wrong_winner_is_a_loss() -> None:
    r = report("q", engine=None, rag=None, kind="best")
    r["synthesis"] = [{"system": ENGINE, "per_study_accuracy": 1.0, "winner_correct": False},
                      {"system": RAG, "per_study_accuracy": 0.5, "winner_correct": True}]
    r["integration"] = {"kind": "best", "kind_accuracy": 1.0}
    (row,) = losses([r])["domains"]["rag"]
    assert row["engine_loss"] and row["systems"] == {ENGINE: 1.0, RAG: 0.5} and row["cost"] == {}


def test_an_oracle_is_not_a_baseline_to_lose_to() -> None:
    r = report("q", engine=0.5, rag=0.4)
    r["synthesis"].append({"system": "oracle-synthesis", "label_correct": True,
                           "rows": [{"level": "all", "direction_accuracy": 1.0}]})
    (row,) = losses([r])["domains"]["rag"]
    assert not row["engine_loss"] and row["systems"]["oracle-synthesis"] == 1.0


def test_answers_only_are_listed_never_a_loss() -> None:
    r = report("q", engine=None, rag=0.4)
    r["synthesis"] = r["synthesis"][1:]
    (row,) = losses([r])["domains"]["rag"]
    assert row["engine_loss"] is False and row["cause"] is None


def test_domains_are_kept_apart() -> None:
    out = losses([report("q1", engine=0.1, rag=0.9, domain="drugtrials"), report("q2", engine=0.1, rag=0.9)])
    assert sorted(out["domains"]) == ["drugtrials", "rag"]


def test_a_report_without_its_ref_is_refused() -> None:
    r = report("q", engine=0.1, rag=0.9)
    del r[REF]
    with pytest.raises(KeyError, match=REF):
        losses([r])


# --- files and the command ------------------------------------------------------------------------------------

def test_losses_md_opens_with_tims_sentence(tmp_path: Path) -> None:
    write_losses(losses([report("q1", engine=0.1, rag=0.9)]), tmp_path)
    md = (tmp_path / "losses.md").read_text(encoding="utf-8")
    assert "We should not assume that the evidence-level approach will necessarily perform better" in md.split("##")[1]
    assert "q1" in md and "wrong rule" in md and json.loads((tmp_path / "losses.json").read_text())["domains"]["rag"]


def test_read_reports_names_each_by_its_folder(tmp_path: Path) -> None:
    for group, name in (("cascade", "c1"), ("regex-only", "c1")):
        rep.write_report({**report("q1", engine=0.1, rag=0.9), "corpus_id": "c", "levels": ["all"]}, tmp_path / group / name)
    (tmp_path / "losses").mkdir()
    (tmp_path / "losses" / "losses.json").write_text("{}")
    got = read_reports(tmp_path)
    assert [r[REF] for r in got] == ["cascade~c1", "regex-only~c1"]


def test_evaluate_losses_writes_both_files(tmp_path: Path) -> None:
    rep.write_report({**report("q1", engine=0.1, rag=0.9), "corpus_id": "c", "levels": ["all"]},
                     tmp_path / "scores" / "cascade" / "c1")
    assert evaluate.main(["losses", "--scores", str(tmp_path / "scores"), "--out", str(tmp_path / "out")]) == 0
    rows = json.loads((tmp_path / "out" / "losses.json").read_text(encoding="utf-8"))["domains"]["rag"]
    assert [(r["report"], r["cause"]) for r in rows] == [("cascade~c1", "wrong rule")]


def test_report_md_has_a_cost_per_system_table_after_c() -> None:
    r = {**report("q1", engine=0.1, rag=0.9), "corpus_id": "c", "levels": ["all"], "extraction": None,
         "integration": None}
    for s in r["synthesis"]:
        s |= {"errors": [], "flags": None}
    md = rep.render(r)
    assert "## Cost per system" in md and md.index("## C. Synthesis") < md.index("## Cost per system")
    assert "| system " in md.split("## Cost per system")[1] and "input_tokens" in md
