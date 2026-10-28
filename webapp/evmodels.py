"""Response models of the evidence-level viewer (`/api/ev`, webapp/evapi.py; docs/evidence-system.md).

The files are written by `synth`, `evidence` and `evaluation`; where those packages define pydantic models
of their own, the viewer returns them as they are (`evidence.protocol.Protocol`, `evidence.contract.Item`,
`ExtractionResult`, `ExtractorSpec`), so the frontend's generated types are the files' types. Every other
file is described here: the fields the pages use are typed, anything else is kept (`Open`), so a field an
evaluation adds later reaches the page without a change here.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, TypeAdapter, model_validator

from evidence.contract import ExtractionResult, ExtractorSpec, Item
from evidence.protocol import Kind, Protocol

from .models import Claim, Step

Direction = Literal["supports", "contradicts", "neutral", "undetermined"]


class Base(BaseModel):
    """A response: a field with a default is always sent, so the schema (and the generated type) says required."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class Open(Base):
    """A file another package writes: the fields the pages use are typed, anything else is kept."""

    model_config = ConfigDict(extra="allow", json_schema_serialization_defaults_required=True)


# --- configuration ---------------------------------------------------------------------------------

class Root(Base):
    path: str | None = Field(None, description="absolute path, or null when not configured")
    exists: bool = False


class EvConfig(Base):
    ev: str | None = Field(None, description="$EV, the root the others default to (docs/slurm-evidence-runbook.md)")
    corpora: Root
    runs: Root
    scores: Root
    proposals: Root
    cache: Root = Field(description="the engine's record cache directory (extractor_calls.jsonl)")
    agent_work: Root = Field(description="the agentic extractor's agent run directories")
    protocols: Root
    questions: Root = Field(description="the questions file (evidence/questions.yaml; `exists`: the file is there)")
    jobs: Root = Field(description="$EV/.jobs: the state and logs of the jobs the app starts (none without $EV)")
    user: str = Field(description="who decides a card in the app (`by` in decisions.yaml, $WEBAPP_USER)")
    default_model: str = Field(description="the model alias every model job uses unless told otherwise (orch-model)")
    llm_base_url: str = Field(description="the model gateway the jobs reach ($LITELLM_BASE_URL)")
    llm_key_set: bool = Field(description="whether $LITELLM_MASTER_KEY is set in the server's environment")
    agent_root: str | None = Field(None, description="$AGENT_ROOT, the agent baseline's pinned toolchain")
    model_jobs: int = Field(description="model jobs that run at a time; the rest queue")
    levels: list[str] = Field(description="the synthetic corpus levels a template build can write (synth/levels.py)")


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


class CorpusSource(Open):
    """source.json of a corpus of real papers (`evidence fetch`, evidence/arxiv.py)."""
    kind: str = Field(description="arxiv")
    query: str | None = None
    category: str | None = None
    fetched: str | None = Field(None, description="when it was fetched (ISO 8601, UTC)")
    ground_truth: bool = False
    papers: int | None = None
    skipped: list[dict[str, Any]] = Field([], description="papers whose PDF could not be fetched or converted, and why")


class CorpusSummary(Base):
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
    ground_truth: bool = Field(True, description="false for a demonstration corpus of real papers (source.json "
                                                 "`ground_truth: false`, `evidence fetch`): nothing to score against")
    source: CorpusSource | None = Field(None, description="source.json: where the papers came from (arXiv)")


class CorpusPaper(Base):
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


class Segment(Base):
    """A piece of a paper's text: `marks` are the ids (items, facts) whose spans cover it, `roles` their roles.
    Cut on the server, in code points, so the page never converts offsets."""
    text: str
    start: int
    end: int
    marks: list[str] = []
    roles: list[str] = []


class CorpusPaperDetail(Base):
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

class ProtocolView(Base):
    source: str = Field(description="repo, proposal, run")
    name: str
    path: str
    sha256: str
    yaml: str
    phases: list[str]
    protocol: Protocol | None = Field(None, description="the parsed protocol; null when it does not validate")
    error: str | None = None


