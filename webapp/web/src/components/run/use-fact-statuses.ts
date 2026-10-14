import { useMemo } from "react"

import { useScore } from "@/api/hooks"
import type { Answer } from "@/api/types"
import { factStatuses } from "@/lib/facts"

/**
 * Support status per fact of a run's answer, from one request: the labels score.json's
 * detail.support holds (src/lib/facts.ts). Before scoring, facts are unsourced or not judged yet.
 */
export function useFactStatuses(runId: string, answer: Answer | null | undefined) {
  const score = useScore(runId, !!answer && answer.rows.length > 0)
  const statuses = useMemo(() => factStatuses(answer, score.data), [answer, score.data])
  return { statuses, score: score.data ?? null, loading: score.isLoading }
}
