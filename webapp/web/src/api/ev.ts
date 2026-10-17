/**
 * The evidence-level viewer's API (/api/ev, webapp/evapi.py): types, client and TanStack Query hooks.
 *
 * Types are aliases onto the generated schema (src/api/schema.d.ts, `npm run gen:api`), so the pages read
 * the files with the fields their writers give them (synth, evidence, evaluation; docs/evidence-system.md).
 * Every endpoint is a read of files on disk: nothing here starts a run or calls a model, so queries are
 * fetched once and refetched on focus.
 */
import { useQuery } from "@tanstack/react-query"

import { getJson } from "./client"
import type { components } from "./schema"

type S = components["schemas"]

export type EvConfig = S["EvConfig"]
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
export type EvAnswer = S["EvAnswer"]
export type Study = S["Study"]
export type Counts = S["Counts"]
export type FunnelDoc = S["FunnelDoc"]
export type RunPaper = S["RunPaper"]
export type Item = S["Item"]
export type CallSummary = S["CallSummary"]
export type CallDetail = S["CallDetail"]
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

/** The effect directions of answer.json and ground_truth.json (evidence/rules.py DIRECTIONS + undetermined). */
export type Direction = "supports" | "contradicts" | "neutral" | "undetermined"
/** `{point, low, high, method}` of report.json `intervals` (evaluation/stats.py interval_row). */
export interface Interval {
  point?: number | null
  low?: number | null
  high?: number | null
  method?: string | null
}

const seg = encodeURIComponent

export const evApi = {
  config: (signal?: AbortSignal) => getJson<EvConfig>("/api/ev/config", undefined, signal),
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
  baselineTrace: (id: string, signal?: AbortSignal) => getJson<AgentTrace>(`/api/ev/runs/${seg(id)}/trace`, undefined, signal),
  scores: (signal?: AbortSignal) => getJson<ScoresIndex>("/api/ev/scores", undefined, signal),
  report: (id: string, signal?: AbortSignal) => getJson<ReportView>(`/api/ev/scores/reports/${seg(id)}`, undefined, signal),
  compare: (id: string, signal?: AbortSignal) => getJson<CompareTable>(`/api/ev/scores/compares/${seg(id)}`, undefined, signal),
  shift: (id: string, signal?: AbortSignal) => getJson<ShiftView>(`/api/ev/scores/shifts/${seg(id)}`, undefined, signal),
  benchmark: (id: string, signal?: AbortSignal) => getJson<BenchmarkView>(`/api/ev/scores/benchmarks/${seg(id)}`, undefined, signal),
}

export const evKeys = {
  all: ["ev"] as const,
  of: (...parts: string[]) => ["ev", ...parts] as const,
}

/** One query per endpoint; `enabled` waits for the ids a page gets from its route. */
function useEv<T>(parts: string[], fetcher: (signal: AbortSignal) => Promise<T>, enabled = true) {
  return useQuery({ queryKey: evKeys.of(...parts), queryFn: ({ signal }) => fetcher(signal), enabled })
}

export const useEvConfig = () => useEv(["config"], (s) => evApi.config(s))
export const useCorpora = () => useEv(["corpora"], (s) => evApi.corpora(s))
export const useCorpus = (name: string) => useEv(["corpora", name], (s) => evApi.corpus(name, s), !!name)
export const useCorpusPaper = (name: string, paper: string) =>
  useEv(["corpora", name, "papers", paper], (s) => evApi.corpusPaper(name, paper, s), !!name && !!paper)
export const useProtocols = () => useEv(["protocols"], (s) => evApi.protocols(s))
export const useProtocol = (name: string) => useEv(["protocols", name], (s) => evApi.protocol(name, s), !!name)
export const useProposals = () => useEv(["proposals"], (s) => evApi.proposals(s))
export const useProposal = (name: string) => useEv(["proposals", name], (s) => evApi.proposal(name, s), !!name)
export const useEvRuns = () => useEv(["runs"], (s) => evApi.runs(s))
export const useEvRun = (id: string) => useEv(["runs", id], (s) => evApi.run(id, s), !!id)
export const useRunPaper = (id: string, doc: string | null) =>
  useEv(["runs", id, "papers", doc ?? ""], (s) => evApi.runPaper(id, doc ?? "", s), !!id && !!doc)
export const useRunGraph = (id: string, enabled = true) => useEv(["runs", id, "graph"], (s) => evApi.runGraph(id, s), !!id && enabled)
export const useRunProtocol = (id: string, enabled = true) =>
  useEv(["runs", id, "protocol"], (s) => evApi.runProtocol(id, s), !!id && enabled)
export const useCall = (id: string, call: string | null) =>
  useEv(["runs", id, "calls", call ?? ""], (s) => evApi.call(id, call ?? "", s), !!id && !!call)
export const useCallTrace = (id: string, call: string | null, agentRun: string | null) =>
  useEv(["runs", id, "calls", call ?? "", "trace", agentRun ?? ""], (s) => evApi.callTrace(id, call ?? "", agentRun ?? "", s),
    !!id && !!call && !!agentRun)
export const useBaselineTrace = (id: string, enabled = true) =>
  useEv(["runs", id, "trace"], (s) => evApi.baselineTrace(id, s), !!id && enabled)
export const useScores = () => useEv(["scores"], (s) => evApi.scores(s))
export const useReport = (id: string) => useEv(["scores", "reports", id], (s) => evApi.report(id, s), !!id)
export const useCompare = (id: string) => useEv(["scores", "compares", id], (s) => evApi.compare(id, s), !!id)
export const useShift = (id: string) => useEv(["scores", "shifts", id], (s) => evApi.shift(id, s), !!id)
export const useBenchmark = (id: string) => useEv(["scores", "benchmarks", id], (s) => evApi.benchmark(id, s), !!id)
