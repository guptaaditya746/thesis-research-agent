/**
 * TanStack Query hooks over `api` (src/api/client.ts): one hook per endpoint, query keys in
 * one table so mutations and the live streams invalidate exactly what they change.
 *
 * Live data polls only while something is live: a run list with a live run (or one a job is still
 * verifying and scoring), such a run's detail, a job queue with queued or running jobs. Everything
 * else is fetched once and refetched on focus.
 */
import { keepPreviousData, QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { ApiError, api } from "./client"
import type {
  Job,
  PickRequest,
  ProposeRequest,
  ProvQueryNumber,
  ProvQueryParams,
  RunFilters,
  RunRequest,
  RunSummary,
  SparqlRequest,
} from "./types"

const LIVE_POLL_MS = 5_000
const JOB_POLL_MS = 2_000

export const keys = {
  health: ["health"] as const,
  config: ["config"] as const,
  questions: ["questions"] as const,
  question: (qid: string) => ["questions", qid] as const,
  runs: ["runs"] as const,
  runList: (filters: RunFilters) => ["runs", "list", filters] as const,
  run: (runId: string) => ["runs", "detail", runId] as const,
  runPart: (runId: string, part: string, ...rest: (string | number)[]) => ["runs", "detail", runId, part, ...rest] as const,
  passage: (paperId: string, start: number, end: number) => ["passage", paperId, start, end] as const,
  gold: ["gold"] as const,
  goldKey: (qid: string) => ["gold", qid, "key"] as const,
  results: (batch?: string) => ["results", batch ?? ""] as const,
  jobs: ["jobs"] as const,
  job: (id: string) => ["jobs", id] as const,
}

/** Retry server and network errors twice; a 4xx is an answer, not a hiccup. */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 10_000,
        retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      },
    },
  })
}

/** Something about the run still changes: the agent writes it, or a job verifies and scores it. */
export const isBusy = (run: Pick<RunSummary, "live" | "post_processing">) => run.live || !!run.post_processing

// --- general -----------------------------------------------------------------------------------

export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: ({ signal }) => api.health(signal), staleTime: 60_000 })
export const useConfig = () => useQuery({ queryKey: keys.config, queryFn: ({ signal }) => api.config(signal), staleTime: 60_000 })

// --- questions and concepts --------------------------------------------------------------------

export const useQuestions = () => useQuery({ queryKey: keys.questions, queryFn: ({ signal }) => api.questions(signal) })

export const useQuestion = (qid: string) =>
  useQuery({ queryKey: keys.question(qid), queryFn: ({ signal }) => api.question(qid, signal), enabled: !!qid })

export function useProposeConcepts(qid: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: ProposeRequest) => api.proposeConcepts(qid, body),
    onSuccess: (job) => {
      client.setQueryData(keys.job(job.id), job)
      void client.invalidateQueries({ queryKey: keys.jobs })
    },
  })
}

export function usePickConcept(qid: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: PickRequest) => api.pickConcept(qid, body),
    onSuccess: (question) => {
      client.setQueryData(keys.question(qid), question)
      void client.invalidateQueries({ queryKey: keys.questions, exact: true })
      void client.invalidateQueries({ queryKey: keys.runs })
    },
  })
}

// --- runs ----------------------------------------------------------------------------------------

export const useRuns = (filters: RunFilters = {}) =>
  useQuery({
    queryKey: keys.runList(filters),
    queryFn: ({ signal }) => api.runs(filters, signal),
    placeholderData: keepPreviousData,
    refetchInterval: (query) => (query.state.data?.some(isBusy) ? LIVE_POLL_MS : false),
  })

export function useStartRun() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: RunRequest) => api.startRun(body),
    onSuccess: (job) => {
      client.setQueryData(keys.job(job.id), job)
      void client.invalidateQueries({ queryKey: keys.jobs })
      void client.invalidateQueries({ queryKey: keys.runs })
    },
  })
}

export const useRun = (runId: string) =>
  useQuery({
    queryKey: keys.run(runId),
    queryFn: ({ signal }) => api.run(runId, signal),
    enabled: !!runId,
    refetchInterval: (query) => (query.state.data && isBusy(query.state.data.summary) ? LIVE_POLL_MS : false),
  })

