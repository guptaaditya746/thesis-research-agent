"""`evidence run` on a run with failed extractor calls (the model gateway went away): exit 2 and a FAIL line, the
run kept on disk; `--allow-failed-calls` only warns; `--retry-errors` with the model back gives a clean run. A run
dir that is already there (a killed run without run.json, or a finished one) is refused with what to do."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models.function import AgentInfo, FunctionModel

from evidence import cli, engine
from evidence.rundir import RunDir

from .conftest import empty, scripted


def down(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    raise ConnectionError("the gateway does not answer")


def use(monkeypatch: pytest.MonkeyPatch, model: FunctionModel) -> None:
    monkeypatch.setattr(engine, "default_provider", lambda alias: model)


def run(protocol_file: Path, corpus: Path, out: Path, run_id: str, *more: str) -> int:
    return cli.main(["run", "--protocol", str(protocol_file), "--corpus", str(corpus), "--out", str(out),
                     "--cache", str(out / "cache"), "--strategy", "all", "--workers", "1", "--run-id", run_id, *more])


def test_failed_calls_exit_2_with_a_fail_line_and_the_run_is_kept(protocol_file: Path, corpus: Path, tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch,
                                                                  capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "runs"
    use(monkeypatch, FunctionModel(down, model_name="down"))
    assert run(protocol_file, corpus, out, "outage") == 2
    printed = capsys.readouterr()
    failed = RunDir(out / "outage").failed_calls()
    assert failed > 0 and RunDir(out / "outage").complete
    assert f"FAIL engine-errors {out / 'outage'} {failed}" in printed.err.splitlines()
    assert json.loads(printed.out)["run"] == str(out / "outage")      # the summary is still printed

    # the cached errors are reused by a plain rerun (same count, still exit 2) ...
    assert run(protocol_file, corpus, out, "again") == 2 and RunDir(out / "again").failed_calls() == failed
    # ... only warned about with --allow-failed-calls (the web app counts them itself) ...
    capsys.readouterr()
    assert run(protocol_file, corpus, out, "allowed", "--allow-failed-calls") == 0
    assert "FAIL" not in capsys.readouterr().err
    # ... and asked again with --retry-errors once the model answers
    calls: list[str] = []
    use(monkeypatch, scripted(empty, calls))
    assert run(protocol_file, corpus, out, "retried", "--retry-errors") == 0
    assert calls and RunDir(out / "retried").failed_calls() == 0


def test_only_calls_the_service_failed_count(tmp_path: Path) -> None:
    (tmp_path / "calls").mkdir()
    rows = {"ok": ("ok", None), "gliner": ("partial", "service_call"), "llm": ("error", "model_call"),
            "agent-budget": ("partial", "no_final_answer"), "agent-none": ("error", "no_final_answer"),
            "crash": ("error", "ValueError")}
    for name, (status, reason) in rows.items():
        (tmp_path / "calls" / f"{name}.json").write_text(json.dumps(
            {"status": status, "error": {"reason": reason, "detail": ""} if reason else None}))
    assert RunDir(tmp_path).failed_calls() == 2       # the GLiNER partial and the LLM error only
    assert RunDir(tmp_path).error_calls() == 3        # status error, any reason



def test_a_clean_regex_run_exits_0(protocol_file: Path, corpus: Path, tmp_path: Path,
                                   capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "runs"
    assert cli.main(["run", "--protocol", str(protocol_file), "--corpus", str(corpus), "--out", str(out),
                     "--extractors", "regex-only", "--run-id", "r"]) == 0
    assert "FAIL" not in capsys.readouterr().err


def test_a_killed_run_dir_is_refused_with_what_to_do(protocol_file: Path, corpus: Path, tmp_path: Path,
                                                     capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "runs"
    args = ["run", "--protocol", str(protocol_file), "--corpus", str(corpus), "--out", str(out),
            "--extractors", "regex-only", "--run-id", "r"]
    (out / "r").mkdir(parents=True)
    (out / "r" / "events.jsonl").write_text("")          # what a killed run leaves: no run.json
    assert cli.main(args) == 2
    err = capsys.readouterr().err
    assert "exists without run.json" in err and "$RUNS/failed/<corpus>/" in err and "run again" in err
    (out / "r").rename(tmp_path / "aside")
    assert cli.main(args) == 0                            # moved aside: the run goes through
    capsys.readouterr()
    assert cli.main(args) == 2 and "holds a finished run" in capsys.readouterr().err
