/** Toasts for actions that start backend work (a Job) or fail. */
import type { NavigateFunction } from "react-router"
import { toast } from "sonner"

import type { Job } from "@/api/ev"

import { jobTitle } from "./jobs"

export function announceJob(job: Job, navigate: NavigateFunction) {
  toast.success(`Started: ${jobTitle(job)}`, {
    description: job.lane === "model" ? "Model jobs run one at a time; it waits its turn in the queue." : undefined,
    action: { label: "Open log", onClick: () => navigate(`/jobs/${job.id}`) },
  })
}

export function announceError(what: string, error: unknown) {
  toast.error(what, { description: error instanceof Error ? error.message : String(error) })
}
