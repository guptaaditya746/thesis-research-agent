/**
 * The evidence-level app's API (/api/ev: webapp/evapi.py, webapp/evjobs.py): types, client and TanStack Query
 * hooks.
 *
 * Types are aliases onto the generated schema (src/api/schema.d.ts, `npm run gen:api`), so the pages read the
 * files with the fields their writers give them (synth, evidence, evaluation; docs/evidence-system.md). The
 * viewer's endpoints are reads of files on disk, fetched once and refetched on focus; while a job writes what a
 * page shows, the page passes `live` and the query polls. The jobs list polls while a job is queued or running.
 * Starting a job, cancelling one or writing decisions invalidates what it changes.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { getJson, getText, postJson, putJson } from "./client"
import type { components } from "./schema"

type S = components["schemas"]

export type Health = S["Health"]
export type EvConfig = S["EvConfig"]
export type RunGroup = S["RunGroup"]
export type CorpusSummary = S["CorpusSummary"]
export type CorpusDetail = S["CorpusDetail"]
export type CorpusPaper = S["CorpusPaper"]
export type CorpusPaperDetail = S["CorpusPaperDetail"]
export type Placement = S["Placement"]
export type Segment = S["Segment"]
export type ProtocolEntry = S["ProtocolEntry"]
export type ProtocolView = S["ProtocolView"]
export type Protocol = S["Protocol"]
export type EvidenceTypeSpec = S["EvidenceTypeSpec"]
export type Synthesis = S["Synthesis"]
export type ProposalSummary = S["ProposalSummary"]
export type ProposalDetail = S["ProposalDetail"]
export type Card = S["Card"]
export type Decision = S["Decision"]
export type Amendment = S["Amendment"]
export type Check = S["Check"]
export type EvRunSummary = S["EvRunSummary"]
export type EvRunDetail = S["EvRunDetail"]
export type EffectAnswer = S["EffectAnswer"]
export type InventoryAnswer = S["InventoryAnswer"]
export type ConsistencyAnswer = S["ConsistencyAnswer"]
export type BestAnswer = S["BestAnswer"]
/** answer.json of any question kind (a `kind` key; effect when it is absent in an old file). */
export type RunAnswer = NonNullable<S["EvRunDetail"]["answer"]>
export type EvAnswer = EffectAnswer
export type QuestionKind = Question["kind"]
export type Study = S["Study"]
export type Counts = S["Counts"]
export type FunnelDoc = S["FunnelDoc"]
export type RunPaper = S["RunPaper"]
export type Item = S["Item"]
export type CallSummary = S["CallSummary"]
export type CallDetail = S["CallDetail"]
export type TracePage = S["TracePage"]
export type TraceRow = S["TraceRow"]
export type ModelCallRecord = S["ModelCallRecord"]
export type AgentTrace = S["AgentTrace"]
export type ExtractorSpec = S["ExtractorSpec"]
export type EvGraph = S["EvGraph"]
export type EvGraphNode = S["EvGraphNode"]
export type EvGraphEdge = S["EvGraphEdge"]
export type ScoresIndex = S["ScoresIndex"]
export type ScoreRef = S["ScoreRef"]
export type ReportView = S["ReportView"]
export type Report = S["Report"]
export type SynthesisScore = S["SynthesisScore"]
export type CompareTable = S["CompareTable"]
export type ShiftView = S["ShiftView"]
export type BenchmarkView = S["BenchmarkView"]
export type Question = S["Question"]
export type Job = S["Job"]
export type JobStep = S["JobStep"]
export type JobState = Job["state"]
export type SynthRequest = S["SynthRequest"]
export type RunRequest = S["RunRequest"]
export type ProtocolRef = S["ProtocolRef"]
export type RagBaselineRequest = S["RagBaselineRequest"]
export type AgentBaselineRequest = S["AgentBaselineRequest"]
export type ScoreRequest = S["ScoreRequest"]
export type CompareRequest = S["CompareRequest"]
export type ProposeRequest = S["ProposeRequest"]
export type FreezeRequest = S["FreezeRequest"]
export type DecisionEntry = S["DecisionEntry"]
export type DecisionsRequest = S["DecisionsRequest"]
export type DecisionsResult = S["DecisionsResult"]
export type WaiverEntry = S["WaiverEntry"]
export type KindRequest = S["KindRequest"]
export type CheckProblem = S["CheckProblem"]
export type CheckResult = S["CheckResult"]
export type PreviewResult = S["PreviewResult"]
export type PreviewHit = S["PreviewHit"]

