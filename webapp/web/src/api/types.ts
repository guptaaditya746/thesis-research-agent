/**
 * Backend API types (docs/e2e-build-plan.md, "Backend API"), written by hand, field for field, from
 * the backend's OpenAPI schema (webapp/web/openapi.json of WP E, made by `webapp openapi` from
 * webapp/models.py). The interface names are the schema names, and a field is optional (`?`) where
 * the schema does not require it, so swapping this module for the types `npm run gen:api` generates
 * (openapi-typescript) is one step: `export type RunSummary = components["schemas"]["RunSummary"]`
 * and so on, here, with nothing else in the app changing.
 *
 * Field names are the backend's (snake_case), never renamed on the way in. Values the schema types
 * as "any" (a claim's s, p, o) are `unknown`. Where the backend passes another package's file
 * through as an open object (score.json, report.json, the gold report, graph.json, config.json),
 * the second half of this module types that file from its writer's documentation (scoring/README.md,
 * gold/REVIEW.md, gold/README.md, agent/rundir.py, agent/kg.py). Those "file contract" types stay
 * hand-written after the swap; src/lib reads them defensively, since a file of an older writer may
 * lack fields.
 */

// --- shared value types ------------------------------------------------------------------------

export type Condition = "claim_on" | "claim_off"
export type Category = "corpus_wide" | "ambiguous"
/** agent/concept_step.py PICKED_BY */
export type PickedBy = "user" | "claude" | "provisional-first"
export type ConceptState = "none" | "proposed" | "picked"
export type GoldState = "none" | "building" | "draft" | "reviewed"
export type VerifyState = "ok" | "failed" | "unknown"
export type AttachState = "not_applicable" | "pending" | "cut" | "done"
export type AnswerFrom = "final" | "draft" | "none"
export type JobState = "queued" | "running" | "done" | "failed"
export type JobStepState = "pending" | "running" | "done" | "failed" | "skipped"
export type SupportLabel = "supports" | "partial" | "no"
/** A fact's label as scoring defines it (FactWalk.label, score.json detail.support[].label). */
export type FactLabel = SupportLabel | "unsourced" | "pending"

// --- app -----------------------------------------------------------------------------------------

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

// --- questions and concepts --------------------------------------------------------------------

export interface ConceptStatus {
  status: ConceptState
  title?: string | null
  /** user, claude or provisional-first (the pick record's) */
  picked_by?: string | null
}

export interface GoldStatus {
  status: GoldState
  rows?: number | null
  facts?: number | null
  /** the gold builder's own stage (progress.json: starting, building, failed, writing, done) */
  stage?: string | null
}

export interface RunCounts {
  claim_on?: number
  claim_off?: number
}

/** GET /api/questions (one item) */
export interface Question {
  id: string
  category?: string | null
  question: string
  source?: string | null
  notes?: string | null
  concept: ConceptStatus
  gold: GoldStatus
  /** runs per condition on the question's current concept */
  runs: RunCounts
}

export interface Measure {
  operation: string
  of: string
  group_by?: string | null
  filter?: string | null
  order?: "asc" | "desc" | null
  limit?: number | null
  [extra: string]: unknown
}

export interface Column {
  name: string
  type: string
}

export interface NodeType {
  type: string
}

export interface EdgeType {
  source: string
  predicate: string
  target: string
  attributes?: Column[]
}

/** A table (columns) or a graph (node types and edge types): the brief's answer template. */
export interface AnswerShape {
  kind: "table" | "graph"
  columns?: Column[] | null
  nodes?: NodeType[] | null
  edges?: EdgeType[] | null
}

/** One reading of a question (agent/schemas/concept.schema.json). */
export interface ConceptBrief {
  id?: string | null
  title: string
  definition: string
  measure: Measure
  scope: Record<string, string>
  answer_shape: AnswerShape
  competency_questions: string[]
  needs?: string[] | null
  [extra: string]: unknown
}

/** The current pick: the last `concept_pick` record of the question's session. */
export interface Pick {
  /** 1-based, as `agent concept pick` takes it */
  choice: number
  title?: string | null
  picked_by: string
  reason?: string | null
  concept_sha256?: string | null
  /** the concept this pick replaced, if it changed one */
  replaces_concept_sha256?: string | null
}

