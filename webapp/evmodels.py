"""Response models of the evidence-level viewer (`/api/ev`, webapp/evapi.py; docs/evidence-system.md).

The files are written by `synth`, `evidence` and `evaluation`; where those packages define pydantic models
of their own, the viewer returns them as they are (`evidence.protocol.Protocol`, `evidence.contract.Item`,
`ExtractionResult`, `ExtractorSpec`), so the frontend's generated types are the files' types. Every other
file is described here: the fields the pages use are typed, anything else is kept (`Open`), so a field an
evaluation adds later reaches the page without a change here.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from evidence.contract import ExtractionResult, ExtractorSpec, Item
from evidence.protocol import Protocol

from .models import Claim, Open, Step

Direction = Literal["supports", "contradicts", "neutral", "undetermined"]


# --- configuration ---------------------------------------------------------------------------------

class Root(BaseModel):
    path: str | None = Field(None, description="absolute path, or null when not configured")
    exists: bool = False


class EvConfig(BaseModel):
    ev: str | None = Field(None, description="$EV, the root the others default to (docs/slurm-evidence-runbook.md)")
    corpora: Root
    runs: Root
    scores: Root
    proposals: Root
    cache: Root = Field(description="the engine's record cache directory (extractor_calls.jsonl)")
    agent_work: Root = Field(description="the agentic extractor's agent run directories")
    protocols: Root


# --- corpora ---------------------------------------------------------------------------------------

class Counts(Open):
    supporting: int = 0
    contradicting: int = 0
    neutral: int = 0
    undetermined: int = 0
    duplicates: int = 0


class TruthAnswer(Open):
    """ground_truth.json `answer`: the label the corpus is built to have."""
    label: str
    supporting: list[str] = []
    contradicting: list[str] = []
    neutral: list[str] = []
    undetermined: list[str] = []
    duplicates: list[str] = []
    flags: dict[str, list[str]] = {}


class VariantInfo(Open):
    """variant.json of a counterfactual corpus (`synth variant`, F3)."""
    base_corpus_id: str
    corpus_id: str | None = None
    study: str
    paper: str | None = None
    to: str | None = None
    changed: list[dict[str, Any]] = []
    expected: dict[str, Any] = {}


class CorpusSummary(BaseModel):
    name: str = Field(description="the directory name under the corpora root")
    corpus_id: str
    level: str | None = None
    renderer: str | None = None
    seed: int | None = None
    question: str | None = None
    protocol: dict[str, Any] | None = None
    settings: dict[str, Any] | None = Field(None, description="corpus.json settings: name, studies, mix, levels and "
                                                              "the knobs (duplicates, missing, outliers, irrelevant)")
    papers: int
    fidelity_ok: int | None = Field(None, description="papers whose fidelity checks all pass")
    excluded: list[str] = []
    answer: TruthAnswer | None = None
    variant: VariantInfo | None = None
    base: str | None = Field(None, description="the base corpus of a variant, by directory name, when it is here")
    manifest_sha256: str


class CorpusPaper(BaseModel):
    id: str
    file: str
    sha256: str
    level: str | None = None
    relevant: bool = True
    direction: Direction | None = Field(None, description="the study's true effect direction")
    delta: float | None = None
    flags: list[str] = []
    duplicate_of: str | None = None
    missing: str | None = None
    fidelity_ok: bool | None = None


class CorpusDetail(CorpusSummary):
    papers_list: list[CorpusPaper]
    models: dict[str, Any] | None = None
    generator: dict[str, Any] | None = None


class Placement(Open):
    fact: str
    role: str
    paper: str
    start: int
    end: int
    exact: str


class Segment(BaseModel):
    """A piece of a paper's text: `marks` are the ids (items, facts) whose spans cover it, `roles` their roles.
    Cut on the server, in code points, so the page never converts offsets."""
    text: str
    start: int
    end: int
    marks: list[str] = []
    roles: list[str] = []


class CorpusPaperDetail(BaseModel):
    corpus: str
    paper: CorpusPaper
    text: str
    segments: list[Segment]
    study: dict[str, Any] | None = Field(None, description="the study's ground truth (conditions, metrics, "
                                                          "measurements, author claim, effect)")
    placements: list[Placement] = []
    fidelity: dict[str, Any] | None = None
    decoys: list[dict[str, Any]] = []


# --- protocols and proposals -----------------------------------------------------------------------

class ProtocolView(BaseModel):
    source: str = Field(description="repo, proposal, run")
    name: str
    path: str
    sha256: str
    yaml: str
    phases: list[str]
    protocol: Protocol | None = Field(None, description="the parsed protocol; null when it does not validate")
    error: str | None = None


class ProtocolEntry(BaseModel):
    name: str
    id: str | None = None
    version: int | None = None
    revision: int | None = None
    question: str | None = None
    sha256: str | None = None
    error: str | None = None


class ProposalSummary(BaseModel):
    name: str
    question: str | None = None
    steps: list[str] = Field(description="the steps whose files exist: frame, draft, critic, cards, freeze")
    frozen: bool
    revision: int | None = None
    protocol_sha256: str | None = None
    decided_by: dict[str, list[str]] = {}
    amendments: int = 0


class Decision(Open):
    card: str
    choice: str | None = None
    reason: str | None = None
    by: str | None = None
    value: Any = None
    default: str | None = None


class Card(Open):
    id: str
    title: str | None = None
    ask: str | None = None
    sets: list[str] = []
    options: list[dict[str, Any]] = []
    vocabulary: list[dict[str, Any]] = []
    default: str | None = None
    rationale: str | None = None
    decision: Decision | None = Field(None, description="the decision of decisions.yaml (or, once frozen, of "
                                                        "proposal.json, which records the default beside it)")


class Amendment(Open):
    revision: int
    sha256: str | None = None
    amends_sha256: str | None = None
    reason: str
    impact: list[str] = []
    before_main_run: bool | None = None
    at: str | None = None


class Check(Open):
    id: str
    kind: str | None = None
    ok: bool
    message: str | None = None


class ProposalDetail(ProposalSummary):
    frame: dict[str, Any] | None = None
    sources: dict[str, Any] | None = Field(None, description="draft.sources.json")
    draft_yaml: str | None = None
    critic: dict[str, Any] | None = None
    checks: list[Check] = Field([], description="critic.json checks (deterministic and the LLM checklist)")
    cards: list[Card] = []
    proposal: dict[str, Any] | None = Field(None, description="proposal.json, written by freeze")
    protocol: ProtocolView | None = None
    revisions: list[int] = Field([], description="the frozen and amended revisions kept as protocol.v<N>.yaml")
    amendment_log: list[Amendment] = []


# --- runs ------------------------------------------------------------------------------------------

class StudyPair(Open):
    condition: str | None = None
    measurement: str | None = None
    value: float | None = None


class StudyReason(Open):
    code: str
    text: str | None = None


class Study(Open):
    """One study of answer.json (A4 with C3 and F1); the baselines give only document and direction."""
    document: str
    direction: Direction
    delta: float | None = None
    metric: str | None = None
    treatment: StudyPair | None = None
    control: StudyPair | None = None
    author_claim: dict[str, Any] | None = None
    reason: StudyReason | None = None
    flags: list[str] = []
    duplicate_of: str | None = None
    funnel: dict[str, Any] | None = None


class Citation(Open):
    document: str
    start: int
    end: int
    score: float | None = None


class EvAnswer(Open):
    system: str
    question: str | None = None
    label: str
    counts: Counts = Counts()
    studies: list[Study] = []
    supporting: list[str] = []
    contradicting: list[str] = []
    neutral: list[str] = []
    undetermined: list[str] = []
    duplicates: list[str] = []
    flags: dict[str, list[str]] = {}
    answer_text: str | None = None
    citations: list[Citation] | None = None
    dropped_citations: list[Citation] | None = None
    retrieved: list[Citation] | None = None
    agent: dict[str, Any] | None = None


class EvRunSummary(BaseModel):
    id: str = Field(description="`<group>~<name>`: the run directory $EV_RUNS/<group>/<name>")
    group: str = Field(description="the output directory the run was written to (regex-only, cascade, rag-baseline, ...)")
    name: str
    kind: Literal["engine", "baseline"]
    system: str
    mode: str | None = Field(None, description="engine: run, replay or reexec")
    strategy: str | None = None
    selection: str | None = None
    model: str | None = None
    protocol: dict[str, Any] | None = None
    corpus_id: str | None = None
    corpus: str | None = Field(None, description="the corpus directory under the corpora root, when it is there")
    label: str | None = None
    counts: Counts | None = None
    papers: int | None = None
    cost: dict[str, Any] | None = None


class FunnelDecision(Open):
    after_round: int | None = None
    after_position: int | None = None
    complete: bool
    gap: str | None = None
    gap_types: list[str] = []


class FunnelStep(Open):
    round: int
    position: int
    types: list[str]
    calls: list[str]


class FunnelDoc(Open):
    screen: dict[str, Any] | None = None
    skipped: bool = False
    steps: list[FunnelStep] = []
    decisions: list[FunnelDecision] = []
    stopped_after: int | None = None


class CallSummary(BaseModel):
    """One extractor call of the run, from its extractor_call event (Part D: screen calls too)."""
    call_id: str
    document: str
    evidence_type: str
    extractor_id: str
    kind: str | None = Field(None, description="regex, llm, model or agent (the extractor spec's kind)")
    position: int | None = None
    status: str
    source: str | None = Field(None, description="cache or fresh")
    attempt: int = 0
    focus: str | None = Field(None, description="the gap a targeted task was made for (Part D)")
    items: int = 0
    rejected: int = 0
    model_calls: int = 0


class EvRunDetail(EvRunSummary):
    extractors: list[ExtractorSpec] = []
    settings: dict[str, Any] | None = None
    chain_head: str | None = None
    source_run: str | None = None
    answer: EvAnswer | None = None
    funnel: dict[str, FunnelDoc] | None = Field(None, description="funnel.json documents")
    documents: list[str] = Field([], description="the manifest's paper ids, in order")
    baselines: list[str] = Field([], description="baseline runs (ids) of the same corpus")
    reports: list[str] = Field([], description="score reports (ids) of this run")
    has_trace: bool = Field(False, description="baseline: the agent baseline's run directory is there")


class RunPaper(BaseModel):
    run: str
    document: str
    text: str | None = Field(None, description="null when the run's corpus is not under the corpora root")
    segments: list[Segment] = []
    items: list[Item] = []
    study: Study | None = None
    funnel: FunnelDoc | None = None
    calls: list[CallSummary] = []


class ModelCallRecord(Open):
    """One record of the engine's record cache (evidence/recording.py): request, response, usage, error."""
    id: str
    request: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    error: str | None = None
    agent_run: str | None = Field(None, description="an agentic call: the agent run's id (its trace)")