/** The effect directions of answer.json and ground_truth.json (evidence/rules.py DIRECTIONS + undetermined). */
export type Direction = "supports" | "contradicts" | "neutral" | "undetermined"
/** `{point, low, high, method}` of report.json `intervals` (evaluation/stats.py interval_row). */
export interface Interval {
  point?: number | null
  low?: number | null
  high?: number | null
  method?: string | null
}

/** What each job endpoint takes (POST /api/ev/jobs/<kind>). */
export interface JobRequests {
  synth: SynthRequest
  run: RunRequest
  "rag-baseline": RagBaselineRequest
  "agent-baseline": AgentBaselineRequest
  score: ScoreRequest
  compare: CompareRequest
  propose: ProposeRequest
  freeze: FreezeRequest
}
export type JobKind = keyof JobRequests

const seg = encodeURIComponent

export const evApi = {
  health: (signal?: AbortSignal) => getJson<Health>("/api/health", undefined, signal),
  config: (signal?: AbortSignal) => getJson<EvConfig>("/api/ev/config", undefined, signal),
  questions: (signal?: AbortSignal) => getJson<Question[]>("/api/ev/questions", undefined, signal),
  runGroup: (protocol: ProtocolRef, extractors: string, strategy: string, signal?: AbortSignal) =>
    getJson<RunGroup>("/api/ev/run-group", { source: protocol.source, name: protocol.name, extractors, strategy }, signal),
  question: (id: string, signal?: AbortSignal) => getJson<Question>(`/api/ev/questions/${seg(id)}`, undefined, signal),
  corpora: (signal?: AbortSignal) => getJson<CorpusSummary[]>("/api/ev/corpora", undefined, signal),
  corpus: (name: string, signal?: AbortSignal) => getJson<CorpusDetail>(`/api/ev/corpora/${seg(name)}`, undefined, signal),
  corpusPaper: (name: string, paper: string, signal?: AbortSignal) =>
    getJson<CorpusPaperDetail>(`/api/ev/corpora/${seg(name)}/papers/${seg(paper)}`, undefined, signal),
  protocols: (signal?: AbortSignal) => getJson<ProtocolEntry[]>("/api/ev/protocols", undefined, signal),
  protocol: (name: string, signal?: AbortSignal) => getJson<ProtocolView>(`/api/ev/protocols/${seg(name)}`, undefined, signal),
  proposals: (signal?: AbortSignal) => getJson<ProposalSummary[]>("/api/ev/proposals", undefined, signal),
  proposal: (name: string, signal?: AbortSignal) => getJson<ProposalDetail>(`/api/ev/proposals/${seg(name)}`, undefined, signal),
  runs: (signal?: AbortSignal) => getJson<EvRunSummary[]>("/api/ev/runs", undefined, signal),
  run: (id: string, signal?: AbortSignal) => getJson<EvRunDetail>(`/api/ev/runs/${seg(id)}`, undefined, signal),
  runPaper: (id: string, doc: string, signal?: AbortSignal) =>
    getJson<RunPaper>(`/api/ev/runs/${seg(id)}/papers/${seg(doc)}`, undefined, signal),
  runGraph: (id: string, signal?: AbortSignal) => getJson<EvGraph>(`/api/ev/runs/${seg(id)}/graph`, undefined, signal),
  runProtocol: (id: string, signal?: AbortSignal) => getJson<ProtocolView>(`/api/ev/runs/${seg(id)}/protocol`, undefined, signal),
  call: (id: string, call: string, signal?: AbortSignal) =>
    getJson<CallDetail>(`/api/ev/runs/${seg(id)}/calls/${seg(call)}`, undefined, signal),
  callTrace: (id: string, call: string, agentRun: string, signal?: AbortSignal) =>
    getJson<AgentTrace>(`/api/ev/runs/${seg(id)}/calls/${seg(call)}/trace/${seg(agentRun)}`, undefined, signal),
  runTrace: (id: string, after: number, signal?: AbortSignal) =>
    getJson<TracePage>(`/api/ev/runs/${seg(id)}/trace`, { after }, signal),
  baselineTrace: (id: string, signal?: AbortSignal) => getJson<AgentTrace>(`/api/ev/runs/${seg(id)}/agent-trace`, undefined, signal),
  scores: (signal?: AbortSignal) => getJson<ScoresIndex>("/api/ev/scores", undefined, signal),
  report: (id: string, signal?: AbortSignal) => getJson<ReportView>(`/api/ev/scores/reports/${seg(id)}`, undefined, signal),
  compare: (id: string, signal?: AbortSignal) => getJson<CompareTable>(`/api/ev/scores/compares/${seg(id)}`, undefined, signal),
  shift: (id: string, signal?: AbortSignal) => getJson<ShiftView>(`/api/ev/scores/shifts/${seg(id)}`, undefined, signal),
  benchmark: (id: string, signal?: AbortSignal) => getJson<BenchmarkView>(`/api/ev/scores/benchmarks/${seg(id)}`, undefined, signal),
  jobs: (signal?: AbortSignal) => getJson<Job[]>("/api/ev/jobs", undefined, signal),
  job: (id: string, signal?: AbortSignal) => getJson<Job>(`/api/ev/jobs/${seg(id)}`, undefined, signal),
  jobLog: (id: string, lines = 200, signal?: AbortSignal) => getText(`/api/ev/jobs/${seg(id)}/log`, { lines }, signal),
  cancelJob: (id: string) => postJson<Job>(`/api/ev/jobs/${seg(id)}/cancel`, {}),
  startJob: <K extends JobKind>(kind: K, body: JobRequests[K]) => postJson<Job>(`/api/ev/jobs/${kind}`, body),
  putKind: (proposal: string, body: KindRequest) => putJson<Job>(`/api/ev/proposals/${seg(proposal)}/kind`, body),
  checkProposal: (proposal: string, decisions: DecisionEntry[]) =>
    postJson<CheckResult>(`/api/ev/proposals/${seg(proposal)}/check`, { decisions }),
  preview: (proposal: string, corpus: string, paper: string, signal?: AbortSignal) =>
    getJson<PreviewResult>(`/api/ev/proposals/${seg(proposal)}/preview`, { corpus, paper }, signal),
  putDecisions: (proposal: string, body: DecisionsRequest) =>
    putJson<DecisionsResult>(`/api/ev/proposals/${seg(proposal)}/decisions`, body),
}

