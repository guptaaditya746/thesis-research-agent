"""What the app starts and writes (webapp/evjobs.py): every job endpoint's argv with a fake interpreter, the
validation of names and paths, the model queue, cancel, decisions.yaml round-tripping through cards.validate,
and freeze (and a whole template corpus -> regex run -> score chain) through the real commands."""
from __future__ import annotations

import json
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from jsonio import file_sha256
from evidence.propose import cards as cards_module
from evidence.propose import critic as critic_module
from evidence.tests.propose_support import EFFECT_CARDS, QUESTION, Scripted, flow
from webapp import evjobs
from webapp.app import create_app
from webapp.settings import REPO, Settings

from .evidence_world import NAME, EvidenceWorld

MIXED, EXPLICIT = f"{NAME}-mixed", f"{NAME}-explicit"
POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="the fake interpreter is a #! script (POSIX)")

FAKE = '''#!{python}
"""Stands in for `python -m webapp.tool ...`: logs its argv, and the proposal steps write their file."""
import json, os, sys, time
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps(args) + "\\n")
print("fake", *args[2:5], flush=True)
if os.environ.get("FAKE_SLEEP"):
    time.sleep(float(os.environ["FAKE_SLEEP"]))
tool = args[2:]
if os.environ.get("FAKE_FAIL") in tool:
    sys.exit(1)
if tool[:2] == ["evidence", "run"] and os.environ.get("FAKE_ERROR_CALLS"):
    calls = Path(tool[tool.index("--out") + 1]) / tool[tool.index("--run-id") + 1] / "calls"
    calls.mkdir(parents=True)
    for n in range(int(os.environ["FAKE_ERROR_CALLS"])):
        (calls / f"c{{n}}.json").write_text('{{"status": "partial", "error": {{"reason": "model_call"}}}}')
    (calls / "ok.json").write_text('{{"status": "ok"}}')
    (calls / "agent.json").write_text('{{"status": "partial", "error": {{"reason": "no_final_answer"}}}}')   # not one
if tool[:2] == ["evidence", "propose"]:
    step = tool[2]
    d = Path(tool[tool.index("--out") + 1]) if step == "frame" else Path(tool[3])
    d.mkdir(parents=True, exist_ok=True)
    text = json.dumps({{"question": tool[tool.index("--question") + 1]}}) if step == "frame" else "{{}}"
    (d / {{"frame": "frame.json", "draft": "draft.yaml", "critic": "critic.json", "cards": "cards.json"}}[step]).write_text(text)
sys.exit(0)
'''


@pytest.fixture
def world(ev_world: EvidenceWorld, tmp_path: Path) -> EvidenceWorld:
    return ev_world.copy(tmp_path / "world")


@pytest.fixture
def fake_python(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "fake-python"
    path.write_text(FAKE.format(python=sys.executable), encoding="utf-8")
    path.chmod(0o755)
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "fake.log"))
    for name in ("FAKE_SLEEP", "FAKE_FAIL"):
        monkeypatch.delenv(name, raising=False)
    return path


@pytest.fixture
def gateway_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """The model gateway answers (no network in the tests; the probe itself is tested on its own)."""
    monkeypatch.setattr(evjobs, "gateway_problem", lambda settings: None)


@pytest.fixture
def client(world: EvidenceWorld, fake_python: Path, gateway_ok: None) -> Iterator[TestClient]:
    settings = Settings(EV=world.root, WEBAPP_PYTHON=str(fake_python), WEBAPP_USER="aditya",  # type: ignore[call-arg]
                        agent_root=Path("/opt/agent-root"))
    with TestClient(create_app(settings)) as c:
        yield c


