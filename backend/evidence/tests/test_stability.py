from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evidence import cli
from evidence import replay as replay_module
from evidence.replay import reexec
from evidence.rundir import write_lines
from evidence.stability import (GROUPS, combine, compare_calls, item_stability, measure, model_calls, render,
                                 same_answer)
from evidence.tests.test_written import paper_facts
from evidence.tests.test_written_stage import writer_model, written_run
from evidence.tests.conftest import provider_of

GOOD = lambda p: {"sentences": [{"text": "Retrieval helped.", "says": "finding", "facts": [1]}]}
SPECS = {"llm_measurement@1#a": {"kind": "llm"}, "agentic@1#b": {"kind": "agent", "config": {"temperature": 0.7}}}
COUNTS = ("calls", "identical", "other_reply", "failed", "unreadable", "not_asked_again", "new")


def fake_run(root: Path, rows: list[dict[str, Any]], specs: dict[str, Any]) -> Path:
    root.mkdir(parents=True)
    (root / "run.json").write_text(json.dumps({"extractor_specs": specs}), encoding="utf-8")
    write_lines(root / "calls.jsonl", rows)
    return root


def row(eid: str, req: str, reply: str | None, temperature: float = 0.0) -> dict[str, Any]:
    record: dict[str, Any] = {"id": "m", "request": {"model": "orch-model", "user_prompt": req,
                                                     "settings": {"temperature": temperature}}}
    if reply is None:
        record["error"] = "down"
    else:
        record["response"] = {"output": {"r": reply}, "served_model": "served-x"}
    return {"key": f"{eid}:{req}", "extractor_id": eid, "model_calls": [record]}


def agent_row(req: str, reply_sha: str, status: str = "finished") -> dict[str, Any]:
    record = {"id": "r/1", "kind": "agent_model_call",
              "request": {"step_id": req, "prompt_sha256": "p", "status": status},
              "response": {"response_sha256": reply_sha}, "usage": {}}
    return {"key": f"agentic@1#b:{req}", "extractor_id": "agentic@1#b", "model_calls": [record]}


def odd_row(req: str) -> dict[str, Any]:
    return {"key": f"llm_measurement@1#a:{req}", "extractor_id": "llm_measurement@1#a",
            "model_calls": [{"id": "x", "request": {"user_prompt": req}}]}


def test_calls_are_matched_by_request_and_told_apart(tmp_path):
    a = fake_run(tmp_path / "a", [row("llm_measurement@1#a", "A", "1"), row("llm_measurement@1#a", "B", "2"),
                                  row("llm_measurement@1#a", "C", "3"), row("stage:written-answer", "D", "4", 0.3),
                                  agent_row("s1", "h1"), agent_row("s2", "h2"), odd_row("F")], SPECS)
    b = fake_run(tmp_path / "b", [row("llm_measurement@1#a", "A", "1"), row("llm_measurement@1#a", "B", "9"),
                                  row("llm_measurement@1#a", "E", "5"), row("stage:written-answer", "D", None, 0.3),
                                  agent_row("s1", "h1"), agent_row("s2", "h9"), odd_row("F")], SPECS)
    out = compare_calls(a, b)
    assert {k: out["llm"][k] for k in COUNTS} == {"calls": 4, "identical": 1, "other_reply": 1, "failed": 0,
                                                 "unreadable": 1, "not_asked_again": 1, "new": 1}
    assert out["stage"]["failed"] == 1 and out["stage"]["temperatures"] == [0.3]
    assert out["llm"]["served"] == ["served-x"]
    assert {k: out["agent"][k] for k in ("calls", "identical", "other_reply")} == {"calls": 2, "identical": 1,
                                                                                   "other_reply": 1}
    assert out["agent"]["temperatures"] == [0.7] and out["agent"]["served"] == []


def test_two_agent_calls_with_another_reply_are_never_identical(tmp_path):
    a = fake_run(tmp_path / "a", [agent_row("s1", "h1")], SPECS)
    b = fake_run(tmp_path / "b", [agent_row("s1", "h2")], SPECS)
    assert compare_calls(a, b)["agent"]["other_reply"] == 1


