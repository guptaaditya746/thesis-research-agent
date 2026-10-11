"""Batch runner (row 2.9): plan, deadline, and real runs as child processes against a fake model server.

The children are the real `python -m agent.cli run|attach`; the model is a tiny OpenAI-compatible
HTTP server in this process that LiteLLM talks to, scripted by what each conversation asks for.
"""
from __future__ import annotations

import json
import re
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

import pytest

from agent import batch as batch_mod
from agent.batch import Batch, Manifest, job_deadline, parse_deadline, run_state
from agent.chain import verify
from agent.cli import main as cli
from agent.rundir import RunDir
from agent.verify import verify_run

from .conftest import REPO, fixture, write_corpus

FENCE = "`" * 3
SAMPLE = REPO / "agent" / "manifests" / "m4-72.json"


# --- plan and deadline (any OS) ------------------------------------------------------------------------

def test_sample_manifest_is_72_paired_runs() -> None:
    assert b"\r" not in SAMPLE.read_bytes()
    plan = Manifest.load(SAMPLE).plan()
    assert len(plan) == 72 and len({e.key for e in plan}) == 72
    assert [e.key for e in plan[:3]] == ["q01-claim_on-r1", "q01-claim_off-r1", "q02-claim_on-r1"]
    assert plan[-1].key == "q12-claim_off-r3"
    seeds: dict[tuple[str, int], set[int]] = {}
    for e in plan:
        seeds.setdefault((e.question_id, e.repeat), set()).add(e.seed)
    assert all(len(s) == 1 for s in seeds.values())  # both conditions share the seed
    assert len({next(iter(s)) for s in seeds.values()}) == 36
    assert plan[0].seed == 1101 and plan[-1].seed == 2203
    assert {e.concept.as_posix() for e in plan} =={f"concepts/q{n:02d}/concept.json" for n in range(1, 13)}


def test_manifest_problems(tmp_path: Path) -> None:
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    for change, problem in [({"repeats": 0}, "repeats"), ({"conditions": ["claim_maybe"]}, "conditions"),
                            ({"questions": [{"id": "q1", "concept": "a"}] * 2}, "duplicate question ids")]:
        (tmp_path / "m.json").write_text(json.dumps(data | change), encoding="utf-8")
        with pytest.raises(ValueError, match=problem):
            Manifest.load(tmp_path / "m.json")


def test_deadline_sources() -> None:
    assert parse_deadline("1700000000") == 1700000000.0
    assert parse_deadline("2026-10-12T10:00:00Z") == parse_deadline("2026-10-12T10:00:00") == \
        parse_deadline("2026-10-12T12:00:00+02:00")
    assert job_deadline(environ={}) is None
    assert job_deadline(environ={"SLURM_JOB_END_TIME": "1700000000"}) == 1700000000.0
    assert job_deadline("1600000000", environ={"SLURM_JOB_END_TIME": "1700000000"}) == 1600000000.0
    soon = job_deadline(time_limit=60, environ={"SLURM_JOB_END_TIME": str(int(time.time()) + 3600)})
    assert soon is not None and abs(soon - (time.time() + 60)) < 5


# --- a fake LiteLLM endpoint ---------------------------------------------------------------------------

