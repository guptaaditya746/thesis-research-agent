"""Models shared by the backend's parts: the app's health, the research agent's trace (steps and claims, shown
for the agentic extractor's calls and the agent baseline; webapp/agenttrace.py) and the jobs (webapp/jobs.py).

The frontend's TypeScript types are generated from the OpenAPI schema (`webapp openapi`), so every endpoint
returns one of these models (or one of webapp/evmodels.py) and their names are the names the frontend sees.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

JobState = Literal["queued", "running", "done", "failed"]
StepState = Literal["pending", "running", "done", "failed", "skipped"]
Lane = Literal["model", "cpu"]


class Health(BaseModel):
    ok: bool
    version: str


# --- the research agent's trace ---------------------------------------------------------------------------

class ModelCall(BaseModel):
    task_id: str
    status: str
    tokens: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    seconds: float | None = None
    parse: str | None = None
    reply: str | None = None
    finish_reason: str | None = None
    final_answer: bool = False
    error: str | None = None


class ClaimRef(BaseModel):
    claim_id: str | None
    status: Literal["accepted", "rejected"]
    reason: str | None = None
    s: Any = None
    p: Any = None
    o: Any = None


class Step(BaseModel):
    step: int
    agent_id: str
    origin: str = Field(description="research, attach, concept or batch")
    phase: str | None = Field(None, description="research, conclude, attach, ... (the model call's phase)")
    started_at: str | None = None
    ended_at: str | None = None
    model_call: ModelCall | None = None
    command: str | None = None
    exit_code: int | None = None
    timed_out: bool = False
    output_head: str | None = None
    output_bytes: int | None = None
    output_file: str | None = None
    repeat: int | None = None
    claims: list[ClaimRef] = []
    coverage: list[str] = []
    spawned: list[str] = Field([], description="subagents started in this step")
    fact_id: str | None = Field(None, description="attach step: the answer fact this step works on")


class Anchor(BaseModel):
    start: int
    end: int


class Claim(BaseModel):
    claim_id: str | None
    task_id: str
    status: Literal["accepted", "rejected"]
    reason: str | None = None
    s: Any = None
    p: Any = None
    o: Any = None
    file: str | None = None
    paper_id: str | None = None
    quote: str | None = Field(None, description="accepted: the exact text anchored in the corpus; "
                                                "rejected: the quote as sent")
    quote_submitted: str | None = None
    step: int
    agent_id: str
    origin: str
    anchor: Anchor | None = None


# --- jobs --------------------------------------------------------------------------------------------

class JobStep(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)  # every field is always sent

    name: str
    argv: list[str]
    command: str = Field(description="argv as one shell-quoted line, for reading")
    required: bool = Field(True, description="a failure fails the job (an optional step's failure is a warning)")
    needs: list[str] = Field([], description="files the step needs; it is skipped when one is missing")
    state: StepState = "pending"
    exit_code: int | None = None
    started_at: str | None = None
    ended_at: str | None = None
    pid: int | None = Field(None, description="the running command's process id (also its process group's)")
    pid_start: str | None = Field(None, description="the process's start time (/proc/<pid>/stat), so a reused pid "
                                                   "is never taken for the job's process")

    @field_validator("needs", mode="before")
    @classmethod
    def _one_or_more(cls, value: Any) -> Any:
        """State files of earlier servers hold one path or null."""
        return [] if value is None else [value] if isinstance(value, str) else value


class Job(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    id: str
    kind: str = Field(description="synth, run, rag-baseline, agent-baseline, score, compare, propose, freeze")
    lane: Lane = Field("cpu", description="model: calls a model, queued one (WEBAPP_MODEL_JOBS) at a time; "
                                          "cpu: no model call, runs beside them (WEBAPP_CPU_JOBS at a time)")
    args: dict[str, Any] = Field(description="the request the job was made from")
    refs: dict[str, str] = Field({}, description="what the job writes, as viewer ids: corpus, run, score, proposal")
    state: JobState
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    exit_code: int | None = None
    error: str | None = None
    warnings: list[str] = Field([], description="optional steps that failed (the job can still be done)")
    failed_calls: int | None = Field(None, description="an engine run's extractor calls the model gateway or the "
                                                       "GLiNER service failed (calls/*.json status error or partial "
                                                       "with reason model_call or service_call): done, but with "
                                                       "failed calls")
    orphaned: bool = Field(False, description="the server that started it stopped while its process ran on; this "
                                              "server watches the process and can cancel it")
    steps: list[JobStep] = []