def test_an_original_that_failed_and_a_rerun_that_answered_is_another_reply(tmp_path):
    a = fake_run(tmp_path / "a", [row("llm_measurement@1#a", "A", None), row("llm_measurement@1#a", "B", None),
                                  agent_row("s1", "h1", status="failed")], SPECS)
    b = fake_run(tmp_path / "b", [row("llm_measurement@1#a", "A", "1"), row("llm_measurement@1#a", "B", None),
                                  agent_row("s1", "h1", status="failed")], SPECS)
    out = compare_calls(a, b)
    assert out["llm"]["other_reply"] == 1 and out["llm"]["failed"] == 1 and out["agent"]["failed"] == 1


def test_a_run_without_calls_jsonl_cannot_be_compared(tmp_path):
    (tmp_path / "a").mkdir()
    with pytest.raises(ValueError, match="has no calls.jsonl"):
        model_calls(tmp_path / "a")


def test_items_found_again_by_content(tmp_path):
    items = paper_facts("S001", 2)
    changed = [*items[:-1], items[-1].model_copy(update={"fields": {**items[-1].fields, "value": 0.7}})]
    a, b = tmp_path / "a", tmp_path / "b"
    for root, rows_ in ((a, items), (b, changed)):
        root.mkdir()
        write_lines(root / "evidence.jsonl", [i.model_dump(mode="json") for i in rows_])
    out = item_stability(a, b)
    assert out["items"] == len(items) and out["found_again"] == len(items) - 1
    assert out["by_type"]["measurement"] == [2, 1]


def test_two_reruns_one_with_another_reply(tmp_path):
    root = written_run(tmp_path, GOOD)
    same = reexec(root, all_calls=True, out_dir=tmp_path / "re", provider=provider_of(writer_model([], GOOD)))
    hurt = lambda p: {"sentences": [{"text": "Retrieval hurt.", "says": "finding", "facts": [1]}]}
    other = reexec(root, all_calls=True, out_dir=tmp_path / "re", provider=provider_of(writer_model([], hurt)))
    report = measure(root, [same, other])
    assert report["answers"] == {"compared": 2, "same_text": 1, "same_headline": 2, "whys": []}
    assert report["calls"]["stage"]["other_reply"] == 1 and report["items"]["found_again"] == report["items"]["items"]
    assert report["items_by_extractor"]["other"][0] > 0 and report["items_by_extractor"]["agent"] == [0, 0]
    lines = render(report)
    assert lines[0] == "Re-run measure: 1 runs x 2 re-runs, no cache (every model call asked again)."
    assert "  agentic extractor: no calls in these runs" in lines
    assert ("Items found again by extractor: LLM extractors no items in these runs, agentic extractor no items in "
            "these runs, other extractors 100.0%") in lines
    assert "Final answer the same: text in 1 of 2 re-runs, headline in 2 of 2" in lines
    assert lines[-1].startswith("This re-asks one run's calls once")


def test_combine_adds_runs(tmp_path):
    r = {"run": "x", "reruns": 2, "calls": {g: dict.fromkeys(COUNTS, 1) | {"temperatures": [0.0], "served": ["s"]}
                                            for g in GROUPS},
         "items": {"items": 4, "found_again": 3, "by_type": {"measurement": [4, 3]}},
         "items_by_extractor": {"llm": [2, 1], "agent": [0, 0], "other": [2, 2]},
         "answers": {"compared": 2, "same_text": 1, "same_headline": 2, "whys": ["b"]}}
    total = combine([r, r | {"answers": r["answers"] | {"whys": ["a", "b"]}}])
    assert total["runs"] == 2 and total["reruns"] == 4 and total["calls"]["llm"]["identical"] == 2
    assert total["items"]["by_type"]["measurement"] == [8, 6] and total["answers"]["same_text"] == 2
    assert total["items_by_extractor"]["llm"] == [4, 2] and total["answers"]["whys"] == ["a", "b"]
    assert render(total)[0] == "Re-run measure: 2 runs x 2 re-runs, no cache (every model call asked again)."
    assert render(total | {"runs": 4})[0].startswith("Re-run measure: 4 runs x 1 re-runs")
    assert render(total | {"runs": 3})[0].startswith("Re-run measure: 3 runs x 1.3 re-runs")


