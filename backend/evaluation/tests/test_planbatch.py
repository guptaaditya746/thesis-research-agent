"""The plan-run batch (evaluation/planbatch.py) and the thin script over it (scripts/plan-runs.py). No model:
planrun.run is faked."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

import repo_paths
from evaluation import planbatch as pb
from evidence import planrun
from evidence.plan import load_plan, write_plan
from evidence.tests.test_plan_run import make_plan


def batch(tmp: Path) -> tuple[list[Any], Path]:
    """(the synthetic question effect-corpus-x, the plans folder with its unconfirmed plan)."""
    plans, corpus = tmp / "plans", tmp / "corpus-x"
    plans.mkdir()
    corpus.mkdir()
    plan = make_plan()
    write_plan(plan.model_copy(update={"decisions": [d.model_copy(update={"confirmed_by": None, "confirmed_at": None})
                                                     for d in plan.decisions]}), plans / "effect-corpus-x.json")
    return pb.questions("synthetic", corpus=corpus, question="Q?"), plans


def fake_run(monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, Any]], status: str) -> None:
    def run(plan_path: Path, corpus: Path, out_dir: Path, **kw: Any) -> Path:
        calls.append({"plan": Path(plan_path), **kw})
        root = Path(out_dir) / kw["run_id"]
        root.mkdir(parents=True)
        (root / "manifest.json").write_text(json.dumps({"status": status}), encoding="utf-8")
        return root
    monkeypatch.setattr(planrun, "run", run)


def test_run_skips_complete_sets_aside_failed_and_redoes_unchecked(tmp_path: Path,
                                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    qs, plans = batch(tmp_path)
    calls: list[dict[str, Any]] = []
    runs = tmp_path / "runs"

    def run(**kw: Any) -> int:
        return pb.run_all(qs, set_name="synthetic", plans=plans, runs=runs, cache=tmp_path / "cache", confirm="auto",
                          reasoning="off", links="off", **kw)
    fake_run(monkeypatch, calls, "failed")
    assert run() == 0 and calls[0]["reason"] == "off" and calls[0]["links"] == "off"
    assert calls[0]["retry_errors"] is False
    fake_run(monkeypatch, calls, "complete")
    assert run() == 0 and (runs / "effect-corpus-x.failed-1").is_dir() and calls[1]["retry_errors"] is True
    assert run() == 0 and len(calls) == 2                                       # complete: skipped
    (runs / "effect-corpus-x" / "recheck_report.json").write_text(json.dumps({"S1": {"unchecked": [
        {"item_id": "a", "why": "failed call: StageCallError: recheck: down"}]}}), encoding="utf-8")
    assert run() == 0 and len(calls) == 2                                       # --redo-unchecked is off by default
    assert run(redo_unchecked=True) == 0 and (runs / "effect-corpus-x.redo-1").is_dir() and len(calls) == 3
    assert {d.confirmed_by for d in load_plan(plans / pb.AUTO / "effect-corpus-x.json").decisions} == {pb.SYSTEM}


def test_hand_row_keeps_an_edited_plan_and_needs_a_person(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                          capsys: pytest.CaptureFixture[str]) -> None:
    qs, plans = batch(tmp_path)
    with pytest.raises(pb.BatchError):
        pb.confirm_hand(qs, plans, "system")
    assert pb.confirm_hand(qs, plans, "aditya") == 0
    hand = plans / pb.HAND / "effect-corpus-x.json"
    assert "decision d1 (threshold)" in capsys.readouterr().out
    plan = load_plan(hand)
    write_plan(plan.model_copy(update={"decisions": [d.model_copy(update={"value": "0.05"}) if d.id == "d1" else d
                                                     for d in plan.decisions]}), hand)
    before = hand.read_bytes()
    assert pb.confirm_hand(qs, plans, "aditya") == 0 and "kept" in capsys.readouterr().out
    calls: list[dict[str, Any]] = []
    fake_run(monkeypatch, calls, "complete")
    assert pb.run_all(qs, set_name="synthetic", plans=plans, runs=tmp_path / "runs", cache=tmp_path / "cache",
                      confirm="hand", reasoning="on") == 0
    assert hand.read_bytes() == before and calls[0]["plan"] == hand   # the run uses the edited file as it is


def test_script_parses_its_args_and_names_a_refusal(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("plan_runs", repo_paths.SCRIPTS / "plan-runs.py")
    script = importlib.util.module_from_spec(spec)   # type: ignore[arg-type]
    spec.loader.exec_module(script)                    # type: ignore[union-attr]
    with pytest.raises(SystemExit, match="plan-runs: confirm needs --by NAME"):
        script.main(["confirm", "--set", "synthetic", "--corpus", str(tmp_path), "--question", "Q?",
                     "--plans", str(tmp_path / "plans"), "--by", "system"])