export const evKeys = {
  all: ["ev"] as const,
  jobs: ["ev", "jobs"] as const,
  of: (...parts: string[]) => ["ev", ...parts] as const,
}

const LIVE_MS = 2_000
const IDLE_JOBS_MS = 15_000

export const isActiveJob = (job: Pick<Job, "state">) => job.state === "queued" || job.state === "running"

/** One query per endpoint; `enabled` waits for the ids a page gets from its route; `live` polls. */
function useEv<T>(parts: string[], fetcher: (signal: AbortSignal) => Promise<T>, enabled = true, live = false) {
  return useQuery({
    queryKey: evKeys.of(...parts),
    queryFn: ({ signal }) => fetcher(signal),
    enabled,
    refetchInterval: live ? LIVE_MS : false,
  })
}

export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: ({ signal }) => evApi.health(signal) })
export const useEvConfig = () => useEv(["config"], (s) => evApi.config(s))
/** The group a run with this protocol and selection is written under: only the backend names it. */
export const useRunGroup = (protocol: ProtocolRef, extractors: string, strategy: string) =>
  useEv(["run-group", protocol.source, protocol.name, extractors, strategy], (s) => evApi.runGroup(protocol, extractors, strategy, s), !!protocol.name)
export const useQuestions = () => useEv(["questions"], (s) => evApi.questions(s))
export const useQuestion = (id: string, live = false) => useEv(["questions", id], (s) => evApi.question(id, s), !!id, live)
export const useCorpora = (live = false) => useEv(["corpora"], (s) => evApi.corpora(s), true, live)
export const useCorpus = (name: string) => useEv(["corpora", name], (s) => evApi.corpus(name, s), !!name)
export const useCorpusPaper = (name: string, paper: string) =>
  useEv(["corpora", name, "papers", paper], (s) => evApi.corpusPaper(name, paper, s), !!name && !!paper)
