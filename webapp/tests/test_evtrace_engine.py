"""The run trace on runs the real engine wrote (scripted model, as evidence/tests/test_parallel.py), with one
worker and with three: the steps the UI knows, the warm rows, tokens, and clicking through to the prompts."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evidence.tests.test_parallel import go
from webapp.app import create_app
from webapp.settings import Settings

STEPS = {"screen", "locate", "extractor_call", "merge", "completeness", "synthesis", "call"}


def trace_of(tmp_path: Path, workers: int) -> tuple[list[dict], TestClient, str]:
    root = go(tmp_path, f"w{workers}", workers=workers)
    dest = tmp_path / "runs" / "g" / f"w{workers}"
    shutil.copytree(root, dest)
    c = TestClient(create_app(Settings(EV=tmp_path, EV_RUNS=tmp_path / "runs")))
    run = f"g~w{workers}"
    return c.get(f"/api/ev/runs/{run}/trace").json()["rows"], c, run


@pytest.mark.parametrize("workers", [1, 3])
def test_trace_of_an_engine_run(tmp_path: Path, workers: int) -> None:
    rows, c, run = trace_of(tmp_path, workers)
    with c:
        assert rows and {r["step"] for r in rows} <= STEPS and [r["n"] for r in rows] == list(range(1, len(rows) + 1))
        warm = [r for r in rows if r["phase"] == "warm"]
        assert bool(warm) == (workers > 1) and all(r["step"] == "call" for r in warm)
        assert {"screen", "locate", "extractor_call", "merge", "synthesis"} <= {r["step"] for r in rows}
        assert c.get(f"/api/ev/runs/{run}/trace").json()["done"] is True
        # a model-backed extractor_call row has its tokens (from calls.jsonl, any phase); regex calls have none
        model_backed = [r for r in rows if r["step"] == "extractor_call" and r["input_tokens"] is not None]
        assert model_backed and all(r["input_tokens"] > 0 and r["output_tokens"] is not None for r in model_backed)
        # clicking through: the full prompt for an extractor_call row and, with workers, for a warm call row
        for row in model_backed[:3] + warm[:3]:
            detail = c.get(f"/api/ev/runs/{run}/calls/{row['call']}")
            assert detail.status_code == 200, row
            assert detail.json()["model_calls"][0]["request"]["user_prompt"]
        # the paging contract
        assert c.get(f"/api/ev/runs/{run}/trace", params={"after": len(rows) - 1}).json()["rows"][0]["n"] == len(rows)