def calls(tmp_path: Path) -> list[list[str]]:
    log = tmp_path / "fake.log"
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def wait(client: TestClient, job_id: str, timeout: float = 60) -> dict[str, Any]:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        job = client.get(f"/api/ev/jobs/{job_id}").json()
        if job["state"] not in ("queued", "running"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


def start(client: TestClient, kind: str, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post(f"/api/ev/jobs/{kind}", json=body)
    assert response.status_code == 202, response.text
    return response.json()


TOOL = ["-m", "webapp.tool"]


# --- argv of every job ------------------------------------------------------------------------------------

@POSIX_ONLY
def test_synth_job(client: TestClient, world: EvidenceWorld, tmp_path: Path) -> None:
    job = start(client, "synth", {"name": "rag-tpl-ui", "seed": 3, "studies": 4, "levels": ["explicit", "complex"],
                                  "duplicates": 1, "irrelevant": 2})
    assert (job["kind"], job["lane"], job["refs"]) == ("synth", "cpu", {"corpus_set": "rag-tpl-ui",
                                                                        "corpus": "rag-tpl-ui-mixed"})
    assert wait(client, job["id"])["state"] == "done"
    [argv] = calls(tmp_path)
    assert argv == [*TOOL, "synth", "build", "--name", "rag-tpl-ui", "--seed", "3", "--studies", "4",
                    "--renderer", "template", "--levels", "explicit,complex", "--duplicates", "1", "--missing", "0",
                    "--outliers", "0", "--irrelevant", "2", "--out", str(world.corpora)]
    taken = client.post("/api/ev/jobs/synth", json={"name": NAME, "levels": ["explicit"]})
    assert taken.status_code == 409 and f"{NAME}-explicit" in taken.json()["detail"]


@POSIX_ONLY
def test_run_jobs_with_the_runbooks_groups(client: TestClient, world: EvidenceWorld, tmp_path: Path) -> None:
    corpus = f"{NAME}-paraphrased"
    regex = start(client, "run", {"corpus": corpus, "protocol": {"source": "repo", "name": "rag-factuality"},
                                  "extractors": "regex-only"})
    gaps = start(client, "run", {"corpus": corpus, "protocol": {"source": "repo", "name": "rag-factuality"},
                                 "extractors": "cascade", "strategy": "gaps"})
    agentic = start(client, "run", {"corpus": corpus, "protocol": {"source": "repo", "name": "rag-factuality-agentic"},
                                    "strategy": "gaps", "model": "other-model"})
    frozen = start(client, "run", {"corpus": corpus, "protocol": {"source": "proposal", "name": "rag-factuality"}})
    for job in (regex, gaps, agentic, frozen):
        assert wait(client, job["id"])["state"] == "done"
    assert (regex["lane"], gaps["lane"]) == ("cpu", "model")
    assert [j["refs"]["run"] for j in (regex, gaps, agentic, frozen)] == [
        f"regex-only~{corpus}", f"cascade-gaps~{corpus}", f"agentic-gaps~{corpus}", f"proposal-rag-factuality-cascade~{corpus}"]
    by_out = {a[a.index("--out") + 1]: a for a in calls(tmp_path)}
    assert by_out[str(world.runs / "cascade-gaps")] == [
        *TOOL, "evidence", "run", "--protocol", str(REPO / "domains" / "rag" / "protocols" / "rag-factuality.yaml"),
        "--corpus", str(world.corpora / corpus), "--out", str(world.runs / "cascade-gaps"), "--cache", str(world.cache),
        "--extractors", "cascade", "--strategy", "gaps", "--model", "orch-model", "--run-id", corpus,
        "--allow-failed-calls"]
    assert by_out[str(world.runs / "regex-only")][by_out[str(world.runs / "regex-only")].index("--extractors") + 1] == "regex-only"
    agentic_argv = by_out[str(world.runs / "agentic-gaps")]
    assert agentic_argv[agentic_argv.index("--model") + 1] == "other-model"
    frozen_argv = by_out[str(world.runs / "proposal-rag-factuality-cascade")]
    assert frozen_argv[frozen_argv.index("--protocol") + 1] == str(world.proposals / "rag-factuality" / "protocol.yaml")
    # an existing run directory is never written over; a name of its own is
    taken = client.post("/api/ev/jobs/run", json={"corpus": MIXED, "protocol": {"source": "repo", "name": "rag-factuality"}})
    assert taken.status_code == 409 and "exists" in taken.json()["detail"]
    renamed = start(client, "run", {"corpus": MIXED, "protocol": {"source": "repo", "name": "rag-factuality"},
                                    "name": f"{MIXED}-again"})
    assert renamed["refs"]["run"] == f"cascade~{MIXED}-again"


@POSIX_ONLY
def test_baseline_jobs(client: TestClient, world: EvidenceWorld, tmp_path: Path) -> None:
    corpus = f"{NAME}-paraphrased"
    rag = start(client, "rag-baseline", {"corpus": corpus, "question": "rag-factuality"})
    agent = start(client, "agent-baseline", {"corpus": corpus, "question": "rag-factuality"})
    for job in (rag, agent):
        assert wait(client, job["id"])["state"] == "done" and job["lane"] == "model"
    rag_argv, agent_argv = calls(tmp_path)
    assert rag_argv == [*TOOL, "evaluate", "rag-baseline", "--corpus", str(world.corpora / corpus),
                        "--out", str(world.runs / "rag-baseline" / corpus),
                        "--cache", str(world.root / "cache" / "rag-baseline.jsonl"), "--model", "orch-model",
                        "--retrieval", "global", "--k", "8", "--question-id", "rag-factuality"]
    assert agent_argv == [*TOOL, "evaluate", "agent-baseline", "--corpus", str(world.corpora / corpus),
                          "--out", str(world.runs / "agent-baseline" / corpus),
                          "--cache", str(world.root / "cache" / "agent-baseline.jsonl"), "--model", "orch-model",
                          "--agent-root", str(Path("/opt/agent-root").resolve()),
                          "--base-url", Settings().litellm_base_url, "--run-id", corpus,
                          "--question-id", "rag-factuality"]
    again = client.post("/api/ev/jobs/rag-baseline", json={"corpus": MIXED, "question": "rag-factuality"})
    assert again.status_code == 409 and "answer.json" in again.json()["detail"]


@POSIX_ONLY
def test_score_and_compare_jobs(client: TestClient, world: EvidenceWorld, tmp_path: Path) -> None:
    score = start(client, "score", {"run": f"cascade~{MIXED}"})
    assert wait(client, score["id"])["state"] == "done" and score["refs"] == {"score": f"cascade~{MIXED}"}
    compare = start(client, "compare", {"reports": [f"cascade~{MIXED}", f"cascade-gaps~{MIXED}"],
                                        "name": f"compare-funnel-{MIXED}"})
    assert wait(client, compare["id"])["state"] == "done"
    score_argv, compare_argv = calls(tmp_path)
    baselines = ["--baseline", str(world.runs / "rag-baseline" / MIXED / "answer.json")]
    if (world.runs / "agent-baseline" / MIXED / "answer.json").is_file():
        baselines += ["--baseline", str(world.runs / "agent-baseline" / MIXED / "answer.json")]
    assert score_argv == [*TOOL, "evaluate", "score", "--run", str(world.runs / "cascade" / MIXED),
                          "--corpus", str(world.corpora / MIXED), *baselines,
                          "--question-id", "rag-factuality", "--out", str(world.scores / "cascade" / MIXED)]
    assert compare_argv == [*TOOL, "evaluate", "compare", "--out", str(world.scores / f"compare-funnel-{MIXED}"),
                            str(world.scores / "cascade" / MIXED), str(world.scores / "cascade-gaps" / MIXED)]
    baseline = client.post("/api/ev/jobs/score", json={"run": f"rag-baseline~{MIXED}"})
    assert baseline.status_code == 409 and "not an engine run" in baseline.json()["detail"]
    clash = client.post("/api/ev/jobs/compare", json={"reports": [f"cascade~{MIXED}", f"cascade~{EXPLICIT}"],
                                                      "name": "cascade"})
    assert clash.status_code == 409 and "not a comparison" in clash.json()["detail"]


@POSIX_ONLY
def test_score_takes_the_latest_reexecution_beside_the_run(client: TestClient, world: EvidenceWorld, tmp_path: Path) -> None:
    for stamp in ("20261017T100000", "20261018T100000"):
        d = world.runs / "cascade" / f"{MIXED}-reexec-{stamp}"
        d.mkdir()
        (d / "reexec.json").write_text("{}", encoding="utf-8")
    assert wait(client, start(client, "score", {"run": f"cascade~{MIXED}"})["id"])["state"] == "done"
    [argv] = calls(tmp_path)
    assert argv[argv.index("--reexec") + 1] == str(world.runs / "cascade" / f"{MIXED}-reexec-20261018T100000" / "reexec.json")


@POSIX_ONLY
def test_retry_errors_and_the_reserved_baseline_groups(client: TestClient, world: EvidenceWorld, tmp_path: Path) -> None:
    corpus = f"{NAME}-paraphrased"
    job = start(client, "run", {"corpus": corpus, "protocol": {"source": "repo", "name": "rag-factuality"},
                                "retry_errors": True})
    assert wait(client, job["id"])["state"] == "done"
    assert calls(tmp_path)[0][-1] == "--retry-errors"
    for group in ("rag-baseline", "agent-baseline"):
        refused = client.post("/api/ev/jobs/run", json={"corpus": corpus, "group": group,
                                                        "protocol": {"source": "repo", "name": "rag-factuality"}})
        assert refused.status_code == 400 and "baselines" in refused.json()["detail"]


@POSIX_ONLY
def test_a_run_with_failed_calls_is_done_with_its_failed_calls(client: TestClient, world: EvidenceWorld,
                                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ERROR_CALLS", "3")
    corpus = f"{NAME}-paraphrased"
    done = wait(client, start(client, "run", {"corpus": corpus, "protocol": {"source": "repo", "name": "rag-factuality"},
                                              "strategy": "gaps"})["id"])
    assert done["state"] == "done" and done["failed_calls"] == 3
    assert any("3 extractor call(s) failed" in w for w in done["warnings"])
    run = next(r for r in client.get("/api/ev/runs").json() if r["id"] == f"cascade-gaps~{corpus}")
    assert run["error_calls"] == 3
    clean = next(r for r in client.get("/api/ev/runs").json() if r["id"] == f"cascade~{MIXED}")
    assert clean["error_calls"] == 0


@POSIX_ONLY
def test_model_jobs_are_refused_without_a_gateway(world: EvidenceWorld, fake_python: Path, tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    import http.server
    import threading

    corpus = f"{NAME}-paraphrased"
    regex = {"corpus": corpus, "protocol": {"source": "repo", "name": "rag-factuality"}, "extractors": "regex-only"}
    monkeypatch.delenv("LITELLM_MASTER_KEY", raising=False)
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_PYTHON=str(fake_python)))) as c:  # type: ignore[call-arg]
        no_key = c.post("/api/ev/jobs/rag-baseline", json={"corpus": corpus, "question": "rag-factuality"})
        assert no_key.status_code == 409 and "LITELLM_MASTER_KEY" in no_key.json()["detail"]
        assert c.post("/api/ev/jobs/propose", json={"proposal": "px", "question": "rag-factuality"}).status_code == 409
        assert c.post("/api/ev/jobs/run", json=regex).status_code == 202   # no model call: no gateway needed
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-never-logged")
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_PYTHON=str(fake_python),  # type: ignore[call-arg]
                                        litellm_base_url="http://127.0.0.1:9/v1"))) as c:
        down = c.post("/api/ev/jobs/agent-baseline", json={"corpus": corpus, "question": "rag-factuality"})
        assert down.status_code == 409 and "does not answer" in down.json()["detail"]
        assert "sk-test" not in down.text

    seen: list[str] = []

    class Gateway(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            seen.append(f"{self.path} {self.headers.get('Authorization')}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"data": []}')

        def log_message(self, *args: Any) -> None:
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Gateway)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/v1"
        with TestClient(create_app(Settings(EV=world.root, WEBAPP_PYTHON=str(fake_python),  # type: ignore[call-arg]
                                            litellm_base_url=url))) as c:
            assert c.post("/api/ev/jobs/rag-baseline", json={"corpus": corpus, "question": "rag-factuality"}).status_code == 202
    finally:
        server.shutdown()
    assert seen == ["/v1/models Bearer sk-test-never-logged"]


@POSIX_ONLY
def test_an_unfinished_run_is_not_scored(client: TestClient, world: EvidenceWorld) -> None:
    (world.runs / "cascade" / MIXED / "run.json").unlink()
    response = client.post("/api/ev/jobs/score", json={"run": f"cascade~{MIXED}"})
    assert response.status_code == 409 and "not finished" in response.json()["detail"]


@POSIX_ONLY
def test_propose_job_runs_the_missing_steps(client: TestClient, world: EvidenceWorld, tmp_path: Path) -> None:
    job = start(client, "propose", {"proposal": "p-new", "question": "rag-factuality"})
    done = wait(client, job["id"])
    assert done["state"] == "done" and job["lane"] == "model" and job["refs"] == {"proposal": "p-new"}
    d = world.proposals / "p-new"
    assert calls(tmp_path) == [
        [*TOOL, "evidence", "propose", "frame", "--question", QUESTION, "--out", str(d), "--model", "orch-model"],
        [*TOOL, "evidence", "propose", "draft", str(d)],
        [*TOOL, "evidence", "propose", "critic", str(d), "--model", "orch-model"],
        [*TOOL, "evidence", "propose", "cards", str(d), "--model", "orch-model"]]
    assert [s["needs"] for s in done["steps"]] == [[], [str(d / "frame.json")], [str(d / "draft.yaml")],
                                                   [str(d / "critic.json")]]
    has_cards = client.post("/api/ev/jobs/propose", json={"proposal": "p-new", "question": "rag-factuality"})
    assert has_cards.status_code == 409 and "has its cards" in has_cards.json()["detail"]
    frozen = client.post("/api/ev/jobs/propose", json={"proposal": "rag-factuality", "question": "rag-factuality"})
    assert frozen.status_code == 409 and "frozen" in frozen.json()["detail"]


@POSIX_ONLY
def test_a_failed_propose_step_skips_the_rest_and_a_new_job_resumes(client: TestClient, world: EvidenceWorld,
                                                                     tmp_path: Path,
                                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_FAIL", "critic")
    failed = wait(client, start(client, "propose", {"proposal": "p2", "question": "rag-factuality"})["id"])
    assert failed["state"] == "failed"
    assert [s["state"] for s in failed["steps"]] == ["done", "done", "failed", "skipped"]
    monkeypatch.delenv("FAKE_FAIL")
    resumed = wait(client, start(client, "propose", {"proposal": "p2", "question": "rag-factuality",
                                                     "model": "orch-model"})["id"])
    assert resumed["state"] == "done" and [s["name"] for s in resumed["steps"]] == ["propose critic", "propose cards"]


# --- validation: names, paths, flags -------------------------------------------------------------------------

@pytest.mark.parametrize(("kind", "body"), [
    ("synth", {"name": "../x"}),
    ("synth", {"name": "-rf"}),
    ("synth", {"name": ".hidden"}),
    ("synth", {"name": "a/b"}),
    ("synth", {"name": "ok", "levels": ["bogus"]}),
    ("synth", {"name": "ok", "levels": []}),
    ("synth", {"name": "ok", "studies": 0}),
    ("synth", {"name": "ok", "renderer": "llm"}),            # no LLM-rendered corpora from the app
    ("synth", {"name": "ok", "duplicates": -1}),
    ("run", {"corpus": "..", "protocol": {"source": "repo", "name": "rag-factuality"}}),
    ("run", {"corpus": MIXED, "protocol": {"source": "repo", "name": "../../pyproject"}}),
    ("run", {"corpus": MIXED, "protocol": {"source": "elsewhere", "name": "x"}}),
    ("run", {"corpus": MIXED, "protocol": {"source": "repo", "name": "rag-factuality"}, "model": "--api-key"}),
    ("run", {"corpus": MIXED, "protocol": {"source": "repo", "name": "rag-factuality"}, "model": "a b"}),
    ("run", {"corpus": MIXED, "protocol": {"source": "repo", "name": "rag-factuality"}, "extractors": "llm-only --x"}),
    ("run", {"corpus": MIXED, "protocol": {"source": "repo", "name": "rag-factuality"}, "group": "../runs"}),
    ("run", {"corpus": MIXED, "protocol": {"source": "repo", "name": "rag-factuality"}, "import": "os"}),
    ("rag-baseline", {"corpus": MIXED, "question": "rag-factuality", "k": 0}),
    ("rag-baseline", {"corpus": MIXED, "question": "rag-factuality", "retrieval": "everything"}),
    ("agent-baseline", {"corpus": "a~b", "question": "rag-factuality"}),
    ("compare", {"reports": [f"cascade~{MIXED}"], "name": "c"}),
    ("compare", {"reports": [f"cascade~{MIXED}", f"cascade-gaps~{MIXED}"], "name": "../c"}),
    ("propose", {"proposal": "../p", "question": "rag-factuality"}),
    ("freeze", {"proposal": ".."}),
])
def test_bad_names_and_values_are_refused_before_any_job(client: TestClient, kind: str, body: dict[str, Any],
                                                          tmp_path: Path) -> None:
    response = client.post(f"/api/ev/jobs/{kind}", json=body)
    assert response.status_code == 422, (kind, body, response.status_code, response.text)
    assert client.get("/api/ev/jobs").json() == [] and calls(tmp_path) == []


@pytest.mark.parametrize(("kind", "body", "status"), [
    ("run", {"corpus": "no-such-corpus", "protocol": {"source": "repo", "name": "rag-factuality"}}, 404),
    ("run", {"corpus": MIXED, "protocol": {"source": "repo", "name": "no-such-protocol"}}, 404),
    ("run", {"corpus": MIXED, "protocol": {"source": "proposal", "name": "no-such-proposal"}}, 404),
    ("score", {"run": "cascade~..%2F..%2Fsecret"}, 404),
    ("score", {"run": "a~b~c"}, 404),
    ("score", {"run": "../cascade"}, 404),
    ("compare", {"reports": ["..~x", f"cascade~{MIXED}"], "name": "c"}, 404),
    ("propose", {"proposal": "p", "question": "no-such-question"}, 404),
    ("freeze", {"proposal": "no-such-proposal"}, 409),
])
def test_unknown_or_outside_names_are_refused(client: TestClient, kind: str, body: dict[str, Any], status: int,
                                              tmp_path: Path) -> None:
    response = client.post(f"/api/ev/jobs/{kind}", json=body)
    assert response.status_code == status, (kind, body, response.text)
    assert client.get("/api/ev/jobs").json() == [] and calls(tmp_path) == []


def test_no_jobs_without_ev(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EV", raising=False)
    with TestClient(create_app(Settings(CORPORA=tmp_path))) as c:  # type: ignore[call-arg]
        (tmp_path / "c1").mkdir()
        (tmp_path / "c1" / "manifest.json").write_text('{"corpus_id": "c1", "papers": []}', encoding="utf-8")
        response = c.post("/api/ev/jobs/rag-baseline", json={"corpus": "c1", "question": "rag-factuality"})
        assert response.status_code == 409 and "$EV" in response.json()["detail"]


# --- queue, cancel, log, reload ------------------------------------------------------------------------------

@POSIX_ONLY
def test_model_jobs_queue_cancel_and_the_log(client: TestClient, world: EvidenceWorld, tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_SLEEP", "30")
    first = start(client, "rag-baseline", {"corpus": f"{NAME}-paraphrased", "question": "rag-factuality"})
    second = start(client, "agent-baseline", {"corpus": f"{NAME}-paraphrased", "question": "rag-factuality"})
    end = time.monotonic() + 20
    while client.get(f"/api/ev/jobs/{first['id']}").json()["state"] != "running":
        assert time.monotonic() < end
        time.sleep(0.05)
    assert client.get(f"/api/ev/jobs/{second['id']}").json()["state"] == "queued"   # one model job at a time
    busy = client.post("/api/ev/jobs/rag-baseline", json={"corpus": f"{NAME}-paraphrased", "question": "rag-factuality"})
    assert busy.status_code == 409 and first["id"] in busy.json()["detail"]
    cancelled = client.post(f"/api/ev/jobs/{second['id']}/cancel", json={}).json()
    assert (cancelled["state"], cancelled["error"]) == ("failed", "cancelled")
    while "fake evaluate" not in client.get(f"/api/ev/jobs/{first['id']}/log").text:   # its output, not its $ line
        assert time.monotonic() < end
        time.sleep(0.05)
    log = client.get(f"/api/ev/jobs/{first['id']}/log", params={"lines": 5}).text
    assert log.startswith("$ ") and "webapp.tool evaluate rag-baseline" in log
    client.post(f"/api/ev/jobs/{first['id']}/cancel", json={})
    done = wait(client, first["id"])
    assert (done["state"], done["error"]) == ("failed", "cancelled")
    assert [j["id"] for j in client.get("/api/ev/jobs").json()] == [second["id"], first["id"]]
    assert len(calls(tmp_path)) == 1   # the cancelled queued job never started
    # the jobs are listed again by a new server (a reloaded page asks the same list)
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_USER="aditya"))) as again:  # type: ignore[call-arg]
        assert {j["id"] for j in again.get("/api/ev/jobs").json()} == {first["id"], second["id"]}
    assert ".jobs" not in [r["group"] for r in client.get("/api/ev/runs").json()]


# --- decisions and freeze through the real proposal flow ------------------------------------------------------

@pytest.fixture
def proposal(world: EvidenceWorld) -> Path:
    """A proposal up to its cards, made by the real flow with the scripted model (evidence/tests/propose_support.py)."""
    return flow(world.proposals / "p1", Scripted(), until="cards")


def body(directory: Path, decisions: list[dict[str, Any]], force: bool = False) -> dict[str, Any]:
    """The PUT body: the decisions and the sha256 of decisions.yaml as it is now (what the form loaded)."""
    path = directory / "decisions.yaml"
    return {"decisions": decisions, "base_sha256": file_sha256(path) if path.is_file() else None, "force": force}


def entries(directory: Path, change: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The model's defaults as the form sends them (by model), with `change` per card applied."""
    cards = json.loads((directory / "cards.json").read_text(encoding="utf-8"))["cards"]
    out = [{"card": c["id"], "choice": c["default"], "reason": f"default: {c['rationale']}", "by": "model"} for c in cards]
    for e in out:
        e.update((change or {}).get(e["card"], {}))
    return out


def test_decisions_round_trip_through_cards_validate(proposal: Path, world: EvidenceWorld) -> None:
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_USER="aditya"))) as c:  # type: ignore[call-arg]
        kept = c.put("/api/ev/proposals/p1/decisions", json=body(proposal, entries(proposal)))
        assert kept.status_code == 200 and kept.json()["problems"] == []
        change = {"min_effect": {"choice": "lenient", "reason": "two points is the noise between runs", "by": "aditya"},
                  "pairing": {"choice": "custom", "value": {"prefer": ["document_order"]}, "reason": "order only",
                              "by": "aditya"}}
        # sent out of order: written in card order
        sent = list(reversed(entries(proposal, change)))
        result = c.put("/api/ev/proposals/p1/decisions", json=body(proposal, sent)).json()
        assert result == {"written": str(proposal / "decisions.yaml"), "problems": [],
                          "sha256": file_sha256(proposal / "decisions.yaml")}
        text = (proposal / "decisions.yaml").read_text(encoding="utf-8")
        assert text.startswith(cards_module.HEADER)
        data = yaml.safe_load(text)
        assert [d["card"] for d in data["decisions"]] == EFFECT_CARDS
        decided = cards_module.validate(json.loads((proposal / "cards.json").read_text(encoding="utf-8"))["cards"], data)
        by_card = {d["card"]: d for d in decided}
        assert by_card["min_effect"]["value"] == {"min_effect": 0.02} and by_card["min_effect"]["by"] == "aditya"
        assert by_card["pairing"]["value"] == {"prefer": ["document_order"]}
        assert by_card["screen"]["by"] == "model" and "value" not in data["decisions"][0]
        detail = c.get("/api/ev/proposals/p1").json()
        assert detail["decision_problems"] == []
        assert next(x for x in detail["cards"] if x["id"] == "min_effect")["decision"]["by"] == "aditya"


