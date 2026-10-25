"""The write contract: what the backend answers to the app's writes (job submission, decisions), recorded from
the real backend so the frontend's mock (webapp/web/src/mocks/handlers.ts) is checked against it
(webapp/web/src/mocks/contract.test.ts) and cannot drift from it unnoticed.

A scenario is {name, method, path, body, status, response}: `SCENARIOS` hold the requests, `record` runs them in
order on one copy of the evidence world (evidence_world.build) with a job manager whose processes are fakes (a
submitted job just sits queued or running) and the model gateway taken as answering, and adds what the backend
answered. Scenario 8 proposes `p-new`; the recorder then makes p-new as the mock's `finishJob` does (the world's
frozen proposal without its protocol, decisions back to the model's defaults: `unproposed`) and ends that job,
so scenarios 9, 10 and 12 run on the same state on both sides. The backend's job ends cancelled there (it waits
queued behind scenario 3's model job), the mock's `done`: a job's end state is not compared (nor is any `state`).

    uv run python -m webapp.tests.write_contract [OUT]   # build a world in a temporary directory and record
                                                         # (default OUT: webapp/web/src/mocks/write-contract.json)
`evidence_world OUT --mocks .../ev-fixtures.json` writes it too, beside the fixtures.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path, PureWindowsPath
from typing import Any
from unittest import mock

from .evidence_world import BASE, MOCK_ROOT, NAME, REPO, EvidenceWorld

CONTRACT = REPO / "webapp" / "web" / "src" / "mocks" / "write-contract.json"
MIXED = f"{NAME}-mixed"
FROZEN = "rag-factuality"   # the world's frozen proposal
NEW = "p-new"               # the proposal scenario 8 starts
USER = "aditya"             # the server's $WEBAPP_USER
REPO_PROTOCOL = {"source": "repo", "name": "rag-factuality"}


def _decisions() -> list[dict[str, Any]]:
    """Every card of p-new decided, four of them as freeze refuses: a missing reason, a choice other than the
    default by the model, an unknown choice, custom without a value."""
    keep = [{"card": c, "choice": "draft", "reason": f"default: {c}", "by": "model"}
            for c in ("roles", "metrics", "cascade", "locate")]
    return [{"card": "screen", "choice": "draft", "reason": "  ", "by": "model"},
            *keep[:2],
            {"card": "min_effect", "choice": "strict", "reason": "noise", "by": "model"},
            {"card": "pairing", "choice": "median", "reason": "the median pairs best", "by": USER},
            {"card": "label", "choice": "custom", "value": None, "reason": "my own rows", "by": USER},
            *keep[2:]]


SCENARIOS: list[dict[str, Any]] = [
    {"name": "synth with a new name", "method": "POST", "path": "/api/ev/jobs/synth",
     "body": {"name": "contract-set", "studies": 4, "levels": ["explicit"]}},
    {"name": "synth reusing the world's corpus set name", "method": "POST", "path": "/api/ev/jobs/synth",
     "body": {"name": NAME, "studies": 4, "levels": ["explicit", "paraphrased"]}},
    {"name": "run cascade on the mixed corpus with a new name", "method": "POST", "path": "/api/ev/jobs/run",
     "body": {"corpus": MIXED, "protocol": REPO_PROTOCOL, "extractors": "cascade", "strategy": "all",
              "name": "contract-run"}},
    {"name": "run on an existing run name", "method": "POST", "path": "/api/ev/jobs/run",
     "body": {"corpus": MIXED, "protocol": REPO_PROTOCOL, "extractors": "cascade", "strategy": "all"}},
    {"name": "run on an unknown corpus", "method": "POST", "path": "/api/ev/jobs/run",
     "body": {"corpus": "no-such-corpus", "protocol": REPO_PROTOCOL}},
    {"name": "rag-baseline on a corpus that has an answer", "method": "POST", "path": "/api/ev/jobs/rag-baseline",
     "body": {"corpus": MIXED, "question": "rag-factuality"}},
    {"name": "propose on the frozen proposal", "method": "POST", "path": "/api/ev/jobs/propose",
     "body": {"proposal": FROZEN, "question": "rag-factuality"}},
    {"name": "propose with a new name", "method": "POST", "path": "/api/ev/jobs/propose",
     "body": {"proposal": NEW, "question": "rag-factuality"}},
    {"name": "decisions with four problems", "method": "PUT", "path": f"/api/ev/proposals/{NEW}/decisions",
     "body": {"decisions": _decisions(), "base_sha256": None, "force": True}},
    {"name": "freeze a proposal with problems", "method": "POST", "path": "/api/ev/jobs/freeze",
     "body": {"proposal": NEW}},
    {"name": "run on the frozen proposal's protocol with a new name", "method": "POST", "path": "/api/ev/jobs/run",
     "body": {"corpus": MIXED, "protocol": {"source": "proposal", "name": FROZEN}, "extractors": "cascade",
              "strategy": "gaps", "name": "contract-proposal-run"}},
    {"name": "propose again on a proposal that has its cards", "method": "POST", "path": "/api/ev/jobs/propose",
     "body": {"proposal": NEW, "question": "rag-factuality"}},
]


def unproposed(world: EvidenceWorld, name: str) -> Path:
    """`name` as a finished proposal job leaves it, made from the world's frozen proposal as the mock's
    `unfrozenProposal` does: no protocol (nor its revisions, amendments or proposal.json), decisions.yaml back to
    the model's defaults as `evidence propose cards` writes them."""
    from evidence.propose.cards import HEADER, MODEL
    from evidence.propose.common import dump_yaml

    source, target = world.proposals / FROZEN, world.proposals / name
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("protocol*.yaml", "proposal.json", "amendments.jsonl"))
    cards = json.loads((target / "cards.json").read_text(encoding="utf-8"))["cards"]
    entries = [{"card": c["id"], "choice": c["default"], "reason": f"default: {c['rationale']}".strip(), "by": MODEL}
               for c in cards]
    (target / "decisions.yaml").write_text(HEADER + dump_yaml({"decisions": entries}), encoding="utf-8", newline="\n")
    return target