class CallDetail(BaseModel):
    run: str
    call: CallSummary
    result: ExtractionResult
    spec: ExtractorSpec | None = None
    task: dict[str, Any] | None = Field(None, description="the ExtractionTask, from the record cache")
    cached: bool = Field(description="the record cache holds this call")
    model_calls: list[ModelCallRecord] = []
    agent_runs: list[str] = Field([], description="agent run ids behind an agentic call")


class AgentTrace(BaseModel):
    run_id: str
    source: Literal["run_dir", "cache"] = Field(description="the agent's own run directory, or the record the "
                                                            "engine's cache keeps of it")
    outcome: dict[str, Any] | None = None
    concept: dict[str, Any] | None = None
    answer: dict[str, Any] | None = None
    steps: list[Step] = []
    claims: list[Claim] = []


class EvGraphNode(Open):
    id: str
    type: str
    document: str | None = None
    fields: dict[str, Any] | None = None
    found_by: list[str] = []


class EvGraphEdge(Open):
    src: str
    dst: str
    rel: str


class EvGraph(BaseModel):
    nodes: list[EvGraphNode]
    edges: list[EvGraphEdge]


# --- scores ----------------------------------------------------------------------------------------

class ScoreRef(BaseModel):
    id: str = Field(description="the directory under the scores root, parts joined by `~`")
    group: str
    name: str | None = None
    corpus_id: str | None = None
    run_id: str | None = None
    levels: list[str] = []
    strategy: str | None = None
    systems: list[str] = []


