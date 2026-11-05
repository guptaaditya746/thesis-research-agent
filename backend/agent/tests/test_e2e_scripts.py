"""The Slurm-session scripts scripts/e2e-*.sh (rows 2.3, 2.9, 2.13), run here against fakes.

`uv` is a stand-in that runs `uv run agent|python ...` with this test's Python, the LiteLLM proxy is a
local HTTP server (the batch tests' FakeModel, plus concept briefs and /models), the agent root a tiny
one that scripts/verify-agent-root.sh accepts, and the runs go without Landlock (E2E_SANDBOX=unsandboxed:
/mnt/c in WSL does not hold Landlock rules). Everything else is the real agent CLI.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import repo_paths
from typing import Any, Iterator

import pytest

from .conftest import REPO, fixture, write_corpus
from .test_batch import FakeModel, git_works_in_children

SCRIPTS = sorted((REPO / "scripts").glob("e2e-*.sh"))
POSIX = sys.platform != "win32" and shutil.which("bash") is not None
needs_tools = pytest.mark.skipif(not POSIX or not all(shutil.which(t) for t in ("curl", "sha256sum", "realpath")),
                                 reason="the scripts need bash, curl and coreutils")
KEY = "sk-test-e2e-not-a-real-key"
FAKE_UV = """#!/bin/sh
# Stand-in for uv in the tests: `uv run agent|python ARGS` with the test's Python.
[ "$1" = run ] || { echo "fake uv: only 'uv run' is supported" >&2; exit 2; }
shift
case "$1" in
  agent) shift; exec "$E2E_TEST_PYTHON" -m agent.cli "$@" ;;
  python) shift; exec "$E2E_TEST_PYTHON" "$@" ;;
  *) exec "$@" ;;