/** GET /api/questions/{qid}; also the reply of POST .../concepts/pick */
export interface QuestionDetail extends Question {
  briefs?: ConceptBrief[]
  picked?: Pick | null
  /** the frozen concept.json, once picked */
  concept_brief?: ConceptBrief | null
}

/** POST /api/questions/{qid}/concepts/propose */
export interface ProposeRequest {
  temperature?: number
  seed?: number
}

/** POST /api/questions/{qid}/concepts/pick */
export interface PickRequest {
  choice: number
  picked_by?: PickedBy
  reason?: string | null
  /** change the pick although runs use the current concept (409 otherwise) */
  force?: boolean
}

// --- runs ----------------------------------------------------------------------------------------

export interface ScoreSummary {
  support_share?: number | null
  /** soft fact F1, else normalised, else strict */
  fact_f1?: number | null
  row_f1?: number | null
  /** v1, or v1-draft */
  key_version?: string | null
  /** scored against the draft key: tests the pipeline, never a result */
  provisional?: boolean | null
}

/** GET /api/runs (one item) */
export interface RunSummary {
  /** the run directory's name, or <batch>~<name> for a run one level down ($RUNS/<batch>/<name>) */
  run_id: string
  /** a batch manifest's name, or `web` for runs the web app started */
  batch?: string | null
  qid: string | null
  concept_sha256?: string | null
  /** the run used the question's current pick; false: a replaced or another concept; null: no pick */
  concept_current?: boolean | null
  condition: string
  seed: number | null
  temperature: number | null
  created_at: string | null
  /** submitted, budget, context_full, error, cut, running, incomplete, or another recorded status */
  exit_status: string
  answer_from?: AnswerFrom | null
  steps: number
  model_calls: number
  tokens: number
  seconds: number
  tokens_without_attach?: number | null
  seconds_without_attach?: number | null
  rows: number | null
  facts: number | null
  claims_accepted: number
  claims_rejected: number
  attach: AttachState
  verify: VerifyState
  score: ScoreSummary | null
  /** the agent is still writing the run (research, or the attach step) */
  live: boolean
  /** a web-app job still runs verify, pairs, graph, export-prov or score on the finished run */
  post_processing?: boolean
}

/** GET /api/runs?qid=&condition=&include_stale= */
export interface RunFilters {
  qid?: string
  condition?: string
  /** with qid: also runs on a replaced concept */
  include_stale?: boolean
}

export interface Verification {
  ok: boolean
  errors: string[]
  stats: Record<string, unknown>
}

/** An answer fact (agent/schemas/answer.schema.json). */
export interface Fact {
  id: string
  s: string
  p: string
  o: string | number | boolean
  claims: string[]
  /** research or attach */
  origin: string
}

/** A table row (`cells`) or a graph row (source, predicate, target, ...), with its facts. */
export interface AnswerRow {
  id: string
  facts: Fact[]
  cells?: Record<string, unknown> | null
  source?: string | null
  source_type?: string | null
  predicate?: string | null
  target?: string | null
  target_type?: string | null
  attributes?: Record<string, unknown> | null
  [extra: string]: unknown
}

export interface Answer {
  concept_sha256: string
  kind: "table" | "graph"
  rows: AnswerRow[]
  notes?: string | null
}

/** GET /api/runs/{run_id}; `config` is the run's config.json (RunConfig below). */
export interface RunDetail {
  summary: RunSummary
  config: Record<string, unknown>
  concept: ConceptBrief | null
  answer: Answer | null
  verify: Verification | null
}

/** A step's model call: its numbers only (the reasoning is never recorded). */
export interface ModelCall {
  task_id: string
  status: string
  tokens?: number | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  seconds?: number | null
  /** how the reply was read (agent/parse.py) */
  parse?: string | null
  /** what the reply was: command, answer, none, ... */
  reply?: string | null
  finish_reason?: string | null
  final_answer?: boolean
  error?: string | null
}

/** One claim sent in a step (an events.jsonl claim record, reduced). */
export interface ClaimRef {
  claim_id: string | null
  status: "accepted" | "rejected"
  reason?: string | null
  s?: unknown
  p?: unknown
  o?: unknown
}

