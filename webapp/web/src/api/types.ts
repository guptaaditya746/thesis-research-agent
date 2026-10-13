/**
 * Backend API types, written by hand from docs/e2e-build-plan.md ("Backend API", "File
 * contracts between packages") while the backend (WP E) is built in parallel.
 *
 * Every type the app uses comes from this one module, so replacing it with the types that
 * `npm run gen:api` generates from webapp/web/openapi.json (openapi-typescript) is one swap:
 * re-export the generated `components["schemas"][...]` under these names.
 *
 * Field names are the backend's (snake_case), never renamed on the way in. Fields the plan
 * names but does not spell out (ClaimRef, the report, gold counts) are typed from the files
 * they come from (agent/broker.py, agent/kg.py, the scoring contract) and marked "assumed".
 */

// --- shared ---------------------------------------------------------------------------------

export type Condition = "claim_on" | "claim_off"
export type Category = "corpus_wide" | "ambiguous"
export type PickedBy = "provisional-first" | "user" | "claude"
export type ConceptStatus = "none" | "proposed" | "picked"
export type GoldStatus = "none" | "building" | "draft" | "reviewed"
export type VerifyState = "ok" | "failed" | "unknown"
/** agent/loop.py Outcome.exit_status; null while the run is still going. */
export type ExitStatus = "submitted" | "budget" | "context_full" | "error" | string
export type Origin = "research" | "attach"
export type Phase = "research" | "conclude" | "attach" | string

/** GET /api/health */
export interface Health {
  ok: boolean
  version: string
}

/** GET /api/config */
export interface AppConfig {
  corpus: string | null
  runs_root: string
  gold_root: string
  concepts_root: string
  llm_base_url: string
  llm_key_set: boolean
  argilla_url: string | null
}

// --- questions and concepts ---------------------------------------------------------------

/** One brief of agent/schemas/concept.schema.json. */
export interface ConceptBrief {
  id?: string
  title: string
  definition: string
  measure: {
    operation: string
    of: string
    group_by?: string
    filter?: string
    order?: "asc" | "desc"
    limit?: number
  }
  scope: Record<string, string>
  answer_shape: TableShape | GraphShape
  competency_questions: string[]
  needs?: string[]
}

export interface TableShape {
  kind: "table"
  columns: { name: string; type: string }[]
}

export interface GraphShape {
  kind: "graph"
  nodes: { type: string }[]
  edges: {
    source: string
    predicate: string
    target: string
    attributes?: { name: string; type: string }[]
  }[]
}

/** GET /api/questions (one item). */
export interface QuestionSummary {
  id: string
  category: Category
  question: string
  source?: string
  notes?: string
  concept: { status: ConceptStatus; title: string | null; picked_by: PickedBy | null }
  gold: { status: GoldStatus; rows: number | null; facts: number | null }
  /** Number of runs per condition. */
  runs: { claim_on: number; claim_off: number }
}

/** $CONCEPTS/picks.json entry, as GET /api/questions/{qid} returns it. */
export interface ConceptPick {
  choice: number
  picked_by: PickedBy
  reason: string
  title?: string
  concept_sha256?: string
}

/** GET /api/questions/{qid}; also the reply of POST .../concepts/pick. */
export interface QuestionDetail extends QuestionSummary {
  briefs: ConceptBrief[]
  picked: ConceptPick | null
}

/** POST /api/questions/{qid}/concepts/propose */
export interface ProposeRequest {
  temperature: number
  seed: number
}

/** POST /api/questions/{qid}/concepts/pick; `choice` is 1-based like `agent concept pick`. */
export interface PickRequest {
  choice: number
  picked_by: PickedBy
  reason: string
}

// --- runs -----------------------------------------------------------------------------------

export interface ScoreHeadline {
  support_share: number | null
  fact_f1: number | null
  row_f1: number | null
}

/** GET /api/runs (one item). */
export interface RunSummary {
  run_id: string
  qid: string
  condition: Condition
  seed: number
  temperature: number
  created_at: string
  exit_status: ExitStatus | null
  steps: number
  model_calls: number
  tokens: number
  seconds: number
  rows: number
  facts: number
  claims_accepted: number
  claims_rejected: number
  verify: VerifyState
  score: ScoreHeadline | null
  live: boolean
}

export interface RunFilters {
  qid?: string
  condition?: Condition
}

/** POST /api/runs: either `qid` (the picked concept) or `concept_path`. */
export interface StartRunRequest {
  qid?: string
  concept_path?: string
  condition: Condition
  temperature: number
  seed: number
  steps: number
  tokens: number
  sandbox: "landlock" | "unsandboxed"
  attach: boolean
}

/** answer.json fact (agent/schemas/answer.schema.json). */
export interface AnswerFact {
  id: string
  s: string
  p: string
  o: string | number | boolean
  claims: string[]
  origin: Origin
}

export interface TableRow {
  id: string
  cells: Record<string, unknown>
  facts: AnswerFact[]
}