class ProtocolEntry(Base):
    name: str
    id: str | None = None
    version: int | None = None
    revision: int | None = None
    question: str | None = None
    sha256: str | None = None
    error: str | None = None


class ProposalSummary(Base):
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
    default: str | None = None
    rationale: str | None = None
    decision: Decision | None = Field(None, description="the decision of decisions.yaml (or, once frozen, of "
                                                        "proposal.json, which records the default beside it)")
    raw_decision: Any = Field(None, description="the card's entry in decisions.yaml as written, when it is not a "
                                                "decision's shape (a hand edit gone wrong)")
    problems: list[str] = Field([], description="what freeze would refuse about this card's decision")


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


class Waiver(Base):
    """A failed critic check a person accepted in decisions.yaml."""

    check: str
    reason: str
    by: str


class ProposalDetail(ProposalSummary):
    frame: dict[str, Any] | None = None
    sources: dict[str, Any] | None = Field(None, description="draft.sources.json")
    draft_yaml: str | None = None
    critic: dict[str, Any] | None = None
    checks: list[Check] = Field([], description="critic.json checks (deterministic and the LLM checklist)")
    cards: list[Card] = []
    proposal: dict[str, Any] | None = Field(None, description="proposal.json, written by freeze, without the frame, "
                                                              "sources and critic it repeats")
    protocol: ProtocolView | None = None
    revisions: list[int] = Field([], description="the frozen and amended revisions kept as protocol.v<N>.yaml")
    amendment_log: list[Amendment] = []
    decision_problems: list[str] = Field([], description="before freeze: everything freeze would refuse in "
                                                         "decisions.yaml (evidence/propose/cards.validate)")
    waivers: list[Waiver] = Field([], description="before freeze: the waivers decisions.yaml holds; a save that "
                                                  "does not send one back removes it")
    decisions_sha256: str | None = Field(None, description="sha256 of decisions.yaml as read; a PUT of the decisions "
                                                           "sends it back and is refused if the file changed since")


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


class EffectAnswer(Open):
    """An effect answer: today's shape, no `kind` key (old answer.json files have none)."""
    kind: Literal["effect"] = "effect"
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


class InventoryEntry(Open):
    name: str
    aliases: list[str] = []
    papers: list[str] = []
    items: list[str] = []


class InventoryAnswer(Open):
    """evidence/kinds/inventory.py: every distinct item of one type the papers report."""
    kind: Literal["inventory"]
    system: str
    target: str | None = None
    entries: list[InventoryEntry] = []


class ConsistencyStudy(Open):
    document: str
    claim: Direction | None = None
    direction: Direction | None = None
    agrees: bool | None = None
    reason: StudyReason | None = None


class ConsistencyAnswer(Open):
    """evidence/kinds/consistency.py: does what the authors claim agree with what they measured?"""
    kind: Literal["consistency"]
    system: str
    metric: str | None = None
    studies: list[ConsistencyStudy] = []
    agreeing: list[str] = []
    disagreeing: list[str] = []
    undetermined: list[str] = []


class BestStudy(Open):
    document: str
    winner: str | None = None
    tied: list[str] = []
    values: dict[str, float] = {}
    reason: StudyReason | None = None


class BestAnswer(Open):
    """evidence/kinds/best.py: which method kind has the top value inside each paper, and wins most papers."""
    kind: Literal["best"]
    system: str
    metric: str | None = None
    studies: list[BestStudy] = []
    wins: dict[str, int] = {}
    winner: str | None = None
    tied: list[str] = []


def _answer_kind(value: Any) -> str:
    """The union's tag: the `kind` key, effect when there is none (answer.json before the question kinds)."""
    kind = value.get("kind") if isinstance(value, dict) else getattr(value, "kind", None)
    if not isinstance(kind, str):
        return "effect"
    return kind if kind in KNOWN_ANSWER_KINDS else "unknown"


class UnknownAnswer(Open):
    """An answer.json of a kind this viewer does not know: kept as written so the run page still loads."""
    kind: str
    system: str | None = None


