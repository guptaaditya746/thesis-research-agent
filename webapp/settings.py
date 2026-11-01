"""Web app settings from the environment (README, "Web app").

The evidence-level directories (docs/slurm-evidence-runbook.md); `$EV` alone is enough, each may be set apart:

| Variable         | Setting       | Default                              |
|------------------|---------------|--------------------------------------|
| `EV`             | `ev`          | none                                 |
| `CORPORA`        | `corpora`     | `$EV/corpora`                        |
| `EV_RUNS`        | `ev_runs`     | `$EV/runs`                           |
| `SCORES`         | `scores`      | `$EV/scores`                         |
| `EV_PROPOSALS`   | `proposals`   | `$EV/proposals`                      |
| `EV_CACHE`       | `ev_cache`    | `$EV/cache/engine` (the engine's record cache) |
| `EV_AGENT_WORK`  | `agent_work`  | `$EVIDENCE_AGENT_WORK_DIR` (the agentic extractor's own), else `$EV/agent-work` |
| `EV_PROTOCOLS`   | `protocols`   | `<repo>/domains/rag/protocols`       |
| `EV_QUESTIONS`   | `questions`   | `<repo>/domains/rag/questions.yaml`  |

The jobs the app starts (webapp/jobs.py, webapp/evjobs.py) keep their state and logs in `$EV/.jobs/` (no
jobs without `$EV`) and write into the directories above:

| Variable                | Setting         | Default                                  |
|-------------------------|-----------------|------------------------------------------|
| `LITELLM_BASE_URL`      | `litellm_base_url` | `http://127.0.0.1:4000/v1`            |
| `AGENT_ROOT`            | `agent_root`    | none (the agent baseline's `--agent-root`) |
| `WEBAPP_PYTHON`         | `python`        | the server's interpreter                 |
| `WEBAPP_MODEL_JOBS`     | `model_jobs`    | 1 (jobs that call a model, at a time)    |
| `WEBAPP_CPU_JOBS`       | `cpu_jobs`      | 2 (jobs without a model call, at a time) |
| `WEBAPP_USER`           | `user`          | the login name (`by` of a decision made in the app) |
| `WEBAPP_DIST`           | `web_dist`      | `<repo>/webapp/web/dist`                 |
| `WEBAPP_ALLOWED_HOSTS`  | `allowed_hosts` | `127.0.0.1,localhost,::1`                |
| `WEBAPP_WRITE_CLIENTS`  | `write_clients` | `127.0.0.1,::1,::ffff:127.0.0.1`         |

Relative paths are resolved against the working directory when the settings are made, so the job
subprocesses (which run in the repo) get absolute paths; an empty variable counts as unset. The API key
($LITELLM_MASTER_KEY) is never a setting: the jobs read it from the environment they inherit.
"""
from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from evidence.pack import DOMAINS, questions_path
from modelcall import DEFAULT_BASE_URL

REPO = Path(__file__).resolve().parents[1]
JOBS_DIR = ".jobs"   # under $EV; a leading dot keeps it out of every viewer listing (files.ID)


