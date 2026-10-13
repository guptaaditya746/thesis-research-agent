"""Request and response models of the backend API (docs/e2e-build-plan.md, "Backend API").

The frontend's TypeScript types are generated from the OpenAPI schema (`webapp openapi`), so every
endpoint returns one of these models and their names are the names the frontend sees. Files
written by other packages (score.json, report.json, answer keys, graph.json) keep fields this
package does not know yet: their models allow extra fields and type only what the plan fixes.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Condition = Literal["claim_on", "claim_off"]
JobState = Literal["queued", "running", "done", "failed"]
StepState = Literal["pending", "running", "done", "failed", "skipped"]
PickedBy = Literal["user", "claude", "provisional-first"]  # agent/concept_step.py PICKED_BY (WP B)
GoldState = Literal["none", "building", "draft", "reviewed"]


class Open(BaseModel):
    """A file another package writes: the plan's fields are typed, anything else is kept."""

    model_config = ConfigDict(extra="allow")


# --- app ---------------------------------------------------------------------------------------------

class Health(BaseModel):
    ok: bool
    version: str


class AppConfig(BaseModel):
    corpus: str | None
    runs_root: str
    gold_root: str
    concepts_root: str
    llm_base_url: str
    llm_key_set: bool
    argilla_url: str | None


# --- questions and concepts -------------------------------------------------------------------------

class ConceptStatus(BaseModel):
    status: Literal["none", "proposed", "picked"]
    title: str | None = None
    picked_by: str | None = None


class GoldStatus(BaseModel):
    status: Literal["none", "building", "draft", "reviewed"]
    rows: int | None = None
    facts: int | None = None


class RunCounts(BaseModel):
    claim_on: int = 0
    claim_off: int = 0


class Question(BaseModel):
    id: str
    category: str | None = None
    question: str
    source: str | None = None
    notes: str | None = None
    concept: ConceptStatus
    gold: GoldStatus
    runs: RunCounts


class Measure(Open):
    operation: str
    of: str
    group_by: str | None = None
    filter: str | None = None
    order: Literal["asc", "desc"] | None = None
    limit: int | None = None


class Column(BaseModel):
    name: str
    type: str


class NodeType(BaseModel):
    type: str


class EdgeType(BaseModel):
    source: str
    predicate: str
    target: str
    attributes: list[Column] = []


class AnswerShape(BaseModel):
    """A table (columns) or a graph (node types and edge types): the brief's answer template."""

    kind: Literal["table", "graph"]
    columns: list[Column] | None = None
    nodes: list[NodeType] | None = None
    edges: list[EdgeType] | None = None


class ConceptBrief(Open):
    """One reading of a question (agent/schemas/concept.schema.json)."""

    id: str | None = None
    title: str
    definition: str
    measure: Measure
    scope: dict[str, str]
    answer_shape: AnswerShape
    competency_questions: list[str]
    needs: list[str] | None = None


class Pick(BaseModel):
    choice: int
    title: str | None = None
    picked_by: str
    reason: str | None = None
    concept_sha256: str | None = None


class QuestionDetail(Question):
    briefs: list[ConceptBrief] = []
    picked: Pick | None = None
    concept_brief: ConceptBrief | None = Field(None, description="the frozen concept.json, once picked")


class ProposeRequest(BaseModel):
    temperature: float = Field(0.7, ge=0, le=2)
    seed: int = 1


class PickRequest(BaseModel):
    choice: int = Field(ge=1, le=5)
    picked_by: str = Field("user", min_length=1, max_length=64)
    reason: str | None = Field(None, max_length=2000)


# --- runs --------------------------------------------------------------------------------------------

class ScoreSummary(BaseModel):
    support_share: float | None = None
    fact_f1: float | None = None
    row_f1: float | None = None


class RunSummary(BaseModel):
    run_id: str
    qid: str | None
    condition: str
    seed: int | None
    temperature: float | None
    created_at: str | None
    exit_status: str = Field(description="submitted, budget, context_full, error, cut, running, incomplete, "
                                         "or another exit status the harness recorded")
    steps: int
    model_calls: int
    tokens: int
    seconds: float
    tokens_without_attach: int | None = None
    seconds_without_attach: float | None = None
    rows: int | None
    facts: int | None
    claims_accepted: int
    claims_rejected: int
    attach: Literal["not_applicable", "pending", "cut", "done"]
    verify: Literal["ok", "failed", "unknown"]
    score: ScoreSummary | None
    live: bool


class Verification(BaseModel):
    ok: bool
    errors: list[str]
    stats: dict[str, Any]


class Fact(BaseModel):
    id: str
    s: str
    p: str
    o: str | float | int | bool
    claims: list[str]
    origin: str


class AnswerRow(Open):
    """A table row (`cells`) or a graph row (source, predicate, target, ...), with its facts."""

    id: str
    facts: list[Fact]
    cells: dict[str, Any] | None = None
    source: str | None = None
    source_type: str | None = None
    predicate: str | None = None
    target: str | None = None
    target_type: str | None = None
    attributes: dict[str, Any] | None = None


class Answer(BaseModel):
    concept_sha256: str
    kind: Literal["table", "graph"]
    rows: list[AnswerRow]
    notes: str | None = None


class RunDetail(BaseModel):
    summary: RunSummary
    config: dict[str, Any]
    concept: ConceptBrief | None
    answer: Answer | None
    verify: Verification | None


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


class Highlight(BaseModel):
    start: int
    end: int