KNOWN_ANSWER_KINDS = ("effect", "inventory", "consistency", "best")
EvAnswer = Annotated[
    Annotated[EffectAnswer, Tag("effect")] | Annotated[InventoryAnswer, Tag("inventory")]
    | Annotated[ConsistencyAnswer, Tag("consistency")] | Annotated[BestAnswer, Tag("best")]
    | Annotated[UnknownAnswer, Tag("unknown")],
    Discriminator(_answer_kind),
]
EV_ANSWER: TypeAdapter[Any] = TypeAdapter(EvAnswer)


class EvRunSummary(Base):
    id: str = Field(description="`<group>~<name>`: the run directory $EV_RUNS/<group>/<name>")
    group: str = Field(description="the output directory the run was written to (regex-only, cascade, rag-baseline, ...)")
    name: str
    kind: Literal["engine", "baseline"]
    complete: bool = Field(True, description="engine: run.json is written (else the run crashed or is still running; "
                                             "its events and calls are shown, its answer is not there yet)")
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
    error_calls: int = Field(0, description="engine: extractor calls the model gateway or the GLiNER service failed, "
                                            "in whole or in part (calls/*.json status error or partial with reason "
                                            "model_call or service_call); `--retry-errors` runs them again")


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


class CallSummary(Base):
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


class RunPaper(Base):
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


class CallDetail(Base):
    run: str
    call: CallSummary
    result: ExtractionResult
    spec: ExtractorSpec | None = None
    task: dict[str, Any] | None = Field(None, description="the ExtractionTask, from the record cache")
    cached: bool = Field(description="the record cache holds this call")
    record_note: str | None = Field(None, description="why the cache cannot hold this call (a fresh call of a re-execution)")
    model_calls: list[ModelCallRecord] = []
    agent_runs: list[str] = Field([], description="agent run ids behind an agentic call")


class TraceRow(Base):
    """One step of the run trace: a warm-pass model call (calls.jsonl) or an engine event (events.jsonl)."""
    n: int = Field(description="row number from 1, stable while the run grows; `after` pages by it")
    phase: Literal["warm", "run"]
    at: str | None = Field(None, description="ISO time: a call's start, an event's end (an extractor_call's start)")
    step: Literal["screen", "locate", "extractor_call", "merge", "completeness", "synthesis", "call"]
    document: str | None = None
    evidence_type: str | None = None
    extractor: str | None = None
    status: str
    source: str | None = Field(None, description="cache or fresh")
    seconds: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    call: str | None = Field(None, description="what GET /runs/{run}/calls/{call} takes: a call id (events) or a calls.jsonl key")


class TracePage(Base):
    rows: list[TraceRow]
    next: int = Field(description="pass as `after` for the following page")
    done: bool = Field(description="answer.json is written: the run has finished")


class AgentTrace(Base):
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


class EvGraph(Base):
    nodes: list[EvGraphNode]
    edges: list[EvGraphEdge]


# --- scores ----------------------------------------------------------------------------------------

class ScoreRef(Base):
    id: str = Field(description="the directory under the scores root, parts joined by `~`")
    group: str
    name: str | None = None
    corpus_id: str | None = None
    run_id: str | None = None
    levels: list[str] = []
    strategy: str | None = None
    systems: list[str] = []


class ScoresIndex(Base):
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


class ReportView(Base):
    ref: ScoreRef
    report: Report
    markdown: str | None = None


class CompareTable(Base):
    ref: ScoreRef
    rows: list[dict[str, Any]]
    intervals: list[dict[str, Any]] = []
    markdown: str | None = None


class ShiftView(Base):
    ref: ScoreRef
    shift: dict[str, Any]
    markdown: str | None = None


class BenchmarkView(Base):
    ref: ScoreRef
    records: list[dict[str, Any]]
    markdown: str | None = None


# --- questions (evidence/questions.yaml; webapp/evquestions.py) --------------------------------------------