export interface GraphRow {
  id: string
  source: string
  source_type: string
  predicate: string
  target: string
  target_type: string
  attributes?: Record<string, unknown>
  facts: AnswerFact[]
}

export type AnswerRow = TableRow | GraphRow

export interface Answer {
  concept_sha256: string
  kind: "table" | "graph"
  rows: AnswerRow[]
  notes?: string
}

/** The run's config.json (agent/rundir.py run_config); only the fields the app reads are typed. */
export interface RunConfig {
  run_id: string
  created_at: string
  condition: Condition
  budget: { steps: number; tokens: number; announced?: boolean }
  sampling: { temperature: number; seed: number }
  prompt: { version: string; sha256: string }
  models?: { orchestrator: { alias: string; name: string; revision: string } }
  git_commit?: string
  sandbox?: Record<string, unknown>
  [key: string]: unknown
}

/** `agent verify`: chain and answer checks; `stats` is agent/verify.py stats() (nested for attach). */
export interface VerifyReport {
  ok: boolean
  errors: string[]
  stats: Record<string, unknown>
}

/** GET /api/runs/{run_id} */
export interface RunDetail {
  summary: RunSummary
  config: RunConfig
  concept: ConceptBrief
  answer: Answer | null
  verify: VerifyReport
}

/** Assumed: one claim sent in a step (an events.jsonl claim record, reduced). */
export interface ClaimRef {
  claim_id: string | null
  status: "accepted" | "rejected"
  reason: string | null
  s?: string
  p?: string
  o?: string | number | boolean
}

export interface ModelCallStats {
  tokens: number | null
  seconds: number | null
  /** parse mode (agent/parse.py), e.g. strict or lenient */
  parse: string | null
  /** what the reply was: command, final answer, none, ... */
  reply: string | null
  finish_reason: string | null
}

/** GET /api/runs/{run_id}/steps (one item). */
export interface Step {
  step: number
  phase: Phase
  model_call: ModelCallStats | null
  command: string | null
  exit_code: number | null
  timed_out: boolean
  output_head: string | null
  output_bytes: number | null
  claims: ClaimRef[]
  /** coverage reasons recorded at this step (unparsed, invalid_final_answer, ...) */
  coverage: string[]
  agent_id: string
  origin: Origin
}

/** GET /api/runs/{run_id}/claims (one item). */
export interface Claim {
  claim_id: string | null
  status: "accepted" | "rejected"
  reason: string | null
  s: string
  p: string
  o: string | number | boolean
  file: string | null
  paper_id: string | null
  quote: string
  step: number
  agent_id: string
  origin: Origin
  anchor: { start: number; end: number } | null
}

// --- knowledge graph (agent/kg.py graph.json, as is) ------------------------------------------

export interface GraphNode {
  id: string
  kind: "paper" | "entity"
  label: string
  paper?: string
}

export interface GraphEdge {
  id: string
  claim: string
  origin: Origin
  step_id: number
  agent_id: string
  source: string
  predicate: { text: string; curie: string; iri: string; vocabulary: string }
  /** node id, or null when the object is a literal */
  target: string | null
  literal: string | number | boolean | null
  evidence: { file: string; paper: string | null; start: number; end: number }
}

export interface KnowledgeGraph {
  schema_version: number
  run_id: string
  sources?: Record<string, string>
  namespaces?: Record<string, string>
  nodes: GraphNode[]
  edges: GraphEdge[]
}

// --- claim walk -------------------------------------------------------------------------------

/** GET /api/corpus/{paper_id}: `text` starts at file offset `offset`; `highlight` is in file offsets. */
export interface Passage {
  paper_id: string
  title: string | null
  text: string
  highlight: { start: number; end: number }
  offset: number
}

/** gold/judge.py support() verdict. */
export interface Verdict {
  label: "supports" | "partial" | "no"
  rationale: string
  model: string
  prompt_sha256: string
  cached: boolean
}

export interface WalkClaim {
  claim: Claim
  step: Step
  passage: Passage
}

/** GET /api/runs/{run_id}/facts/{fact_id}/walk */
export interface FactWalk {
  fact: AnswerFact
  row_id: string
  claims: WalkClaim[]
  support: Verdict | null
}

// --- score (scoring contract, <run>/score.json) ------------------------------------------------

export interface PRF {
  tp: number
  fp: number
  fn: number
  precision: number | null
  recall: number | null
  f1: number | null
}

/** Assumed optional detail: which facts matched the key, were missed or were wrong. */
export interface FactMatches {
  matched: { fact_id: string; key_fact_id: string }[]
  missed: string[]
  wrong: string[]
}

/** GET /api/runs/{run_id}/score */
export interface Score {
  run_id: string
  qid: string
  condition: Condition
  seed: number
  exit_status: ExitStatus | null
  verify_ok: boolean
  key_version: string
  rows: PRF
  facts: { strict: PRF; normalised: PRF; soft: PRF }
  vital_recall: number | null
  support: {
    facts: number
    with_claims: number
    supports: number
    partial: number
    no: number
    unsourced: number
    support_share: number | null
  }
  cost: {
    steps: number
    model_calls: number
    tokens: number
    tokens_without_attach: number
    seconds: number
    seconds_without_attach: number
    claim_steps: number
    claim_step_tokens: number
  }
  matches?: FactMatches
}

