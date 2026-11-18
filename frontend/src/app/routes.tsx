/**
 * Routes. Home selects a question; its guided flow (`/flow/:qid/:step`) follows the supervisor's order
 * (STATE.md §1, §4) and starts the missing steps as jobs; the viewer's pages (protocols and proposals,
 * corpora, runs with their papers and scores, the Report over all runs) and the jobs are linked from it. Pages
 * load lazily, so the graph (React Flow) and the charts (recharts) stay out of the first bundle until needed.
 * The old Scores page's addresses (/scores, /scores/...) lead to the same place under /report.
 */
import { lazy } from "react"
import { Navigate, useLocation, type RouteObject } from "react-router"

import { AppLayout } from "@/components/layout/AppLayout"

import { RouteError } from "./RouteError"

const HomePage = lazy(() => import("@/pages/ev/HomePage"))
const FlowPage = lazy(() => import("@/pages/flow/FlowPage"))
const JobsPage = lazy(() => import("@/pages/JobsPage"))
const CorporaPage = lazy(() => import("@/pages/ev/CorporaPage"))
const CorpusPage = lazy(() => import("@/pages/ev/CorpusPage"))
const CorpusPaperPage = lazy(() => import("@/pages/ev/CorpusPaperPage"))
const ProtocolsPage = lazy(() => import("@/pages/ev/ProtocolsPage"))
const ProtocolPage = lazy(() => import("@/pages/ev/ProtocolPage"))
const ProposalPage = lazy(() => import("@/pages/ev/ProposalPage"))
const EvRunsPage = lazy(() => import("@/pages/ev/RunsPage"))
const EvRunPage = lazy(() => import("@/pages/ev/RunPage"))
const RunPaperPage = lazy(() => import("@/pages/ev/RunPaperPage"))
const ReportsPage = lazy(() => import("@/pages/ev/ReportsPage"))
const ReportPage = lazy(() => import("@/pages/ev/ReportPage"))
const EvComparePage = lazy(() => import("@/pages/ev/ComparePage"))
const ShiftPage = lazy(() => import("@/pages/ev/ShiftPage"))
const BenchmarkPage = lazy(() => import("@/pages/ev/BenchmarkPage"))
const PlanPage = lazy(() => import("@/routes/plan/PlanPage"))
const SystemPage = lazy(() => import("@/routes/system/SystemPage"))
const ReviewPage = lazy(() => import("@/routes/review/ReviewPage"))
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage"))

/** /scores/<rest> (the old Scores page's addresses) → /report/<rest>, keeping the query. */
function OldScoresPath() {
  const { pathname, search } = useLocation()
  return <Navigate to={`${pathname.replace(/^\/scores/, "/report")}${search}`} replace />
}

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppLayout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "flow/:qid", element: <FlowPage /> },
      { path: "flow/:qid/:step", element: <FlowPage /> },
      { path: "plan", element: <PlanPage /> },
      { path: "system", element: <SystemPage /> },
      { path: "review", element: <ReviewPage /> },
      { path: "review/:tab", element: <ReviewPage /> },
      { path: "jobs", element: <JobsPage /> },
      { path: "jobs/:jobId", element: <JobsPage /> },
      { path: "corpora", element: <CorporaPage /> },
      { path: "corpora/:name", element: <CorpusPage /> },
      { path: "corpora/:name/papers/:paper", element: <CorpusPaperPage /> },
      { path: "protocol", element: <ProtocolsPage /> },
      { path: "protocol/:name", element: <ProtocolPage /> },
      { path: "proposals/:name", element: <ProposalPage /> },
      { path: "runs", element: <EvRunsPage /> },
      { path: "runs/:runId", element: <EvRunPage /> },
      { path: "runs/:runId/papers/:doc", element: <RunPaperPage /> },
      { path: "report", element: <ReportsPage /> },
      { path: "report/reports/:id", element: <ReportPage /> },
      { path: "report/compares/:id", element: <EvComparePage /> },
      { path: "report/shifts/:id", element: <ShiftPage /> },
      { path: "report/benchmarks/:id", element: <BenchmarkPage /> },
      { path: "scores", element: <Navigate to="/report" replace /> },
      { path: "scores/*", element: <OldScoresPath /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]