@pytest.mark.parametrize(("change", "problem"), [
    ({"min_effect": {"choice": "lenient", "reason": "x", "by": "model"}}, "not the model's default"),
    ({"min_effect": {"reason": "   ", "by": "aditya"}}, "without a reason"),
    ({"min_effect": {"choice": "nope", "by": "aditya"}}, "not an option"),
    ({"min_effect": {"choice": "custom", "value": {"min_effect": -1}, "by": "aditya"}}, "card's shape"),
    ({"metrics": {"choice": "custom", "value": None, "by": "aditya"}}, "card's shape"),
])
def test_decisions_freeze_would_refuse_are_written_and_shown(proposal: Path, world: EvidenceWorld,
                                                             change: dict[str, Any], problem: str) -> None:
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_USER="aditya"))) as c:  # type: ignore[call-arg]
        result = c.put("/api/ev/proposals/p1/decisions", json=body(proposal, entries(proposal, change))).json()
        assert any(problem in p for p in result["problems"]), result["problems"]
        refused = c.post("/api/ev/jobs/freeze", json={"proposal": "p1"})
        assert refused.status_code == 409 and problem in refused.json()["detail"]
        assert c.get("/api/ev/jobs").json() == []


def test_a_missing_card_is_a_problem(proposal: Path, world: EvidenceWorld) -> None:
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_USER="aditya"))) as c:  # type: ignore[call-arg]
        result = c.put("/api/ev/proposals/p1/decisions", json=body(proposal, entries(proposal)[1:])).json()
        assert result["problems"] == ["screen: no decision"]