export const useProtocols = () => useEv(["protocols"], (s) => evApi.protocols(s))
export const useProtocol = (name: string) => useEv(["protocols", name], (s) => evApi.protocol(name, s), !!name)
export const useProposals = (live = false) => useEv(["proposals"], (s) => evApi.proposals(s), true, live)
export const useProposal = (name: string, live = false) => useEv(["proposals", name], (s) => evApi.proposal(name, s), !!name, live)
export const usePreview = (proposal: string, corpus: string | null, paper: string | null) =>
  useEv(["proposals", proposal, "preview", corpus ?? "", paper ?? ""], (s) => evApi.preview(proposal, corpus ?? "", paper ?? "", s),
    !!proposal && !!corpus && !!paper)
export const useEvRuns = (live = false) => useEv(["runs"], (s) => evApi.runs(s), true, live)
export const useEvRun = (id: string, live = false) => useEv(["runs", id], (s) => evApi.run(id, s), !!id, live)
export const useRunPaper = (id: string, doc: string | null, live = false) =>
  useEv(["runs", id, "papers", doc ?? ""], (s) => evApi.runPaper(id, doc ?? "", s), !!id && !!doc, live)
export const useRunGraph = (id: string, enabled = true, live = false) =>
  useEv(["runs", id, "graph"], (s) => evApi.runGraph(id, s), !!id && enabled, live)
export const useRunProtocol = (id: string, enabled = true) =>
  useEv(["runs", id, "protocol"], (s) => evApi.runProtocol(id, s), !!id && enabled)
export const useCall = (id: string, call: string | null) =>
  useEv(["runs", id, "calls", call ?? ""], (s) => evApi.call(id, call ?? "", s), !!id && !!call)
export const useCallTrace = (id: string, call: string | null, agentRun: string | null) =>
  useEv(["runs", id, "calls", call ?? "", "trace", agentRun ?? ""], (s) => evApi.callTrace(id, call ?? "", agentRun ?? "", s),
    !!id && !!call && !!agentRun)
export const useBaselineTrace = (id: string, enabled = true) =>
  useEv(["runs", id, "trace"], (s) => evApi.baselineTrace(id, s), !!id && enabled)
/**
 * The run's step trace, accumulated: each fetch asks for the rows after the last one seen and appends them.
 * Polls while a job writes the run (`live`) or until the trace says `done`.
 */