/** GET /api/runs/{run_id}/steps (one item): one per (agent, step id), in chain order. */
export interface Step {
  step: number
  agent_id: string
  /** research, attach, concept or batch */
  origin: string
  /** research, conclude, attach, ... (the model call's phase) */
  phase?: string | null
  started_at?: string | null
  ended_at?: string | null
  model_call?: ModelCall | null
  command?: string | null
  exit_code?: number | null
  timed_out?: boolean
  output_head?: string | null
  output_bytes?: number | null
  output_file?: string | null
  repeat?: number | null
  claims?: ClaimRef[]
  /** coverage reasons recorded at this step (unparsed, invalid_final_answer, ...) */
  coverage?: string[]
  /** subagents started in this step */
  spawned?: string[]
  /** attach step: the answer fact this step works on */
  fact_id?: string | null
}

export interface Anchor {
  start: number
  end: number
}

/** GET /api/runs/{run_id}/claims (one item) */
export interface Claim {
  claim_id: string | null
  task_id: string
  status: "accepted" | "rejected"
  reason?: string | null
  s?: unknown
  p?: unknown
  o?: unknown
  file?: string | null
  paper_id?: string | null
  /** accepted: the exact text anchored in the corpus; rejected: the quote as sent */
  quote?: string | null
  quote_submitted?: string | null
  step: number
  agent_id: string
  origin: string
  /** raw offsets in the corpus file, in code points */
  anchor?: Anchor | null
}

export interface Highlight {
  start: number
  end: number
}

/**
 * GET /api/corpus/{paper_id}: a window of the paper's text. `highlight` is the span inside `text`
 * in code points (Python, the anchors); `highlight_utf16` the same span in UTF-16 code units, which
 * is what `text.slice()` takes in JavaScript. `offset` is where `text` starts in the file.
 */
export interface Passage {
  paper_id: string
  title: string
  text: string
  highlight: Highlight | null
  highlight_utf16?: Highlight | null
  offset: number
  length: number
}

/** gold/judge.py support() verdict, as scoring counted it (source score) or asked live (judge). */
export interface Verdict {
  label: SupportLabel
  rationale?: string | null
  model?: string | null
  prompt_sha256?: string | null
  cached?: boolean | null
  source?: "score" | "judge" | null
  [extra: string]: unknown
}

export interface WalkClaim {
  claim_id: string
  /** null when the id is not an accepted claim of this run */
  claim: Claim | null
  step: Step | null
  passage: Passage | null
  /** ok, relocated, ambiguous, broken, missing, or unknown (no corpus) */
  anchor_status: string
  support?: Verdict | null
}

/** GET /api/runs/{run_id}/facts/{fact_id}/walk[?judge=true] */
export interface FactWalk {
  run_id: string
  fact: Fact
  row_id: string
  row: AnswerRow
  claims: WalkClaim[]
  /** the best verdict over the fact's quotes, or null */
  support: Verdict | null
  /** null: nothing judged yet */
  label?: FactLabel | null
}

// --- knowledge graph (GET /api/runs/{run_id}/graph: agent/kg.py graph.json as is) --------------

export interface GraphNode {
  id: string
  kind: "paper" | "entity"
  label: string
  paper?: string | null
  [extra: string]: unknown
}

export interface Predicate {
  text: string
  curie: string
  iri: string
  vocabulary: string
  [extra: string]: unknown
}

export interface Evidence {
  file: string
  paper: string | null
  start: number
  end: number
  [extra: string]: unknown
}

export interface GraphEdge {
  id: string
  claim: string
  origin: string
  step_id: number
  agent_id: string
  source: string
  /** node id, or null when the object is a literal */
  target: string | null
  literal?: unknown
  predicate: Predicate
  evidence: Evidence
  [extra: string]: unknown
}

export interface KnowledgeGraph {
  run_id: string
  nodes: GraphNode[]
  edges: GraphEdge[]
  namespaces?: Record<string, string>
  [extra: string]: unknown
}

// --- jobs ------------------------------------------------------------------------------------------

export interface JobStep {
  name: string
  argv: string[]
  /** argv as one shell-quoted line, for reading */
  command: string
  /** a failure fails the job (an optional step's failure is a warning) */
  required?: boolean
  /** files the step needs; it is skipped when one is missing */
  needs?: string[]
  state?: JobStepState
  exit_code?: number | null
  started_at?: string | null
  ended_at?: string | null
}

