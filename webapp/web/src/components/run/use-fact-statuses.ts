import { useFactWalks } from "@/api/hooks"
import type { Answer } from "@/api/types"
import { answerFacts, factStatus, type FactStatus } from "@/lib/facts"

/**
 * Support status per fact id (and whether its walk is still loading): unsourced facts need no
 * request; sourced ones take the judge's verdict from their walk.
 */
export function useFactStatuses(runId: string, answer: Answer | null | undefined) {
  const facts = answerFacts(answer).map((r) => r.fact)
  const sourced = facts.filter((f) => f.claims.length > 0)
  const walks = useFactWalks(runId, sourced.map((f) => f.id))
  const byId = new Map<string, { status: FactStatus; loading: boolean }>()
  for (const fact of facts) {
    const index = sourced.indexOf(fact)
    const walk = index >= 0 ? walks[index] : undefined
    byId.set(fact.id, { status: factStatus(fact, walk?.data?.support), loading: !!walk?.isPending })
  }
  return byId
}
