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
from .task import TEMPLATE_VERSION, concept_for

NAME, VERSION = "agentic", 1
DEFAULT_BUDGET = {"steps": 30, "tokens": 600_000}
PACKAGE = Path(__file__).resolve().parent
AGENT = PACKAGE.parents[1] / "agent"
# Source whose change changes what the extractor does: this package, and the agent's loop, answer check,
# broker, anchoring and reply parser. The prompt files are hashed separately (prompt_files in config).
AGENT_FILES = ("loop.py", "answer.py", "broker.py", "anchor.py", "parse.py", "sandbox.py", "claim_client.py")


def code_sha256() -> str:
    files = sorted(PACKAGE.glob("*.py")) + [AGENT / f for f in AGENT_FILES]
    return digest({f.name if f.parent == PACKAGE else f"agent/{f.name}": sha256_hex(f.read_bytes().replace(b"\r\n", b"\n"))
                   for f in files})


def prompt_files(version: str) -> dict[str, str]:
    from agent import prompts

    return dict(prompts.load(version, "claim_on").files)


def safe_name(document_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", document_id) + ".md"


class AgenticExtractor:
    """contract.Extractor running the research agent through an AgentRunner (real or recorded/fake)."""

    def __init__(self, runner: AgentRunner | None = None, settings: AgentSettings | None = None,
                 budget: dict[str, int] | None = None) -> None:
        self.settings = settings or AgentSettings()
        self.runner = runner or ResearchAgentRunner(self.settings)
        self.budget = dict(budget or DEFAULT_BUDGET)
        config = {**self.settings.config(), "budget": self.budget, "template": TEMPLATE_VERSION,
                  "prompt_files": prompt_files(self.settings.prompt_version)}
        self.spec = ExtractorSpec(name=NAME, version=VERSION, kind="agent",
                                  evidence_types=("condition", "metric", "measurement", "author_claim"),
                                  code_sha256=code_sha256(), config=config, determinism="variable")
        self.records: dict[str, dict[str, Any]] = {}  # task_sha256 -> the agent run's record

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> AgenticExtractor:
        """The registry's factory: AgentSettings fields, `budget`, and `work_dir` (keep the agent's run directories)."""
        fields = {k: v for k, v in config.items() if k in AgentSettings.__dataclass_fields__}
        settings = AgentSettings(**fields)
        runner = ResearchAgentRunner(settings, work_dir=Path(config["work_dir"]) if config.get("work_dir") else None)
        return cls(runner, settings, config.get("budget"))

    def extract(self, task: ExtractionTask, ctx: RunContext) -> ExtractionResult:
        return self.extract_recorded(task, ctx)[0]

    def extract_recorded(self, task: ExtractionTask, ctx: RunContext) -> tuple[ExtractionResult, dict[str, Any]]:
        text = ctx.text()
        index = ctx.index()
        index = index if isinstance(index, Index) else Index(text)
        context = list(ctx.context_items())
        schema = ctx.field_schema()
        file = safe_name(task.document.id)
        concept = concept_for(task, schema, context, file, len(text))
        budget = {**self.budget, **{k: v for k, v in (task.budget.model_dump() if task.budget else {}).items() if v}}
        job = AgentJob(run_id=f"agentic-{task.task_sha256[:16]}", files={file: text}, concept=concept, budget=budget)
        try:
            record = self.runner.run(job)
        except Exception as exc:
            record = {"run_id": job.run_id, "error": redact(f"{type(exc).__name__}: {exc}")[:1000]}
        record = {**record, "concept": concept}
        self.records[task.task_sha256] = record
        return self.convert(task, record, schema, context, text, index), record

    def convert(self, task: ExtractionTask, record: dict[str, Any], schema: dict[str, Any], context: list[Item],
                text: str, index: Index) -> ExtractionResult:
        """The ExtractionResult for one agent record (pure: the same record gives the same result)."""
        base = {"extractor_id": self.spec.extractor_id, "task_sha256": task.task_sha256}
        if "error" in record:
            return ExtractionResult(**base, status="error", error=ExtractionError(reason="agent_failed",
                                                                                   detail=record["error"]))
        claims = {c["claim_id"]: c for c in record.get("claims", []) if c["status"] == "accepted"}
        items: list[Item] = []
        rejected: list[Rejected] = convert.rejected_claims(record, task.evidence_type)
        for row in (record.get("answer") or {}).get("rows", []):
            made = convert.row_item(row, task, schema, context, claims, index)
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
                                coverage=tuple(convert.coverage(text, record, scope, items)),
                                model_calls=tuple(f"{record.get('run_id')}/{c['task_id']}"
                                                  for c in record.get("model_calls", []))).canonical()