def _login() -> str:
    try:
        return getpass.getuser() or "user"
    except Exception:  # noqa: BLE001 - no login name (a container): a plain default
        return "user"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True, env_ignore_empty=True, validate_default=True)

    litellm_base_url: str = DEFAULT_BASE_URL
    agent_root: Path | None = None
    # The web app's own settings: in the environment (and as keyword arguments) only by their
    # WEBAPP_ name, so a stray $PYTHON or $USER cannot set them.
    web_dist: Path = Field(REPO / "webapp" / "web" / "dist", validation_alias="WEBAPP_DIST")
    python: str = Field(sys.executable, validation_alias="WEBAPP_PYTHON",
                        description="interpreter for the job subprocesses (`python -m webapp.tool ...`)")
    model_jobs: int = Field(1, ge=1, validation_alias="WEBAPP_MODEL_JOBS",
                            description="jobs that call a model running at a time; the rest wait in a queue")
    cpu_jobs: int = Field(2, ge=1, validation_alias="WEBAPP_CPU_JOBS",
                          description="jobs without a model call (template corpora, scores, freeze) at a time")
    user: str = Field(default_factory=_login, validation_alias="WEBAPP_USER",
                      description="who decides a card in the app (`by` in decisions.yaml)")
    allowed_hosts: str = Field("127.0.0.1,localhost,::1", validation_alias="WEBAPP_ALLOWED_HOSTS",
                               description="comma-separated Host names the app answers (webapp/guard.py: "
                                           "a DNS-rebinding page sends its own name)")
    write_clients: str = Field("127.0.0.1,::1,::ffff:127.0.0.1", validation_alias="WEBAPP_WRITE_CLIENTS",
                               description="comma-separated client addresses whose requests may write or start "
                                           "jobs (webapp/guard.py): loopback, the end of the SSH tunnel")

    # The evidence-level directories (module docstring); None: under $EV, or not configured.
    ev: Path | None = Field(None, validation_alias="EV")
    corpora: Path | None = Field(None, validation_alias="CORPORA")
    ev_runs: Path | None = Field(None, validation_alias="EV_RUNS")
    scores: Path | None = Field(None, validation_alias="SCORES")
    proposals: Path | None = Field(None, validation_alias="EV_PROPOSALS")
    ev_cache: Path | None = Field(None, validation_alias="EV_CACHE")
    agent_work: Path | None = Field(None, validation_alias="EV_AGENT_WORK")
    # where the agentic extractor itself keeps its agent runs (evidence/agentic/extractor.py; the runbook sets it)
    extractor_agent_work: Path | None = Field(None, validation_alias="EVIDENCE_AGENT_WORK_DIR")
    protocols: Path = Field(DOMAINS / "rag" / "protocols", validation_alias="EV_PROTOCOLS")
    questions: Path = Field(questions_path("rag"), validation_alias="EV_QUESTIONS")

    @property
    def hosts(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def writers(self) -> list[str]:
        return [h.strip() for h in self.write_clients.split(",") if h.strip()]

    @field_validator("user")
    @classmethod
    def _a_person(cls, value: str) -> str:
        """`by` in decisions.yaml: a decision by `model` is the model's default, so a person is never called that."""
        value = value.strip()
        if not value or value == "model":
            raise ValueError("WEBAPP_USER must name a person: not blank and not 'model' (decisions.yaml's `by` "
                             "for the model's defaults)")
        return value

    @field_validator("agent_root", "web_dist", "ev", "corpora", "ev_runs", "scores", "proposals", "ev_cache",
                     "agent_work", "extractor_agent_work", "protocols", "questions")
    @classmethod
    def _absolute(cls, value: Path | None) -> Path | None:
        return None if value is None else Path(value).expanduser().resolve()

    def _under_ev(self, value: Path | None, *parts: str) -> Path | None:
        return value if value is not None else (self.ev.joinpath(*parts) if self.ev else None)

    @property
    def corpora_dir(self) -> Path | None:
        return self._under_ev(self.corpora, "corpora")

    @property
    def ev_runs_dir(self) -> Path | None:
        return self._under_ev(self.ev_runs, "runs")

    @property
    def scores_dir(self) -> Path | None:
        return self._under_ev(self.scores, "scores")

    @property
    def proposals_dir(self) -> Path | None:
        return self._under_ev(self.proposals, "proposals")

    @property
    def ev_cache_dir(self) -> Path | None:
        return self._under_ev(self.ev_cache, "cache", "engine")

    @property
    def cache_root(self) -> Path | None:
        """$EV/cache: the baselines' call caches (rag-baseline.jsonl, agent-baseline.jsonl) beside engine/."""
        return self.ev / "cache" if self.ev else (self.ev_cache_dir.parent if self.ev_cache_dir else None)

    @property
    def agent_work_dir(self) -> Path | None:
        """$EV_AGENT_WORK, else the agentic extractor's own $EVIDENCE_AGENT_WORK_DIR, else $EV/agent-work."""
        return self._under_ev(self.agent_work or self.extractor_agent_work, "agent-work")

    @property
    def jobs_dir(self) -> Path | None:
        return self.ev / JOBS_DIR if self.ev else None


def llm_key_set() -> bool:
    """Whether $LITELLM_MASTER_KEY is set; the key itself is never read into the app's state."""
    return bool(os.environ.get("LITELLM_MASTER_KEY"))
