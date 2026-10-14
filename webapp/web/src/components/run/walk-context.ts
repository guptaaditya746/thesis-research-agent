import { createContext, useContext } from "react"

import type { Answer } from "@/api/types"
import { factsByClaim } from "@/lib/facts"

/**
 * What the claim walk opens on: an answer fact (with its judge verdict) or bare claims (a graph
 * edge, possibly merged from several claims), each with the answer facts that cite it.
 */
export type WalkTarget =
  | { kind: "fact"; factId: string }
  | { kind: "claims"; claimIds: string[]; label?: string; citedBy?: Record<string, string[]> }

/**
 * The walk of some claims (a graph edge's, a claim of the Claims tab): the walk of the one fact
 * that cites every one of them, else a walk over all the claims, each naming the facts citing it,
 * so no claim's evidence is left out.
 */
export function walkTargetForClaims(claimIds: string[], answer: Answer | null | undefined, label?: string): WalkTarget {
  const facts = factsByClaim(answer)
  const citedBy = Object.fromEntries(claimIds.map((c) => [c, [...new Set((facts.get(c) ?? []).map((r) => r.fact.id))]]))
  const factIds = new Set(Object.values(citedBy).flat())
  if (factIds.size === 1 && claimIds.every((c) => citedBy[c].length > 0)) return { kind: "fact", factId: [...factIds][0] }
  return { kind: "claims", claimIds, label, citedBy }
}

export interface WalkApi {
  runId: string
  open: (target: WalkTarget) => void
}

export const WalkContext = createContext<WalkApi>({ runId: "", open: () => {} })

export const useWalk = () => useContext(WalkContext)