class FakeModel:
    """Replies like orch-model would in a run, a baseline run and an attach step."""

    def __init__(self, quote: str, sleeping: Path) -> None:
        self.quote = quote
        self.slow = False
        self.sleeping = sleeping  # the slow command touches it once it runs
        self.sleep_arg = f"100.{time.time_ns() % 10**9:09d}"  # names this test's sleep among all processes
        self.requests = 0
        self.seeds: set[int] = set()

    def sleepers(self) -> list[int]:
        """Processes still running this test's slow command."""
        needle = b"sleep\x00" + self.sleep_arg.encode()
        out = []
        for path in Path("/proc").glob("[0-9]*/cmdline"):
            try:
                if needle in path.read_bytes():
                    out.append(int(path.parent.name))
            except (OSError, ValueError):
                pass
        return out

    def wait_sleeping(self, timeout: float = 60) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.sleeping.exists():
                return True
            time.sleep(0.1)
        return False

    @staticmethod
    def bash(command: str) -> str:
        return f"Next.\n{FENCE}bash\n{command}\n{FENCE}"

    @staticmethod
    def block(obj: Any) -> str:
        return f"Done.\n{FENCE}json\n{json.dumps(obj)}\n{FENCE}"

    def claim(self) -> str:
        request = json.dumps({"s": "Paper p1", "p": "states", "o": "a fact", "file": "p1.md", "quote": self.quote})
        return self.bash(f"echo '{request}' | claim")

    def reply(self, messages: list[dict[str, Any]]) -> str:
        system = messages[0]["content"]
        turns = sum(m["role"] == "assistant" for m in messages)
        last = messages[-1]["content"]
        ids = re.findall(r'"claim_id": "(claim-\d+)"', last)
        if "Your task: an answer to a research question" in system:  # attach step
            if turns == 0:
                return self.claim()
            return self.block({"claim_id": ids[0]} if ids else {"no_source": "nothing found"})
        if turns == 0 and self.slow:
            return self.bash(f"touch '{self.sleeping}'; sleep {self.sleep_arg}")
        if turns == 0:
            return self.claim() if "Recording facts with claim" in system else self.bash('rg -c "the" "$CORPUS/p1.md"')
        fact = {"id": "f1", "s": "Paper p1", "p": "states", "o": "a fact"}
        if ids:
            fact["claims"] = ids[:1]
        cells = {"author": "Ann Lee", "first_author_papers": 1, "papers": ["p1"]}
        return self.block({"rows": [{"id": "r1", "cells": cells, "facts": [fact]}], "notes": ""})


