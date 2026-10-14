"""The agentic extractor: our research agent behind the extractor contract (kind agent, determinism variable).

Per task the agent gets a corpus holding one file, the task's document (`<id>.md`, the text exactly
as the engine has it), and a concept brief asking for every item of the task's evidence type with a
claimed quote per field (task.py). The run's record (runner.collect) becomes the ExtractionResult
(convert.py). The record is also returned (`extract_recorded`) and kept in `records`, so the engine
can store it with the result in its call cache: it holds the agent's whole trajectory, its commands
with what they showed, its claims and the ids of its model calls.

Status: ok when the agent gave a final answer; partial when the harness took its draft (budget or
context ran out) and items were kept; error when the run failed or left no answer and no item.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agent.anchor import Index
from agent.canonical import sha256_hex
from evidence.contract import (ExtractionError, ExtractionResult, ExtractionTask, ExtractorSpec, Item, Rejected,
                               RunContext, digest)
from gold.llm import redact

from . import convert
from .runner import AgentJob, AgentRunner, AgentSettings, ResearchAgentRunner
from .task import TEMPLATE_VERSION, concept_for, link_names

NAME, VERSION = "agentic", 1
DEFAULT_BUDGET = {"steps": 30, "tokens": 600_000}
PACKAGE = Path(__file__).resolve().parent
AGENT = PACKAGE.parents[1] / "agent"
# Source whose change changes what the extractor does: this package, and the agent's loop, answer check,
# broker, anchoring, reply parser, sandbox, claim client, run settings (budget, command limits: rundir.py),
# concept and prompt handling, stopping and spawn hooks; plus the mini-swe-agent version the loop runs on.
# The prompt files are hashed separately (prompt_files in config).
AGENT_FILES = ("loop.py", "answer.py", "broker.py", "anchor.py", "parse.py", "sandbox.py", "claim_client.py",
               "rundir.py", "concept.py", "stopping.py", "prompts.py", "spawn.py")


def harness_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("mini-swe-agent")
    except PackageNotFoundError:
        return "missing"


def code_sha256() -> str:
    files = sorted(PACKAGE.glob("*.py")) + [AGENT / f for f in AGENT_FILES]
    hashes = {f.name if f.parent == PACKAGE else f"agent/{f.name}": sha256_hex(f.read_bytes().replace(b"\r\n", b"\n"))
              for f in files}
    return digest({**hashes, "mini-swe-agent": harness_version()})


def prompt_files(version: str) -> dict[str, str]:
    from agent import prompts

    return dict(prompts.load(version, "claim_on").files)


def safe_name(document_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", document_id) + ".md"


class AgenticExtractor:
    """contract.Extractor running the research agent through an AgentRunner (real or recorded/fake)."""

    def __init__(self, runner: AgentRunner | None = None, settings: AgentSettings | None = None,
                 budget: dict[str, int] | None = None, *, evidence_type: str | None = None,
                 links: dict[str, str] | None = None, description: str = "") -> None:
        """`evidence_type`, `links` and `description` are what the engine's config gives per protocol step
        (evidence/extractors: the evidence type, its links {name: target type} and the protocol's text);
        without them the extractor takes any type and infers links from the context's types."""
        self.settings = settings or AgentSettings()
        self.runner = runner or ResearchAgentRunner(self.settings)
        self.budget = dict(budget or DEFAULT_BUDGET)
        self.evidence_type, self.links, self.description = evidence_type, dict(links or {}), description
        config = {**self.settings.config(), "budget": self.budget, "template": TEMPLATE_VERSION,
                  "prompt_files": prompt_files(self.settings.prompt_version)}
        if evidence_type:
            config |= {"evidence_type": evidence_type, "links": self.links, "description": description}
        types = (evidence_type,) if evidence_type else ("condition", "metric", "measurement", "author_claim")
        self.spec = ExtractorSpec(name=NAME, version=VERSION, kind="agent", evidence_types=types,  # type: ignore[arg-type]
                                  code_sha256=code_sha256(), config=config, determinism="variable")
        self.records: dict[str, dict[str, Any]] = {}  # task_sha256 -> the agent run's record

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> AgenticExtractor:
        """The registry's factory: AgentSettings fields, `budget`, `work_dir` (keep the agent's run
        directories), and the engine's `evidence_type`, `links`, `description`; other keys are ignored."""
        fields = {k: v for k, v in config.items() if k in AgentSettings.__dataclass_fields__}
        settings = AgentSettings(**fields)
        runner = ResearchAgentRunner(settings, work_dir=Path(config["work_dir"]) if config.get("work_dir") else None)
        return cls(runner, settings, config.get("budget"), evidence_type=config.get("evidence_type"),
                   links=config.get("links"), description=config.get("description") or "")

    def extract(self, task: ExtractionTask, ctx: RunContext) -> ExtractionResult:
        return self.extract_recorded(task, ctx)[0]

    def extract_recorded(self, task: ExtractionTask, ctx: RunContext) -> tuple[ExtractionResult, dict[str, Any]]:
        text = ctx.text()
        index = ctx.index()
        index = index if isinstance(index, Index) else Index(text)
        context = list(ctx.context_items())
        schema = ctx.field_schema()
        links = link_names(task, self.links, context)
        file = safe_name(task.document.id)
        concept = concept_for(task, schema, links, context, file, len(text), self.description)
        budget = {**self.budget, **{k: v for k, v in (task.budget.model_dump() if task.budget else {}).items() if v}}
        job = AgentJob(run_id=f"agentic-{task.task_sha256[:16]}", files={file: text}, concept=concept, budget=budget)
        try:
            record = self.runner.run(job)
        except Exception as exc:
            record = {"run_id": job.run_id, "error": redact(f"{type(exc).__name__}: {exc}")[:1000]}
        record = {**record, "concept": concept}
        self.records[task.task_sha256] = record
        ids = engine_records(ctx, record)
        return self.convert(task, record, schema, links, context, text, index, ids), record

    def convert(self, task: ExtractionTask, record: dict[str, Any], schema: dict[str, Any], links: dict[str, str],
                context: list[Item], text: str, index: Index, model_calls: list[str] | None = None) -> ExtractionResult:
        """The ExtractionResult for one agent record (pure: the same record gives the same result)."""
        calls = tuple(model_calls if model_calls is not None else call_ids(record))
        base = {"extractor_id": self.spec.extractor_id, "task_sha256": task.task_sha256, "model_calls": calls}
        if "error" in record:
            return ExtractionResult(**base, status="error", error=ExtractionError(reason="agent_failed",
                                                                                   detail=record["error"]))
        claims = {c["claim_id"]: c for c in record.get("claims", []) if c["status"] == "accepted"}
        items: list[Item] = []
        rejected: list[Rejected] = convert.rejected_claims(record, task.evidence_type)
        for row in (record.get("answer") or {}).get("rows", []):
            made = convert.row_item(row, task, schema, links, context, claims, index)
            (items if isinstance(made, Item) else rejected).append(made)
        items = convert.merge(items)
        scope = [(0, len(text))] if task.scope.kind == "document" or not task.scope.ranges else list(task.scope.ranges)
        outcome = record.get("outcome") or {}
        answer_from = outcome.get("answer_from", "final" if record.get("answer") else "none")
        status, error = "ok", None
        if answer_from != "final":
            status = "partial" if items else "error"
            error = ExtractionError(reason="no_final_answer", detail=f"exit {outcome.get('exit_status')}, "
                                                                     f"answer from {answer_from}")
        return ExtractionResult(**base, status=status, error=error, items=tuple(items), rejected=tuple(rejected),
                                coverage=tuple(convert.coverage(text, record, scope, items))).canonical()


def call_ids(record: dict[str, Any]) -> list[str]:
    """One id per model call of the agent run: <run id>/<its ai_model_invocation task id>."""
    return [f"{record.get('run_id')}/{c['task_id']}" for c in record.get("model_calls", [])] or [f"{record.get('run_id')}/run"]


def engine_records(ctx: Any, record: dict[str, Any]) -> list[str]:
    """Hand the run to the engine's recorder (ctx.llm().records, evidence/recording.py) when it has one.

    One record per model call of the agent (id, prompt and response hashes, usage as input/output
    tokens, so the engine's cost counts the agent's calls and tokens); the last one also holds the
    whole agent record (`agent_run`: concept, claims, commands with their output, answer, trajectory),
    which the engine stores in its call cache. Without a recorder the record stays in `records` only.
    """
    llm = getattr(ctx, "llm", None)
    recorder = llm() if callable(llm) else None
    ids = call_ids(record)
    if recorder is None or not isinstance(getattr(recorder, "records", None), list):
        return ids
    calls = record.get("model_calls") or [{}]
    for n, (call_id, call) in enumerate(zip(ids, calls)):
        usage = call.get("usage") or {}
        entry: dict[str, Any] = {"id": call_id, "kind": "agent_model_call",
                                 "request": {k: call.get(k) for k in ("step_id", "prompt_sha256", "status")},
                                 "response": {"response_sha256": call.get("response_sha256")},
                                 "usage": {"input_tokens": int(usage.get("prompt_tokens") or 0),
                                           "output_tokens": int(usage.get("completion_tokens") or 0)}}
        if n == len(ids) - 1:
            entry["agent_run"] = record
            if "error" in record:
                entry["error"] = record["error"]
        recorder.records.append(entry)
    return ids
