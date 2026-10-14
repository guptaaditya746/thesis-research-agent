"""Web app settings from the environment (docs/e2e-build-plan.md, "Environment").

| Variable               | Setting            | Default                                  |
|------------------------|--------------------|------------------------------------------|
| `CORPUS`               | `corpus`           | none (passages, verify, new runs need it) |
| `RUNS`                 | `runs`             | `runs`                                   |
| `GOLD`                 | `gold`             | `gold-data`                              |
| `CONCEPTS`             | `concepts`         | `concepts`                               |
| `QUESTIONS`            | `questions`        | `<repo>/questions/questions.json`        |
| `LITELLM_BASE_URL`     | `litellm_base_url` | `http://127.0.0.1:4000/v1`               |
| `ARGILLA_API_URL`      | `argilla_api_url`  | none                                     |
| `AGENT_ROOT`           | `agent_root`       | none                                     |
| `WEBAPP_DIST`          | `web_dist`         | `<repo>/webapp/web/dist`                 |
| `WEBAPP_PYTHON`        | `python`           | the server's interpreter                 |
| `WEBAPP_CHAT_MODEL`    | `chat_model`       | `sub-model-1`                            |
| `WEBAPP_LIVE_WINDOW_S` | `live_window_s`    | 900                                      |
| `WEBAPP_POLL_S`        | `poll_s`           | 0.5                                      |
| `WEBAPP_ALLOWED_HOSTS` | `allowed_hosts`    | `127.0.0.1,localhost,::1`                |

Relative paths are resolved against the working directory when the settings are made, so the job
subprocesses (which run in the repo) get absolute paths; an empty variable counts as unset. The
API keys ($LITELLM_MASTER_KEY, $ARGILLA_API_KEY) are never settings: they are read from the
environment at call time only.

$RUNS is one batch root, the RUNS_ROOT scripts/e2e-batch.sh prints for a manifest ($RUNS/m4-72 on
the cluster; docs/e2e-build-plan.md, Environment), which scoring takes too: its runs, its report/,
and the web app's own runs in $RUNS/web/ (ids web~<name>), so they never count as a manifest's runs.
A batch root one level down is listed as well (ids <batch>~<name>), but a root above several
batches is not what the app is for: run ids are directory names, and two batches have runs of the
same name (webapp/README.md).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from gold.llm import DEFAULT_BASE_URL

REPO = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True, env_ignore_empty=True, validate_default=True)

    corpus: Path | None = None
    runs: Path = Path("runs")
    gold: Path = Path("gold-data")
    concepts: Path = Path("concepts")
    questions: Path = REPO / "questions" / "questions.json"
    litellm_base_url: str = DEFAULT_BASE_URL
    argilla_api_url: str | None = None
    agent_root: Path | None = None
    # The web app's own settings: in the environment (and as keyword arguments) only by their
    # WEBAPP_ name, so a stray $PYTHON or $POLL_S cannot set them.
    web_dist: Path = Field(REPO / "webapp" / "web" / "dist", validation_alias="WEBAPP_DIST")
    python: str = Field(sys.executable, validation_alias="WEBAPP_PYTHON",
                        description="interpreter for the job subprocesses (`python -m agent.cli ...`)")
    chat_model: str = Field("sub-model-1", validation_alias="WEBAPP_CHAT_MODEL",
                            description="LiteLLM alias of the chat agent's model")
    live_window_s: float = Field(900.0, validation_alias="WEBAPP_LIVE_WINDOW_S",
                                 description="a run with no answer.json whose events.jsonl changed this "
                                             "recently is live: longer than the longest quiet spell of a run, "
                                             "one model call (timeout 600 s, OrchestratorModel) after a command "
                                             "(120 s, COMMAND_LIMITS), with a margin for the proxy's queue")
    poll_s: float = Field(0.5, validation_alias="WEBAPP_POLL_S", description="how often the SSE streams look "
                                                                            "for new lines")
    allowed_hosts: str = Field("127.0.0.1,localhost,::1", validation_alias="WEBAPP_ALLOWED_HOSTS",
                               description="comma-separated Host names the app answers (webapp/guard.py: "
                                           "a DNS-rebinding page sends its own name)")

    @property
    def hosts(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @field_validator("corpus", "runs", "gold", "concepts", "questions", "agent_root", "web_dist")
    @classmethod
    def _absolute(cls, value: Path | None) -> Path | None:
        return None if value is None else Path(value).expanduser().resolve()

    @property
    def corpus_manifest(self) -> Path | None:
        return self.corpus / "manifest.json" if self.corpus else None

    @property
    def jobs_dir(self) -> Path:
        return self.runs / ".jobs"

    @property
    def report_dir(self) -> Path:
        return self.runs / "report"

    @property
    def web_runs(self) -> Path:
        """Where runs started from the web app go (their ids are web~<name>)."""
        return self.runs / "web"


def llm_key_set() -> bool:
    """Whether $LITELLM_MASTER_KEY is set; the key itself is never read into the app's state."""
    return bool(os.environ.get("LITELLM_MASTER_KEY"))
