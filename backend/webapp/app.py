"""The FastAPI backend: `webapp.app:create_app()`.

The Workbench API under /api/evqa (read-only GETs over data/seed, data/dataset and runs/evqa: webapp/evqa_api.py,
evqa_questions_api.py, evqa_papers_api.py, evqa_runs_api.py), the optional review queue (evqa_review_api.py: its
POST saves a human label under data/reviews) and `/api/health`. The built frontend (frontend/dist)
is served at / with every other path falling back to index.html (client-side routes), when that directory exists.

No authentication: it binds to 127.0.0.1 and is reached through an SSH tunnel; webapp/guard.py answers only
loopback Host names (DNS rebinding) and takes a write only from a loopback client.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .evqa_api import router as evqa_router
from .evqa_papers_api import router as evqa_papers_router
from .evqa_questions_api import router as evqa_questions_router
from .evqa_review_api import router as evqa_review_router
from .evqa_runs_api import router as evqa_runs_router
from .guard import Guard
from .settings import Settings


class Health(BaseModel):
    ok: bool
    version: str


def app_version() -> str:
    try:
        return version("thesis-agent")
    except PackageNotFoundError:
        return "0"


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or Settings()
    app = FastAPI(title="Thesis: evqa Workbench", version=app_version(),
                  description="Read-only views of the evqa seed, papers, questions and runs.")
    app.state.settings = s
    app.add_middleware(Guard, allowed_hosts=s.hosts, write_clients=s.writers)  # webapp/guard.py
    app.include_router(health_router(), prefix="/api")
    for router in (evqa_router, evqa_questions_router, evqa_papers_router, evqa_runs_router, evqa_review_router):
        app.include_router(router, prefix="/api")
    if s.web_dist.is_dir():
        add_frontend(app, s.web_dist)
    return app


def health_router() -> APIRouter:
    api = APIRouter(generate_unique_id_function=lambda route: route.name)

    @api.get("/health", response_model=Health, tags=["app"])
    def health() -> Health:
        return Health(ok=True, version=app_version())

    return api


def add_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built frontend: files from dist/, any other path (a client route) as index.html."""
    root = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, f"no such API endpoint: /{path}")
        target = (root / path).resolve() if path else root / "index.html"
        if target.is_relative_to(root) and target.is_file():
            return FileResponse(target)
        index = root / "index.html"
        if not index.is_file():
            raise HTTPException(404, "the frontend is not built (frontend/dist/index.html missing)")
        return FileResponse(index)
