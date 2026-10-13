"""scoring/batch.py: finished runs only, the key per question (draft = provisional), reuse and rescoring."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agent.batch import mark_cut
from agent.tests.runs import baseline_run, corpus_env, research_run  # noqa: F401  (pytest fixtures)
from scoring.batch import find_keys, score_batch
from scoring.cli import main as cli
from scoring.judge import Judge

from .helpers import C2Judge, finish_attach, graph_key, judge, write_key


@pytest.fixture
def batch(tmp_path: Path, corpus_env: tuple[Path, Path]) -> dict[str, Any]:
    """q01 x 2 conditions x 2 repeats: r1 finished in both conditions, claim_on r2 cut, claim_off r2 not run."""
    on1 = research_run(tmp_path, *corpus_env, run_id="q01-claim_on-r1-a1").run
    off1 = baseline_run(tmp_path, *corpus_env, run_id="q01-claim_off-r1-a1").run
    finish_attach(off1)
    on2 = research_run(tmp_path, *corpus_env, run_id="q01-claim_on-r2-a1").run
    assert mark_cut(on2, "job_time_limit", {"by": "test"})
    runs = tmp_path / "runs"
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "name": "test", "runs_root": str(runs), "questions": [{"id": "q01", "concept": "c.json"}],
        "conditions": ["claim_on", "claim_off"], "repeats": 2, "temperature": 0.7, "seed_base": 1000}), encoding="utf-8")
    gold = tmp_path / "gold"
    write_key(gold / "q01" / "key.draft.json", graph_key(on1, reviewed=False))
    return {"runs": runs, "manifest": manifest, "gold": gold, "on1": on1, "off1": off1, "corpus": corpus_env}


def lines(runs: Path) -> list[dict[str, Any]]:
    path = runs / "report" / "scores.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_manifest_batch_scores_finished_runs_with_the_draft_key(batch: dict[str, Any]) -> None:
    j, _ = judge()
    summary = score_batch(batch["runs"], batch["gold"], manifest=batch["manifest"], judge=j, log=lambda _: None)
    assert summary["counts"] == {"scored": 2, "reused": 0, "skipped": 2, "failed": 0}
    states = [(i["key"], i["run_id"], i["state"], i["scored"]) for i in summary["items"]]
    assert states == [("q01-claim_on-r1", "q01-claim_on-r1-a1", "finished", True),
                      ("q01-claim_off-r1", "q01-claim_off-r1-a1", "finished", True),
                      ("q01-claim_on-r2", "q01-claim_on-r2-a1", "cut", False),
                      ("q01-claim_off-r2", None, "not_started", False)]
    scores = lines(batch["runs"])
    assert [s["run_id"] for s in scores] == ["q01-claim_off-r1-a1", "q01-claim_on-r1-a1"]
    assert all(s["provisional"] and s["qid"] == "q01" and s["repeat"] == 1 and s["attempt"] == 1 for s in scores)
    assert summary["provisional"] is True
    assert json.loads((batch["runs"] / "report" / "batch.json").read_text(encoding="utf-8"))["counts"]["scored"] == 2

    # Run again: the scores are current (same key file, nothing pending), so they are reused ...
    again = score_batch(batch["runs"], batch["gold"], manifest=batch["manifest"], judge=j, log=lambda _: None)
    assert again["counts"]["reused"] == 2 and again["counts"]["scored"] == 0
    # ... until the reviewed key arrives: every run is rescored against it, no longer provisional.
    write_key(batch["gold"] / "q01" / "key.json", graph_key(batch["on1"]))
    reviewed = score_batch(batch["runs"], batch["gold"], manifest=batch["manifest"], judge=j, log=lambda _: None)
    assert reviewed["counts"]["scored"] == 2 and reviewed["provisional"] is False
    assert {s["key_version"] for s in lines(batch["runs"])} == {"v1"}
    forced = score_batch(batch["runs"], batch["gold"], manifest=batch["manifest"], judge=j, force=True,
                         log=lambda _: None)
    assert forced["counts"]["scored"] == 2


def test_pending_judge_decisions_are_rescored_when_a_judge_is_back(batch: dict[str, Any]) -> None:
    score_batch(batch["runs"], batch["gold"], manifest=batch["manifest"], judge=None, log=lambda _: None)
    assert all(s["support"]["pending"] > 0 for s in lines(batch["runs"]))
    again = score_batch(batch["runs"], batch["gold"], manifest=batch["manifest"], judge=None, log=lambda _: None)
    assert again["counts"]["reused"] == 2
    j, _ = judge()
    back = score_batch(batch["runs"], batch["gold"], manifest=batch["manifest"], judge=j, log=lambda _: None)
    assert back["counts"]["scored"] == 2 and all(s["support"]["pending"] == 0 for s in lines(batch["runs"]))


def test_without_manifest_runs_find_their_key_by_concept(batch: dict[str, Any]) -> None:
    corpus, manifest = batch["corpus"]
    summary = score_batch(batch["runs"], batch["gold"], corpus=corpus, corpus_manifest=manifest, judge=judge()[0],
                          log=lambda _: None)
    states = {i["key"]: (i["qid"], i["state"]) for i in summary["items"]}
    assert states == {"q01-claim_on-r1-a1": ("q01", "finished"), "q01-claim_off-r1-a1": ("q01", "finished"),
                      "q01-claim_on-r2-a1": (None, "cut")}
    assert all(s["verify_ok"] is True for s in lines(batch["runs"]))


def test_attach_pending_is_not_finished(batch: dict[str, Any]) -> None:
    (batch["off1"].root / "attach.json").unlink()
    config = batch["off1"].load_config()
    del config["attach"]
    (batch["off1"].root / "config.json").write_text(json.dumps(config), encoding="utf-8")
    summary = score_batch(batch["runs"], batch["gold"], manifest=batch["manifest"], judge=None, log=lambda _: None)
    assert [i["state"] for i in summary["items"]][:2] == ["finished", "attach_pending"]


def test_key_for_another_concept_fails_the_run(batch: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    write_key(batch["gold"] / "q01" / "key.draft.json", graph_key(batch["on1"], concept_sha256="f" * 64))
    code = cli(["batch", str(batch["runs"]), "--gold", str(batch["gold"]), "--manifest", str(batch["manifest"]),
                "--no-judge"])
    assert code == 1
    out = capsys.readouterr().out
    assert "is for concept ffffffffffff" in out and "failed 2" in out
    assert lines(batch["runs"]) == []


def test_cli_batch(batch: dict[str, Any], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORPUS", raising=False)
    monkeypatch.setenv("GOLD", str(batch["gold"]))
    assert cli(["batch", str(batch["runs"]), "--manifest", str(batch["manifest"]), "--no-judge"]) == 0
    out = capsys.readouterr().out
    assert "scored 2, reused 0, skipped 2, failed 0 (PROVISIONAL: draft keys used)" in out


def test_find_keys_prefers_the_reviewed_key(tmp_path: Path) -> None:
    write_key(tmp_path / "q01" / "key.draft.json", {"qid": "q01", "concept_sha256": "a" * 64, "rows": []})
    write_key(tmp_path / "q02" / "key.draft.json", {"qid": "q02", "concept_sha256": "b" * 64, "rows": []})
    write_key(tmp_path / "q02" / "key.json", {"qid": "q02", "concept_sha256": "b" * 64, "rows": [], "reviewed": True})
    (tmp_path / "q03").mkdir()
    keys = find_keys(tmp_path)
    assert {q: k.path.name for q, k in keys.items()} == {"q01": "key.draft.json", "q02": "key.json"}
    # A key.json that does not parse falls back to the draft, and says so.
    (tmp_path / "q01" / "key.json").write_text("{not json", encoding="utf-8")
    problems: list[str] = []
    assert find_keys(tmp_path, problems)["q01"].path.name == "key.draft.json"
    assert len(problems) == 1 and "q01" in problems[0] and "key.json" in problems[0]


def test_manifest_runs_root_below_the_report_root(tmp_path: Path, corpus_env: tuple[Path, Path],
                                                  capsys: pytest.CaptureFixture[str],
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """scripts/e2e-batch.sh: runs in $RUNS/<name>/ (the effective manifest's runs_root), report in $RUNS/report/."""
    runs = tmp_path / "RUNS"
    on1 = research_run(runs / "m4", *corpus_env, run_id="q01-claim_on-r1-a1").run  # -> RUNS/m4/runs/<id>
    manifest = runs / "m4" / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "name": "m4", "runs_root": str(on1.root.parent), "questions": [{"id": "q01", "concept": "c"}],
        "conditions": ["claim_on"], "repeats": 1, "temperature": 0.7, "seed_base": 1000}), encoding="utf-8")
    gold = tmp_path / "gold"
    write_key(gold / "q01" / "key.json", graph_key(on1))
    summary = score_batch(runs, gold, manifest=manifest, judge=judge()[0], log=lambda _: None)
    assert summary["counts"]["scored"] == 1 and summary["attempts_root"] == str(on1.root.parent)
    assert [s["run_id"] for s in lines(runs)] == ["q01-claim_on-r1-a1"]
    # Without the manifest the nested run is found too, and an ad hoc run only with --all.
    adhoc = research_run(runs / "web", *corpus_env, run_id="run-20261013-1").run
    write_key(gold / "q01" / "key.json", graph_key(adhoc))
    tree = score_batch(runs, gold, judge=judge()[0], log=lambda _: None)
    assert {i["key"]: i["state"] for i in tree["items"]} == {"q01-claim_on-r1-a1": "finished",
                                                              "run-20261013-1": "not_a_batch_run"}
    assert score_batch(runs, gold, judge=judge()[0], include_all=True, log=lambda _: None)["counts"]["scored"] == 1
    # A manifest whose runs_root does not exist is an error, not "every run not started".
    data = json.loads(manifest.read_text(encoding="utf-8"))
    manifest.write_text(json.dumps(data | {"runs_root": str(tmp_path / "elsewhere")}), encoding="utf-8")
    monkeypatch.delenv("CORPUS", raising=False)
    assert cli(["batch", str(runs), "--gold", str(gold), "--manifest", str(manifest), "--no-judge"]) == 1
    assert "runs_root" in capsys.readouterr().out