def _path_like(value: str) -> bool:
    return value.startswith("/") or PureWindowsPath(value).is_absolute()


def normalise(response: Any, root: Path) -> Any:
    """A response as both sides can give it: a job's id, every `*_at`, pid, pid_start, its steps' command and
    the paths in their argv and needs as "*"; the world's directory as MOCK_ROOT."""
    if isinstance(response, list):
        return [normalise(r, root) for r in response]
    if not isinstance(response, dict):
        if isinstance(response, str) and _path_like(response):
            try:   # a path in the world (DecisionsResult.written), as the mock writes it
                return f"{MOCK_ROOT}/{Path(response).resolve().relative_to(root.resolve()).as_posix()}"
            except ValueError:
                return response
        return response
    out: dict[str, Any] = {}
    for key, value in response.items():
        if key.endswith("_at") or key in ("pid", "pid_start", "command") or (key == "id" and "steps" in response):
            out[key] = "*"
        elif key in ("argv", "needs") and isinstance(value, list):
            out[key] = ["*" if isinstance(a, str) and _path_like(a) else a for a in value]
        else:
            out[key] = normalise(value, root)
    return out


def record(world: EvidenceWorld) -> list[dict[str, Any]]:
    """The scenarios run in order on `world` (changed: take a copy), each with the backend's status and its
    normalised response."""
    from fastapi.testclient import TestClient

    from webapp import evjobs
    from webapp.app import create_app
    from webapp.settings import Settings

    from .fakes import FakeProcesses

    app = create_app(Settings(EV=world.root, WEBAPP_USER=USER, agent_root=None))  # type: ignore[arg-type]
    app.state.services.jobs.processes = FakeProcesses()   # no subprocess: a job just sits queued or running
    recorded = []
    with mock.patch.object(evjobs, "gateway_problem", lambda settings: None), \
            TestClient(app, base_url=BASE) as client:
        for scenario in SCENARIOS:
            response = client.request(scenario["method"], scenario["path"], json=scenario["body"])
            recorded.append({**scenario, "status": response.status_code,
                             "response": normalise(response.json(), world.root)})
            if scenario["path"] == "/api/ev/jobs/propose" and response.status_code == 202:
                unproposed(world, scenario["body"]["proposal"])
                _end(client, response.json()["id"])
    return recorded


def _end(client: Any, job_id: str) -> None:
    """End a job whose processes are fakes (cancel: a queued one ends at once, a running one's fake process
    ends on SIGTERM), so its proposal is free for the next scenario."""
    client.post(f"/api/ev/jobs/{job_id}/cancel", headers={"X-Requested-With": "write-contract"})
    for _ in range(200):
        if client.get(f"/api/ev/jobs/{job_id}").json()["state"] not in ("queued", "running"):
            return
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not end")


def dumps(recorded: list[dict[str, Any]]) -> str:
    return json.dumps(recorded, ensure_ascii=False, indent=1) + "\n"


def write(world: EvidenceWorld, out: Path = CONTRACT) -> Path:
    """Record on a copy of `world` (the world itself stays as built) and write `out`."""
    with tempfile.TemporaryDirectory() as tmp:
        recorded = record(world.copy(Path(tmp) / "world"))
    out.write_text(dumps(recorded), encoding="utf-8", newline="\n")
    return out


if __name__ == "__main__":
    from .evidence_world import build

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else CONTRACT
    with tempfile.TemporaryDirectory() as tmp:
        print(write(build(Path(tmp) / "world"), target))
