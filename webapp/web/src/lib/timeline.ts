/**
 * Run timeline state (Run page, Timeline tab; plan "Frontend pages" 4).
 *
 * Two inputs feed one state: the steps the backend has already summarised (GET .../steps, a
 * `seed`) and the raw events.jsonl records of the live stream (`event: record` of
 * GET .../stream, one `record` action each; `event: done` when the agent stops writing the run).
 * Records are grouped per (agent, step) like the backend's steps_of() and agent/timeline.py do.
 *
 * Merging is idempotent: a record seen twice (same task_id) is skipped, and a seeded step that
 * the stream replays only fills fields still empty; claims merge by claim id (rejected ones by
 * reason and triple), coverage reasons as a set. So the stream may replay from the first line,
 * reconnect, or start after the seed without duplicating anything.
 *
 * Derived numbers (tokens used, research steps, phase changes, the budget notices the agent got
 * at 50/75/90 %) are computed from the steps in `summarize`, never accumulated, for the same reason.
 */
import type { ClaimRef, EventRecord, ModelCall, Step } from "@/api/types"

export interface TimelineStep {
  key: string
  step: number
  agent_id: string
  phase: string | null
  /** research, attach, concept or batch */
  origin: string
  model_call: ModelCall | null
  final_answer: boolean
  command: string | null
  exit_code: number | null
  timed_out: boolean
  output_head: string | null
  output_bytes: number | null
  claims: ClaimRef[]
  coverage: string[]
  /** agent ids spawned at this step (row 2.12) */
  spawned: string[]
  /** attach step: the answer fact it works on */
  fact_id: string | null
  started_at: string | null
}

export interface TimelineState {
  steps: Record<string, TimelineStep>
  seen: Record<string, true>
  records: number
  done: boolean
}

export type TimelineAction =
  | { type: "seed"; steps: Step[] }
  | { type: "record"; record: EventRecord }
  | { type: "done" }
  | { type: "reset" }

export const initialTimeline: TimelineState = { steps: {}, seen: {}, records: 0, done: false }

export const stepKey = (agent: string, step: number) => `${agent}:${step}`

function blank(agent: string, step: number): TimelineStep {
  return {
    key: stepKey(agent, step), step, agent_id: agent, phase: null, origin: "research", model_call: null,
    final_answer: false, command: null, exit_code: null, timed_out: false, output_head: null, output_bytes: null,
    claims: [], coverage: [], spawned: [], fact_id: null, started_at: null,
  }
}

const claimKey = (c: ClaimRef) => c.claim_id ?? `rejected:${c.reason ?? ""}:${String(c.s)}|${String(c.p)}|${String(c.o)}`

function mergeClaims(old: ClaimRef[], add: ClaimRef[]): ClaimRef[] {
  const keys = new Set(old.map(claimKey))
  return [...old, ...add.filter((c) => !keys.has(claimKey(c)))]
}

const union = (old: string[], add: string[]) => [...old, ...add.filter((x) => !old.includes(x))]

type ListField = "claims" | "coverage" | "spawned"
type Patch = Partial<Omit<TimelineStep, "key" | "step" | "agent_id" | ListField>> & {
  claims?: ClaimRef[]
  coverage?: string[]
  spawned?: string[]
}

/** Fill a step: scalar fields only where still empty (null/false), lists merged. */
function upsert(state: TimelineState, agent: string, step: number, patch: Patch): TimelineState {
  const key = stepKey(agent, step)
  const current = state.steps[key] ?? blank(agent, step)
  const next: TimelineStep = { ...current }
  for (const [field, value] of Object.entries(patch) as [keyof Patch, unknown][]) {
    if (value === undefined || value === null) continue
    if (field === "claims") next.claims = mergeClaims(current.claims, value as ClaimRef[])
    else if (field === "coverage") next.coverage = union(current.coverage, value as string[])
    else if (field === "spawned") next.spawned = union(current.spawned, value as string[])
    else if (field === "origin") next.origin = current.origin !== "research" ? current.origin : (value as string)
    else if (current[field] === null || current[field] === false) (next as unknown as Record<string, unknown>)[field] = value
  }
  return { ...state, steps: { ...state.steps, [key]: next } }
}

const str = (v: unknown): string | null => (typeof v === "string" ? v : null)
const numOrNull = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null)

function tokensOf(generated: Record<string, unknown>): number | null {
  const usage = generated.usage as Record<string, unknown> | undefined
  if (!usage) return null
  const total = numOrNull(usage.total_tokens)
  if (total) return total
  const parts = [numOrNull(usage.prompt_tokens), numOrNull(usage.completion_tokens)]
  return parts.some((p) => p !== null) ? parts.reduce<number>((a, b) => a + (b ?? 0), 0) : null
}

