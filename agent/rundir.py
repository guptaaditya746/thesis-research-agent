"""The run directory `runs/<run-id>/` and its `config.json` (docs/earlier-work.md, build row 1.2)."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import schema
from jsonio import file_sha256, write_json
from .concept import validate_answer, validate_concept

FILES = ("config.json", "concept.json", "events.jsonl", "claims.jsonl")
DIRS = ("out", "scratch")
ATTACH_FILE = "attach.json"  # the baseline's attach step (row 2.5) writes it when it finishes
ANSWER_BEFORE = "answer.research.json"  # ... after keeping the run's own answer here
# The bytes of the agent's draft answer as the harness read them when the run ended without an
# answer (row 1.13): scratch/ stays writable (the attach step works there), this copy does not change.
DRAFT_COPY = "answer.draft.json"

# Fixed run settings (docs/earlier-work.md, Fixed run settings). Budget is adjusted once after 1.13, then frozen.
ORCHESTRATOR = {"alias": "orch-model", "name": "Qwen/Qwen3.8-27B-FP8", "revision": "017b9c7",
                "thinking": False, "max_tokens": 4096, "context_tokens": 65536}
SUBAGENTS = [{"alias": f"sub-model-{i}", "name": "Qwen/Qwen3-30B-A3B-Instruct-2507-FP8",
              "revision": "5a5a776", "context_tokens": 32768} for i in (1, 2)]
# Provisional (the e2e build of 13 Oct, docs/earlier-work.md; the user freezes it after the Slurm test). The token sum
# counts the whole prompt again at every step, so the M1-real runs' 150 steps / 400k lasted only
# ~26 steps: 2M tokens over 60 steps is ~33k per step, about what a masked context costs.
BUDGET = {"steps": 60, "tokens": 2_000_000, "announced": True}
BUDGET_M1 = {"steps": 150, "tokens": 400_000, "announced": True}  # the M1-real runs (prompt v1), for reruns
COMMAND_LIMITS = {"timeout_s": 120, "ulimit_v_kib": 2 * 1024 * 1024, "output_cap_bytes": 8192}


def attach_state(run: RunDir) -> str:
    """The baseline's attach step (2.5): not_applicable (claim_on), pending, cut (started, no attach.json) or done."""
    config = run.load_config()
    if config["condition"] != "claim_off":
        return "not_applicable"
    if (run.root / ATTACH_FILE).is_file():
        return "done"
    return "cut" if "attach" in config else "pending"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def git_head(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()


def run_config(run_id: str, *, condition: str, temperature: float, seed: int, prompt_version: str,
               prompt_sha256: str, concept_sha256: str, corpus_manifest_sha256: str,
               agent_root_manifest_sha256: str, git_commit: str,
               budget: dict[str, Any] | None = None, prompt_files: dict[str, str] | None = None,
               sandbox: dict[str, Any] | None = None, loop: dict[str, Any] | None = None,
               spawn: dict[str, Any] | None = None) -> dict[str, Any]:
    """A complete config.json; the fixed settings come from the constants above.

    The main loop (row 1.8) adds `prompt_files` (sha256 of each prompt file), `sandbox` (which
    sandbox mode ran the commands), `loop` (harness version and model endpoint) and `spawn`
    (whether the agent may start subagents and with what, row 2.12); all optional.
    """
    config = {
        "schema_version": 1, "run_id": run_id, "created_at": utc_now(), "condition": condition,
        "models": {"orchestrator": dict(ORCHESTRATOR), "subagents": [dict(s) for s in SUBAGENTS]},
        "budget": dict(budget or BUDGET),
        "sampling": {"temperature": temperature, "seed": seed},
        "command_limits": dict(COMMAND_LIMITS),
        "prompt": {"version": prompt_version, "sha256": prompt_sha256},
        "hashes": {"concept_sha256": concept_sha256, "corpus_manifest_sha256": corpus_manifest_sha256,
                   "agent_root_manifest_sha256": agent_root_manifest_sha256},
        "git_commit": git_commit,
    }
    if prompt_files:
        config["prompt"]["files"] = dict(prompt_files)
    if sandbox is not None:
        config["sandbox"] = dict(sandbox)
    if loop is not None:
        config["loop"] = dict(loop)
    if spawn is not None:
        config["spawn"] = dict(spawn)
    return config


@dataclass(frozen=True)
class RunDir:
    root: Path

    @property
    def run_id(self) -> str:
        return self.root.name

    @property
    def config(self) -> Path:
        return self.root / "config.json"

    @property
    def concept(self) -> Path:
        return self.root / "concept.json"

    @property
    def events(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def claims(self) -> Path:
        return self.root / "claims.jsonl"

    @property
    def out(self) -> Path:
        return self.root / "out"

    @property
    def scratch(self) -> Path:
        return self.root / "scratch"

    @property
    def answer(self) -> Path:
        return self.root / "answer.json"

    @classmethod
    def create(cls, runs_root: Path, run_id: str, concept: dict[str, Any], *,
               corpus_manifest: Path, **settings: Any) -> RunDir:
        """Make `runs_root/run_id/` with every file and directory of the layout.

        `concept.json` is written in canonical form and its hash, and the hash of the corpus
        manifest file, go into config.json. `settings` are the remaining run_config() keywords.
        Refuses to reuse an existing directory or an invalid concept.
        """
        problems = validate_concept(concept)
        if problems:
            raise ValueError(f"invalid concept: {problems}")
        run = cls(Path(runs_root) / run_id)
        run.root.mkdir(parents=True, exist_ok=False)
        for name in DIRS:
            (run.root / name).mkdir()
        concept_sha = write_json(run.concept, concept)
        config = run_config(run_id, concept_sha256=concept_sha,
                            corpus_manifest_sha256=file_sha256(corpus_manifest), **settings)
        problems = schema.check("config", config)
        if problems:
            raise ValueError(f"invalid config: {problems}")
        write_json(run.config, config)
        run.events.touch()
        run.claims.touch()
        return run

    def load_config(self) -> dict[str, Any]:
        return json.loads(self.config.read_text(encoding="utf-8"))

    def load_concept(self) -> dict[str, Any]:
        return json.loads(self.concept.read_text(encoding="utf-8"))

    def validate(self, complete: bool = False) -> list[str]:
        """Layout problems; empty means valid. `complete` also requires answer.json.

        The hash chain in events.jsonl is checked by `agent verify-chain`, not here.
        """
        problems = [f"missing {n}" for n in FILES if not (self.root / n).is_file()]
        problems += [f"missing {n}/" for n in DIRS if not (self.root / n).is_dir()]
        if complete and not self.answer.is_file():
            problems.append("missing answer.json")
        if problems:
            return problems
        try:
            config = self.load_config()
        except ValueError as exc:
            return [f"config.json: {exc}"]
        problems += [f"config.json {p}" for p in schema.check("config", config)]
        if config.get("run_id") != self.run_id:
            problems.append(f"config.json run_id {config.get('run_id')!r} != directory {self.run_id!r}")
        concept_sha = file_sha256(self.concept)
        if config.get("hashes", {}).get("concept_sha256") != concept_sha:
            problems.append("concept.json hash differs from config.json")
        problems += self._concept_problems()
        if self.answer.is_file() and not problems:
            try:
                answer = json.loads(self.answer.read_text(encoding="utf-8"))
                problems += [f"answer.json {p}" for p in validate_answer(answer, self.load_concept())]
            except ValueError as exc:
                problems.append(f"answer.json: {exc}")
        for path in (self.events, self.claims):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                try:
                    json.loads(line)
                except ValueError:
                    problems.append(f"{path.name}:{n} is not JSON")
        return problems

    def _concept_problems(self) -> list[str]:
        try:
            concept = self.load_concept()
        except ValueError as exc:
            return [f"concept.json: {exc}"]
        return [f"concept.json {p}" for p in validate_concept(concept)]