class Passage(BaseModel):
    """Offsets count Unicode code points (Python's), as the agent's anchors do; JavaScript strings count
    UTF-16 code units, which differ after any character outside the BMP (e.g. math italic letters in
    a converted PDF), so the frontend slices `text` with `highlight_utf16`."""

    paper_id: str
    title: str
    text: str = Field(description="the window of the paper's text around the span")
    highlight: Highlight | None = Field(description="the span in `text`, in code points (Python, the anchors)")
    highlight_utf16: Highlight | None = Field(None, description="the same span in UTF-16 code units: "
                                                                "text.slice(start, end) in JavaScript")
    offset: int = Field(description="raw offset of `text` in the paper file, in code points")
    length: int = Field(description="length of the whole paper file in code points")


class Verdict(Open):
    label: Literal["supports", "partial", "no"]
    rationale: str | None = None
    model: str | None = None
    prompt_sha256: str | None = None
    cached: bool | None = None


class WalkClaim(BaseModel):
    claim_id: str
    claim: Claim | None = Field(description="null when the id is not an accepted claim of this run")
    step: Step | None
    passage: Passage | None
    anchor_status: str = Field(description="ok, relocated, ambiguous, broken, or unknown (no corpus)")
    support: Verdict | None = None


class FactWalk(BaseModel):
    run_id: str
    fact: Fact
    row_id: str
    row: AnswerRow
    claims: list[WalkClaim]
    support: Verdict | None = Field(description="the best verdict over the fact's quotes (judge), or null")


class GraphNode(Open):
    id: str
    kind: Literal["paper", "entity"]
    label: str
    paper: str | None = None


class Predicate(Open):
    text: str
    curie: str
    iri: str
    vocabulary: str


class Evidence(Open):
    file: str
    paper: str | None
    start: int
    end: int


class GraphEdge(Open):
    id: str
    claim: str
    origin: str
    step_id: int
    agent_id: str
    source: str
    target: str | None
    literal: Any = None
    predicate: Predicate
    evidence: Evidence


class KnowledgeGraph(Open):
    run_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    namespaces: dict[str, str] = {}


class FactScores(Open):
    tp: int | None = None
    fp: int | None = None
    fn: int | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None


class Score(Open):
    """`<run>/score.json` (scoring, M4); only the plan's top-level fields are typed."""

    run_id: str | None = None
    qid: str | None = None
    condition: str | None = None
    seed: int | None = None
    key_version: str | None = None
    rows: FactScores | None = None
    facts: dict[str, FactScores] | None = None
    vital_recall: float | None = None
    support: dict[str, Any] | None = None
    cost: dict[str, Any] | None = None


class RunRequest(BaseModel):
    qid: str | None = Field(None, description="question id; its picked concept ($CONCEPTS/<qid>/concept.json) is used")
    concept_path: str | None = Field(None, description="a concept.json under $CONCEPTS or $RUNS instead of a qid")
    condition: Condition = "claim_on"
    temperature: float = Field(0.7, ge=0, le=2)
    seed: int = 1
    steps: int | None = Field(None, ge=1)
    tokens: int | None = Field(None, ge=1)
    sandbox: Literal["landlock", "unsandboxed"] = "landlock"
    attach: bool = Field(True, description="claim_off: run the attach step after the run")


# --- gold, results, provenance ---------------------------------------------------------------------

class GoldEntry(BaseModel):
    qid: str
    status: Literal["none", "building", "draft", "reviewed"]
    coverage: dict[str, Any] | None = None
    counts: dict[str, Any] | None = None
    key_version: str | None = None
    report: dict[str, Any] | None = None
    rows: int | None = None
    facts: int | None = None


class AnswerKey(Open):
    qid: str | None = None
    concept_sha256: str | None = None
    kind: str | None = None
    version: str | None = None
    reviewed: bool | None = None
    rows: list[dict[str, Any]] = []
    notes: Any = None


class Results(Open):
    """$RUNS/report/report.json (scoring, M4) as written: per question x condition means, paired
    differences, intervals, Wilcoxon results and the pre-registered primary test."""


class SparqlRequest(BaseModel):
    query: str = Field(min_length=1, max_length=100_000)
    run_id: str | None = None


class SparqlResult(BaseModel):
    vars: list[str]
    rows: list[dict[str, Any]]
    boolean: bool | None = Field(None, description="ASK queries: the answer (vars and rows are empty)")


class QueryResult(BaseModel):
    n: int
    name: str
    run_id: str
    rows: list[dict[str, Any]]


# --- jobs --------------------------------------------------------------------------------------------

class JobStep(BaseModel):
    name: str
    argv: list[str]
    command: str = Field(description="argv as one shell-quoted line, for reading")
    required: bool = Field(True, description="a failure fails the job (an optional step's failure is a warning)")
    needs: list[str] = Field([], description="files the step needs; it is skipped when one is missing")
    state: StepState = "pending"
    exit_code: int | None = None
    started_at: str | None = None
    ended_at: str | None = None

    @field_validator("needs", mode="before")
    @classmethod
    def _one_or_more(cls, value: Any) -> Any:
        """State files of earlier servers hold one path or null."""
        return [] if value is None else [value] if isinstance(value, str) else value


class Job(BaseModel):
    id: str
    kind: str = Field(description="concepts, run or gold; one job of a kind runs at a time")
    args: dict[str, Any]
    state: JobState
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    run_id: str | None = None
    qid: str | None = None
    exit_code: int | None = None
    error: str | None = None
    warnings: list[str] = Field([], description="optional steps that failed (the job can still be done)")
    steps: list[JobStep] = []
