/**
 * The guided flow's state, kept in the URL (`/flow/:qid/:step?protocol=repo:rag-factuality&corpus=...&run=...`),
 * so a reload, a link or the back button keep the choices: the protocol, the corpus, the run (an engine run's
 * `<group>~<name>`) and the proposal being worked on.
 */
import { useSearchParams } from "react-router"

import type { ProtocolRef, Question } from "@/api/ev"
import { parseProtocolParam } from "@/lib/jobs"

export const STEPS = [
  { id: "protocol", label: "Protocol" },
  { id: "corpus", label: "Corpus" },
  { id: "run", label: "Run" },
  { id: "graph", label: "Evidence graph" },
  { id: "answer", label: "Answer" },
  { id: "scores", label: "Scores" },
] as const
export type StepId = (typeof STEPS)[number]["id"]

export const isStep = (value: string | undefined): value is StepId => STEPS.some((s) => s.id === value)

export interface Flow {
  question: Question
  /** The chosen protocol; the hand-written one until another is chosen. */
  protocol: ProtocolRef | null
  corpus: string | null
  run: string | null
  proposal: string | null
  /** `push` for a choice the user made (Back undoes it); a choice that follows from a started job replaces. */
  set: (patch: Partial<Record<"protocol" | "corpus" | "run" | "proposal", string | null>>, how?: { push?: boolean }) => void
  href: (step: StepId) => string
}

export function useFlow(question: Question): Flow {
  const [params, setParams] = useSearchParams()
  const chosen = parseProtocolParam(params.get("protocol"))
  const protocol = chosen ?? (question.protocol ? { source: "repo" as const, name: question.protocol } : null)
  const set: Flow["set"] = (patch, how) =>
    setParams((old) => {
      const next = new URLSearchParams(old)
      for (const [k, v] of Object.entries(patch)) {
        if (v) next.set(k, v)
        else next.delete(k)
      }
      return next
    }, { replace: !how?.push })
  const href = (step: StepId) => {
    const query = params.toString()
    return `/flow/${encodeURIComponent(question.id)}/${step}${query ? `?${query}` : ""}`
  }
  return { question, protocol, corpus: params.get("corpus"), run: params.get("run"), proposal: params.get("proposal"), set, href }
}

/** "hand-written rag-factuality", "proposal p1 (frozen)". */
export function protocolLabel(ref: ProtocolRef | null): string {
  if (!ref) return "none chosen"
  return ref.source === "repo" ? `hand-written ${ref.name}` : `proposal ${ref.name}`
}