esac
"""


def test_scripts_are_strict_bash() -> None:
    assert {p.name for p in SCRIPTS} == {"e2e-env.sh", "e2e-concepts.sh", "e2e-batch.sh", "e2e-replay.sh"}
    for path in SCRIPTS:
        raw = path.read_bytes()
        assert b"\r" not in raw and raw.startswith(b"#!/usr/bin/env bash\n"), path.name
        assert b"set -euo pipefail" in raw, path.name
        if POSIX:
            subprocess.run(["bash", "-n", str(path)], check=True)


class Proxy(FakeModel):
    """orch-model for the concept step (one brief: the table fixture) and for runs and attach steps."""

    def reply(self, messages: list[dict[str, Any]]) -> str:
        if "into concept briefs" in messages[0]["content"]:
            brief = {k: v for k, v in fixture("concept_table.json").items() if k != "id"}
            return self.block({"concepts": [brief]})
        return super().reply(messages)


def serve(model: Proxy) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, obj: Any) -> None:
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            if self.headers.get("Authorization") != f"Bearer {KEY}":
                self._send(401, {"error": "no key"})
            else:
                self._send(200, {"data": [{"id": m} for m in ("orch-model", "sub-model-1", "sub-model-2")]})

        def do_POST(self) -> None:  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            model.requests += 1
            self._send(200, {
                "id": f"chatcmpl-{model.requests}", "object": "chat.completion", "created": int(time.time()),
                "model": "orch-model", "choices": [{"index": 0, "finish_reason": "stop", "message": {
                    "role": "assistant", "content": model.reply(body["messages"])}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 50, "total_tokens": 1050}})

        def log_message(self, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def agent_root(tmp: Path) -> Path:
    """A toolchain directory that scripts/verify-agent-root.sh accepts: hashes and modes recorded."""
    root = tmp / "agent-root"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "tool").write_text("#!/bin/sh\n", encoding="utf-8")
    subprocess.run(["bash", "-c", 'cd "$1" && sha256sum bin/tool > agent-root.sha256 && touch agent-root.modes '
                    "&& find . -printf '%m %p\\n' | sort > agent-root.modes", "_", str(root)], check=True)
    return root


@pytest.fixture
def session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Path, Proxy]]:
    from .test_loop import unique_quote

    corpus, manifest = write_corpus(tmp_path)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "uv").write_text(FAKE_UV, encoding="utf-8")
    (tmp_path / "bin" / "uv").chmod(0o755)
    model = Proxy(unique_quote("p1"), tmp_path / "sleeping")
    server = serve(model)
    env = {"PATH": f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}", "E2E_TEST_PYTHON": sys.executable,
           "CORPUS": str(corpus), "E2E_CORPUS_MANIFEST_SHA256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
           "RUNS": str(tmp_path / "runs"), "GOLD": str(tmp_path / "gold"), "CONCEPTS": str(tmp_path / "concepts"),
           "AGENT_ROOT": str(agent_root(tmp_path)), "LITELLM_MASTER_KEY": KEY, "E2E_SANDBOX": "unsandboxed",
           "LITELLM_BASE_URL": f"http://127.0.0.1:{server.server_address[1]}/v1",
           "LITELLM_LOCAL_MODEL_COST_MAP": "True", "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost",
           "MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT": "1"}
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    for key in ("SLURM_JOB_END_TIME", "SLURM_JOB_ID"):
        monkeypatch.delenv(key, raising=False)
    git_works_in_children(monkeypatch)
    yield tmp_path, model
    server.shutdown()


def script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(repo_paths.SCRIPTS / name), *args], capture_output=True, text=True, timeout=600)


@needs_tools
def test_env_script_checks_and_stops(session: tuple[Path, Proxy], monkeypatch: pytest.MonkeyPatch) -> None:
    tmp, _ = session
    done = script("e2e-env.sh")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "PASS LITELLM_MASTER_KEY is set" in done.stdout and "serves orch-model, sub-model-1, sub-model-2" in done.stdout
    assert KEY not in done.stdout + done.stderr and (tmp / "concepts").is_dir()
    # Sourced, it exports into the caller's shell and leaves its options alone.
    done = subprocess.run(["bash", "-c", f'source "{REPO}/scripts/e2e-env.sh" >/dev/null && '
                           'echo "$CORPUS_MANIFEST_SHA256 $-"'], capture_output=True, text=True)
    sha, flags = done.stdout.split()
    assert sha == os.environ["E2E_CORPUS_MANIFEST_SHA256"] and "e" not in flags and "u" not in flags
    monkeypatch.setenv("LITELLM_MASTER_KEY", "wrong")
    done = script("e2e-env.sh")
    assert done.returncode == 1 and "does not answer /models" in done.stderr and "wrong" not in done.stderr
    monkeypatch.setenv("E2E_CORPUS_MANIFEST_SHA256", "0" * 64)
    done = script("e2e-env.sh")
    assert done.returncode == 1 and "expected 0000" in done.stderr and "PASS RUNS" not in done.stdout


@needs_tools
def test_concepts_batch_and_replay_scripts(session: tuple[Path, Proxy]) -> None:
    """The whole path on one baseline run (run, attach, exports, replay, reexec); every step is a new process."""
    tmp, model = session
    concepts, runs = tmp / "concepts", tmp / "runs" / "e2e-test"
    done = script("e2e-concepts.sh")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "PASS 12 proposed" in done.stdout and "PASS 12 picked" in done.stdout
    picks = json.loads((concepts / "picks.json").read_text(encoding="utf-8"))
    assert sorted(picks) == [f"q{n:02d}" for n in range(1, 13)]
    assert {p["picked_by"] for p in picks.values()} == {"provisional-first"}

    # The smoke manifest cut to one run, to keep the test short (each agent command is a new Python process).
    smoke = json.loads((repo_paths.BACKEND / "agent" / "manifests" / "e2e-smoke.json").read_text(encoding="utf-8"))
    manifest = tmp / "e2e-test.json"
    manifest.write_text(json.dumps(smoke | {"name": "e2e-test", "questions": smoke["questions"][1:],
                                            "conditions": ["claim_off"], "repeats": 1}), encoding="utf-8")
    done = script("e2e-batch.sh", str(manifest))
    assert done.returncode == 0, done.stdout + done.stderr
    effective = json.loads((runs / "manifest.json").read_text(encoding="utf-8"))
    assert effective["runs_root"] == str(runs) and effective["sandbox"] == "unsandboxed"
    assert effective["questions"] == [{"id": "q10", "concept": str(concepts / "q10" / "concept.json")}]
    assert effective["base_url"] == os.environ["LITELLM_BASE_URL"] and effective["notes"].startswith("Effective copy")
    run = runs / "q10-claim_off-r1-a1"
    assert all((run / f).is_file() for f in ("attach.json", "graph.ttl", "graph.json", "timeline.html", "pairs.jsonl"))
    assert "== done: 1 finished runs" in done.stdout and "PASS edges=1" in done.stdout
    assert done.stdout.rstrip().endswith(f"RUNS_ROOT={runs}")  # what scoring and the web app take as RUNS
    # The next job: nothing runs again, nothing is exported again.
    done = script("e2e-batch.sh", str(manifest))
    assert done.returncode == 0 and "q10-claim_off-r1-a1: checked and exported before" in done.stdout

    # A claim_off run: its attach calls are checked from attach-trajectory.json, so it replays in full.
    done = script("e2e-replay.sh", str(manifest), "--reexec")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "q10-claim_off-r1-a1 replay ok, reexec identical\n" in done.stdout
    assert "PASS 1 runs" in done.stdout

    # A changed concept (e.g. a pick replaced) stops the batch instead of mixing two concepts' runs in one root.
    concept = concepts / "q10" / "concept.json"
    concept.write_bytes(concept.read_bytes().replace(b"ACL 2025", b"EMNLP 2025"))
    done = script("e2e-batch.sh", str(manifest))
    assert done.returncode == 1 and "the concept of q10 changed" in done.stderr
    assert model.requests == 12 + 2 + 2  # 12 concept proposals, the run's 2 replies, the attach step's 2


@needs_tools
def test_concepts_script_says_how_to_retry(session: tuple[Path, Proxy], monkeypatch: pytest.MonkeyPatch) -> None:
    """A question without valid briefs stops the script with the way out; the rerun retries only it."""
    tmp, model = session
    broken = Proxy.reply

    def no_briefs_for_q03(self: Proxy, messages: list[dict[str, Any]]) -> str:
        if "Which low-resource languages" in messages[1]["content"]:
            return "I cannot answer that."
        return broken(self, messages)
    monkeypatch.setattr(Proxy, "reply", no_briefs_for_q03)
    done = script("e2e-concepts.sh")
    assert done.returncode == 1 and "== pick" not in done.stdout
    assert "FAIL 1 failed, 11 proposed (needs action: q03)" in done.stdout
    assert "run the script again to retry only those, with another seed" in done.stderr
    assert "E2E_CONCEPT_SEED=2" in done.stderr
    monkeypatch.setattr(Proxy, "reply", broken)
    monkeypatch.setenv("E2E_CONCEPT_SEED", "2")
    done = script("e2e-concepts.sh")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "PASS 1 proposed, 11 skipped" in done.stdout and "PASS 12 picked" in done.stdout
    attempts = json.loads((tmp / "concepts" / "q03" / "session.json").read_text(encoding="utf-8"))["attempts"]
    assert [a["sampling"]["seed"] for a in attempts] == [1, 2]
    assert model.requests == 11 + 2 + 1  # 11 proposals, q03's two rounds without briefs, q03's retry
