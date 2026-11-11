"""The job plans (webapp/evjobs.py): what each job kind would start, as data: its steps, refs, lane and whether
it needs the gateway. No HTTP (but for the run-group endpoint) and no subprocess: the job manager runs on fakes."""
from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from evidence.propose.common import CRITIC, DRAFT, FRAME
from webapp.app import create_app
from webapp.evfiles import EvidenceFiles
from webapp.evjobs import Commands, run_group
from webapp.evmodels import (
    AgentBaselineRequest,
    FetchRequest,
    KindRequest,
    ProposeRequest,
    ProtocolRef,
    RagBaselineRequest,
    RunRequest,
    ScoreRequest,
    SynthRequest,
)
from webapp.evquestions import Questions
from webapp.files import Conflict, NotFound
from webapp.jobs import JobManager
from webapp.settings import Settings

from .evidence_world import BASE, NAME, EvidenceWorld
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
    plan = commands.run(RunRequest(corpus=MIXED, protocol=repo("rag-factuality"), strategy="all", name="fresh"))
    assert plan.kind == "run" and len(plan.steps) == 1
    assert plan.steps[0].argv[3:] == [
        "evidence", "run", "--protocol", str(settings.protocols / "rag-factuality.yaml"),
        "--corpus", str(world.corpora / MIXED), "--out", str(world.runs / "cascade"),
        "--cache", str(settings.ev_cache_dir), "--extractors", "cascade", "--strategy", "all",
        "--model", "orch-model", "--run-id", "fresh", "--allow-failed-calls"]
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
    factuality = next(q for q in Questions(commands.s).list() if q.id == "rag-factuality")
    for system in ("rag-baseline", "agent-baseline"):
        answer = world.runs / system / MIXED / "answer.json"
        answer.parent.mkdir(parents=True, exist_ok=True)
        if not answer.exists():
            answer.write_text(json.dumps({"question": factuality.question}), encoding="utf-8")
    plan = commands.score(ScoreRequest(run=f"cascade-gaps~{MIXED}"))
    argv = plan.steps[0].argv
    assert argv[3:6] == ["evaluate", "score", "--run"]
    assert argv[argv.index("--question-id") + 1] == "rag-factuality"
    assert argv.count("--baseline") == 2
    assert [argv[i + 1] for i, a in enumerate(argv) if a == "--baseline"] == [
        str(world.runs / "rag-baseline" / MIXED / "answer.json"),
        str(world.runs / "agent-baseline" / MIXED / "answer.json")]
    assert argv[argv.index("--reexec") + 1] == str(run.parent / f"{MIXED}-reexec-20260102T000000" / "reexec.json")
    assert plan.refs == {"score": f"cascade-gaps~{MIXED}"}
    assert plan.lane == "cpu" and not plan.needs_gateway


def _engine_run(world: EvidenceWorld, group: str, protocol: Path) -> str:
    """A copy of the world's regex-only run on the mixed corpus whose frozen protocol is `protocol`."""
    import shutil
    run = world.runs / group / MIXED
    shutil.copytree(world.runs / "regex-only" / MIXED, run)
    (run / "protocol.yaml").write_bytes(protocol.read_bytes())
    return f"{group}~{MIXED}"


def test_score_plan_scores_the_runs_question_with_its_baselines_only(commands: Commands, world: EvidenceWorld,
                                                                     settings: Settings) -> None:
    run = _engine_run(world, "rag-hallucination-regex-only", settings.protocols / "rag-hallucination.yaml")
    for name, qid in ((MIXED, "rag-factuality"), (f"{MIXED}.rag-hallucination", "rag-hallucination"),
                      (f"{MIXED}.inv-metrics", "inv-metrics")):
        path = world.runs / "rag-baseline" / name / "answer.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"system": "rag-baseline", "question_id": qid}), encoding="utf-8")
    argv = commands.score(ScoreRequest(run=run)).steps[0].argv
    assert argv[argv.index("--question-id") + 1] == "rag-hallucination"
    assert [argv[i + 1] for i, a in enumerate(argv) if a == "--baseline"] == [
        str(world.runs / "rag-baseline" / f"{MIXED}.rag-hallucination" / "answer.json")]


