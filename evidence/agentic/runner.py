"""Running our research agent (agent/loop.py) on a small corpus, and the record of one run.

The agent is used as it is: `agent.loop.research_run` with prompt v2, condition claim_on, its
sandbox (Landlock on the Slurm nodes; `unsandboxed` only for tests), its broker and the `claim`
command, whose accepted claims carry quote-checked anchors. Nothing in agent/ is changed: what the
agent is asked to do goes into the concept brief it researches (evidence/agentic/task.py).

`ResearchAgentRunner` writes the given files as an agent corpus (`<id>.md` plus a manifest in the
agent's format) in a temporary directory, runs the agent there and returns `collect(run)`: a JSON
record of everything the conversion and the engine's cache need (claims, commands with the output
the agent was shown, model calls, the answer, the trajectory). Real runs need Linux and the LiteLLM
gateway (key from $LITELLM_MASTER_KEY, read by the agent's model, never recorded); tests inject a
scripted model (`model_factory`) and run unsandboxed with the in-process broker, or skip the agent
altogether with a fake `AgentRunner`.

The agent's model is `AgentSettings.model`, a LiteLLM alias (default `orch-model`: one model for every
extractor and both baselines, docs/evidence-system.md Part G.3). The runner builds the agent's
`OrchestratorModel` on that alias (`default_model`); for an alias modelcall/pins.py pins (`orch-model`,
`sub-model-*`) the config and the model record the pinned name and revision, for any other alias the
alias as the name and the revision "unpinned" (the same in both places).
"""
from __future__ import annotations

import dataclasses
import json
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from jsonio import file_sha256, sha256_hex
from agent.rundir import BUDGET, COMMAND_LIMITS, ORCHESTRATOR, SUBAGENTS

REPO = Path(__file__).resolve().parents[2]
PINNED: dict[str, dict[str, Any]] = {m["alias"]: dict(m) for m in (ORCHESTRATOR, *SUBAGENTS)}


UNPINNED = "unpinned"  # the revision recorded, and given to the model, for an alias modelcall/pins.py does not pin


def model_record(alias: str) -> dict[str, Any]:
    """{alias, name, revision} for the config: the pinned weights of an alias modelcall/pins.py pins (for
    orch-model byte for byte what the config held before `model` existed), else the alias as the name with
    revision "unpinned", the same the model itself records (`default_model`)."""
    pinned = PINNED.get(alias)
    return {"alias": alias, "name": pinned["name"] if pinned else alias,
            "revision": pinned.get("revision") if pinned else UNPINNED}


@dataclass(frozen=True)
class AgentSettings:
    """How the agent runs; everything here but `agent_root`'s path goes into the extractor's config."""
    prompt_version: str = "v2"
    model: str = ORCHESTRATOR["alias"]   # LiteLLM alias of the agent's model (orch-model)
    temperature: float = 0.7
    seed: int = 1234
    sandbox_mode: str = "landlock"
    base_url: str = "http://127.0.0.1:4000/v1"
    broker: str = "auto"
    agent_root: str | None = None

    def config(self) -> dict[str, Any]:
        return {"prompt_version": self.prompt_version, "temperature": self.temperature, "seed": self.seed,
                "sandbox_mode": self.sandbox_mode, "model": model_record(self.model),
                "condition": "claim_on", "commands": "bash in the sandbox (python3, rg, jq, grep, sed, awk) + claim"}


def default_model(settings: AgentSettings) -> Any:
    """The agent's model for `settings.model`: agent.loop.OrchestratorModel on that alias through LiteLLM at
    `base_url`, with the pinned name, revision and context window of an alias modelcall/pins.py pins (for
    `orch-model` exactly what agent.loop.research_run builds by itself); an unpinned alias is served and
    recorded under its own name with revision "unpinned"."""
    from agent.loop import OrchestratorModel  # LiteLLM and mini-swe-agent: imported only when an agent runs

    pinned = PINNED.get(settings.model)
    extra = ({"name": pinned["name"], "revision": pinned["revision"], "context_tokens": pinned["context_tokens"]}
             if pinned else {"name": settings.model, "revision": UNPINNED})
    return OrchestratorModel(base_url=settings.base_url, temperature=settings.temperature, seed=settings.seed,
                             alias=settings.model, **extra)


@dataclass(frozen=True)
class AgentJob:
    """One agent run: the corpus files it sees ({file name: text}), the concept brief, the budget."""
    run_id: str
    files: dict[str, str]
    concept: dict[str, Any]
    budget: dict[str, int] = field(default_factory=lambda: {"steps": BUDGET["steps"], "tokens": BUDGET["tokens"]})


class AgentRunner(Protocol):
    def run(self, job: AgentJob) -> dict[str, Any]: ...


