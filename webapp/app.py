"""The FastAPI backend (docs/e2e-build-plan.md, "Backend API"): `webapp.app:create_app()`.

JSON under /api, server-sent events for the live run stream and the job logs, the chat as an AI
SDK UI-message stream, and the built frontend (webapp/web/dist) at / with every other path
falling back to index.html (client-side routes), when that directory exists.

The server reads run directories, the corpus, concept sessions, gold files and reports; it writes
only job state and logs ($RUNS/.jobs/) and concept picks ($CONCEPTS, through agent/concept_step.py),
and the jobs it starts write what their commands write. One GET can cause a write elsewhere: a
claim walk with `?judge=true` asks the judge, which appends its verdicts to $GOLD/judge-cache.jsonl.
It has no authentication: it binds to 127.0.0.1 and is reached through an SSH tunnel
(webapp/README.md). Request paths are checked against their roots (webapp/files.py); SPARQL is
read-only (scoring/store.py).
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from sse_starlette import EventSourceResponse

from agent.canonical import file_sha256

from . import chat, commands, goldstate, judge
from .corpus import Corpus
from .files import ID, BadRequest, Conflict, NotFound, check_id, inside, read_json
from .jobs import JobManager
from .models import (AnswerKey, AppConfig, Claim, FactWalk, GoldEntry, Health, Job, KnowledgeGraph, Passage,
                     PickRequest, ProposeRequest, Question, QuestionDetail, QueryResult, Results, RunDetail,
                     RunRequest, RunSummary, Score, SparqlRequest, SparqlResult, Step)
from .provenance import Provenance
from .questions import Questions
from .runs import Runs
from .settings import Settings, llm_key_set

SSE = {200: {"content": {"text/event-stream": {}}, "description": "server-sent events"}}


def app_version() -> str:
    try:
        return version("thesis-agent")
    except PackageNotFoundError:
        return "0"


@dataclass
class Services:
    """Everything the routes and the chat tools read through; one per app."""

    settings: Settings
    chat_model: Any = None  # tests put a pydantic-ai FunctionModel here
    judge: Callable[..., Any] | None = None  # support(fact, quote, *, context); default gold.judge.support
    corpus: Corpus = field(init=False)
    jobs: JobManager = field(init=False)
    runs: Runs = field(init=False)
    questions: Questions = field(init=False)
    provenance: Provenance = field(init=False)
    agent: Any = field(init=False)  # the chat agent (webapp/chat.py)

    def __post_init__(self) -> None:
        self.corpus = Corpus(self.settings.corpus)
        self.jobs = JobManager(self.settings)
        self.runs = Runs(self.settings, self.corpus, job_steps=self.jobs.run_steps)
        self.questions = Questions(self.settings, self.runs.index,
                                   gold_building=lambda qid: bool(self.jobs.active("gold", qid=qid)))
        self.provenance = Provenance(self.runs)
        self.agent = chat.build_agent()

    def judge_support(self) -> Callable[..., Any] | None:
        return self.judge if self.judge is not None else judge.default_support()

    def reports(self) -> list[Path]:
        """report.json files: $RUNS/report/, then each batch root's report/, newest first."""
        root = self.settings.runs
        nested = [p / "report" / "report.json" for p in (sorted(root.iterdir()) if root.is_dir() else [])
                  if p.is_dir() and ID.fullmatch(p.name) and (p / "report" / "report.json").is_file()]
        nested.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        top = self.settings.report_dir / "report.json"
        return ([top] if top.is_file() else []) + nested

    def results(self, batch: str | None = None) -> dict[str, Any]:
        """`score report`'s report.json: of the batch root $RUNS/<batch>/, or $RUNS's own, else the newest."""
        if batch is not None:
            found = [inside(self.settings.runs, check_id(batch, "batch"), "report", "report.json")]
        else:
            found = self.reports()
        data = read_json(found[0]) if found else None
        if not isinstance(data, dict):
            raise NotFound("no results report yet (`score report` writes <runs root>/report/report.json)")
        return data