class Question(Base):
    id: str
    question: str
    kind: Kind = Field("effect", description="what the question asks: an effect, an inventory, whether claims "
                                            "agree with results (consistency), or which method kind is best")
    protocol: str | None = Field(None, description="the hand-written protocol's name under the protocols directory "
                                                   "(`/api/ev/protocols/{name}`), or null: the question needs a "
                                                   "proposal")
    agentic_protocol: str | None = Field(None, description="its variant with the agentic extractor, when there is one")
    proposals: list[str] = Field([], description="proposals (by directory name) whose frame asks this question")


# --- jobs: what the app can start (webapp/evjobs.py) -------------------------------------------------------

NAME = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"   # webapp/files.py ID: a directory name, never a flag or a path
MODEL = r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,127}$"   # a LiteLLM alias (orch-model); never starts with a dash
Name = Annotated[str, Field(pattern=NAME)]
Level = Literal["explicit", "paraphrased", "distributed", "complex", "contradictory"]   # synth/levels.py LEVELS


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SynthRequest(Request):
    """`synth build --renderer template` (no model); writes `<name>-<level>` per level and `<name>-mixed`."""
    name: Name
    seed: int = Field(1, ge=0, le=2**31 - 1)
    studies: int = Field(20, ge=1, le=200)
    levels: list[Level] = Field(["explicit", "paraphrased", "distributed", "complex", "contradictory"], min_length=1)
    duplicates: int = Field(0, ge=0, le=50)
    missing: int = Field(0, ge=0, le=50)
    outliers: int = Field(0, ge=0, le=50)
    irrelevant: int = Field(0, ge=0, le=50)


class FetchRequest(Request):
    """`evidence fetch` (evidence/arxiv.py): real papers from the arXiv API into `$EV/corpora/<name>`, a
    demonstration corpus with no ground truth. The name defaults to `arxiv-<slug of the query>-<yyyymmdd>`."""
    query: str = Field(min_length=3, max_length=300, pattern=r"^[^\x00-\x1f\x7f]*\w[^\x00-\x1f\x7f]*$",
                       description="search words; every word must occur in the paper's arXiv record")
    max_papers: int = Field(10, ge=1, le=50, description="papers to fetch (one request every three seconds)")
    category: str | None = Field(None, pattern=r"^[a-z][a-z-]*(\.[A-Za-z][A-Za-z-]*)?$",
                                 description="an arXiv category, e.g. cs.CL")
    name: Name | None = Field(None, description="the corpus directory; default arxiv-<slug>-<yyyymmdd>")


class ProtocolRef(Request):
    source: Literal["repo", "proposal"] = Field(description="repo: a hand-written protocol under the protocols "
                                                            "directory; proposal: a frozen proposal's protocol.yaml")
    name: Name


class RunGroup(Base):
    """The group `evidence run` writes under for a protocol and selection (`runs/<group>/<name>`)."""
    group: str


class RunRequest(Request):
    """`evidence run` over one corpus into `$EV/runs/<group>/<name>` (the runbook's layout)."""
    corpus: Name
    protocol: ProtocolRef
    extractors: Literal["regex-only", "cascade"] = "cascade"
    strategy: Literal["all", "gaps"] = "gaps"
    model: str = Field("orch-model", pattern=MODEL)
    group: Name | None = Field(None, description="default as the runbook names it: regex-only, cascade, "
                                                 "cascade-gaps, agentic, agentic-gaps, or <protocol>-...")
    name: Name | None = Field(None, description="default: the corpus name")
    retry_errors: bool = Field(False, description="`--retry-errors`: run cached error results again instead of "
                                                  "taking them from the record cache")


class RagBaselineRequest(Request):
    """`evaluate rag-baseline --question-id <question>` into `$EV/runs/rag-baseline/<corpus>` (rag-factuality),
    else `$EV/runs/rag-baseline/<corpus>.<question>`."""
    corpus: Name
    question: Name = Field(description="the question's id in the questions file: the question the baseline answers")
    model: str = Field("orch-model", pattern=MODEL)
    retrieval: Literal["global", "per_paper"] = "global"
    k: int = Field(8, ge=1, le=100)