export const useSteps = (runId: string, enabled = true) =>
  useQuery({ queryKey: keys.runPart(runId, "steps"), queryFn: ({ signal }) => api.steps(runId, signal), enabled: !!runId && enabled })

export const useClaims = (runId: string, enabled = true) =>
  useQuery({ queryKey: keys.runPart(runId, "claims"), queryFn: ({ signal }) => api.claims(runId, signal), enabled: !!runId && enabled })

export const useGraph = (runId: string, enabled = true) =>
  useQuery({ queryKey: keys.runPart(runId, "graph"), queryFn: ({ signal }) => api.graph(runId, signal), enabled: !!runId && enabled })

export const useScore = (runId: string, enabled = true) =>
  useQuery({ queryKey: keys.runPart(runId, "score"), queryFn: ({ signal }) => api.score(runId, signal), enabled: !!runId && enabled })

/**
 * The claim walk of one fact. Without `judge` it carries the verdicts score.json counted (no model
 * call); with it, the backend asks the judge about quotes that have none yet.
 */
export const useFactWalk = (runId: string, factId: string | null, { judge = false }: { judge?: boolean } = {}) =>
  useQuery({
    queryKey: keys.runPart(runId, "walk", factId ?? "", judge ? "judge" : "scored"),
    queryFn: ({ signal }) => api.factWalk(runId, factId!, { judge }, signal),
    enabled: !!runId && !!factId,
    staleTime: 5 * 60_000,
  })

export const usePassage = (paperId: string | null | undefined, start: number, end: number, enabled = true) =>
  useQuery({
    queryKey: keys.passage(paperId ?? "", start, end),
    queryFn: ({ signal }) => api.passage(paperId!, { start, end }, signal),
    enabled: !!paperId && enabled,
    staleTime: Infinity,
  })

export const useStepOutput = (runId: string, step: number | null, agentId?: string | null) =>
  useQuery({
    queryKey: keys.runPart(runId, "output", step ?? -1, agentId ?? "main"),
    queryFn: ({ signal }) => api.stepOutput(runId, step!, agentId, signal),
    enabled: !!runId && step !== null,
    staleTime: Infinity,
  })

// --- gold, results, provenance ---------------------------------------------------------------------

export const useGold = () => useQuery({ queryKey: keys.gold, queryFn: ({ signal }) => api.gold(signal) })

export const useGoldKey = (qid: string | null) =>
  useQuery({ queryKey: keys.goldKey(qid ?? ""), queryFn: ({ signal }) => api.goldKey(qid!, signal), enabled: !!qid })

export function useBuildGold() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (qid: string) => api.buildGold(qid),
    onSuccess: (job) => {
      client.setQueryData(keys.job(job.id), job)
      void client.invalidateQueries({ queryKey: keys.jobs })
      void client.invalidateQueries({ queryKey: keys.gold })
    },
  })
}

export const useResults = (batch?: string) =>
  useQuery({ queryKey: keys.results(batch), queryFn: ({ signal }) => api.results(batch, signal) })

export const useSparql = () => useMutation({ mutationFn: (body: SparqlRequest) => api.sparql(body) })

export const useProvQuery = (runId: string) =>
  useMutation({ mutationFn: ({ n, params }: { n: ProvQueryNumber; params?: ProvQueryParams }) => api.provQuery(n, runId, params) })

// --- jobs ------------------------------------------------------------------------------------------

export const isActiveJob = (job: Pick<Job, "state">) => job.state === "queued" || job.state === "running"

export const useJobs = () =>
  useQuery({
    queryKey: keys.jobs,
    queryFn: ({ signal }) => api.jobs(signal),
    refetchInterval: (query) => (query.state.data?.some(isActiveJob) ? JOB_POLL_MS : 15_000),
  })

export const useJob = (id: string | null) =>
  useQuery({
    queryKey: keys.job(id ?? ""),
    queryFn: ({ signal }) => api.job(id!, signal),
    enabled: !!id,
    refetchInterval: (query) => (query.state.data && isActiveJob(query.state.data) ? JOB_POLL_MS : false),
  })

export function useCancelJob() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.cancelJob(id),
    onSuccess: (job) => {
      client.setQueryData(keys.job(job.id), job)
      void client.invalidateQueries({ queryKey: keys.jobs })
    },
  })
}
