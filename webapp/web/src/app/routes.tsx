/**
 * Routes. The main flow is the evidence-level viewer (the supervisor's flow, STATE.md §4): protocol,
 * corpora, runs with their papers, scores. The earlier work (docs/earlier-work.md: questions, concept pick,
 * claim on/off runs, results, gold, jobs, chat) lives under /earlier, framed as such. Pages load lazily, so
 * the graph (React Flow), the charts (recharts) and the chat stay out of the first bundle until needed.
 */
import { lazy } from "react"
import type { RouteObject } from "react-router"

import { AppLayout } from "@/components/layout/AppLayout"
import { EarlierFrame } from "@/components/layout/EarlierFrame"

import { RouteError } from "./RouteError"

const HomePage = lazy(() => import("@/pages/ev/HomePage"))
const CorporaPage = lazy(() => import("@/pages/ev/CorporaPage"))
const CorpusPage = lazy(() => import("@/pages/ev/CorpusPage"))
const CorpusPaperPage = lazy(() => import("@/pages/ev/CorpusPaperPage"))
const ProtocolsPage = lazy(() => import("@/pages/ev/ProtocolsPage"))
const ProtocolPage = lazy(() => import("@/pages/ev/ProtocolPage"))
const ProposalPage = lazy(() => import("@/pages/ev/ProposalPage"))
const EvRunsPage = lazy(() => import("@/pages/ev/RunsPage"))
const EvRunPage = lazy(() => import("@/pages/ev/RunPage"))
const RunPaperPage = lazy(() => import("@/pages/ev/RunPaperPage"))
const ScoresPage = lazy(() => import("@/pages/ev/ScoresPage"))
const ReportPage = lazy(() => import("@/pages/ev/ReportPage"))
const EvComparePage = lazy(() => import("@/pages/ev/ComparePage"))
const ShiftPage = lazy(() => import("@/pages/ev/ShiftPage"))
const BenchmarkPage = lazy(() => import("@/pages/ev/BenchmarkPage"))

const OverviewPage = lazy(() => import("@/pages/OverviewPage"))
const QuestionPage = lazy(() => import("@/pages/QuestionPage"))
const RunsPage = lazy(() => import("@/pages/RunsPage"))
const RunPage = lazy(() => import("@/pages/RunPage"))
const ComparePage = lazy(() => import("@/pages/ComparePage"))
const ResultsPage = lazy(() => import("@/pages/ResultsPage"))
const GoldPage = lazy(() => import("@/pages/GoldPage"))
const JobsPage = lazy(() => import("@/pages/JobsPage"))
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage"))

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppLayout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "corpora", element: <CorporaPage /> },
      { path: "corpora/:name", element: <CorpusPage /> },
      { path: "corpora/:name/papers/:paper", element: <CorpusPaperPage /> },
      { path: "protocol", element: <ProtocolsPage /> },
      { path: "protocol/:name", element: <ProtocolPage /> },
      { path: "proposals/:name", element: <ProposalPage /> },
      { path: "runs", element: <EvRunsPage /> },
      { path: "runs/:runId", element: <EvRunPage /> },
      { path: "runs/:runId/papers/:doc", element: <RunPaperPage /> },
      { path: "scores", element: <ScoresPage /> },
      { path: "scores/reports/:id", element: <ReportPage /> },
      { path: "scores/compares/:id", element: <EvComparePage /> },
      { path: "scores/shifts/:id", element: <ShiftPage /> },
      { path: "scores/benchmarks/:id", element: <BenchmarkPage /> },
      {
        path: "earlier",
        element: <EarlierFrame />,
        children: [
          { index: true, element: <OverviewPage /> },
          { path: "questions/:qid", element: <QuestionPage /> },
          { path: "runs", element: <RunsPage /> },
          { path: "runs/:runId", element: <RunPage /> },
          { path: "compare/:qid", element: <ComparePage /> },
          { path: "results", element: <ResultsPage /> },
          { path: "gold", element: <GoldPage /> },
          { path: "jobs", element: <JobsPage /> },
          { path: "jobs/:jobId", element: <JobsPage /> },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]
