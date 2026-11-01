"""Sealed runs (spec 6.7): manifest.json hashes every file of a run folder, a crash still leaves every expected
file and a failed manifest, and `evidence verify` recomputes the hashes."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from evidence import cli, seal
from evidence.rundir import CorpusError, RunDirExists
from jsonio import file_sha256

from .conftest import DOCS, PROTOCOL, make_corpus, regex_run_dir, run_json

REPO = Path(__file__).resolve().parents[2]


def corpus_with_bad_sha_at(n: int, tmp: Path) -> Path:
    """A corpus of three papers whose paper `n` (1-based) no longer matches its manifest sha256."""
    root = make_corpus(tmp / "corpus", DOCS[:3])
    paper = root / "papers" / f"{DOCS[n - 1]}.md"
    paper.write_bytes(paper.read_bytes() + b"\nedited after the manifest\n")
    return root


def test_a_run_ends_with_a_complete_manifest(tmp_path):
    out = regex_run_dir(make_corpus(tmp_path / "corpus"), tmp_path, PROTOCOL)
    m = json.loads((out / "manifest.json").read_text())
    assert m["status"] == "complete" and "run.json" in m["files"] and "manifest.json" not in m["files"]
    assert m["error"] is None and m["code_commit"] == "test"
    assert list(m["files"]) == sorted(m["files"])
    assert m["corpus_manifest_sha256"] == run_json(out)["manifest_sha256"]
    assert m["protocol_lock_sha256"] == file_sha256(out / "protocol.lock.json")
    assert seal.check(out) == {"ok": True, "mismatched": [], "missing": [], "extra": [], "status": "complete"}


def test_verify_names_an_edited_file(tmp_path):
    out = regex_run_dir(make_corpus(tmp_path / "corpus"), tmp_path, PROTOCOL)
    (out / "answer.json").write_bytes((out / "answer.json").read_bytes() + b" ")
    assert seal.check(out)["mismatched"] == ["answer.json"]
    assert cli.main(["verify", str(out)]) == 1


def test_verify_names_a_missing_and_an_extra_file(tmp_path):
    out = regex_run_dir(make_corpus(tmp_path / "corpus"), tmp_path, PROTOCOL)
    (out / "graph.json").unlink()
    (out / "calls").mkdir(exist_ok=True)
    (out / "calls" / "x.json").write_text("{}")
    report = seal.check(out)
    assert report["missing"] == ["graph.json"] and report["extra"] == ["calls/x.json"] and not report["ok"]


def test_verify_old_run_says_pre_ev4(tmp_path):
    out = regex_run_dir(make_corpus(tmp_path / "corpus"), tmp_path, PROTOCOL); (out / "manifest.json").unlink()
    assert seal.check(out) == "no manifest (pre-EV4)" and cli.main(["verify", str(out)]) == 0


def test_a_crash_writes_all_expected_files_and_a_failed_manifest(tmp_path):
    corpus = corpus_with_bad_sha_at(2, tmp_path)          # CorpusError at paper 2 of 3
    with pytest.raises(CorpusError):
        regex_run_dir(corpus, tmp_path, PROTOCOL, settings={"run_id": "r", "names": "on", "reason": "on"})
    root = tmp_path / "runs" / "r"
    assert not (root / "run.json").exists()
    for name in ("locate.json", "evidence.jsonl", "funnel.json", "answer.json", "graph.json", "protocol.lock.json",
                 "names.json", "reason.json"):
        assert (root / name).is_file()
    assert (root / "calls").is_dir()
    assert json.loads((root / "funnel.json").read_text()) == {"strategy": "all", "documents": {}}
    assert json.loads((root / "graph.json").read_text()) == {"nodes": [], "edges": []}
    assert json.loads((root / "names.json").read_text()) == {"groups": {}, "matches": [], "unresolved": []}
    m = json.loads((root / "manifest.json").read_text())
    assert m["status"] == "failed" and m["error"].startswith("CorpusError")
    assert "killed or crashed" in str(RunDirExists(root))


def test_verify_a_failed_run_checks_the_manifest_without_a_head(tmp_path, capsys):
    corpus = corpus_with_bad_sha_at(2, tmp_path)
    with pytest.raises(CorpusError):
        regex_run_dir(corpus, tmp_path, PROTOCOL, settings={"run_id": "r"})
    assert cli.main(["verify", str(tmp_path / "runs" / "r")]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["chain_head"] is None and report["manifest"]["status"] == "failed" and report["manifest"]["ok"]


def test_report_files_are_never_converted():
    out = subprocess.run(["git", "check-attr", "text", "reports/ev4/runs/x/answer.json"], capture_output=True, text=True, cwd=REPO)
    assert out.stdout.strip().endswith(": text: unset")


def test_ev4_test_corpora_are_lf():
    out = subprocess.run(["git", "check-attr", "eol", "tests/EV4/corpora/x/papers/a.md"], capture_output=True, text=True, cwd=REPO)
    assert out.stdout.strip().endswith(": eol: lf")