def serve(model: FakeModel) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            model.requests += 1
            model.seeds.add(body.get("seed"))
            content = model.reply(body["messages"])
            data = json.dumps({
                "id": f"chatcmpl-{model.requests}", "object": "chat.completion", "created": int(time.time()),
                "model": "orch-model",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 50, "total_tokens": 1050}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


POSIX = sys.platform != "win32"
posix_only = pytest.mark.skipif(not POSIX, reason="runs need bash, process groups and descriptor passing")


def git_works_in_children(monkeypatch: pytest.MonkeyPatch) -> None:
    """`agent run` records the git commit. A git worktree made on Windows and tested from WSL has a
    `.git` file naming a C:/ path that WSL's git cannot follow; point GIT_DIR at /mnt/c/... instead."""
    ok = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True).returncode == 0
    dot_git = REPO / ".git"
    if ok or not dot_git.is_file():
        return
    match = re.fullmatch(r"gitdir: ([A-Za-z]):[/\\](.*)", dot_git.read_text(encoding="utf-8").strip())
    if match:
        monkeypatch.setenv("GIT_DIR", f"/mnt/{match.group(1).lower()}/{match.group(2).replace(chr(92), '/')}")


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Path, FakeModel]]:
    from .test_loop import unique_quote
    corpus, corpus_manifest = write_corpus(tmp_path)
    (tmp_path / "concept.json").write_text(json.dumps(fixture("concept_table.json")), encoding="utf-8")
    model = FakeModel(unique_quote("p1"), tmp_path / "sleeping")
    server = serve(model)
    for key, value in {"LITELLM_LOCAL_MODEL_COST_MAP": "True", "NO_PROXY": "127.0.0.1,localhost",
                       "no_proxy": "127.0.0.1,localhost", "MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT": "1"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("SLURM_JOB_END_TIME", raising=False)
    git_works_in_children(monkeypatch)
    manifest = {
        "schema_version": 1, "name": "test", "runs_root": str(tmp_path / "runs"), "corpus": str(corpus),
        "corpus_manifest": str(corpus_manifest), "questions": [{"id": "q01", "concept": str(tmp_path / "concept.json")}],
        "conditions": ["claim_on", "claim_off"], "repeats": 1, "temperature": 0.7, "seed_base": 1000,
        "budget": {"steps": 10, "tokens": 100000}, "attach_budget": {"steps": 3, "tokens": 50000},
        "sandbox": "unsandboxed", "base_url": f"http://127.0.0.1:{server.server_address[1]}/v1", "broker": "auto",
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    yield tmp_path, model
    server.shutdown()


def make(tmp: Path, **change: Any) -> Batch:
    data = json.loads((tmp / "manifest.json").read_text(encoding="utf-8")) | change
    (tmp / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    kw = {"deadline": None, "margin_s": 0, "min_start_s": 0, "grace_s": 20}
    return Batch(Manifest.load(tmp / "manifest.json"), **kw)


def records(run: RunDir) -> list[dict[str, Any]]:
    return [json.loads(line) for line in run.events.read_text(encoding="utf-8").splitlines()]


def dirs(tmp: Path) -> list[str]:
    return sorted(p.name for p in (tmp / "runs").iterdir()) if (tmp / "runs").exists() else []


# --- runs (POSIX) ----------------------------------------------------------------------------------------

@posix_only
def test_batch_runs_both_conditions_then_skips_them(setup: tuple[Path, FakeModel],
                                                     capfd: pytest.CaptureFixture[str]) -> None:
    tmp, model = setup
    b = make(tmp)
    assert b.run() == 0
    assert dirs(tmp) == ["q01-claim_off-r1-a1", "q01-claim_on-r1-a1"]
    corpus = (tmp / "corpus", tmp / "corpus" / "manifest.json")
    on, off = RunDir(tmp / "runs" / "q01-claim_on-r1-a1"), RunDir(tmp / "runs" / "q01-claim_off-r1-a1")
    for run in (on, off):
        assert run_state(run, *corpus) == ("finished", "")
        assert verify_run(run, *corpus).ok
        assert run.load_config()["sampling"] == {"temperature": 0.7, "seed": 1101}
        assert run.load_config()["budget"]["steps"] == 10
    assert model.seeds == {1101}
    answer = json.loads(off.answer.read_text(encoding="utf-8"))
    assert answer["rows"][0]["facts"][0] == {"id": "f1", "s": "Paper p1", "p": "states", "o": "a fact",
                                             "claims": ["claim-000001"], "origin": "attach"}
    assert off.load_config()["attach"]["budget_per_fact"]["steps"] == 3
    assert json.loads(on.answer.read_text(encoding="utf-8"))["rows"][0]["facts"][0]["origin"] == "research"
    out = capfd.readouterr().out
    assert "q01-claim_on-r1-a1: start (seed 1101" in out and "q01-claim_off-r1-a1: attach step" in out
    assert "done: 2/2 finished" in out
    # A second job finds both finished and starts nothing.
    requests = model.requests
    assert make(tmp).run() == 0
    assert model.requests == requests and dirs(tmp) == ["q01-claim_off-r1-a1", "q01-claim_on-r1-a1"]
    assert "start" not in capfd.readouterr().out
    assert cli(["batch", str(tmp / "manifest.json"), "--status"]) == 0
    assert capfd.readouterr().out.splitlines() == ["q01-claim_on-r1 seed=1101: q01-claim_on-r1-a1=finished",
                                                   "q01-claim_off-r1 seed=1101: q01-claim_off-r1-a1=finished"]


@posix_only
@pytest.mark.parametrize("how", ["deadline", "sigterm"])
def test_a_cut_run_is_marked_and_rerun_fresh(setup: tuple[Path, FakeModel], how: str,
                                             capfd: pytest.CaptureFixture[str]) -> None:
    tmp, model = setup
    model.slow = True
    b = make(tmp, conditions=["claim_on"])

    def cut_when_slow() -> None:  # the job limit arrives while the run's command sleeps
        model.wait_sleeping()
        if how == "deadline":
            b.deadline = time.time()
        else:
            b.on_sigterm(signal.SIGTERM, None)
    threading.Thread(target=cut_when_slow, daemon=True).start()
    started = time.monotonic()
    assert b.run() == 2
    assert time.monotonic() - started < 60  # the sleeping command did not hold the job
    assert b.stopping == how
    cut = RunDir(tmp / "runs" / "q01-claim_on-r1-a1")
    recs = records(cut)
    last = recs[-1]
    assert (last["subtype"], last["agent_id"], last["generated"]["reason"]) == ("coverage", "batch", "job_time_limit")
    assert last["generated"]["detail"]["phase"] == "research" and last["generated"]["detail"]["stopped_by"] == how
    assert verify(cut.events, cut.claims).ok and not cut.answer.exists()
    assert [r["subtype"] for r in recs] == ["ai_model_invocation", "coverage"]  # the call, then the cut
    out = capfd.readouterr().out
    assert "marked job_time_limit" in out and "stopped (" in out
    assert "run q01-claim_on-r1-a1: broker head=" in out  # the child stopped cleanly: broker closed, head printed
    assert model.sleepers() == []  # the sleeping command went with it
    # The next job reruns the key in a fresh directory and keeps the cut one.
    model.slow = False
    assert make(tmp).run() == 0
    assert dirs(tmp) == ["q01-claim_on-r1-a1", "q01-claim_on-r1-a2"]
    corpus = (tmp / "corpus", tmp / "corpus" / "manifest.json")
    assert run_state(cut, *corpus) == ("cut", "job_time_limit")
    assert run_state(RunDir(tmp / "runs" / "q01-claim_on-r1-a2"), *corpus) == ("finished", "")


@posix_only
def test_sigterm_to_the_runner_process(setup: tuple[Path, FakeModel]) -> None:
    tmp, model = setup
    model.slow = True
    make(tmp, conditions=["claim_on"])
    proc = subprocess.Popen([sys.executable, "-m", "agent.cli", "batch", str(tmp / "manifest.json"),
                             "--min-start", "0", "--margin", "0"], cwd=REPO,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        assert model.wait_sleeping()
        proc.send_signal(signal.SIGTERM)  # our own test child, as Slurm would signal the batch step
        out, _ = proc.communicate(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 2, out.decode()
    assert model.sleepers() == []
    last = records(RunDir(tmp / "runs" / "q01-claim_on-r1-a1"))[-1]
    assert last["generated"]["reason"] == "job_time_limit" and last["generated"]["detail"]["stopped_by"] == "sigterm"


@posix_only
def test_resume_marks_unmarked_runs_and_runs_a_pending_attach(setup: tuple[Path, FakeModel],
                                                              capfd: pytest.CaptureFixture[str]) -> None:
    tmp, model = setup
    b = make(tmp)
    plan = b.manifest.plan()
    # A job died outright mid-run (no mark), and another after a baseline run but before its attach step.
    dead = RunDir.create(tmp / "runs", "q01-claim_on-r1-a1", fixture("concept_table.json"),
                         corpus_manifest=tmp / "corpus" / "manifest.json", condition="claim_on", temperature=0.7,
                         seed=1101, prompt_version="v1", prompt_sha256="a" * 64,
                         agent_root_manifest_sha256="b" * 64, git_commit="c" * 40)
    subprocess.run(b.run_argv(plan[1], "q01-claim_off-r1-a1"), check=False, cwd=REPO)
    corpus = (tmp / "corpus", tmp / "corpus" / "manifest.json")
    off = RunDir(tmp / "runs" / "q01-claim_off-r1-a1")
    assert run_state(off, *corpus)[0] == "attach_pending"
    assert run_state(dead, *corpus) == ("incomplete", "no answer.json")
    capfd.readouterr()
    assert b.run() == 0
    out = capfd.readouterr().out
    assert "q01-claim_on-r1-a1: found incomplete (no answer.json); marked interrupted" in out
    assert dirs(tmp) == ["q01-claim_off-r1-a1", "q01-claim_on-r1-a1", "q01-claim_on-r1-a2"]
    assert records(dead)[-1]["generated"]["reason"] == "interrupted"
    assert run_state(off, *corpus) == ("finished", "") and (off.root / "attach.json").is_file()


@posix_only
def test_gives_up_after_max_attempts(setup: tuple[Path, FakeModel], capfd: pytest.CaptureFixture[str]) -> None:
    tmp, _ = setup
    b = make(tmp, conditions=["claim_on"], max_attempts=1)
    RunDir.create(tmp / "runs", "q01-claim_on-r1-a1", fixture("concept_table.json"),
                  corpus_manifest=tmp / "corpus" / "manifest.json", condition="claim_on", temperature=0.7, seed=1101,
                  prompt_version="v1", prompt_sha256="a" * 64, agent_root_manifest_sha256="b" * 64, git_commit="c" * 40)
    assert b.run() == 1
    assert "gave up after 1 attempts" in capfd.readouterr().out
    # A concept file that does not exist: the run cannot start, and the runner does not loop on it.
    b = make(tmp, questions=[{"id": "q02", "concept": str(tmp / "missing.json")}], max_attempts=3)
    assert b.run() == 1
    assert "no run directory; giving up on q02-claim_on-r1" in capfd.readouterr().out


def test_no_time_left_starts_nothing(tmp_path: Path) -> None:
    corpus, manifest = write_corpus(tmp_path)
    data = json.loads(SAMPLE.read_text(encoding="utf-8")) | {"runs_root": str(tmp_path / "runs"), "corpus": str(corpus)}
    (tmp_path / "m.json").write_text(json.dumps(data), encoding="utf-8")
    b = Batch(Manifest.load(tmp_path / "m.json"), deadline=time.time() + 600, margin_s=300, min_start_s=900)
    assert b.run() == 2 and b.stopping == "deadline"
    assert not (tmp_path / "runs").exists()
    assert batch_mod.attempts(tmp_path / "runs", "q01-claim_on-r1") == []