def write_agent_corpus(files: dict[str, str], root: Path) -> tuple[Path, Path]:
    """`<name>` files (each `<id>.md`) and manifest.json in the agent's format (corpus/manifest.json, D5)."""
    root.mkdir(parents=True, exist_ok=True)
    papers = []
    for name, text in sorted(files.items()):
        data = text.encode("utf-8")
        (root / name).write_bytes(data)
        papers.append({"id": Path(name).stem, "markdown_sha256": sha256_hex(data), "bytes": len(data), "failure": None})
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({"paper_count": len(papers), "papers": papers}, indent=2), encoding="utf-8",
                        newline="\n")
    return root, manifest


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] \
        if path.is_file() else []


def collect(run_root: Path, outcome: dict[str, Any] | None = None) -> dict[str, Any]:
    """The record of a finished agent run directory (see the module docstring)."""
    run_root = Path(run_root)
    cap = COMMAND_LIMITS["output_cap_bytes"]
    claims = []
    for r in _lines(run_root / "claims.jsonl"):
        meta, used = r.get("custom_metadata", {}), r.get("used", {})
        claims.append({"step_id": r["step_id"], "status": r["status"], "claim_id": r.get("generated", {}).get("claim_id"),
                       "reason": meta.get("reason"), **{k: meta.get(k) for k in ("s", "p", "o", "quote")},
                       "file": (used.get("anchor") or {}).get("file") or used.get("file"), "anchor": used.get("anchor")})
    commands, calls = [], []
    events = _lines(run_root / "events.jsonl")
    for r in events:
        if r["subtype"] == "agent_tool":
            out = run_root / r["generated"]["output_file"]
            shown = out.read_bytes()[:cap].decode("utf-8", errors="replace") if out.is_file() else ""
            commands.append({"step_id": r["step_id"], "command": r["used"]["command"], "output": shown,
                             "output_sha256": r["generated"]["output_sha256"], "exit_code": r["generated"]["exit_code"]})
        elif r["subtype"] == "ai_model_invocation":
            calls.append({"task_id": r["task_id"], "step_id": r["step_id"], "status": r["status"],
                          "prompt_sha256": r["used"].get("prompt_sha256"),
                          "response_sha256": r["generated"].get("response_sha256"),
                          "usage": r["generated"].get("usage")})
    answer = run_root / "answer.json"
    trajectory = run_root / "trajectory.json"
    return {"run_id": run_root.name, "outcome": outcome or {}, "claims": claims, "commands": commands,
            "model_calls": calls, "answer": json.loads(answer.read_text(encoding="utf-8")) if answer.is_file() else None,
            "trajectory": json.loads(trajectory.read_text(encoding="utf-8")) if trajectory.is_file() else None,
            "head": events[-1]["hash"] if events else None}


def git_commit() -> str:
    from agent.rundir import git_head

    try:
        return git_head(REPO)
    except Exception:  # not a checkout (an installed copy): the record says so with zeros
        return "0" * 40


class ResearchAgentRunner:
    """AgentRunner that runs the real research agent (agent.loop.research_run) in a temporary directory.

    `model_factory(settings)` builds the orchestrator model (tests: a scripted OrchestratorModel);
    by default `default_model` builds the LiteLLM one on `settings.model`. `work_dir` keeps the run
    directories (for inspection) instead of deleting them.
    """

    def __init__(self, settings: AgentSettings | None = None, *, model_factory: Callable[[AgentSettings], Any] | None = None,
                 work_dir: Path | None = None) -> None:
        self.settings = settings or AgentSettings()
        self.model_factory = model_factory
        self.work_dir = Path(work_dir) if work_dir else None

    def run(self, job: AgentJob) -> dict[str, Any]:
        """Each attempt gets a fresh directory (`<run_id>-<random>` under work_dir), so a rerun, a
        re-execution or a second `evaluate agent-baseline` into the same --out never meets the run
        directory of an earlier attempt (agent/rundir.py refuses to reuse one). The directory name is in
        no record: the record's run_id is the job's."""
        if self.work_dir is not None:
            return self._run(job, self.work_dir / f"{job.run_id}-{uuid.uuid4().hex[:12]}")
        with tempfile.TemporaryDirectory(prefix="agentic-") as tmp:
            return self._run(job, Path(tmp))

    def _run(self, job: AgentJob, base: Path) -> dict[str, Any]:
        from agent.loop import research_run  # LiteLLM and mini-swe-agent: imported only when an agent runs

        s = self.settings
        corpus, manifest = write_agent_corpus(job.files, base / "corpus")
        agent_root = Path(s.agent_root) if s.agent_root else None
        root_sha = file_sha256(agent_root / "agent-root.sha256") if agent_root else sha256_hex(b"")
        run, outcome, _ = research_run(
            runs_root=base / "runs", run_id=job.run_id, concept=job.concept, corpus=corpus, manifest=manifest,
            condition="claim_on", temperature=s.temperature, seed=s.seed, git_commit=git_commit(),
            agent_root_manifest_sha256=root_sha, sandbox_mode=s.sandbox_mode, agent_root=agent_root,
            base_url=s.base_url, budget={**BUDGET, **job.budget}, prompt_version=s.prompt_version, broker=s.broker,
            model=(self.model_factory or default_model)(s))
        record = collect(run.root, dataclasses.asdict(outcome))
        return {**record, "run_id": job.run_id}
