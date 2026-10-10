from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.canonical import canonical, file_sha256
from agent.cli import main
from agent.rundir import RunDir

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "corpus" / "manifest.json"
SETTINGS = dict(condition="claim_on", temperature=0.7, seed=1234, prompt_version="v1",
                prompt_sha256="a" * 64, agent_root_manifest_sha256="b" * 64, git_commit="c" * 40)


def make(tmp_path: Path, concept: dict | None = None) -> RunDir:
    return RunDir.create(tmp_path / "runs", "q01-claim_on-r1", concept or {"title": "x"},
                         corpus_manifest=MANIFEST, **SETTINGS)


def test_canonical_form() -> None:
    assert canonical({"b": 1, "a": "é"}) == '{"a":"é","b":1}'
    with pytest.raises(ValueError):
        canonical({"x": float("nan")})


def test_create_layout_and_config(tmp_path: Path) -> None:
    run = make(tmp_path)
    for name in ("config.json", "concept.json", "events.jsonl", "claims.jsonl"):
        assert (run.root / name).is_file()
    assert run.out.is_dir() and run.scratch.is_dir()
    config = run.load_config()
    assert config["models"]["orchestrator"] == {
        "alias": "orch-model", "name": "Qwen/Qwen3.8-27B-FP8", "revision": "017b9c7",
        "thinking": False, "max_tokens": 4096, "context_tokens": 65536}
    assert [s["alias"] for s in config["models"]["subagents"]] == ["sub-model-1", "sub-model-2"]
    assert config["budget"] == {"steps": 150, "tokens": 400000, "announced": True}
    assert config["command_limits"] == {"timeout_s": 120, "ulimit_v_kib": 2097152, "output_cap_bytes": 8192}
    assert config["sampling"] == {"temperature": 0.7, "seed": 1234}
    assert config["hashes"]["corpus_manifest_sha256"] == file_sha256(MANIFEST)
    assert config["hashes"]["concept_sha256"] == file_sha256(run.concept)
    assert run.config.read_text(encoding="utf-8") == canonical(config) + "\n"
    assert run.validate() == []
    assert run.validate(complete=True) == ["missing answer.json"]


def test_create_refuses_existing(tmp_path: Path) -> None:
    make(tmp_path)
    with pytest.raises(FileExistsError):
        make(tmp_path)


def test_bad_settings_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="condition"):
        RunDir.create(tmp_path, "r", {}, corpus_manifest=MANIFEST, **{**SETTINGS, "condition": "maybe"})


def test_validate_catches_edits(tmp_path: Path) -> None:
    run = make(tmp_path)
    run.concept.write_text(json.dumps({"title": "changed"}), encoding="utf-8")
    assert "concept.json hash differs from config.json" in run.validate()
    run.scratch.rmdir()
    assert run.validate() == ["missing scratch/"]


def test_cli_check_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run = make(tmp_path)
    assert main(["check-run", str(run.root)]) == 0
    assert main(["check-run", str(run.root), "--complete"]) == 1
    assert "missing answer.json" in capsys.readouterr().out
