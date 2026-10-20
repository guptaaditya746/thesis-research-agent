"""The job plans (webapp/evjobs.py): what each job kind would start, as data: its steps, refs, lane and whether
it needs the gateway. No HTTP (but for the run-group endpoint) and no subprocess: the job manager runs on fakes."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evidence.propose.common import CRITIC, DRAFT, FRAME
from webapp.app import create_app
from webapp.evfiles import EvidenceFiles
from webapp.evjobs import Commands, run_group
from webapp.evmodels import (
    ProposeRequest,
    ProtocolRef,
    RunRequest,
    ScoreRequest,
    SynthRequest,
)
from webapp.evquestions import Questions
from webapp.jobs import JobManager
from webapp.settings import Settings

from .evidence_world import NAME, EvidenceWorld
from .fakes import FakeProcesses

MIXED, EXPLICIT = f"{NAME}-mixed", f"{NAME}-explicit"


def repo(name: str) -> ProtocolRef:
    return ProtocolRef(source="repo", name=name)


@pytest.fixture
def world(ev_world: EvidenceWorld, tmp_path: Path) -> EvidenceWorld:
    return ev_world.copy(tmp_path / "world")


@pytest.fixture
def settings(world: EvidenceWorld) -> Settings:
    return Settings(EV=world.root, WEBAPP_USER="aditya", agent_root=None)  # type: ignore[call-arg]


@pytest.fixture
def commands(settings: Settings) -> Commands:
    return Commands(settings, EvidenceFiles(settings), JobManager(settings, processes=FakeProcesses()),
                    Questions(settings))


@pytest.mark.parametrize(("protocol", "extractors", "strategy", "group"), [
    (repo("rag-factuality"), "regex-only", "all", "regex-only"),
    (repo("rag-factuality-agentic"), "regex-only", "all", "regex-only"),
    (repo("rag-factuality"), "cascade", "all", "cascade"),
    (repo("rag-factuality"), "cascade", "gaps", "cascade-gaps"),
    (repo("rag-factuality-agentic"), "cascade", "gaps", "agentic-gaps"),
    (ProtocolRef(source="proposal", name="p1"), "cascade", "gaps", "proposal-p1-cascade-gaps"),
    (repo("other"), "regex-only", "gaps", "other-regex-only"),
])
def test_run_group_table(protocol: ProtocolRef, extractors: str, strategy: str, group: str) -> None:
    assert run_group(protocol, extractors, strategy) == group


def test_run_plan_argv(commands: Commands, world: EvidenceWorld, settings: Settings) -> None:
    plan = commands.run(RunRequest(corpus=MIXED, protocol=repo("rag-factuality"), name="fresh"))
    assert plan.kind == "run" and len(plan.steps) == 1
    assert plan.steps[0].argv[3:] == [
        "evidence", "run", "--protocol", str(settings.protocols / "rag-factuality.yaml"),
        "--corpus", str(world.corpora / MIXED), "--out", str(world.runs / "cascade"),
        "--cache", str(settings.ev_cache_dir), "--extractors", "cascade", "--strategy", "all",
        "--model", "orch-model", "--run-id", "fresh"]
    assert plan.refs == {"run": "cascade~fresh", "corpus": MIXED}
    assert plan.lane == "model" and plan.needs_gateway


def test_regex_only_run_is_cpu_without_gateway(commands: Commands) -> None:
    plan = commands.run(RunRequest(corpus=MIXED, protocol=repo("rag-factuality"), extractors="regex-only", name="fresh"))
    assert plan.lane == "cpu" and not plan.needs_gateway
    assert plan.refs["run"] == "regex-only~fresh"


def test_score_plan_takes_latest_reexec_and_both_baselines(commands: Commands, world: EvidenceWorld) -> None:
    run = world.runs / "cascade-gaps" / MIXED
    for stamp in ("20260101T000000", "20260102T000000"):
        again = run.parent / f"{MIXED}-reexec-{stamp}"
        again.mkdir()
        (again / "reexec.json").write_text("{}", encoding="utf-8")
    for system in ("rag-baseline", "agent-baseline"):
        answer = world.runs / system / MIXED / "answer.json"
        answer.parent.mkdir(parents=True, exist_ok=True)
        if not answer.exists():
            answer.write_text("{}", encoding="utf-8")
    plan = commands.score(ScoreRequest(run=f"cascade-gaps~{MIXED}"))
    argv = plan.steps[0].argv
    assert argv[3:6] == ["evaluate", "score", "--run"]
    assert argv.count("--baseline") == 2
    assert [argv[i + 1] for i, a in enumerate(argv) if a == "--baseline"] == [
        str(world.runs / "rag-baseline" / MIXED / "answer.json"),
        str(world.runs / "agent-baseline" / MIXED / "answer.json")]
    assert argv[argv.index("--reexec") + 1] == str(run.parent / f"{MIXED}-reexec-20260102T000000" / "reexec.json")
    assert plan.refs == {"score": f"cascade-gaps~{MIXED}"}
    assert plan.lane == "cpu" and not plan.needs_gateway


def test_propose_plan_resumes_after_existing_frame(commands: Commands, world: EvidenceWorld, settings: Settings) -> None:
    question = Questions(settings).list()[0]
    directory = world.root / "proposals" / "fresh"
    directory.mkdir(parents=True)
    (directory / FRAME).write_text(json.dumps({"question": question.question}), encoding="utf-8")
    plan = commands.propose(ProposeRequest(question=question.id, proposal="fresh"))
    assert [s.name for s in plan.steps] == ["propose draft", "propose critic", "propose cards"]
    assert [s.needs for s in plan.steps] == [[str(directory / FRAME)], [str(directory / DRAFT)],
                                             [str(directory / CRITIC)]]
    assert plan.steps[-1].argv[3:6] == ["evidence", "propose", "cards"]
    assert plan.refs == {"proposal": "fresh"} and plan.lane == "model" and plan.needs_gateway


def test_synth_plan_refs(commands: Commands) -> None:
    n = "fresh-set"
    plan = commands.synth(SynthRequest(name=n))
    assert plan.refs == {"corpus_set": n, "corpus": f"{n}-mixed"}
    assert plan.lane == "cpu" and not plan.needs_gateway


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c


def test_get_run_group_endpoint(client: TestClient) -> None:
    response = client.get("/api/ev/run-group", params={"source": "repo", "name": "rag-factuality-agentic",
                                                       "extractors": "cascade", "strategy": "gaps"})
    assert response.status_code == 200
    assert response.json() == {"group": "agentic-gaps"}