/** GET /api/jobs, /api/jobs/{id}; returned by every POST that starts work. */
export interface Job {
  id: string
  /** concepts, run or gold; one job of a kind runs at a time */
  kind: string
  args: Record<string, unknown>
  state: JobState
  created_at: string
  started_at?: string | null
  ended_at?: string | null
  run_id?: string | null
  qid?: string | null
  exit_code?: number | null
  error?: string | null
  /** optional steps that failed (the job can still be done) */
  warnings?: string[]
  steps?: JobStep[]
}

/** POST /api/runs: `qid` (its picked concept) or `concept_path`. */
export interface RunRequest {
  qid?: string | null
  concept_path?: string | null
  condition?: Condition
  temperature?: number
  seed?: number
  /** null: the agent's default budget */
  steps?: number | null
  tokens?: number | null
  sandbox?: "landlock" | "unsandboxed"
  /** claim_off: run the attach step after the run */
  attach?: boolean
  /** start although a run the web app did not start (a cluster batch) is live */
  force?: boolean
}

// --- gold, results, provenance ---------------------------------------------------------------------

/** GET /api/gold (one item); coverage, counts and report are the gold files (below). */
export interface GoldEntry {
  qid: string
  status: GoldState
  stage?: string | null
  coverage?: Record<string, unknown> | null
  counts?: Record<string, unknown> | null
  key_version?: string | null
  report?: Record<string, unknown> | null
  rows?: number | null
  facts?: number | null
}

/** GET /api/gold/{qid}/key: key.json, else key.draft.json (rows: KeyRow below). */
export interface AnswerKey {
  qid?: string | null
  concept_sha256?: string | null
  kind?: string | null
  version?: string | null
  reviewed?: boolean | null
  rows?: Record<string, unknown>[]
  notes?: unknown
  [extra: string]: unknown
}

/** POST /api/sparql */
export interface SparqlRequest {
  query: string
  run_id?: string | null
}

export interface SparqlResult {
  vars: string[]
  rows: Record<string, unknown>[]
  /** ASK queries: the answer (vars and rows are empty) */
  boolean?: boolean | null
}

/** GET /api/queries/{n}?run_id=&...: one of agent/queries.py's five queries on one run. */
export interface QueryResult {
  n: number
  name: string
  run_id: string
  rows: Record<string, unknown>[]
}

export type ProvQueryNumber = 1 | 2 | 3 | 4 | 5
export type ProvQueryParams = Partial<Record<"edge" | "fact" | "claim" | "step" | "agent", string>>

// --- streams ---------------------------------------------------------------------------------------