export function useTrace(id: string, live = false) {
  const client = useQueryClient()
  const key = evKeys.of("runs", id, "run-trace")
  return useQuery({
    queryKey: key,
    queryFn: async ({ signal }): Promise<TracePage> => {
      const before = client.getQueryData<TracePage>(key)
      const page = await evApi.runTrace(id, before?.next ?? 0, signal)
      if (!before) return page
      // `next` below the one we hold: the trace restarted, so the rows we hold are stale; read it again from the start
      if (page.next < before.next) return evApi.runTrace(id, 0, signal)
      const seen = new Set(before.rows.map((r) => r.n))
      return { ...page, rows: [...before.rows, ...page.rows.filter((r) => !seen.has(r.n))] }
    },
    enabled: !!id,
    refetchInterval: (query) => (live || !query.state.data?.done ? LIVE_MS : false),
  })
}
export const useScores = (live = false) => useEv(["scores"], (s) => evApi.scores(s), true, live)
export const useReport = (id: string) => useEv(["scores", "reports", id], (s) => evApi.report(id, s), !!id)
export const useCompare = (id: string) => useEv(["scores", "compares", id], (s) => evApi.compare(id, s), !!id)
export const useShift = (id: string) => useEv(["scores", "shifts", id], (s) => evApi.shift(id, s), !!id)
export const useBenchmark = (id: string) => useEv(["scores", "benchmarks", id], (s) => evApi.benchmark(id, s), !!id)

// --- jobs ----------------------------------------------------------------------------------------------

/** Every job, newest first; polls fast while one is queued or running, slowly otherwise (jobs from another tab). */
export const useJobs = () =>
  useQuery({
    queryKey: evKeys.jobs,
    queryFn: ({ signal }) => evApi.jobs(signal),
    refetchInterval: (query) => (query.state.data?.some(isActiveJob) ? LIVE_MS : IDLE_JOBS_MS),
  })

export const useJob = (id: string) =>
  useQuery({
    queryKey: [...evKeys.jobs, id],
    queryFn: ({ signal }) => evApi.job(id, signal),
    enabled: !!id,
    refetchInterval: (query) => (query.state.data && isActiveJob(query.state.data) ? LIVE_MS : false),
  })

export const useJobLog = (id: string, active: boolean, lines = 200) =>
  useQuery({
    queryKey: [...evKeys.jobs, id, "log", lines],
    queryFn: ({ signal }) => evApi.jobLog(id, lines, signal),
    enabled: !!id,
    refetchInterval: active ? LIVE_MS : false,
  })

/** The queued or running jobs whose refs match (e.g. `{run: "cascade~c1"}`, `{corpus: "c1"}`). */
export function useActiveJobs(refs: Partial<Record<string, string | null | undefined>>) {
  const jobs = useJobs()
  const wanted = Object.entries(refs).filter(([, v]) => !!v) as [string, string][]
  if (!wanted.length) return []
  return (jobs.data ?? []).filter((j) => isActiveJob(j) && wanted.some(([k, v]) => j.refs[k] === v))
}

export function useStartJob<K extends JobKind>(kind: K) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: JobRequests[K]) => evApi.startJob(kind, body),
    onSuccess: (job) => {
      client.setQueryData<Job[]>(evKeys.jobs, (old) => [job, ...(old ?? []).filter((j) => j.id !== job.id)])
      void client.invalidateQueries({ queryKey: evKeys.jobs })
    },
  })
}

export function useCancelJob() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => evApi.cancelJob(id),
    onSuccess: () => void client.invalidateQueries({ queryKey: evKeys.jobs }),
  })
}

export function usePutDecisions(proposal: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: DecisionsRequest) => evApi.putDecisions(proposal, body),
    onSuccess: () => void client.invalidateQueries({ queryKey: evKeys.of("proposals", proposal) }),
  })
}

/** Say which kind a proposal asks: starts the job that drafts, checks and makes the cards again from that kind. */
export function usePutKind(proposal: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: KindRequest) => evApi.putKind(proposal, body),
    onSuccess: (job) => {
      client.setQueryData<Job[]>(evKeys.jobs, (old) => [job, ...(old ?? []).filter((j) => j.id !== job.id)])
      void client.invalidateQueries({ queryKey: evKeys.jobs })
      void client.invalidateQueries({ queryKey: evKeys.of("proposals", proposal) })
    },
  })
}
