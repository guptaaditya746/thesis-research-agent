"""The FastAPI backend: `webapp.app:create_app()`.

The evidence-level app under /api/ev, the supervisor's flow (STATE.md §4 "Web app"): the viewer (webapp/evapi.py,
read-only GETs over the files the commands write: corpora, protocols and proposals, runs with the funnel,
evidence graph and answer, scores A/B/C with the baselines beside the engine) and what the app starts and
writes (webapp/evjobs.py: the questions to select from, jobs that run the same commands as the runbook, a
proposal's decisions.yaml). `/api/health` says the server is up. The built frontend (webapp/web/dist) is served
at / with every other path falling back to index.html (client-side routes), when that directory exists.

The server writes only job state and logs ($EV/.jobs/) and decisions.yaml of a proposal; the jobs it starts
write what their commands write, into the $EV layout. It has no authentication: it binds to 127.0.0.1 and is
reached through an SSH tunnel (README, "Web app"); webapp/guard.py answers only loopback Host names and takes
a write only from a loopback client as a same-origin JSON request, so neither other hosts nor other web pages
the user has open can start jobs or read through DNS rebinding. Request paths are checked against their roots
(webapp/files.py).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from .evapi import evidence_router
from .evfiles import EvidenceFiles
from .evjobs import evjobs_router
from .evquestions import Questions
from .files import BadRequest, Conflict, NotFound, inside
from .guard import Guard
from .jobs import JobManager
from .models import Health
from .settings import Settings


def app_version() -> str:
    try:
        return version("thesis-agent")
    except PackageNotFoundError:
        return "0"


@dataclass
class Services:
    """Everything the routes read through; one per app."""

    settings: Settings
    jobs: JobManager = field(init=False)
    evidence: EvidenceFiles = field(init=False)  # the evidence-level viewer (webapp/evfiles.py)
    questions: Questions = field(init=False)

    def __post_init__(self) -> None:
        self.jobs = JobManager(self.settings)
        self.evidence = EvidenceFiles(self.settings)
        self.questions = Questions(self.settings)


def create_app(settings: Settings | None = None) -> FastAPI:
    services = Services(settings or Settings())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        services.jobs.load()
        yield
        await services.jobs.shutdown()

    app = FastAPI(title="Thesis: evidence-level synthesis", version=app_version(), lifespan=lifespan,
                  description="The supervisor's flow: question, protocol (or a proposal), corpus, run, evidence graph, "
                              "answer and scores with the baselines beside the engine; the jobs that make them.")
    app.state.services = services
    s = services.settings
    app.add_middleware(Guard, allowed_hosts=s.hosts, write_clients=s.writers)  # webapp/guard.py
    for exc_type, status in ((NotFound, 404), (Conflict, 409), (BadRequest, 400)):
        app.add_exception_handler(exc_type, _handler(status))
    app.include_router(health_router(), prefix="/api")
    app.include_router(evidence_router(services.evidence), prefix="/api/ev")
    app.include_router(evjobs_router(s, services.evidence, services.jobs, services.questions), prefix="/api/ev")
    if s.web_dist.is_dir():
        add_frontend(app, s)
    return app


def _handler(status: int):
    async def handle(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=status)
    return handle


def health_router() -> APIRouter:
    api = APIRouter(generate_unique_id_function=lambda route: route.name)

    @api.get("/health", response_model=Health, tags=["app"])
    def health() -> Health:
        return Health(ok=True, version=app_version())

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