def test_freeze_through_the_real_command(proposal: Path, world: EvidenceWorld) -> None:
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_USER="aditya"))) as c:  # type: ignore[call-arg]
        change = {"min_effect": {"choice": "lenient", "reason": "two points is the noise between runs", "by": "aditya"}}
        assert c.put("/api/ev/proposals/p1/decisions", json=body(proposal, entries(proposal, change))).json()["problems"] == []
        job = start(c, "freeze", {"proposal": "p1"})
        done = wait(c, job["id"])
        assert done["state"] == "done", c.get(f"/api/ev/jobs/{job['id']}/log").text
        record = json.loads((proposal / "proposal.json").read_text(encoding="utf-8"))
        assert record["decided_by"]["aditya"] == ["min_effect"] and "min_effect" not in record["decided_by"]["model"]
        assert (proposal / "protocol.yaml").is_file()
        detail = c.get("/api/ev/proposals/p1").json()
        assert detail["frozen"] and detail["protocol"]["error"] is None
        again = c.put("/api/ev/proposals/p1/decisions", json=body(proposal, entries(proposal)))
        assert again.status_code == 409 and "frozen" in again.json()["detail"]
        assert c.post("/api/ev/jobs/freeze", json={"proposal": "p1"}).status_code == 409


def test_decisions_need_cards(world: EvidenceWorld) -> None:
    flow(world.proposals / "p0", Scripted(), until="critic")
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_USER="aditya"))) as c:  # type: ignore[call-arg]
        response = c.put("/api/ev/proposals/p0/decisions", json={"decisions": [], "base_sha256": None})
        assert response.status_code == 409 and "no cards" in response.json()["detail"]
        assert c.put("/api/ev/proposals/p0/decisions", json={"decisions": []}).status_code == 422   # no base_sha256