def test_score_plan_refuses_a_run_of_no_listed_question(commands: Commands, world: EvidenceWorld,
                                                        settings: Settings, tmp_path: Path) -> None:
    typed = tmp_path / "typed.yaml"
    text = (settings.protocols / "rag-factuality.yaml").read_text(encoding="utf-8")
    question = next(q for q in Questions(settings).list() if q.id == "rag-factuality").question
    typed.write_text(text.replace(question, "Does anything help at all?"), encoding="utf-8")
    run = _engine_run(world, "proposal-typed-regex-only", typed)
    with pytest.raises(Conflict, match="answers none of the listed questions") as refused:
        commands.score(ScoreRequest(run=run))
    message = str(refused.value)   # advice a web user can follow, not the command line's
    assert "Does anything help at all?" in message and "listed questions" in message
    assert "--question-id" not in message and "evaluate score" not in message


def test_baseline_plans_answer_the_question_asked(commands: Commands, world: EvidenceWorld) -> None:
    corpus = f"{NAME}-paraphrased"
    rag = commands.rag_baseline(RagBaselineRequest(corpus=corpus, question="inv-metrics"))
    argv = rag.steps[0].argv
    assert argv[argv.index("--question-id") + 1] == "inv-metrics"
    assert argv[argv.index("--out") + 1] == str(world.runs / "rag-baseline" / f"{corpus}.inv-metrics")
    assert rag.refs == {"run": f"rag-baseline~{corpus}.inv-metrics", "corpus": corpus}
    agent = commands.agent_baseline(AgentBaselineRequest(corpus=corpus, question="rag-factuality"))
    argv = agent.steps[0].argv
    assert argv[argv.index("--out") + 1] == str(world.runs / "agent-baseline" / corpus)   # the runbook's layout
    assert argv[argv.index("--run-id") + 1] == corpus and argv[argv.index("--question-id") + 1] == "rag-factuality"
    with pytest.raises(NotFound, match="no such question"):
        commands.rag_baseline(RagBaselineRequest(corpus=corpus, question="no-such-question"))


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


def test_kind_plan_redrafts_from_the_new_kind(commands: Commands, world: EvidenceWorld) -> None:
    directory = world.root / "proposals" / "kinded"
    directory.mkdir(parents=True)
    (directory / FRAME).write_text(json.dumps({"question": "q?", "kind": "effect"}), encoding="utf-8")
    for name in (DRAFT, CRITIC, "cards.json", "decisions.yaml", "draft.sources.json"):
        (directory / name).write_text("old", encoding="utf-8")
    plan = commands.set_kind("kinded", KindRequest(kind="best"))
    frame = json.loads((directory / FRAME).read_text(encoding="utf-8"))
    assert (frame["kind"], frame["kind_by"]) == ("best", "user")
    assert not any((directory / n).exists() for n in (DRAFT, CRITIC, "cards.json", "decisions.yaml", "draft.sources.json"))
    assert [s.name for s in plan.steps] == ["propose draft", "propose critic", "propose cards"]
    assert plan.refs == {"proposal": "kinded"} and plan.lane == "model" and plan.needs_gateway


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


def test_a_run_request_defaults_to_gaps() -> None:
    assert RunRequest(corpus="c", protocol=ProtocolRef(source="repo", name="rag-factuality")).strategy == "gaps"


# --- evidence fetch: real papers from arXiv, a demonstration corpus with no ground truth ---------------------

def _demo(world: EvidenceWorld, corpus: str = MIXED) -> None:
    """`corpus` as `evidence fetch` marks one: source.json with ground_truth false."""
    (world.corpora / corpus / "source.json").write_text(json.dumps(
        {"kind": "arxiv", "query": "retrieval augmented", "category": "cs.CL", "fetched": "2026-10-28T09:00:00+00:00",
         "ground_truth": False, "papers": 3, "skipped": [{"id": "x", "reason": "HTTPStatusError: 404"}]}),
        encoding="utf-8")