class ScoresIndex(BaseModel):
    reports: list[ScoreRef] = []
    compares: list[ScoreRef] = []
    shifts: list[ScoreRef] = []
    benchmarks: list[ScoreRef] = []


class Interval(Open):
    point: float | None = None
    low: float | None = None
    high: float | None = None
    method: str | None = None


class SynthesisScore(Open):
    system: str
    label: str | None = None
    expected_label: str | None = None
    label_correct: bool | None = None
    rows: list[dict[str, Any]] = []
    studies: list[dict[str, Any]] = []
    confusion: list[dict[str, Any]] = []
    flags: dict[str, Any] | None = None


class Report(Open):
    """report.json of `evaluate score` (evaluation/report.py): A extraction, B integration, C synthesis per
    level, intervals, locate, cascade, extractors, cost, stability, funnel."""
    corpus_id: str
    run_id: str | None = None
    question: str | None = None
    levels: list[str] = []
    extraction: dict[str, Any] | None = None
    integration: dict[str, Any] | None = None
    synthesis: list[SynthesisScore] = []
    intervals: dict[str, Any] | None = None
    locate: dict[str, Any] | None = None
    cascade: dict[str, Any] | None = None
    extractors: dict[str, Any] | None = None
    cost: dict[str, Any] | None = None
    stability: dict[str, Any] | None = None
    funnel: dict[str, Any] | None = None


class ReportView(BaseModel):
    ref: ScoreRef
    report: Report
    markdown: str | None = None


class CompareTable(BaseModel):
    ref: ScoreRef
    rows: list[dict[str, Any]]
    intervals: list[dict[str, Any]] = []
    markdown: str | None = None


class ShiftView(BaseModel):
    ref: ScoreRef
    shift: dict[str, Any]
    markdown: str | None = None


class BenchmarkView(BaseModel):
    ref: ScoreRef
    records: list[dict[str, Any]]
    markdown: str | None = None
