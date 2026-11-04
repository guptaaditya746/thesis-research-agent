"""scripts/plan-runs.py (final review C3 (3)-(4), I1, I7): the switches reach the plan run, only a complete run is
skipped, a failed one is set aside and rerun, and `confirm` keeps a hand-edited plan. No model: planrun.run is faked."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from evidence import planrun
from evidence.plan import load_plan, write_plan
from evidence.tests.test_plan_run import make_plan

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "plan-runs.py"


def script() -> Any:
    spec = importlib.util.spec_from_file_location("plan_runs", SCRIPT)
    module = importlib.util.module_from_spec(spec)   # type: ignore[arg-type]
    spec.loader.exec_module(module)                    # type: ignore[union-attr]
    return module


def unconfirmed(tmp: Path) -> tuple[Path, Path]:
    """(plans folder, corpus) with the unconfirmed plan of the synthetic question effect-<corpus>."""
    plans, corpus = tmp / "plans", tmp / "corpus-x"
    plans.mkdir()
    corpus.mkdir()
    plan = make_plan()
    plan = plan.model_copy(update={"decisions": [d.model_copy(update={"confirmed_by": None, "confirmed_at": None})
                                                 for d in plan.decisions]})
    write_plan(plan, plans / "effect-corpus-x.json")
    return plans, corpus


def fake_run(monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, Any]], status: str = "complete") -> None:
    def run(plan_path: Path, corpus: Path, out_dir: Path, **kw: Any) -> Path:
        calls.append({"plan": Path(plan_path), **kw})
        root = Path(out_dir) / kw["run_id"]
        root.mkdir(parents=True)
        (root / "manifest.json").write_text(json.dumps({"status": status}), encoding="utf-8")
        return root
    monkeypatch.setattr(planrun, "run", run)


def argv(plans: Path, corpus: Path, tmp: Path, *more: str, confirm: str = "auto") -> list[str]:
    return ["run", "--set", "synthetic", "--corpus", str(corpus), "--question", "Q?", "--plans", str(plans),
            "--cache", str(tmp / "cache"), "--runs", str(tmp / "runs"), "--confirm", confirm, *more]


def test_the_switches_reach_the_plan_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plans, corpus = unconfirmed(tmp_path)
    calls: list[dict[str, Any]] = []
    fake_run(monkeypatch, calls)
    assert script().main(argv(plans, corpus, tmp_path, "--reasoning", "off", "--links", "off")) == 0
    assert calls[0]["reasoning"] == "off" and calls[0]["links"] == "off" and calls[0]["retry_errors"] is False


def test_links_default_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plans, corpus = unconfirmed(tmp_path)
    calls: list[dict[str, Any]] = []
    fake_run(monkeypatch, calls)
    monkeypatch.delenv("EV_ONTOLOGY_DIR", raising=False)
    assert script().main(argv(plans, corpus, tmp_path, "--reasoning", "off")) == 0
    assert calls[0]["links"] == "on"
    import os
    assert "EV_ONTOLOGY_DIR" not in os.environ   # reasoning off is a real switch, not an empty ontology folder


def test_a_complete_run_is_skipped_a_failed_one_is_set_aside_and_rerun(tmp_path: Path,
                                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    plans, corpus = unconfirmed(tmp_path)
    calls: list[dict[str, Any]] = []
    fake_run(monkeypatch, calls, status="failed")
    mod = script()
    assert mod.main(argv(plans, corpus, tmp_path, "--reasoning", "on")) == 0
    runs = tmp_path / "runs"
    assert mod.main(argv(plans, corpus, tmp_path, "--reasoning", "on")) == 0     # failed: set aside, run again
    assert (runs / "effect-corpus-x.failed-1").is_dir() and calls[1]["retry_errors"] is True
    (runs / "effect-corpus-x" / "manifest.json").unlink()                        # never sealed: also rerun
    fake_run(monkeypatch, calls, status="complete")
    assert mod.main(argv(plans, corpus, tmp_path, "--reasoning", "on")) == 0
    assert (runs / "effect-corpus-x.failed-2").is_dir() and len(calls) == 3
    assert mod.main(argv(plans, corpus, tmp_path, "--reasoning", "on")) == 0     # complete: skipped
    assert len(calls) == 3


def test_confirm_writes_and_prints_then_keeps_a_hand_edited_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                                 capsys: pytest.CaptureFixture[str]) -> None:
    plans, corpus = unconfirmed(tmp_path)
    mod = script()
    base = ["confirm", "--set", "synthetic", "--corpus", str(corpus), "--question", "Q?", "--plans", str(plans)]
    with pytest.raises(SystemExit):
        mod.main([*base, "--by", "system"])
    assert mod.main([*base, "--by", "aditya"]) == 0
    hand = plans / "hand-confirmed" / "effect-corpus-x.json"
    out = capsys.readouterr().out
    assert hand.is_file() and "decision d1 (threshold)" in out and "words rag: retrieval-augmented model" in out
    plan = load_plan(hand)
    assert plan.ready() and {d.confirmed_by for d in plan.decisions} == {"aditya"}
    edited = plan.model_copy(update={"decisions": [d.model_copy(update={"value": "0.05"}) if d.id == "d1" else d
                                                   for d in plan.decisions]})
    write_plan(edited, hand)
    before = hand.read_bytes()
    assert mod.main([*base, "--by", "aditya"]) == 0 and "kept" in capsys.readouterr().out
    calls: list[dict[str, Any]] = []
    fake_run(monkeypatch, calls)
    assert mod.main(argv(plans, corpus, tmp_path, "--reasoning", "on", "--confirm-by", "aditya", confirm="hand")) == 0
    assert hand.read_bytes() == before and calls[0]["plan"] == hand   # the run uses the edited file as it is


def test_redo_unchecked_reruns_a_complete_run_with_unchecked_items(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plans, corpus = unconfirmed(tmp_path)
    calls: list[dict[str, Any]] = []
    fake_run(monkeypatch, calls)
    mod = script()
    assert mod.main(argv(plans, corpus, tmp_path, "--reasoning", "on")) == 0
    folder = tmp_path / "runs" / "effect-corpus-x"
    (folder / "stage_report.json").write_text(json.dumps({"claims": {"S1": ["unchecked: sentence 0-9: x"]}}),
                                              encoding="utf-8")
    assert mod.main(argv(plans, corpus, tmp_path, "--reasoning", "on")) == 0 and len(calls) == 1   # default off
    assert mod.main(argv(plans, corpus, tmp_path, "--reasoning", "on", "--redo-unchecked")) == 0
    assert (tmp_path / "runs" / "effect-corpus-x.redo-1").is_dir() and calls[1]["retry_errors"] is True
    assert mod.main(argv(plans, corpus, tmp_path, "--reasoning", "on", "--redo-unchecked")) == 0
    assert len(calls) == 2                                   # the new run has nothing unchecked: skipped


def test_redo_unchecked_reads_failed_recheck_calls(tmp_path: Path) -> None:
    mod = script()
    (tmp_path / "recheck_report.json").write_text(json.dumps({"S1": {"unchecked": [
        {"item_id": "a", "why": "the model gave no verdict for this find"}]}}), encoding="utf-8")
    assert not mod.has_unchecked(tmp_path)
    (tmp_path / "recheck_report.json").write_text(json.dumps({"S1": {"unchecked": [
        {"item_id": "a", "why": "failed call: StageCallError: recheck: down"}]}}), encoding="utf-8")
    assert mod.has_unchecked(tmp_path)


def test_confirm_refuses_before_writing_when_a_plan_is_missing(tmp_path: Path) -> None:
    plans, corpus = unconfirmed(tmp_path)
    (plans / "effect-corpus-x.json").unlink()
    with pytest.raises(SystemExit, match="plan-runs.py plan"):
        script().main(["confirm", "--set", "synthetic", "--corpus", str(corpus), "--question", "Q?", "--plans",
                       str(plans), "--by", "aditya"])
    assert not list((plans / "hand-confirmed").glob("*.json"))