def test_a_malformed_run_does_not_stop_the_batch(batch: dict[str, Any]) -> None:
    config = json.loads(batch["on1"].config.read_text(encoding="utf-8"))
    del config["hashes"]
    batch["on1"].config.write_text(json.dumps(config), encoding="utf-8")
    summary = score_batch(batch["runs"], batch["gold"], manifest=batch["manifest"], judge=judge()[0],
                          log=lambda _: None)
    assert summary["counts"] == {"scored": 1, "reused": 0, "skipped": 2, "failed": 1}
    failed = next(i for i in summary["items"] if i["state"] == "score_failed")
    assert failed["run_id"] == "q01-claim_on-r1-a1" and failed["detail"].startswith("KeyError")
    assert [s["run_id"] for s in lines(batch["runs"])] == ["q01-claim_off-r1-a1"]


def test_scores_are_redone_when_the_judge_or_its_calibration_change(batch: dict[str, Any]) -> None:
    impl = C2Judge()
    j = Judge(impl, "gold.judge")
    run = lambda judge, **kw: score_batch(batch["runs"], batch["gold"], manifest=batch["manifest"], judge=judge,  # noqa: E731
                                          log=lambda _: None, **kw)["counts"]
    assert run(j)["scored"] == 2 and run(j)["reused"] == 2
    impl.prompt = "p2"  # the judge's prompt changed: its old verdicts are not comparable
    assert run(j)["scored"] == 2 and run(j)["reused"] == 2
    (batch["gold"] / "judge-report.json").write_text(json.dumps({"calibration": {"partial_counts_as": "yes"}}),
                                                     encoding="utf-8")
    assert run(j)["scored"] == 2
    assert {s["support"]["partial_counts_as"] for s in lines(batch["runs"])} == {"yes"}
    # A corpus now at hand: the scores were not verified, so they are redone, with the calibrated context.
    corpus, manifest = batch["corpus"]
    assert run(j, corpus=corpus, corpus_manifest=manifest)["scored"] == 2
    assert all(s["verify_ok"] is True and s["support"]["context"] == "calibrated" for s in lines(batch["runs"]))
    # Without a judge nothing judged is thrown away.
    assert run(None)["reused"] == 2
    assert all(s["judge"]["used"] for s in lines(batch["runs"]))
