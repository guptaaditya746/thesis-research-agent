"""scoring/run_score.py: the score.json contract on realistic runs (agent/tests/runs.py)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.batch import mark_cut
from agent.tests.runs import Built, baseline, corpus_env, research, rows  # noqa: F401  (pytest fixtures)
from agent.verify import stats
from scoring.cli import main as cli
from scoring.run_score import ScoreError, exit_status, key_problems, provisional, records, score_run

from .helpers import finish_attach, graph_key, judge, write_key

# The plan's contract (docs/e2e-build-plan.md, Scores); score.json may add fields, never drop these.
CONTRACT = {"run_id", "qid", "condition", "seed", "exit_status", "verify_ok", "key_version", "rows", "facts",
            "vital_recall", "support", "cost"}
PRF = {"tp", "fp", "fn", "precision", "recall", "f1"}
SUPPORT = {"facts", "with_claims", "supports", "partial", "no", "unsourced", "support_share"}
COST = {"steps", "model_calls", "tokens", "tokens_without_attach", "seconds", "seconds_without_attach", "claim_steps",
        "claim_step_tokens"}


def test_score_json_contract(research: Built, tmp_path: Path) -> None:
    key = write_key(tmp_path / "gold" / "q01" / "key.json", graph_key(research.run))
    j, _ = judge(same_facts={("HotpotQA", "Hotpot QA dataset")})
    score = score_run(research.run.root, key, judge=j, corpus=research.corpus, manifest=research.manifest)
    assert json.loads((research.run.root / "score.json").read_text(encoding="utf-8")) == score
    assert CONTRACT <= set(score)
    assert PRF <= set(score["rows"]) and set(score["facts"]) == {"strict", "normalised", "soft"}
    assert all(PRF | {"vital_recall"} <= set(level) for level in score["facts"].values())
    assert SUPPORT <= set(score["support"]) and COST <= set(score["cost"])
    assert (score["run_id"], score["qid"], score["condition"], score["seed"]) == ("research-r1", "q01", "claim_on", 1234)
    assert (score["exit_status"], score["verify_ok"], score["key_version"], score["provisional"]) == (
        "submitted", True, "v1", False)
    assert score["key_problems"] == []
    # Facts: f1 Spider and f3 GSM8K strict, f2 BIRD/Bird normalised, f4 by the judge; f5 HellaSwag extra;
    # the key's vital p4 MegaPairs is missed.
    f = score["facts"]
    assert (f["strict"]["tp"], f["normalised"]["tp"], f["soft"]["tp"]) == (2, 3, 4)
    assert (f["soft"]["precision"], f["soft"]["recall"], score["vital_recall"]) == (0.8, 0.8, 0.5)
    assert score["rows"]["tp"] == 3 and score["rows_by_level"]["normalised"]["tp"] == 3
    s = score["support"]
    assert (s["supports"], s["partial"], s["unsourced"], s["support_share"]) == (3, 1, 1, 0.6)
    expected = stats(rows(research.run.events))
    assert score["cost"]["model_calls"] == expected["model_calls"] == 6
    assert score["cost"]["tokens"] == score["cost"]["tokens_without_attach"] == expected["tokens"]
    assert score["cost"]["claim_steps"] == expected["claim_steps"]
    assert score["cost"]["seconds"] == score["cost"]["seconds_without_attach"] == expected["seconds"]
    assert score["judge"]["calls"] > 0 and score["judge"]["models"] == ["fake-judge"]
    assert {d["fact_id"]: d["label"] for d in score["detail"]["support"]}["f2"] == "partial"
    assert [m["key"]["fact"] for m in score["detail"]["facts"]["missed"]] == ["f5"]


def test_cost_with_and_without_attach(baseline: Built, tmp_path: Path) -> None:
    finish_attach(baseline.run)
    key = write_key(tmp_path / "key.json", graph_key(baseline.run))
    score = score_run(baseline.run.root, key, judge=judge()[0])
    expected = stats(rows(baseline.run.events))
    assert score["cost"]["tokens"] == expected["tokens"]
    assert score["cost"]["tokens_without_attach"] == expected["without_attach"]["tokens"]
    assert score["cost"]["seconds_without_attach"] == expected["without_attach"]["seconds"]
    assert score["cost"]["model_calls"] == 8 and expected["without_attach"]["model_calls"] == 4
    assert score["verify_ok"] is None  # no corpus given
    assert (score["condition"], score["support"]["unsourced"], score["support"]["support_share"]) == ("claim_off", 1, 0.75)


def test_draft_key_is_provisional_and_problems_are_recorded(research: Built, tmp_path: Path) -> None:
    key = graph_key(research.run, reviewed=False)
    key["rows"][0]["cells"] = {"x": 1}  # not a graph row
    score = score_run(research.run.root, write_key(tmp_path / "key.draft.json", key), write=False)
    assert score["provisional"] is True and score["key_version"] == "v1-draft"
    assert any("cells" in p or "oneOf" in p or "valid" in p for p in score["key_problems"])
    assert not (research.run.root / "score.json").exists()
    assert provisional({"reviewed": True, "version": "v2-draft"}) and not provisional({"reviewed": True, "version": "v1"})
    assert key_problems(graph_key(research.run), research.run.load_concept()) == []


def test_key_for_another_concept_is_refused(research: Built, tmp_path: Path) -> None:
    key = write_key(tmp_path / "key.json", graph_key(research.run, concept_sha256="f" * 64))
    with pytest.raises(ScoreError, match="is for concept"):
        score_run(research.run.root, key)


def test_exit_status_from_the_records(research: Built) -> None:
    run = research.run
    assert exit_status(run, records(run)) == "submitted"
    no_answer = {"subtype": "coverage", "generated": {"reason": "no_final_answer", "detail": {"exit_status": "budget"}},
                 "custom_metadata": {"origin": "research"}}
    assert exit_status(run, [no_answer]) == "budget"
    assert exit_status(run, [no_answer, {"subtype": "coverage", "generated": {"reason": "run_error"},
                                         "custom_metadata": {}}]) == "error"
    (run.root / "trajectory.json").write_text(json.dumps({"info": {"exit_status": "context_full"}}), encoding="utf-8")
    assert exit_status(run, []) == "context_full"
    assert mark_cut(run, "job_time_limit", {"by": "test"})
    assert exit_status(run, records(run)) == "cut"


def test_cli_score_run(research: Built, tmp_path: Path, capsys: pytest.CaptureFixture[str],
                      monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORPUS", raising=False)
    key = write_key(tmp_path / "key.json", graph_key(research.run))
    assert cli(["run", str(research.run.root), "--key", str(key), "--no-judge"]) == 0
    out = capsys.readouterr().out
    assert "research-r1: claim_on exit=submitted" in out and "pending=4" in out
    score = json.loads((research.run.root / "score.json").read_text(encoding="utf-8"))
    assert score["judge"]["used"] is False and score["support"]["support_share"] is None
    assert score["facts"]["soft"] == score["facts"]["normalised"]
    assert cli(["run", str(research.run.root), "--key", str(tmp_path / "missing.json"), "--no-judge"]) == 1
