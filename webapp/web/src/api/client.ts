/**
 * The one typed client for the backend API (docs/e2e-build-plan.md, "Backend API").
 *
 * All HTTP access of the app goes through `api` (JSON and text) or the URL helpers (streams,
 * links), so a change of base URL, auth or generated types happens here only. Errors become
 * `ApiError` with the HTTP status and FastAPI's `detail`; endpoints where 404 means "not there
 * yet" (score, results, gold key) resolve to null instead.
 */
import type {
  AnswerKey,
  AppConfig,
  Claim,
  FactWalk,
  GoldSummary,
  Health,
  Job,
  KnowledgeGraph,
  Passage,
  PickRequest,
  ProposeRequest,
  ProvQueryNumber,
  ProvQueryParams,
  QuestionDetail,
  QuestionSummary,
  ResultsReport,
  RunDetail,
  RunFilters,
  RunSummary,
  Score,
  SparqlRequest,
  SparqlResult,
  StartRunRequest,
  Step,
} from "./types"

export class ApiError extends Error {
  readonly status: number
  readonly path: string
  readonly detail: unknown

  constructor(status: number, path: string, message: string, detail?: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.path = path
    this.detail = detail
  }
}

export const isNotFound = (error: unknown) => error instanceof ApiError && error.status === 404

type Params = Record<string, string | number | boolean | null | undefined>

/** Absolute URL for an API path; empty parameters are left out. VITE_API_BASE prefixes paths. */
export function apiUrl(path: string, params?: Params): string {
  const base = (import.meta.env.VITE_API_BASE as string | undefined) ?? ""
  const url = new URL(base + path, window.location.origin)
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value))
  }
  return url.toString()
}

const seg = encodeURIComponent

/** FastAPI puts the reason in `detail` (a string, or a list of validation errors). */
function describe(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : JSON.stringify(d)))
      .join("; ")
  }
  return fallback
}

interface RequestOptions {
  params?: Params
  body?: unknown
  signal?: AbortSignal
}

async function request(method: string, path: string, { params, body, signal }: RequestOptions = {}) {
  const response = await fetch(apiUrl(path, params), {
    method,
    signal,
    headers: body === undefined ? { Accept: "application/json" } : { Accept: "application/json", "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    let detail: unknown = undefined
    try {
      const data: unknown = await response.json()
      detail = typeof data === "object" && data && "detail" in data ? (data as { detail: unknown }).detail : data
    } catch {
      // not JSON: keep the status text
    }
    throw new ApiError(response.status, path, describe(detail, `${response.status} ${response.statusText || "error"}`), detail)
  }
  return response
}

async function json<T>(method: string, path: string, options?: RequestOptions): Promise<T> {
  const response = await request(method, path, options)
  return (await response.json()) as T
}

async function orNull<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise
  } catch (error) {
    if (isNotFound(error)) return null
    throw error
  }
}

const get = <T>(path: string, params?: Params, signal?: AbortSignal) => json<T>("GET", path, { params, signal })
const post = <T>(path: string, body: unknown, signal?: AbortSignal) => json<T>("POST", path, { body, signal })

export const api = {
  health: (signal?: AbortSignal) => get<Health>("/api/health", undefined, signal),
  config: (signal?: AbortSignal) => get<AppConfig>("/api/config", undefined, signal),

  questions: (signal?: AbortSignal) => get<QuestionSummary[]>("/api/questions", undefined, signal),
  question: (qid: string, signal?: AbortSignal) => get<QuestionDetail>(`/api/questions/${seg(qid)}`, undefined, signal),
  proposeConcepts: (qid: string, body: ProposeRequest) => post<Job>(`/api/questions/${seg(qid)}/concepts/propose`, body),
  pickConcept: (qid: string, body: PickRequest) => post<QuestionDetail>(`/api/questions/${seg(qid)}/concepts/pick`, body),

  runs: (filters: RunFilters = {}, signal?: AbortSignal) =>
    get<RunSummary[]>("/api/runs", { qid: filters.qid, condition: filters.condition }, signal),
  startRun: (body: StartRunRequest) => post<Job>("/api/runs", body),
  run: (runId: string, signal?: AbortSignal) => get<RunDetail>(`/api/runs/${seg(runId)}`, undefined, signal),
  steps: (runId: string, signal?: AbortSignal) => get<Step[]>(`/api/runs/${seg(runId)}/steps`, undefined, signal),
  stepOutput: async (runId: string, step: number, signal?: AbortSignal) =>
    (await request("GET", `/api/runs/${seg(runId)}/steps/${step}/output`, { signal })).text(),
  claims: (runId: string, signal?: AbortSignal) => get<Claim[]>(`/api/runs/${seg(runId)}/claims`, undefined, signal),
  graph: (runId: string, signal?: AbortSignal) => get<KnowledgeGraph>(`/api/runs/${seg(runId)}/graph`, undefined, signal),
  factWalk: (runId: string, factId: string, signal?: AbortSignal) =>
    get<FactWalk>(`/api/runs/${seg(runId)}/facts/${seg(factId)}/walk`, undefined, signal),
  score: (runId: string, signal?: AbortSignal) => orNull(get<Score>(`/api/runs/${seg(runId)}/score`, undefined, signal)),

  passage: (paperId: string, span: { start: number; end: number; context?: number }, signal?: AbortSignal) =>
    get<Passage>(`/api/corpus/${seg(paperId)}`, { start: span.start, end: span.end, context: span.context ?? 1500 }, signal),

  gold: (signal?: AbortSignal) => get<GoldSummary[]>("/api/gold", undefined, signal),
  goldKey: (qid: string, signal?: AbortSignal) => orNull(get<AnswerKey>(`/api/gold/${seg(qid)}/key`, undefined, signal)),
  results: (signal?: AbortSignal) => orNull(get<ResultsReport>("/api/results", undefined, signal)),

  sparql: (body: SparqlRequest, signal?: AbortSignal) => post<SparqlResult>("/api/sparql", body, signal),
  provQuery: (n: ProvQueryNumber, runId: string, params: ProvQueryParams = {}, signal?: AbortSignal) =>
    get<Record<string, unknown>[]>(`/api/queries/${n}`, { run_id: runId, ...params }, signal),

  jobs: (signal?: AbortSignal) => get<Job[]>("/api/jobs", undefined, signal),
  job: (id: string, signal?: AbortSignal) => get<Job>(`/api/jobs/${seg(id)}`, undefined, signal),
}

/** Stream and link URLs (EventSource, <a href>, the chat transport). */
export const urls = {
  runStream: (runId: string) => apiUrl(`/api/runs/${seg(runId)}/stream`),
  jobLog: (jobId: string) => apiUrl(`/api/jobs/${seg(jobId)}/log`),
  stepOutput: (runId: string, step: number) => apiUrl(`/api/runs/${seg(runId)}/steps/${step}/output`),
  chat: () => apiUrl("/api/chat"),
}