def test_by_is_the_model_the_user_or_the_name_already_in_the_file(proposal: Path, world: EvidenceWorld) -> None:
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_USER="aditya"))) as c:  # type: ignore[call-arg]
        someone = c.put("/api/ev/proposals/p1/decisions",
                        json=body(proposal, entries(proposal, {"min_effect": {"choice": "lenient", "by": "someone"}})))
        assert someone.status_code == 400 and "someone" in someone.json()["detail"]
        # a hand edit names its author; the form sends that name back for an untouched card and it is kept
        data = yaml.safe_load((proposal / "decisions.yaml").read_text(encoding="utf-8"))
        for d in data["decisions"]:
            if d["card"] == "pairing":
                d.update(choice="order_only", reason="hand edit", by="tim")
        (proposal / "decisions.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        kept = entries(proposal, {"pairing": {"choice": "order_only", "reason": "hand edit", "by": "tim"}})
        result = c.put("/api/ev/proposals/p1/decisions", json=body(proposal, kept))
        assert result.status_code == 200 and result.json()["problems"] == []
        after = {d["card"]: d for d in yaml.safe_load((proposal / "decisions.yaml").read_text(encoding="utf-8"))["decisions"]}
        assert after["pairing"]["by"] == "tim" and after["screen"]["by"] == "model"


def test_a_file_changed_since_it_was_loaded_is_not_overwritten_unless_forced(proposal: Path, world: EvidenceWorld) -> None:
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_USER="aditya"))) as c:  # type: ignore[call-arg]
        loaded = c.get("/api/ev/proposals/p1").json()["decisions_sha256"]
        assert loaded == file_sha256(proposal / "decisions.yaml")
        (proposal / "decisions.yaml").write_text((proposal / "decisions.yaml").read_text(encoding="utf-8") + "# edited\n",
                                                 encoding="utf-8")
        stale = {"decisions": entries(proposal), "base_sha256": loaded}
        refused = c.put("/api/ev/proposals/p1/decisions", json=stale)
        assert refused.status_code == 409 and "changed since" in refused.json()["detail"]
        assert (proposal / "decisions.yaml").read_text(encoding="utf-8").endswith("# edited\n")   # untouched
        forced = c.put("/api/ev/proposals/p1/decisions", json={**stale, "force": True})
        assert forced.status_code == 200 and "# edited" not in (proposal / "decisions.yaml").read_text(encoding="utf-8")