/** One events.jsonl record (agent/broker.py), the data of `event: record` of /api/runs/{id}/stream. */
export interface EventRecord {
  subtype: "ai_model_invocation" | "agent_tool" | "claim" | "coverage" | "spawn" | "concept_pick" | (string & {})
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

// =================================================================================================
// File contracts inside the open schemas (hand-written; see the module comment)
// =================================================================================================

/** The run's config.json (agent/rundir.py run_config), the fields the app reads. */
export interface RunConfig {
  run_id?: string
  created_at?: string
  condition?: string
  budget?: { steps?: number; tokens?: number; announced?: boolean }
  sampling?: { temperature?: number; seed?: number }
  prompt?: { version?: string; sha256?: string }
  models?: { orchestrator?: { alias?: string; name?: string; revision?: string } }
  git_commit?: string
}

// --- score.json (scoring/README.md, schema_version 2) ----------------------------------------------

export interface FactScores {
  tp?: number | null
  fp?: number | null
  fn?: number | null
  precision?: number | null
  recall?: number | null
  f1?: number | null
  vital?: number | null
  vital_tp?: number | null
  vital_recall?: number | null
  asked?: number | null
  pending?: number | null
}

/** A fact of the run or of the key in the match detail: its row and fact id. */
export interface FactRefIds {
  row: string
  fact: string
}

export interface FactTriple {
  s: unknown
  p: unknown
  o: unknown
}

export interface SupportDetail {
  row_id: string
  fact_id: string
  origin?: string
  label: FactLabel
  first_claim_label?: FactLabel | null
  claims?: { claim_id: string; file?: string; label: SupportLabel | null; rationale?: string | null; model?: string | null }[]
}

export interface ScoreSupport {
  facts?: number
  with_claims?: number
  supports?: number
  partial?: number
  no?: number
  unsourced?: number
  pending?: number
  /** how the judge's `partial` counts (the calibration's choice) */
  partial_counts_as?: "yes" | "no" | null
  support_share?: number | null
  support_share_partial_no?: number | null
  support_share_partial_yes?: number | null
  support_share_first_claim?: number | null
  claims_per_fact?: number | null
  unsourced_share?: number | null
  context?: string | null
}

export interface ScoreCost {
  steps?: number
  model_calls?: number
  tokens?: number
  tokens_without_attach?: number
  seconds?: number
  seconds_without_attach?: number
  wall_seconds?: number
  claim_steps?: number
  claim_step_tokens?: number
  attach_tokens?: number
  attach_seconds?: number
}

/** GET /api/runs/{run_id}/score: <run>/score.json. */
export interface Score {
  schema_version?: number
  run_id?: string | null
  qid?: string | null
  condition?: string | null
  seed?: number | null
  exit_status?: string | null
  answer_from?: AnswerFrom | null
  verify_ok?: boolean | null
  verify_errors?: string[]
  key_version?: string | null
  key_reviewed?: boolean | null
  provisional?: boolean | null
  key_problems?: unknown[]
  /** soft level */
  rows?: FactScores | null
  rows_by_level?: { normalised?: FactScores; soft?: FactScores } | null
  facts?: { strict?: FactScores; normalised?: FactScores; soft?: FactScores } | null
  vital_recall?: number | null
  judged_precision?: { correct?: number; wrong?: number | null; precision?: number | null; coverage?: number | null } | null
  support?: ScoreSupport | null
  pending?: { support?: number; same_fact?: number; same_row?: number } | null
  cost?: ScoreCost | null
  detail?: {
    rows?: { pairs?: { run: string; key: string; level: string }[]; missed?: string[]; extra?: string[]; duplicates?: number }
    facts?: {
      pairs?: { run: FactRefIds; run_same?: FactRefIds[]; key: FactRefIds; level: string; vital?: boolean }[]
      missed?: { key: FactRefIds; spo: FactTriple; vital?: boolean }[]
      extra?: { run: FactRefIds; same?: FactRefIds[]; spo: FactTriple; wrong?: boolean | null }[]
      duplicates?: number
    }
    support?: SupportDetail[]
  } | null
  scored_at?: string | null
  [extra: string]: unknown
}

// --- answer key (key.json / key.draft.json) ------------------------------------------------------

export interface KeyFact extends Fact {
  paper_id: string
  quote: string
  vital: boolean
  candidate_id: string
}

/** A key row: an answer row whose facts carry the gold-only fields (one of AnswerKey.rows). */
export type KeyRow = {
  id: string
  cells?: Record<string, unknown> | null
  source?: string | null
  source_type?: string | null
  predicate?: string | null
  target?: string | null
  target_type?: string | null
  attributes?: Record<string, unknown> | null
  facts: KeyFact[]
}

// --- gold files (gold/README.md doc.json; gold/REVIEW.md report.json) -----------------------------

export interface GoldCoverage {
  papers?: number
  relevant?: number
  not_relevant?: number
  no_text?: number
  error?: number
  papers_in_corpus?: number
  partial?: boolean
}

/** doc.json `counts` (gold/build.py counts()): D's size and what it cost. */
export interface GoldCounts {
  chunks?: number
  chunks_relevant?: number
  chunks_error?: number
  extraction_errors?: number
  candidates?: number
  anchored?: number
  /** candidates whose quote did not anchor, by reason */
  rejected?: Record<string, number>
  /** rows of D (before review) */
  rows?: number
  papers_with_candidates?: number
  model_calls?: { made?: number; cached?: number; failed?: number; total?: number }
  cost?: { invocations?: number; seconds?: number; calls_made?: number; input_tokens?: number; output_tokens?: number }
}

export interface KappaField {
  items?: number
  kappa?: number | null
  raw_agreement?: number | null
  kappa_95?: [number | null, number | null] | null
}

/** $GOLD/<qid>/report.json (gold agreement). */
export interface GoldReport {
  qid?: string
  generated_at?: string
  review?: { records?: number; decided?: number; kept?: number; unreviewed?: number; disagreements?: number; stale?: number }
  kappa?: {
    reviewers?: string[]
    items?: number
    label?: KappaField
    keep?: KappaField
    vital?: KappaField
    bar?: number
    keep_kappa_meets_bar?: boolean | null
    independent?: boolean
    warning?: string
  } | null
  triage?: {
    estimated_missed?: number | null
    estimated_missed_95?: [number, number] | null
    estimated_recall?: number | null
    estimated_recall_95?: [number, number] | null
    sample_reviewed?: number
    sampled?: number
  } | null
  screening?: {
    not_relevant?: number
    checked?: number
    found_relevant?: number
    false_negative_rate?: number | null
    false_negative_rate_95?: [number | null, number | null] | null
  } | null
}

// --- results ($RUNS/report/report.json, scoring/report.py schema_version 2) ----------------------

/** The outcomes the report aggregates (scoring/report.py OUTCOMES). */
export type Outcome =
  | "support_share"
  | "fact_precision"
  | "fact_recall"
  | "fact_f1"
  | "fact_f1_normalised"
  | "fact_f1_strict"
  | "row_f1"
  | "row_f1_normalised"
  | "vital_recall"
  | "judged_precision"
  | "unsourced_share"
  | "claims_per_fact"
  | "tokens"
  | "tokens_without_attach"
  | "seconds"
  | "seconds_without_attach"

/** A mean over questions with its BCa bootstrap interval (null bounds: fewer than 2 questions). */
export interface Interval {
  n: number
  mean: number | null
  low: number | null
  high: number | null
  method: string | null
  runs?: number
  runs_without_value?: number
}

export interface OutcomeSummary {
  label: string
  claim_on: Interval
  claim_off: Interval
  /** the paired mean difference claim_on - claim_off over the questions with both */
  difference: Interval
}

/** The pre-registered Wilcoxon test (scoring/report.py primary()). */
export interface PairedTest {
  outcome: string
  test: string
  alternative: string
  zero_method?: string
  alpha: number
  n_pairs: number
  n_nonzero: number
  computed: boolean
  /** why the test was not computed (too few pairs, pending verdicts) */
  reason: string | null
  statistic: number | null
  p_value: number | null
  significant: boolean | null
  t_plus?: number | null
  t_minus?: number | null
  /** matched-pairs rank-biserial correlation (T+ - T-) / (T+ + T-) */
  rank_biserial: number | null
  mean_difference: number | null
  ci_low: number | null
  ci_high: number | null
  ci_method: string | null
  questions: string[]
  excluded_questions: string[]
  label?: string
}

export interface PrimaryTest extends PairedTest {
  sensitivity_empty_as_zero?: PairedTest
  sensitivity_other_mapping?: PairedTest
  sensitivity_first_claim?: PairedTest
}

/** One question x condition of report.json `per_question`: means over the repeats. */
export type QuestionResult = {
  qid: string
  condition: string
  runs: number
  answered: number
  primary_runs: number
  pending_runs: number
} & Partial<Record<Outcome, number | null>>

/** GET /api/results: report.json. */
export interface ResultsReport {
  schema_version?: number
  generated_at?: string
  runs_root?: string
  /** some runs were scored against a draft key: the numbers test the pipeline, they are no result */
  provisional?: boolean
  provisional_runs?: number
  complete?: boolean
  completeness?: { pending_support_runs?: string[]; pending_soft_runs?: string[]; unverified_runs?: string[]; verify_failed_runs?: string[] }
  settings?: { interval?: string; confidence?: number; resamples?: number; alpha?: number; min_pairs?: number }
  runs?: { scored?: number; by_condition?: Partial<Record<Condition, number>>; by_exit_status?: Record<string, Record<string, number>> }
  coverage?: Partial<Record<Condition, { scored: number; answered: number; answered_share: number | null; not_scored: number }>>
  questions?: string[]
  per_question?: QuestionResult[]
  paired?: ({ qid: string } & Partial<Record<Outcome, { claim_on: number | null; claim_off: number | null; difference: number | null }>>)[]
  summary?: Partial<Record<Outcome, OutcomeSummary>>
  primary?: PrimaryTest | null
  secondary?: string[]
  [extra: string]: unknown
}