def test_the_command_measures_n_reruns(tmp_path, monkeypatch, capsys):
    root = written_run(tmp_path, GOOD)
    monkeypatch.setattr(replay_module, "default_provider", lambda alias: writer_model([], GOOD))
    assert cli.main(["reexec", str(root), "--all-calls", "--times", "2", "--out", str(tmp_path / "re")]) == 0
    assert "Final answer the same: text in 2 of 2 re-runs, headline in 2 of 2" in capsys.readouterr().out
    assert (tmp_path / "re" / "stability.json").is_file()
    assert cli.main(["reexec", str(root), "--times", "2", "--out", str(tmp_path / "x")]) == 2   # needs --all-calls
    assert cli.main(["reexec", str(root), "--all-calls", "--times", "2"]) == 2                  # needs --out
    assert cli.main(["reexec", str(root), "--all-calls", "--times", "1", "--out", str(root / "re")]) == 2


def test_an_unreadable_answer_is_named_and_the_other_measures_survive(tmp_path):
    root = written_run(tmp_path, GOOD)
    new = reexec(root, all_calls=True, out_dir=tmp_path / "re", provider=provider_of(writer_model([], GOOD)))
    (new / "protocol.yaml").unlink()
    out = same_answer(root, new)
    assert out["text"] is None and out["headline"] is None and out["why"]
    assert measure(root, [new])["calls"]["stage"]["calls"] > 0


def test_any_error_reading_an_answer_is_named_not_raised(tmp_path, monkeypatch, capsys):
    """M1: an AssertionError (a run whose pack gives no roles) is a reason like any other, in the measure and in the
    command's check of the original."""
    import evidence.readable as readable
    import evidence.stability as stability

    def broken(*args, **kwargs):
        raise AssertionError

    monkeypatch.setattr(stability, "read_run", broken)
    out = same_answer(tmp_path / "a", tmp_path / "b")
    assert out == {"text": None, "headline": None, "why": "AssertionError"}
    root = written_run(tmp_path, GOOD)
    monkeypatch.setattr(readable, "read_refusal", broken)
    monkeypatch.setattr(replay_module, "default_provider", lambda alias: writer_model([], GOOD))
    assert cli.main(["reexec", str(root), "--all-calls", "--times", "1", "--out", str(tmp_path / "o")]) == 0
    assert "cannot be compared (AssertionError)" in capsys.readouterr().out


def test_a_rerun_that_read_the_record_is_refused(tmp_path):
    """M7: a re-run made without --all-calls read its calls from the record; measuring it would count copies as
    identical replies."""
    root = written_run(tmp_path, GOOD)
    plain = reexec(root, out_dir=tmp_path / "re", provider=provider_of(writer_model([], GOOD)))
    with pytest.raises(ValueError, match=r'its reexec.json has no "all_calls": true; make it with reexec --all-calls'):
        measure(root, [plain])
    (tmp_path / "bare").mkdir()
    with pytest.raises(ValueError, match="all_calls"):
        measure(root, [tmp_path / "bare"])


def test_an_agent_call_without_a_step_or_prompt_hash_is_unreadable(tmp_path):
    bare = agent_row("s1", "h1")
    del bare["model_calls"][0]["request"]["prompt_sha256"]
    a = fake_run(tmp_path / "a", [bare], SPECS)
    b = fake_run(tmp_path / "b", [bare], SPECS)
    out = compare_calls(a, b)["agent"]
    assert out["unreadable"] == 1 and out["identical"] == 0


def test_the_command_checks_the_original_before_any_rerun(tmp_path, monkeypatch, capsys):
    asked: list[str] = []
    monkeypatch.setattr(replay_module, "default_provider", lambda alias: asked.append(alias) or writer_model([], GOOD))
    bare = tmp_path / "bare"
    bare.mkdir()
    assert cli.main(["reexec", str(bare), "--all-calls", "--times", "1", "--out", str(tmp_path / "o")]) == 2
    assert "has no calls.jsonl" in capsys.readouterr().err and asked == []
    root = written_run(tmp_path, GOOD)
    import evidence.readable as readable
    monkeypatch.setattr(readable, "read_refusal", lambda run, corpus=None: "no readable answer")
    assert cli.main(["reexec", str(root), "--all-calls", "--times", "1", "--out", str(tmp_path / "o2")]) == 0
    assert "cannot be compared" in capsys.readouterr().out