# --- the real commands end to end: template corpus -> regex-only run -> score ---------------------------------

def test_template_corpus_regex_run_and_score_through_the_real_commands(tmp_path: Path) -> None:
    ev = tmp_path / "ev"
    with TestClient(create_app(Settings(EV=ev))) as c:  # type: ignore[call-arg]
        synth = wait(c, start(c, "synth", {"name": "ui", "seed": 5, "studies": 3, "levels": ["explicit"]})["id"])
        assert synth["state"] == "done", c.get(f"/api/ev/jobs/{synth['id']}/log").text
        assert {x["name"] for x in c.get("/api/ev/corpora").json()} == {"ui-explicit", "ui-mixed"}
        run = start(c, "run", {"corpus": "ui-explicit", "protocol": {"source": "repo", "name": "rag-factuality"},
                               "extractors": "regex-only"})
        assert wait(c, run["id"])["state"] == "done", c.get(f"/api/ev/jobs/{run['id']}/log").text
        summary = c.get("/api/ev/runs/regex-only~ui-explicit").json()
        assert summary["complete"] and summary["corpus"] == "ui-explicit" and summary["answer"]["label"]
        score = wait(c, start(c, "score", {"run": "regex-only~ui-explicit"})["id"])
        assert score["state"] == "done", c.get(f"/api/ev/jobs/{score['id']}/log").text
        report = c.get("/api/ev/scores/reports/regex-only~ui-explicit").json()
        assert report["report"]["levels"] == ["explicit"]