class AgentBaselineRequest(Request):
    """`evaluate agent-baseline --question-id <question>` into `$EV/runs/agent-baseline/<corpus>` (rag-factuality),
    else `$EV/runs/agent-baseline/<corpus>.<question>`."""
    corpus: Name
    question: Name = Field(description="the question's id in the questions file: the question the baseline answers")
    model: str = Field("orch-model", pattern=MODEL)


class ScoreRequest(Request):
    """`evaluate score --question-id <the question the run's protocol asks>` of an engine run (with the corpus's
    baselines of that question beside it) into `$EV/scores/<group>/<name>`."""
    run: str = Field(description="the run's id, `<group>~<name>`")


class CompareRequest(Request):
    """`evaluate compare` over score reports into `$EV/scores/<name>`."""
    reports: list[str] = Field(min_length=2, max_length=60, description="score ids (`<group>~<name>`)")
    name: Name = Field(description="the output directory under the scores root, e.g. compare-funnel-<corpus>")


class ProposeRequest(Request):
    """The proposal flow's frame, draft, critic and cards steps into `$EV/proposals/<proposal>` (resumed from the
    first step whose file is missing)."""
    proposal: Name
    question: Name | None = Field(None, description="the question's id in the questions file")
    text: str | None = Field(None, min_length=10, max_length=600,
                             description="a question the person typed, instead of one of the questions file")
    model: str = Field("orch-model", pattern=MODEL)

    @model_validator(mode="after")
    def one_question(self) -> "ProposeRequest":
        if (self.question is None) == (self.text is None):
            raise ValueError("give either `question` (an id of the questions file) or `text` (a typed question)")
        return self


class FreezeRequest(Request):
    proposal: Name


class KindRequest(Request):
    """Say which kind of question a proposal asks, instead of the model's guess: the draft, critic and cards
    steps run again from that kind's template (the cards and decisions made so far are dropped)."""
    kind: Literal["effect", "inventory", "consistency", "best"]
    model: str = Field("orch-model", pattern=MODEL)


class DecisionEntry(Request):
    card: Name
    choice: Name = Field(description="an option id of the card, or custom (with a value)")
    value: Any = Field(None, description="only with choice custom: the value in the card's shape")
    reason: str = Field(max_length=4000)
    by: str = Field(min_length=1, max_length=128,
                    description="who decided: `model` (the model's default, kept), the server's $WEBAPP_USER (decided "
                                "in the app), or the name decisions.yaml already has for this card (kept as it is)")


class WaiverEntry(Request):
    check: Name = Field(description="the critic check id the person accepts as failing")
    reason: str = Field(max_length=4000, description="why it is safe: at least 10 characters (cards.waivers)")


class DecisionsRequest(Request):
    decisions: list[DecisionEntry] = Field(max_length=50)
    waivers: list[WaiverEntry] = Field([], max_length=20, description="serious problems the person waives; written to "
                                       "decisions.yaml as {check, reason, by: the server's user}")
    base_sha256: str | None = Field(description="decisions_sha256 of the proposal as the form loaded it (null: there "
                                                "was no decisions.yaml); refused with 409 if the file changed since")
    force: bool = Field(False, description="write even though decisions.yaml changed since it was loaded")


class DecisionsResult(Base):
    written: str = Field(description="the decisions.yaml written")
    sha256: str = Field(description="its sha256 now: the base_sha256 of the next PUT")
    problems: list[str] = Field(description="what `evidence propose freeze` would refuse (cards.validate)")


class CheckRequest(Request):
    decisions: list[DecisionEntry] = Field(max_length=50, description="the decisions as the form holds them now")


class CheckProblem(Base):
    check: str = Field(description="a critic check id, or `decision` for a decision cards.validate refuses")
    severity: Literal["serious", "advisory"] = Field(description="serious: freeze refuses it unless a person waives it")
    message: str
    card: str | None = Field(description="the card to look at, when one is the cause")


class CheckResult(Base):
    problems: list[CheckProblem]


class PreviewHit(Base):
    start: int
    end: int
    card: str = Field(description="the card whose terms hit here: screen, roles, metrics or method_kinds")
    what: str = Field(description="the term or name that hit")


class PreviewResult(Base):
    text: str
    hits: list[PreviewHit]
