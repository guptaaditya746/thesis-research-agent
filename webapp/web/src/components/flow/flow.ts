/**
 * The guided flow's state, kept in the URL (`/flow/:qid/:step?protocol=repo:<protocol>&corpus=...&run=...`),
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

/** "hand-written <protocol>", "proposal p1 (frozen)". */
export function protocolLabel(ref: ProtocolRef | null): string {
  if (!ref) return "none chosen"
  return ref.source === "repo" ? `hand-written ${ref.name}` : `proposal ${ref.name}`
}

/** What each step asks of the person, in one heading and one sentence. */
export const STEP_TEXT: Record<StepId, { title: string; hint: string }> = {
  protocol: {
    title: "Choose the protocol",
    hint: "The protocol says what the engine extracts from each paper and how it combines it. Use the hand-written one, or propose your own and decide its cards.",
  },
  corpus: {
    title: "Choose a corpus",
    hint: "The papers the run reads. Use one that is built, or build a template corpus (no model needed).",
  },
  run: {
    title: "Run the engine and the baselines",
    hint: "Start the engine on the chosen corpus, run the two baselines beside it, then choose the engine run to read.",
  },
  graph: {
    title: "Read the evidence graph",
    hint: "What the engine found in each paper, and how the pieces connect.",
  },
  answer: {
    title: "Read the answer",
    hint: "The engine's answer in the form of the question's kind, with the baselines' answers beside it.",
  },
}

/** The question counts as step 1; the flow's steps follow it. */
export const TOTAL_STEPS = STEPS.length + 1

/** Whether a step's choice is made, and the value it shows as chosen. */
export function stepState(flow: Flow, step: StepId): { done: boolean; value: string | null } {
  switch (step) {
    case "protocol": return { done: !!flow.protocol, value: flow.protocol ? flow.protocol.name : null }
    case "corpus": return { done: !!flow.corpus, value: flow.corpus }
    case "run": return { done: !!flow.run, value: flow.run }
    default: return { done: false, value: null }
  }
}