def test_propose_needs_exactly_one_of_question_and_text(client: TestClient) -> None:
    for bad in ({"proposal": "p9"}, {"proposal": "p9", "question": "rag-factuality", "text": "a typed question here"},
                {"proposal": "p9", "text": "short"}):
        assert client.post("/api/ev/jobs/propose", json=bad).status_code == 422


@POSIX_ONLY
def test_propose_a_typed_question(client: TestClient, world: EvidenceWorld, tmp_path: Path) -> None:
    text = "Which retriever is best on long documents?"
    job = start(client, "propose", {"proposal": "p-typed", "text": text})
    assert wait(client, job["id"])["state"] == "done"
    d = world.proposals / "p-typed"
    assert calls(tmp_path)[0] == [*TOOL, "evidence", "propose", "frame", "--question", text, "--out", str(d),
                                  "--model", "orch-model"]


def test_decisions_write_waivers_and_refuse_a_short_reason(proposal: Path, world: EvidenceWorld) -> None:
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_USER="aditya"))) as c:  # type: ignore[call-arg]
        check = next(iter(critic_module.DETERMINISTIC))
        waiver = {"check": check, "reason": "the screen is deliberately broad here"}
        ok = c.put("/api/ev/proposals/p1/decisions", json={**body(proposal, entries(proposal)), "waivers": [waiver]})
        assert ok.status_code == 200
        assert yaml.safe_load((proposal / "decisions.yaml").read_text(encoding="utf-8"))["waivers"] == [
            {**waiver, "by": "aditya"}]
        short = c.put("/api/ev/proposals/p1/decisions",
                      json={**body(proposal, entries(proposal)), "waivers": [{"check": check, "reason": "too short"}]})
        assert short.status_code == 400 and "at least 10" in short.json()["detail"]