/** One events.jsonl record as a patch of its step (the fields the backend's steps_of() reads). */
export function patchFromRecord(record: EventRecord): Patch | null {
  const used = record.used ?? {}
  const gen = record.generated ?? {}
  const meta = record.custom_metadata ?? {}
  const origin = str(meta.origin) ?? "research"
  const common: Patch = { origin, fact_id: str(meta.fact_id), started_at: str(record.started_at) }
  // the attach step's records name their origin; older ones carry no phase
  const phase = str(meta.phase) ?? (origin === "attach" ? "attach" : null)
  switch (record.subtype) {
    case "ai_model_invocation": {
      const usage = (gen.usage ?? {}) as Record<string, unknown>
      return {
        ...common, phase, final_answer: meta.final_answer === true,
        model_call: {
          task_id: record.task_id ?? "", status: record.status ?? "finished", tokens: tokensOf(gen),
          prompt_tokens: numOrNull(usage.prompt_tokens), completion_tokens: numOrNull(usage.completion_tokens),
          seconds: numOrNull(meta.seconds), parse: str(gen.parse), reply: str(gen.reply), finish_reason: str(gen.finish_reason),
          final_answer: meta.final_answer === true, error: str(gen.error),
        },
      }
    }
    case "agent_tool":
      return {
        ...common, phase, command: str(used.command), exit_code: numOrNull(gen.exit_code),
        timed_out: gen.timed_out === true, output_bytes: numOrNull(gen.output_bytes),
      }
    case "claim":
      return {
        ...common,
        claims: [{
          claim_id: str(gen.claim_id), status: record.status === "accepted" ? "accepted" : "rejected",
          reason: str(meta.reason), s: meta.s, p: meta.p, o: meta.o,
        }],
      }
    case "coverage":
      return { ...common, coverage: str(gen.reason) ? [gen.reason as string] : [] }
    case "spawn":
      return { ...common, spawned: str(gen.agent_id) ? [gen.agent_id as string] : [] }
    default:
      return null // concept_pick and future subtypes: not part of the run timeline
  }
}

function seedPatch(s: Step): Patch {
  return {
    phase: s.phase, origin: s.origin, model_call: s.model_call, final_answer: s.model_call?.final_answer === true,
    command: s.command, exit_code: s.exit_code, timed_out: s.timed_out, output_head: s.output_head,
    output_bytes: s.output_bytes, claims: s.claims, coverage: s.coverage, spawned: s.spawned, fact_id: s.fact_id,
    started_at: s.started_at,
  }
}

export function timelineReducer(state: TimelineState, action: TimelineAction): TimelineState {
  switch (action.type) {
    case "reset":
      return initialTimeline
    case "done":
      return state.done ? state : { ...state, done: true }
    case "seed":
      return action.steps.reduce((acc, s) => upsert(acc, s.agent_id, s.step, seedPatch(s)), state)
    case "record": {
      const { record } = action
      if (record.task_id && state.seen[record.task_id]) return state
      const patch = patchFromRecord(record)
      const marked: TimelineState = {
        ...state,
        records: state.records + 1,
        seen: record.task_id ? { ...state.seen, [record.task_id]: true } : state.seen,
      }
      if (!patch || typeof record.step_id !== "number") return marked
      return upsert(marked, record.agent_id ?? "main", record.step_id, patch)
    }
  }
}

export interface PhaseChange {
  /** the step key where the new phase starts */
  at: string
  from: string | null
  to: string
}

/** The agent's one-time budget notice (agent/loop.py budget_warnings): research passed `percent` of a budget. */
export interface BudgetNotice {
  at: string
  percent: number
}

export interface TimelineSummary {
  steps: TimelineStep[]
  /** tokens of every model call shown (all agents, all phases) */
  tokens: number
  /** the main agent's tokens, as its token budget counts them */
  mainTokens: number
  /** steps of the main agent in the research phase that have a model call (the step budget) */
  researchSteps: number
  modelCalls: number
  claimsAccepted: number
  claimsRejected: number
  phaseChanges: PhaseChange[]
  coverage: { at: string; reason: string }[]
  budgetNotices: BudgetNotice[]
}

export const BUDGET_WARNINGS = [50, 75, 90] as const

const agentOrder = (a: string) => (a === "main" ? "" : a)
const isResearch = (s: TimelineStep) => (s.phase ?? "research") === "research" && s.origin === "research"

/** Steps in order (step number, main agent first) plus the numbers the budget line shows. */
export function summarize(state: TimelineState, budget?: { steps?: number; tokens?: number }): TimelineSummary {
  const steps = Object.values(state.steps).sort(
    (a, b) => a.step - b.step || agentOrder(a.agent_id).localeCompare(agentOrder(b.agent_id)),
  )
  let previous: string | null = null
  const phaseChanges: PhaseChange[] = []
  const budgetNotices: BudgetNotice[] = []
  const warned = new Set<number>()
  let researchSteps = 0
  let mainTokens = 0
  for (const s of steps) {
    if (s.agent_id !== "main") continue
    const phase = s.phase ?? (s.origin === "attach" ? "attach" : null)
    if (phase) {
      if (phase !== previous && previous !== null) phaseChanges.push({ at: s.key, from: previous, to: phase })
      previous = phase
    }
    if (s.origin !== "research" || !s.model_call) continue
    mainTokens += s.model_call.tokens ?? 0
    if (!isResearch(s)) continue
    researchSteps += 1
    // as the loop does after each research step: the highest threshold newly passed of either budget
    const used = 100 * Math.max(budget?.steps ? researchSteps / budget.steps : 0, budget?.tokens ? mainTokens / budget.tokens : 0)
    const passed = BUDGET_WARNINGS.filter((p) => used >= p && !warned.has(p))
    if (passed.length) {
      passed.forEach((p) => warned.add(p))
      budgetNotices.push({ at: s.key, percent: Math.max(...passed) })
    }
  }
  return {
    steps,
    tokens: steps.reduce((sum, s) => sum + (s.model_call?.tokens ?? 0), 0),
    mainTokens,
    researchSteps,
    modelCalls: steps.filter((s) => s.model_call).length,
    claimsAccepted: steps.reduce((n, s) => n + s.claims.filter((c) => c.status === "accepted").length, 0),
    claimsRejected: steps.reduce((n, s) => n + s.claims.filter((c) => c.status === "rejected").length, 0),
    phaseChanges,
    coverage: steps.flatMap((s) => s.coverage.map((reason) => ({ at: s.key, reason }))),
    budgetNotices,
  }
}