def create_app(settings: Settings | None = None, *, chat_model: Any = None,
               judge: Callable[..., Any] | None = None) -> FastAPI:
    services = Services(settings or Settings(), chat_model=chat_model, judge=judge)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        services.jobs.load()
        yield
        await services.jobs.shutdown()

    app = FastAPI(title="Thesis research agent", version=app_version(), lifespan=lifespan,
                  description="Runs, provenance, gold standard and scores of the research agent "
                              "(docs/e2e-build-plan.md, Backend API).")
    app.state.services = services
    for exc_type, status in ((NotFound, 404), (Conflict, 409), (BadRequest, 400)):
        app.add_exception_handler(exc_type, _handler(status))
    app.include_router(api_router(services), prefix="/api")
    if services.settings.web_dist.is_dir():
        add_frontend(app, services.settings)
    return app


def _handler(status: int):
    async def handle(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=status)
    return handle


def api_router(services: Services) -> APIRouter:  # noqa: C901 (one route per endpoint of the plan)
    s = services.settings
    # Operation ids are the function names, so generated clients get readable names.
    api = APIRouter(generate_unique_id_function=lambda route: route.name)

    # --- app ---------------------------------------------------------------------------------------

    @api.get("/health", response_model=Health, tags=["app"])
    def health() -> Health:
        return Health(ok=True, version=app_version())

    @api.get("/config", response_model=AppConfig, tags=["app"])
    def config() -> AppConfig:
        return AppConfig(corpus=str(s.corpus) if s.corpus else None, runs_root=str(s.runs), gold_root=str(s.gold),
                         concepts_root=str(s.concepts), llm_base_url=s.litellm_base_url, llm_key_set=llm_key_set(),
                         argilla_url=s.argilla_api_url)

    # --- questions and concepts ------------------------------------------------------------------------

    @api.get("/questions", response_model=list[Question], tags=["questions"])
    def questions() -> list[Question]:
        return services.questions.list()

    @api.get("/questions/{qid}", response_model=QuestionDetail, tags=["questions"])
    def question(qid: str) -> QuestionDetail:
        return services.questions.detail(qid)

    @api.post("/questions/{qid}/concepts/propose", response_model=Job, status_code=202, tags=["questions"])
    async def propose(qid: str, request: ProposeRequest) -> Job:
        q = services.questions.find(qid)
        if services.jobs.active("concepts", qid=qid):
            raise Conflict(f"a concept proposal for {qid} is already queued or running")
        if (services.questions.session(qid) / "proposal.json").exists():
            raise Conflict(f"{qid} already has proposed briefs; pick one")
        steps = commands.propose_steps(s, qid, str(q.get("question", "")), request)
        return services.jobs.submit("concepts", {"qid": qid, **request.model_dump()}, steps, qid=qid)

    @api.post("/questions/{qid}/concepts/pick", response_model=QuestionDetail, tags=["questions"])
    def pick(qid: str, request: PickRequest) -> QuestionDetail:
        return services.questions.pick(qid, request)

    # --- runs ------------------------------------------------------------------------------------------

    @api.get("/runs", response_model=list[RunSummary], tags=["runs"])
    def runs(qid: str | None = Query(None, description="the question's runs on its current concept"),
             condition: str | None = None,
             verify: bool = Query(False, description="run `agent verify` on runs not checked yet (slow)"),
             include_stale: bool = Query(False, description="with qid: also runs on a replaced concept")
             ) -> list[RunSummary]:
        return services.runs.summaries(qid=qid, condition=condition, verify=verify, include_stale=include_stale)

    @api.post("/runs", response_model=Job, status_code=202, tags=["runs"])
    async def start_run(request: RunRequest) -> Job:
        concept, prefix = commands.concept_for(s, request)
        live = services.runs.live_elsewhere()
        if live and not request.force:
            raise Conflict(f"{len(live)} run(s) the web app did not start are live ({', '.join(live[:3])}"
                           f"{', ...' if len(live) > 3 else ''}): a batch shares the orchestrator; set force to "
                           "start anyway")
        sha = file_sha256(concept)
        qid = next((q for q, current in services.runs.concept_index().current.items() if current == sha), None)
        name = commands.new_run_name(s, prefix, request)
        steps = commands.run_steps(s, concept, name, request, qid)
        return services.jobs.submit("run", request.model_dump(), steps, run_id=commands.run_id_of(name),
                                    qid=request.qid or qid)

    @api.get("/runs/{run_id}", response_model=RunDetail, tags=["runs"])
    def run(run_id: str) -> RunDetail:
        return services.runs.detail(run_id)

    @api.get("/runs/{run_id}/steps", response_model=list[Step], tags=["runs"])
    def steps(run_id: str) -> list[Step]:
        return services.runs.steps(run_id)

    @api.get("/runs/{run_id}/steps/{step}/output", response_class=PlainTextResponse, tags=["runs"],
             responses={200: {"content": {"text/plain": {}}, "description": "the command's full output"}})
    def step_output(run_id: str, step: int, agent_id: str | None = None) -> FileResponse:
        path = services.runs.output_file(run_id, step, agent_id)
        return FileResponse(path, media_type="text/plain; charset=utf-8")

    @api.get("/runs/{run_id}/stream", response_class=EventSourceResponse, responses=SSE, tags=["runs"])
    async def stream(run_id: str, request: Request) -> EventSourceResponse:
        services.runs.exists_or_pending(run_id)  # 404 before the stream starts
        after = request.headers.get("last-event-id", "0")
        return EventSourceResponse(services.runs.stream(run_id, int(after) if after.isdigit() else 0))

    @api.get("/runs/{run_id}/claims", response_model=list[Claim], tags=["runs"])
    def claims(run_id: str) -> list[Claim]:
        return services.runs.claims(run_id)

    @api.get("/runs/{run_id}/graph", response_model=KnowledgeGraph, tags=["runs"])
    def graph(run_id: str) -> Any:
        return services.runs.graph(run_id)

    @api.get("/runs/{run_id}/facts/{fact_id}/walk", response_model=FactWalk, tags=["runs"])
    async def walk(run_id: str, fact_id: str,
                   judge_live: bool = Query(False, alias="judge",
                                            description="also ask the judge (gold/judge.py, a model call per quote "
                                                        "it has not cached) about quotes score.json has no "
                                                        "verdict for")) -> FactWalk:
        result = services.runs.walk(run_id, fact_id)
        if judge_live:
            await judge.add_live(result, services.judge_support(), s.corpus)
        return result

    @api.get("/runs/{run_id}/score", response_model=Score, tags=["runs"])
    def score(run_id: str) -> Any:
        return services.runs.score(run_id)

    # --- corpus --------------------------------------------------------------------------------------

    @api.get("/corpus/{paper_id}", response_model=Passage, tags=["corpus"])
    def corpus(paper_id: str, start: int | None = Query(None, ge=0), end: int | None = Query(None, ge=0),
               context: int = Query(1500, ge=0, le=20_000)) -> Passage:
        try:
            return services.corpus.passage(paper_id, start, end, context)
        except ValueError as exc:
            raise BadRequest(str(exc)) from exc

    # --- gold and results ----------------------------------------------------------------------------

    @api.get("/gold", response_model=list[GoldEntry], tags=["gold"])
    def gold() -> list[GoldEntry]:
        """The questions, then any other question directory in $GOLD (a plain id holding gold files)."""
        qids = list(dict.fromkeys([q["id"] for q in services.questions.load()] + goldstate.qids(s.gold)))
        return [goldstate.entry(s.gold, qid, bool(services.jobs.active("gold", qid=qid))) for qid in qids]

    @api.get("/gold/{qid}/key", response_model=AnswerKey, tags=["gold"])
    def gold_key(qid: str) -> Any:
        return goldstate.key(s.gold, qid)

    @api.post("/gold/{qid}/build", response_model=Job, status_code=202, tags=["gold"])
    async def gold_build(qid: str) -> Job:
        services.questions.find(qid)
        if services.jobs.active("gold", qid=qid):
            raise Conflict(f"a gold build for {qid} is already queued or running")
        return services.jobs.submit("gold", {"qid": qid}, commands.gold_steps(s, qid), qid=qid)

    @api.get("/results", response_model=Results, tags=["results"])
    def results(batch: str | None = Query(None, description="the batch root ($RUNS/<batch>) whose report to show; "
                                                            "default $RUNS/report, else the newest batch's")) -> Any:
        return services.results(batch)

    # --- provenance ----------------------------------------------------------------------------------

    @api.post("/sparql", response_model=SparqlResult, tags=["provenance"])
    def sparql(request: SparqlRequest) -> SparqlResult:
        return services.provenance.sparql(request.query, request.run_id)

    @api.get("/queries/{n}", response_model=QueryResult, tags=["provenance"])
    def provenance_query(n: int, run_id: str, edge: str | None = None, fact: str | None = None,
                         claim: str | None = None, step: int | None = None, agent: str | None = None) -> QueryResult:
        return services.provenance.query(services.runs.run(run_id), n, edge=edge, fact=fact, claim=claim, step=step,
                                         agent=agent, corpus=s.corpus)

    # --- jobs ----------------------------------------------------------------------------------------

    @api.get("/jobs", response_model=list[Job], tags=["jobs"])
    def jobs() -> list[Job]:
        return services.jobs.list()

    @api.get("/jobs/{job_id}", response_model=Job, tags=["jobs"])
    def job(job_id: str) -> Job:
        return services.jobs.get(job_id)

    @api.get("/jobs/{job_id}/log", response_class=EventSourceResponse, responses=SSE, tags=["jobs"])
    async def job_log(job_id: str, request: Request) -> EventSourceResponse:
        services.jobs.get(job_id)
        after = request.headers.get("last-event-id", "0")
        return EventSourceResponse(services.jobs.log_stream(job_id, int(after) if after.isdigit() else 0))

    @api.post("/jobs/{job_id}/cancel", response_model=Job, tags=["jobs"])
    async def cancel_job(job_id: str) -> Job:
        return services.jobs.cancel(job_id)

    # --- chat ----------------------------------------------------------------------------------------

    @api.post("/chat", tags=["chat"], response_class=EventSourceResponse,
              responses={200: {"content": {"text/event-stream": {}},
                               "description": "Vercel AI SDK UI-message stream (x-vercel-ai-ui-message-stream: v1)"}})
    async def chat_route(request: Request, run_id: str | None = None) -> Any:
        """Body: an AI SDK v5 chat request ({id, messages, trigger}); `run_id` in the body or the query
        scopes the chat to one run."""
        try:
            body = json.loads(await request.body() or b"{}")
        except ValueError:
            body = {}
        scope = run_id or (body.get("run_id") or body.get("runId") if isinstance(body, dict) else None)
        deps = chat.ChatDeps(services=services, run_id=str(scope) if scope else None)
        return await VercelAIAdapter.dispatch_request(request, agent=services.agent, deps=deps,
                                                      model=chat.chat_model(services),
                                                      model_settings=chat.model_settings())

    return api


def add_frontend(app: FastAPI, settings: Settings) -> None:
    """Serve the built frontend: files from dist/, any other path (a client route) as index.html."""
    dist = settings.web_dist

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise NotFound(f"no such API endpoint: /{path}")
        target = inside(dist, path) if path else dist / "index.html"
        if target.is_file():
            return FileResponse(target)
        index = dist / "index.html"
        if not index.is_file():
            raise NotFound("the frontend is not built (webapp/web/dist/index.html missing)")
        return FileResponse(index)
