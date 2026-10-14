import { useMemo } from "react"

import { useScore } from "@/api/hooks"
import type { Answer } from "@/api/types"
import { factStatuses } from "@/lib/facts"

/**
 * Support status per fact of a run's answer, from one request: the labels score.json's
 * detail.support holds (src/lib/facts.ts). Before scoring, facts are unsourced or not judged yet.
 * A failed request (not a 404, which means "not scored yet") is `error`: the statuses then only
 * say whether a fact cites a claim, and the caller must say the verdicts could not be loaded.
 */
export function useFactStatuses(runId: string, answer: Answer | null | undefined) {
  const score = useScore(runId, !!answer && answer.rows.length > 0)
  const statuses = useMemo(() => factStatuses(answer, score.data), [answer, score.data])
  return {
    statuses,
    score: score.data ?? null,
    loading: score.isLoading,
    error: score.isError ? score.error : null,
    retry: () => void score.refetch(),
  }
}
