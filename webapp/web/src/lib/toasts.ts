/** Toasts for actions that start backend work (a Job) or fail. */
import type { NavigateFunction } from "react-router"
import { toast } from "sonner"

import type { Job } from "@/api/types"

export function announceJob(job: Job, navigate: NavigateFunction, what: string) {
  toast.success(`${what}: job ${job.id} ${job.state}`, {
    description: "Follow its log on the Jobs page.",
    action: { label: "Open log", onClick: () => navigate(`/jobs/${job.id}`) },
  })
}

export function announceError(what: string, error: unknown) {
  toast.error(what, { description: error instanceof Error ? error.message : String(error) })
}