// --- gold ---------------------------------------------------------------------------------------

export interface WilsonRate {
  rate: number | null
  low: number | null
  high: number | null
  n?: number
}

/** gold report.json (C2), reduced. Assumed field names. */
export interface GoldReport {
  kappa: { value: number | null; low: number | null; high: number | null; n?: number } | null
  triage_miss: WilsonRate | null
  screening_false_negative: WilsonRate | null
}

/** GET /api/gold (one item). */
export interface GoldSummary {
  qid: string
  status: GoldStatus
  coverage: { papers: number; relevant: number; not_relevant: number; no_text: number; error: number } | null
  /** doc.json counts plus review progress; assumed keys: candidates, rows, facts, pool, reviewed */
  counts: Record<string, number>
  key_version: string | null
  report: GoldReport | null
}

export interface KeyFact {
  id: string
  s: string
  p: string
  o: string | number | boolean
  paper_id: string
  quote: string
  vital: boolean
  candidate_id: string
}

/** GET /api/gold/{qid}/key: key.json or key.draft.json */
export interface AnswerKey {
  qid: string
  concept_sha256: string
  kind: "table" | "graph"
  version: string
  reviewed: boolean
  rows: KeyRow[]
  notes?: string
}

export type KeyRow = (Omit<TableRow, "facts"> | Omit<GraphRow, "facts">) & { facts: KeyFact[] }

// --- results ($RUNS/report/report.json) -----------------------------------------------------------

/** Assumed: an interval as the scoring report writes it (BCa bootstrap or Wilson). */
export interface Interval {
  low: number
  high: number
  level?: number
  method?: string
}

export interface MetricStat {
  mean: number | null
  ci: Interval | null
  n: number
}

/** Metrics the report aggregates per condition (fact_f1 = soft fact F1). */
export type MetricName =
  | "support_share"
  | "fact_precision"
  | "fact_recall"
  | "fact_f1"
  | "row_f1"
  | "vital_recall"
  | "unsourced_share"
  | "tokens"
  | "tokens_without_attach"
  | "seconds"
  | "seconds_without_attach"

export interface PairedTest {
  metric: MetricName
  n: number
  mean_difference: number | null
  ci: Interval | null
  wilcoxon: { statistic: number | null; p_value: number | null } | null
}

export interface PrimaryTest extends PairedTest {
  hypothesis: string
  test: string
  alternative: "two-sided" | "greater" | "less"
  alpha: number
  significant: boolean | null
}

export interface QuestionResult {
  qid: string
  category: Category
  runs: Record<Condition, number>
  claim_on: Partial<Record<MetricName, number | null>>
  claim_off: Partial<Record<MetricName, number | null>>
}

/** GET /api/results. Assumed shape (WP D owns it); src/lib/results.ts is the only reader. */
export interface ResultsReport {
  generated_at: string
  key_version: string | null
  n_questions: number
  repeats: number
  conditions: Record<Condition, Partial<Record<MetricName, MetricStat>>>
  per_question: QuestionResult[]
  paired: Partial<Record<MetricName, PairedTest>>
  primary: PrimaryTest | null
}

// --- provenance queries ---------------------------------------------------------------------------

/** POST /api/sparql */
export interface SparqlRequest {
  query: string
  run_id?: string
}

/** Rows may come as objects keyed by variable or as arrays in `vars` order. */
export interface SparqlResult {
  vars: string[]
  rows: (Record<string, unknown> | unknown[])[]
}

/** The five queries of agent/queries.py; the parameters each takes. */
export type ProvQueryNumber = 1 | 2 | 3 | 4 | 5
export type ProvQueryParams = Partial<Record<"edge" | "fact" | "claim" | "step" | "agent", string>>

// --- jobs -------------------------------------------------------------------------------------------

export type JobState = "queued" | "running" | "done" | "failed"

/** GET /api/jobs, /api/jobs/{id}; returned by every POST that starts work. */
export interface Job {
  id: string
  kind: string
  args: string[] | Record<string, unknown>
  state: JobState
  started_at: string | null
  ended_at: string | null
  run_id?: string | null
  exit_code: number | null
}

// --- streams ----------------------------------------------------------------------------------------

/** One events.jsonl record (agent/broker.py), as `event: record` of /api/runs/{id}/stream sends it. */
export interface EventRecord {
  subtype: "ai_model_invocation" | "agent_tool" | "claim" | "coverage" | "spawn" | "concept_pick" | string
  step_id: number
  task_id?: string
  agent_id?: string
  parent_task_id?: string | null
  status?: string
  started_at?: string
  ended_at?: string
  used?: Record<string, unknown>
  generated?: Record<string, unknown>
  custom_metadata?: Record<string, unknown>
  hash?: string
}
