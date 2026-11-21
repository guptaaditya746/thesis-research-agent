"""Run settings: one JSON file per run (configs/*.json). Everything that may change between runs lives here, never
in code: field, genre, number of papers, paper length, and the model for each job."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from repo_paths import REPO

ROLES = ("world", "writer", "tagger", "verifier", "judge", "qa", "leak")
CHEAPEST_CLAUDE = "claude-haiku-5-5"


@dataclass
class Settings:
    field: str
    genre: str
    papers: int = 20
    pages: int = 6
    models: dict[str, str] = field(default_factory=dict)
    out: str = "runs/paperfactory/default"
    seed: int = 1
    qa_papers_per_question: int = 3
    leak_trials: int = 150
    world_file: str | None = None        # use a hand-written world instead of the world agent
    slot_dir: str = "data/cache/claude-slots"   # shared with other tools: at most 3 model calls at once
    timeout: int = 900

    def model(self, role: str) -> str:
        if role not in ROLES:
            raise KeyError(f"unknown role {role!r}; roles: {ROLES}")
        return self.models.get(role) or self.models.get("default") or CHEAPEST_CLAUDE

    @property
    def out_dir(self) -> Path:
        return REPO / self.out

    @property
    def slots(self) -> Path:
        return REPO / self.slot_dir


def load(path: str | Path) -> Settings:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw.pop("_note", None)
    unknown = set(raw.get("models", {})) - set(ROLES) - {"default"}
    if unknown:
        raise ValueError(f"unknown model roles {sorted(unknown)}; roles: {ROLES}")
    return Settings(**raw)
