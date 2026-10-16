/**
 * Routes of docs/earlier-work.md "Backend API and frontend pages". Pages load lazily, so the graph (React
 * Flow), the charts (recharts) and the chat stay out of the first bundle until needed.
 */
import { lazy } from "react"
import type { RouteObject } from "react-router"

import { AppLayout } from "@/components/layout/AppLayout"

import { RouteError } from "./RouteError"

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
      { index: true, element: <OverviewPage /> },
      { path: "questions/:qid", element: <QuestionPage /> },
      { path: "runs", element: <RunsPage /> },
      { path: "runs/:runId", element: <RunPage /> },
      { path: "compare/:qid", element: <ComparePage /> },
      { path: "results", element: <ResultsPage /> },
      { path: "gold", element: <GoldPage /> },
      { path: "jobs", element: <JobsPage /> },
      { path: "jobs/:jobId", element: <JobsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]
