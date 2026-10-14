"""scoring/run_score.py: the score.json contract on realistic runs (agent/tests/runs.py)."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from agent.batch import mark_cut
from agent.tests.runs import Built, baseline, corpus_env, research, rows  # noqa: F401  (pytest fixtures)
from agent.verify import stats
from scoring.cli import main as cli
from scoring.run_score import (ScoreError, answer_from, cost, exit_status, key_problems, provisional, records,
                               score_run, wrong_facts)

from .helpers import C2Judge, finish_attach, graph_key, judge, write_key

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
    assert score["judge"]["identity"] == {"name": "fake", "model": None, "prompts": None}
    assert score["pending"] == {"support": 0, "same_fact": 0, "same_row": 0}
    assert score["scorer"]["version"] == 2 and score["answer_from"] == "final"
    assert score["run_settings"]["temperature"] == score["temperature"]
    assert {d["fact_id"]: d["label"] for d in score["detail"]["support"]}["f2"] == "partial"
    assert [m["key"]["fact"] for m in score["detail"]["facts"]["missed"]] == ["f5"]
    assert score["support"]["calibration"] == {"partial_counts_as": "no", "source": None, "sha256": None}
    assert score["judged_precision"]["precision"] is None and score["judged_precision"]["source"] is None


def test_judge_counts_are_the_runs_own(research: Built, baseline: Built, tmp_path: Path) -> None:
    """One judge for a batch: each score.json counts only its own calls and errors."""
    finish_attach(baseline.run)
    j, fake = judge(fail=True)
    first = score_run(research.run.root, write_key(tmp_path / "a.json", graph_key(research.run)), judge=j)
    fake.fail, before = False, len(fake.calls)
    second = score_run(baseline.run.root, write_key(tmp_path / "b.json", graph_key(baseline.run)), judge=j)
    assert first["judge"]["pending"] == 4 and first["pending"]["support"] == 4 and len(first["judge"]["errors"]) == 4
    assert second["judge"]["pending"] == 0 and second["judge"]["errors"] == [] and second["pending"]["support"] == 0
    assert second["judge"]["calls"] == len(fake.calls) - before > 0
    assert j.pending == 0 and j.calls == 0  # the batch's judge itself only hands out forks


def test_cost_with_and_without_attach(baseline: Built, tmp_path: Path) -> None:
    finish_attach(baseline.run)
    key = write_key(tmp_path / "key.json", graph_key(baseline.run))
    score = score_run(baseline.run.root, key, judge=judge()[0])
    expected = stats(rows(baseline.run.events))
    assert score["cost"]["tokens"] == expected["tokens"]
    assert score["cost"]["tokens_without_attach"] == expected["without_attach"]["tokens"]
    assert score["cost"]["seconds_without_attach"] == expected["without_attach"]["seconds"]
    assert score["cost"]["seconds"] == pytest.approx(expected["without_attach"]["seconds"] + expected["attach"]["seconds"])
    assert score["cost"]["wall_seconds"] == expected["seconds"]
    assert score["cost"]["model_calls"] == 8 and expected["without_attach"]["model_calls"] == 4
    assert score["verify_ok"] is None  # no corpus given
    assert (score["condition"], score["support"]["unsourced"], score["support"]["support_share"]) == ("claim_off", 1, 0.75)


def test_time_with_attach_leaves_out_the_wait_between_jobs() -> None:
    def call(step: int, start: str, end: str, origin: str | None = None) -> dict:
        return {"subtype": "ai_model_invocation", "step_id": step, "agent_id": "main",  # as the broker writes it
                "started_at": f"2026-10-13T{start}:00Z",
                "ended_at": f"2026-10-13T{end}:00Z", "generated": {"usage": {"total_tokens": 10}},
                "custom_metadata": {"origin": origin} if origin else {}}

    # Research 10:00-10:10 in one Slurm job, the attach step 14:00-14:02 in a later one.
    c = cost([call(1, "10:00", "10:05"), call(2, "10:05", "10:10"), call(3, "14:00", "14:02", "attach")])
    assert (c["seconds"], c["seconds_without_attach"], c["attach_seconds"], c["wall_seconds"]) == (720.0, 600.0,
                                                                                                    120.0, 14520.0)
    assert (c["tokens"], c["tokens_without_attach"], c["attach_tokens"]) == (30, 20, 10)


def test_wrong_facts_from_the_review_export(research: Built, tmp_path: Path) -> None:
    qdir = tmp_path / "gold" / "q01"
    key = write_key(qdir / "key.json", graph_key(research.run))
    assert wrong_facts(key) == (None, None)
    decisions = [{"candidate_id": "q01-c000009", "keep": False, "reason": "incorrect"},
                 {"candidate_id": "q01-c000010", "keep": False, "reason": "adjudicated by ann (one of the two raters): "
                                                                         "incorrect"},
                 {"candidate_id": "q01-c000011", "keep": False, "reason": "unsure"},
                 {"candidate_id": "q01-c000001", "keep": True, "reason": "correct"}]
    (qdir / "export.json").write_text(json.dumps({"decisions": decisions, "rejected": [
        {"s": "p3", "p": "evaluatesOn", "o": "HellaSwag", "reason": "format"}]}), encoding="utf-8")
    candidates = [{"id": "q01-c000009", "s": "p3", "p": "evaluatesOn", "o": "HellaSwag"},
                  {"id": "q01-c000011", "s": "p1", "p": "evaluatesOn", "o": "BIRD"}]
    (qdir / "candidates.jsonl").write_text("".join(json.dumps(c) + "\n" for c in candidates), encoding="utf-8")
    (qdir / "pool.jsonl").write_text(json.dumps({"id": "q01-c000010", "s": "p6", "p": "evaluatesOn", "o": "X"}) + "\n",
                                     encoding="utf-8")
    wrong, source = wrong_facts(key)
    assert [w["candidate_id"] for w in wrong] == ["q01-c000009", "q01-c000010"]
    assert all(w["verdict"] == "wrong" for w in wrong) and (source["rejected_as_wrong"], source["with_fact"]) == (2, 2)
    # The run's f5 (p3 evaluatesOn HellaSwag) is not in the key and was rejected as wrong; the export's own
    # `rejected` list (lines that did not anchor) is not read as wrong facts.
    score = score_run(research.run.root, key, judge=judge(same_facts={("HotpotQA", "Hotpot QA dataset")})[0],
                      write=False)
    jp = score["judged_precision"]
    assert (jp["correct"], jp["wrong"], jp["precision"], jp["coverage"]) == (4, 1, 0.8, 1.0)
    assert jp["source"]["file"].endswith("export.json")


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
    assert exit_status(run, []) == "context_full" and answer_from([]) is None
    assert answer_from([no_answer]) == "none" and answer_from(records(run)) == "final"
    # The harness took the agent's draft file (e2e/agent-fix): the loop's reason, and answer_from "draft".
    draft = {"subtype": "coverage", "generated": {"reason": "answer_from_draft", "detail": {"exit_status": "budget",
                                                                                          "draft": "ab", "rows": 2}},
             "custom_metadata": {"phase": "conclude"}}
    assert (exit_status(run, [draft]), answer_from([draft])) == ("budget", "draft")
    assert mark_cut(run, "job_time_limit", {"by": "test"})
    assert exit_status(run, records(run)) == "cut"


def test_cli_score_run(research: Built, tmp_path: Path, capsys: pytest.CaptureFixture[str],
                      monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORPUS", raising=False)
    key = write_key(tmp_path / "key.json", graph_key(research.run))
    assert cli(["run", str(research.run.root), "--key", str(key), "--no-judge"]) == 0
    out = capsys.readouterr().out
    assert "research-r1: claim_on exit=submitted" in out and "pending=4+1+" in out
    score = json.loads((research.run.root / "score.json").read_text(encoding="utf-8"))
    assert score["judge"]["used"] is False and score["support"]["support_share"] is None
    # Without a judge the soft level is the normalised one plus pending asks: a lower bound, flagged.
    soft, normalised = score["facts"]["soft"], score["facts"]["normalised"]
    assert {k: soft[k] for k in normalised} == normalised and soft["pending"] == score["pending"]["same_fact"] == 1
    assert cli(["run", str(research.run.root), "--key", str(tmp_path / "missing.json"), "--no-judge"]) == 1


def test_cli_score_run_finds_the_key_in_gold(research: Built, tmp_path: Path, capsys: pytest.CaptureFixture[str],
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    """The web app runs `score run <run_dir>` with $GOLD set and no --key (e2e/webapp-api commands.py)."""
    monkeypatch.delenv("CORPUS", raising=False)
    gold = tmp_path / "gold"
    monkeypatch.setenv("GOLD", str(gold))
    assert cli(["run", str(research.run.root), "--no-judge"]) == 1
    assert "no key yet" in capsys.readouterr().out
    write_key(gold / "q01" / "key.draft.json", graph_key(research.run, reviewed=False))
    assert cli(["run", str(research.run.root), "--no-judge"]) == 0
    assert "PROVISIONAL" in capsys.readouterr().out
    score = json.loads((research.run.root / "score.json").read_text(encoding="utf-8"))
    assert score["key_path"].endswith("key.draft.json") and score["provisional"] is True


def test_cli_refuses_the_judge_without_the_corpus(research: Built, tmp_path: Path,
                                                  capsys: pytest.CaptureFixture[str],
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    impl = C2Judge()
    module = types.ModuleType("gold.judge")
    module.default_judge = lambda: impl
    monkeypatch.setitem(sys.modules, "gold.judge", module)
    monkeypatch.delenv("CORPUS", raising=False)
    monkeypatch.setenv("GOLD", str(tmp_path / "gold"))
    key = write_key(tmp_path / "key.json", graph_key(research.run))
    assert cli(["run", str(research.run.root), "--key", str(key)]) == 1
    assert "the judge needs the corpus" in capsys.readouterr().out
    assert cli(["run", str(research.run.root), "--key", str(key), "--corpus", str(research.corpus)]) == 0
    score = json.loads((research.run.root / "score.json").read_text(encoding="utf-8"))
    assert score["support"]["context"] == "calibrated" and score["verify_ok"] is True
    assert score["judge"]["identity"]["model"] == C2Judge.model_id and len(impl.loops) == 1
