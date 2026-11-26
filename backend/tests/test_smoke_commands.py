"""Smoke test: the installed `evqa` and `webapp` commands run against the real repo paths.

Runs them as a user would: the venv's console scripts, from a folder outside the repo, with no PYTHONPATH. If another
installed package shadows `repo_paths` (as paper-factory's own `repo_paths` did on 26 Nov 2026 when it was added as
a dependency), the data folder points to the wrong place and these tests fail. Skipped in a clone without the data.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BIN = Path(sys.executable).parent
DOMAIN = "bench_law"
pytestmark = pytest.mark.skipif(not (REPO / "data" / "seed" / DOMAIN).is_dir(), reason="real data not checked out")


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=300)


def test_repo_paths_is_the_backend_one(tmp_path: Path):
    p = run([str(BIN / "python"), "-c", "import json, repo_paths as r; print(json.dumps([r.__file__, str(r.DATA)]))"],
            tmp_path)
    assert p.returncode == 0, p.stderr
    where, data = json.loads(p.stdout)
    assert Path(where).resolve().is_relative_to(REPO / "backend"), f"repo_paths shadowed by {where}"
    assert Path(data).resolve() == (REPO / "data").resolve()


def test_evqa_gold_export_reads_real_data(tmp_path: Path):
    out = tmp_path / "gold.json"
    p = run([str(BIN / "evqa"), "gold-export", DOMAIN, "--out", str(out)], tmp_path)
    assert p.returncode == 0, p.stderr[-2000:]
    assert json.loads(out.read_text(encoding="utf-8"))["questions"]


def test_webapp_openapi_builds_the_app(tmp_path: Path):
    out = tmp_path / "openapi.json"
    p = run([str(BIN / "webapp"), "openapi", "-o", str(out)], tmp_path)
    assert p.returncode == 0, p.stderr[-2000:]
    assert json.loads(out.read_text(encoding="utf-8"))["paths"]
