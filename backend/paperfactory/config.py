"""Run settings: one JSON file per run (configs/*.json). Everything that may change between runs lives here, never
in code: field, genre, number of papers, paper length, and the model for each job."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from repo_paths import REPO

ROLES = ("world", "writer", "tagger", "verifier", "judge", "rewriter", "repair", "qa", "leak")
CHEAPEST_CLAUDE = "claude-haiku-5-5"
BACKENDS = ("claude_cli", "openai")
DEFAULT_GATEWAY = "http://127.0.0.1:4000/v1"     # the llm-setup LiteLLM gateway (modelcall.gateway)


@dataclass(frozen=True)
class RoleModel:
    """The model of one job. backend "claude_cli": `claude -p` (cost reported by the CLI). backend "openai": any
    OpenAI-compatible server (the LiteLLM gateway, vLLM, Ollama, a hosted API behind LiteLLM) through
    modelcall; base_url None = $LITELLM_BASE_URL or the local gateway. Cost: reported by the backend, else
    tokens x price (USD per million tokens), else 0 for local=true, else unknown (None)."""
    model: str
    backend: str = "claude_cli"
    base_url: str | None = None
    context_window: int | None = None      # tokens; None = not checked
    timeout: int = 900
    max_parallel: int = 3
    max_tokens: int = 8192                 # output tokens (openai backend)
    price_in_per_mtok: float | None = None
    price_out_per_mtok: float | None = None
    local: bool = False

    def __post_init__(self) -> None:
        if self.backend not in BACKENDS:
            raise ValueError(f"unknown backend {self.backend!r}; backends: {BACKENDS}")
        if self.max_parallel < 1:
            raise ValueError("max_parallel must be at least 1")

    @property
    def url(self) -> str | None:
        if self.backend != "openai":
            return None
        return (self.base_url or os.environ.get("LITELLM_BASE_URL") or DEFAULT_GATEWAY).rstrip("/")

    @classmethod
    def parse(cls, v: str | dict[str, Any], timeout: int) -> RoleModel:
        """A model name ("claude-haiku-5-5"; "qwen:<alias>" = that alias on the LiteLLM gateway, as in
        PaperOrchestra) or a dict of RoleModel fields."""
        if isinstance(v, str):
            if v.startswith("qwen:"):
                return cls(v.split(":", 1)[1], backend="openai", timeout=timeout)
            return cls(v, timeout=timeout)
        unknown = set(v) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"unknown model settings {sorted(unknown)}")
        return cls(**({"timeout": timeout} | v))


@dataclass
class Settings:
    field: str
    genre: str
    papers: int = 20
    pages: int = 6
    models: dict[str, str | dict[str, Any]] = field(default_factory=dict)   # role or "default" -> RoleModel
    out: str = "runs/paperfactory/default"
    seed: int = 1
    qa_papers_per_question: int = 3
    leak_trials: int = 150
    world_file: str | None = None        # use a hand-written world instead of the world agent
    # strict evidence rule (#2): share of the quote inside gold spans; share of a gold sentence a quote must cover
    # when it does not name both the subject and the object. Saved in report.json with SCORING_VERSION.
    evidence: dict[str, float] = field(default_factory=lambda: {"min_inside": 0.9, "min_sentence_cover": 0.5})
    slot_dir: str = "data/cache/claude-slots"   # shared with other tools: lock files cap the calls per server
    # papers written / checked at once, and threads for the evaluation's model calls (the role's max_parallel still
    # caps the calls per server across all processes)
    parallel: int = 3
    timeout: int = 900

    def role(self, role: str) -> RoleModel:
        if role not in ROLES:
            raise KeyError(f"unknown role {role!r}; roles: {ROLES}")
        return RoleModel.parse(self.models.get(role) or self.models.get("default") or CHEAPEST_CLAUDE, self.timeout)

    def model(self, role: str) -> str:
        return self.role(role).model

    @property
    def out_dir(self) -> Path:
        return REPO / self.out

    @property
    def slots(self) -> Path:
        return REPO / self.slot_dir


# roles that should not share a model: a model can favour its own writing (D2)
INDEPENDENT = ("writer", "rewriter", "judge", "verifier")


def shared_models(s: Settings) -> list[str]:
    """Warnings for roles in INDEPENDENT that use the same model (same backend, model and server)."""
    by: dict[tuple[str, str, str | None], list[str]] = {}
    for r in INDEPENDENT:
        rm = s.role(r)
        by.setdefault((rm.backend, rm.model, rm.url), []).append(r)
    return [f"{', '.join(rs)} share the model {m} ({b}); a model can favour its own wording, so set a different "
            f"model family per job in 'models' for final numbers" for (b, m, _), rs in by.items() if len(rs) > 1]


def load(path: str | Path) -> Settings:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw.pop("_note", None)
    unknown = set(raw.get("models", {})) - set(ROLES) - {"default"}
    if unknown:
        raise ValueError(f"unknown model roles {sorted(unknown)}; roles: {ROLES}")
    s = Settings(**raw)
    if s.parallel < 1:
        raise ValueError("parallel must be at least 1")
    for r in ROLES:
        s.role(r)                                     # every role's model settings are valid
    return s