def test_fetch_plan_names_the_corpus_after_the_query_and_the_day(commands: Commands, world: EvidenceWorld) -> None:
    day = datetime(2026, 10, 28, tzinfo=timezone.utc)
    request = FetchRequest(query="Retrieval-Augmented Generation & factuality!", max_papers=5, category="cs.CL")
    plan = commands.fetch(request, today=day)
    name = "arxiv-retrieval-augmented-generation-20261028"   # the slug stops before 40 characters
    assert plan.kind == "fetch" and plan.refs == {"corpus": name}
    assert plan.lane == "cpu" and not plan.needs_gateway
    argv = plan.steps[0].argv
    assert argv[3:5] == ["evidence", "fetch"]
    assert "--query=Retrieval-Augmented Generation & factuality!" in argv   # one argv item, never a flag
    assert argv[argv.index("--max") + 1] == "5" and argv[argv.index("--category") + 1] == "cs.CL"
    assert argv[argv.index("--out") + 1] == str(world.corpora / name)
    (world.corpora / name).mkdir()
    assert commands.fetch(request, today=day).refs == {"corpus": f"{name}-2"}   # the day's name is taken
    with pytest.raises(Conflict, match="exists"):
        commands.fetch(FetchRequest(query="retrieval", name=MIXED))


def test_fetch_request_refuses_a_bad_category_and_a_query_without_words() -> None:
    for bad in ({"query": "retrieval", "category": "cs.CL --out /tmp"}, {"query": "?!?"}, {"query": "a\nb c"},
                {"query": "retrieval", "max_papers": 51}):
        with pytest.raises(ValidationError):
            FetchRequest.model_validate(bad)


def test_a_fetched_corpus_is_listed_without_ground_truth(world: EvidenceWorld, settings: Settings) -> None:
    _demo(world)
    listed = {c.name: c for c in EvidenceFiles(settings).corpora()}
    assert listed[MIXED].ground_truth is False
    assert listed[MIXED].source is not None and listed[MIXED].source.kind == "arxiv"
    assert listed[MIXED].source.query == "retrieval augmented"
    assert all(c.ground_truth and c.source is None for n, c in listed.items() if n != MIXED)


def test_score_refuses_a_run_on_a_demonstration_corpus(commands: Commands, world: EvidenceWorld) -> None:
    _demo(world)
    with pytest.raises(Conflict, match="is not scored here: real papers") as refused:
        commands.score(ScoreRequest(run=f"cascade-gaps~{MIXED}"))
    message = str(refused.value)
    assert MIXED in message and "arxiv" in message and "graph, answer and trace stay open" in message


def test_a_real_dataset_without_ground_truth_json_is_not_scored_here(commands: Commands, world: EvidenceWorld,
                                                                     settings: Settings) -> None:
    (world.corpora / MIXED / "ground_truth.json").unlink()   # as a SciREX corpus: its gold is scirex_gold.json
    assert {c.name: c for c in EvidenceFiles(settings).corpora()}[MIXED].ground_truth is False
    with pytest.raises(Conflict, match="evaluate wholerun"):
        commands.score(ScoreRequest(run=f"cascade-gaps~{MIXED}"))


def test_post_fetch_starts_a_job(settings: Settings) -> None:
    app = create_app(settings)
    app.state.services.jobs.processes = FakeProcesses()   # no subprocess, so no network
    with TestClient(app, base_url=BASE) as client:
        response = client.post("/api/ev/jobs/fetch", json={"query": "retrieval augmented", "max_papers": 3,
                                                            "name": "arxiv-demo"})
        assert response.status_code == 202, response.text
        job = response.json()
        assert job["kind"] == "fetch" and job["refs"] == {"corpus": "arxiv-demo"} and job["lane"] == "cpu"
        again = client.post("/api/ev/jobs/fetch", json={"query": "retrieval augmented", "name": "arxiv-demo"})
        assert again.status_code == 409 and "arxiv-demo" in again.json()["detail"]   # the first job writes it
