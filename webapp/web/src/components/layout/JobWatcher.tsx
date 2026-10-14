/**
 * Watches the job queue from every page: when a job finishes, the data it changed is refetched
 * (briefs after a proposal, runs and questions after a run, gold after a gold build) and a toast
 * says so, with a link to the run or the log. Jobs already finished when the app opens stay quiet.
 */
import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef } from "react"
import { useNavigate } from "react-router"
import { toast } from "sonner"

import { isActiveJob, keys, useJobs } from "@/api/hooks"
import type { Job } from "@/api/types"

const REFRESH: Record<string, readonly (readonly string[])[]> = {
  concepts: [keys.questions],
  run: [keys.runs, keys.questions, ["results"]],
  gold: [keys.gold, keys.questions],
}

export function JobWatcher() {
  const jobs = useJobs()
  const client = useQueryClient()
  const navigate = useNavigate()
  const previous = useRef<Map<string, Job["state"]> | null>(null)

  useEffect(() => {
    if (!jobs.data) return
    const before = previous.current
    previous.current = new Map(jobs.data.map((j) => [j.id, j.state]))
    if (!before) return
    for (const job of jobs.data) {
      const was = before.get(job.id)
      if (!was || !isActiveJob({ state: was }) || isActiveJob(job)) continue
      for (const key of REFRESH[job.kind] ?? [keys.runs]) void client.invalidateQueries({ queryKey: key })
      const what = `${job.kind} job ${job.id}${job.qid ? ` (${job.qid})` : ""}`
      const action = job.run_id
        ? { label: "Open run", onClick: () => navigate(`/runs/${encodeURIComponent(job.run_id!)}`) }
        : { label: "Open log", onClick: () => navigate(`/jobs/${job.id}`) }
      if (job.state === "done") {
        toast.success(`${what} is done`, { description: job.warnings?.length ? job.warnings.join("; ") : undefined, action })
      } else {
        toast.error(`${what} failed`, { description: job.error ?? `exit ${job.exit_code ?? "?"}`, action })
      }
    }
  }, [jobs.data, client, navigate])

  return null
}