def _kinded(world: EvidenceWorld) -> Path:
    directory = world.proposals / "kinded"
    directory.mkdir(parents=True)
    (directory / "frame.json").write_text(json.dumps({"question": "q?", "kind": "effect"}), encoding="utf-8")
    (directory / "draft.yaml").write_text("old", encoding="utf-8")
    return directory


def test_kind_change_checks_the_gateway_before_wiping(world: EvidenceWorld, fake_python: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    d = _kinded(world)
    monkeypatch.setattr(evjobs, "gateway_problem", lambda settings: "the gateway is down")
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_PYTHON=str(fake_python)))) as c:  # type: ignore[call-arg]
        response = c.put("/api/ev/proposals/kinded/kind", json={"kind": "best"})
    assert response.status_code == 409 and "gateway is down" in response.json()["detail"]
    assert (d / "draft.yaml").exists() and json.loads((d / "frame.json").read_text(encoding="utf-8"))["kind"] == "effect"


def test_kind_change_to_the_same_kind_does_nothing(client: TestClient, world: EvidenceWorld) -> None:
    d = _kinded(world)
    response = client.put("/api/ev/proposals/kinded/kind", json={"kind": "effect"})
    assert response.status_code == 409 and "already" in response.json()["detail"]
    assert (d / "draft.yaml").exists() and "kind_by" not in json.loads((d / "frame.json").read_text(encoding="utf-8"))
    assert client.put("/api/ev/proposals/kinded/kind", json={"kind": "best"}).status_code == 202
    assert not (d / "draft.yaml").exists()


def test_existing_waivers_are_shown_and_kept_on_a_plain_save(proposal: Path, world: EvidenceWorld) -> None:
    import yaml
    path = proposal / "decisions.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["waivers"] = [{"check": "metric_rules_collide", "reason": "known and harmless here", "by": "someone-else"}]
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with TestClient(create_app(Settings(EV=world.root, WEBAPP_USER="aditya"))) as c:  # type: ignore[call-arg]
        detail = c.get("/api/ev/proposals/p1").json()
        assert detail["waivers"] == data["waivers"]
        sent = body(proposal, entries(proposal))
        sent["base_sha256"] = detail["decisions_sha256"]
        sent["waivers"] = [{"check": w["check"], "reason": w["reason"]} for w in detail["waivers"]]
        assert c.put("/api/ev/proposals/p1/decisions", json=sent).status_code == 200
        assert c.get("/api/ev/proposals/p1").json()["waivers"] == data["waivers"]   # still someone-else's, not rewritten
        sent["base_sha256"] = c.get("/api/ev/proposals/p1").json()["decisions_sha256"]
        sent["waivers"] = []   # the person removed it
        assert c.put("/api/ev/proposals/p1/decisions", json=sent).status_code == 200
        assert c.get("/api/ev/proposals/p1").json()["waivers"] == []
