import { createContext, useContext } from "react"

/** What the claim walk opens on: an answer fact (with its judge verdict) or bare claims (a graph edge). */
export type WalkTarget = { kind: "fact"; factId: string } | { kind: "claims"; claimIds: string[]; label?: string }

export interface WalkApi {
  runId: string
  open: (target: WalkTarget) => void
}

export const WalkContext = createContext<WalkApi>({ runId: "", open: () => {} })

export const useWalk = () => useContext(WalkContext)
