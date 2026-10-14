/**
 * Backend API types (docs/e2e-build-plan.md, "Backend API"). The response and request types are
 * aliases onto the types `npm run gen:api` generates with openapi-typescript (src/api/schema.d.ts)
 * from the backend's OpenAPI schema (webapp/web/openapi.json, made by `webapp openapi` from
 * webapp/models.py), so the type checker holds the frontend to the API the backend serves: after a
 * change to the backend's models, regenerate both files and fix what `npm run typecheck` shows.
 *
 * Field names are the backend's (snake_case), never renamed on the way in. Where the backend passes
 * another package's file through as an open object (score.json, report.json, the gold report,
 * graph.json, config.json), the second half of this module types that file from its writer's
 * documentation (scoring/README.md, gold/README.md, agent/rundir.py, agent/kg.py). Those "file
 * contract" types are hand-written; src/lib reads them defensively, since a file of an older writer
 * may lack fields.
 */
import type { components } from "./schema"

type Schemas = components["schemas"]

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

// --- generated from the backend's OpenAPI schema ------------------------------------------------

/** GET /api/health */
export type Health = Schemas["Health"]
/** GET /api/config */
export type AppConfig = Schemas["AppConfig"]

export type ConceptStatus = Schemas["ConceptStatus"]
export type GoldStatus = Schemas["GoldStatus"]
export type RunCounts = Schemas["RunCounts"]
/** GET /api/questions (one item) */
export type Question = Schemas["Question"]
export type Measure = Schemas["Measure"]
export type Column = Schemas["Column"]
export type NodeType = Schemas["NodeType"]
export type EdgeType = Schemas["EdgeType"]
/** A table (columns) or a graph (node types and edge types): the brief's answer template. */
export type AnswerShape = Schemas["AnswerShape"]
/** One reading of a question (agent/schemas/concept.schema.json). */
export type ConceptBrief = Schemas["ConceptBrief"]
/** The current pick: the last `concept_pick` record of the question's session. */
export type Pick = Schemas["Pick"]
/** GET /api/questions/{qid}; also the reply of POST .../concepts/pick */
export type QuestionDetail = Schemas["QuestionDetail"]
/** POST /api/questions/{qid}/concepts/propose */
export type ProposeRequest = Schemas["ProposeRequest"]
/** POST /api/questions/{qid}/concepts/pick */
export type PickRequest = Schemas["PickRequest"]

export type ScoreSummary = Schemas["ScoreSummary"]
/** GET /api/runs (one item) */
export type RunSummary = Schemas["RunSummary"]
export type Verification = Schemas["Verification"]
/** An answer fact (agent/schemas/answer.schema.json). */
export type Fact = Schemas["Fact"]
/** A table row (`cells`) or a graph row (source, predicate, target, ...), with its facts. */
export type AnswerRow = Schemas["AnswerRow"]
export type Answer = Schemas["Answer"]
/** GET /api/runs/{run_id}; `config` is the run's config.json (RunConfig below). */
export type RunDetail = Schemas["RunDetail"]
/** A step's model call: its numbers only (the reasoning is never recorded). */
export type ModelCall = Schemas["ModelCall"]
/** One claim sent in a step (an events.jsonl claim record, reduced). */
export type ClaimRef = Schemas["ClaimRef"]
/** GET /api/runs/{run_id}/steps (one item): one per (agent, step id), in chain order. */
export type Step = Schemas["Step"]
export type Anchor = Schemas["Anchor"]
/** GET /api/runs/{run_id}/claims (one item) */
export type Claim = Schemas["Claim"]
export type Highlight = Schemas["Highlight"]
/**
 * GET /api/corpus/{paper_id}: a window of the paper's text. `highlight` is the span inside `text`
 * in code points (Python, the anchors); `highlight_utf16` the same span in UTF-16 code units, which
 * is what `text.slice()` takes in JavaScript. `offset` is where `text` starts in the file.
 */
export type Passage = Schemas["Passage"]
/** gold/judge.py support() verdict, as scoring counted it (source score) or asked live (judge). */
export type Verdict = Schemas["Verdict"]
export type WalkClaim = Schemas["WalkClaim"]
/** GET /api/runs/{run_id}/facts/{fact_id}/walk[?judge=true] */
export type FactWalk = Schemas["FactWalk"]

// knowledge graph (GET /api/runs/{run_id}/graph: agent/kg.py graph.json as is)
export type GraphNode = Schemas["GraphNode"]
export type Predicate = Schemas["Predicate"]
export type Evidence = Schemas["Evidence"]
export type GraphEdge = Schemas["GraphEdge"]
export type KnowledgeGraph = Schemas["KnowledgeGraph"]

export type JobStep = Schemas["JobStep"]
/** GET /api/jobs, /api/jobs/{id}; returned by every POST that starts work. */
export type Job = Schemas["Job"]
/** POST /api/runs: `qid` (its picked concept) or `concept_path`. */
export type RunRequest = Schemas["RunRequest"]

/** GET /api/gold (one item); coverage, counts and report are the gold files (below). */
export type GoldEntry = Schemas["GoldEntry"]
/** GET /api/gold/{qid}/key: key.json, else key.draft.json (rows: KeyRow below). */
export type AnswerKey = Schemas["AnswerKey"]
/** POST /api/sparql */
export type SparqlRequest = Schemas["SparqlRequest"]
export type SparqlResult = Schemas["SparqlResult"]
/** GET /api/queries/{n}?run_id=&...: one of agent/queries.py's five queries on one run. */
export type QueryResult = Schemas["QueryResult"]

// --- client-side request shapes ---------------------------------------------------------------------

/** GET /api/runs?qid=&condition=&include_stale= */
export interface RunFilters {
  qid?: string
  condition?: string
  /** with qid: also runs on a replaced concept */
  include_stale?: boolean
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

// --- gold files (gold/README.md doc.json; gold/README.md report.json) -----------------------------

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
