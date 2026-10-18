/**
 * Watches the jobs from every page: when a job ends, everything read from disk is refetched (a new corpus,
 * run, score or proposal) and a toast says so, with a link to what it made or to its log. Jobs that had
 * already ended when the app opened stay quiet.
 */
import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef } from "react"
import { useNavigate } from "react-router"
import { toast } from "sonner"

import { isActiveJob, useJobs, type Job } from "@/api/ev"
import { jobTarget, jobTitle } from "@/lib/jobs"

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
    const ended = jobs.data.filter((job) => {
      const was = before.get(job.id)
      return was && isActiveJob({ state: was }) && !isActiveJob(job)
    })
    if (!ended.length) return
    void client.invalidateQueries({ predicate: (q) => q.queryKey[0] === "ev" && q.queryKey[1] !== "jobs" })
    for (const job of ended) {
      const target = jobTarget(job)
      const action = job.state === "done" && target
        ? { label: "Open", onClick: () => navigate(target) }
        : { label: "Open log", onClick: () => navigate(`/jobs/${job.id}`) }
      if (job.state === "done") {
        toast.success(`${jobTitle(job)} is done`, { description: job.warnings.length ? job.warnings.join("; ") : undefined, action })
      } else {
        toast.error(`${jobTitle(job)} failed`, { description: job.error ?? `exit ${job.exit_code ?? "?"}`, action })
      }
    }
  }, [jobs.data, client, navigate])

  return null
}

