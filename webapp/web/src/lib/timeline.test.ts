import { describe, expect, it } from "vitest"

import type { EventRecord, Step } from "@/api/types"
import { LIVE_RECORDS, RUN, STEPS } from "@/mocks/fixtures"

import { budgetNoticeAsk, initialTimeline, patchFromRecord, summarize, timelineReducer, type TimelineState } from "./timeline"

const fold = (records: EventRecord[], state: TimelineState = initialTimeline) =>
  records.reduce((s, record) => timelineReducer(s, { type: "record", record }), state)

const call = (step: number, total: number, phase = "research", extra: Partial<EventRecord> = {}): EventRecord => ({
  subtype: "ai_model_invocation", step_id: step, task_id: `t${step}a`, agent_id: "main", status: "finished",
  generated: { usage: { prompt_tokens: total - 10, completion_tokens: 10, total_tokens: total }, parse: "strict", reply: "command", finish_reason: "stop" },
  custom_metadata: { phase, seconds: 1.5, final_answer: false },
  ...extra,
})

describe("timeline reducer", () => {
  it("groups the records of a step: model call, claims, command", () => {
    const state = fold(LIVE_RECORDS.slice(0, 3))
    const [step] = summarize(state).steps
    expect(step.step).toBe(4)
    expect(step.model_call).toMatchObject({ tokens: 10_090, seconds: 5.6, parse: "strict", reply: "command" })
    expect(step.command).toContain("claim")
    expect(step.exit_code).toBe(0)
    expect(step.claims).toEqual([{ claim_id: "claim-000001", status: "accepted", reason: null, s: "p6", p: "evaluatesOn", o: "HotpotQA" }])
  })

  it("records rejected claims with the broker's reason", () => {
    const state = fold(LIVE_RECORDS)
    const step5 = summarize(state).steps.find((s) => s.step === 5)!
    expect(step5.claims).toMatchObject([{ claim_id: null, status: "rejected", reason: "not_found", o: "Natural Questions" }])
    expect(step5.exit_code).toBe(1)
  })

  it("is idempotent: a replayed stream adds nothing", () => {
    const once = fold(LIVE_RECORDS)
    const twice = fold(LIVE_RECORDS, once)
    expect(twice.steps).toEqual(once.steps)
    expect(twice.records).toBe(once.records)
  })

  it("merges the live records into the seeded steps without duplicates", () => {
    const seeded = timelineReducer(initialTimeline, { type: "seed", steps: STEPS[RUN.live] })
    const state = fold(LIVE_RECORDS, seeded)
    const summary = summarize(state)
    expect(summary.steps.map((s) => s.step)).toEqual([1, 2, 3, 4, 5, 6])
    // seeded output heads survive; the stream does not carry them
    expect(summary.steps[0].output_head).toContain("p1.md")
    // a record for a seeded step fills only what the seed lacked
    const again = timelineReducer(state, { type: "seed", steps: STEPS[RUN.live] })
    expect(summarize(again).steps).toEqual(summary.steps)
  })

  it("sums tokens, counts research steps and claims, and finds phase changes", () => {
    const seeded = timelineReducer(initialTimeline, { type: "seed", steps: STEPS[RUN.live] })
    const summary = summarize(fold(LIVE_RECORDS, seeded))
    expect(summary.tokens).toBe(8_870 + 9_502 + 1_210 + 10_090 + 10_802 + 1_840)
    expect(summary.researchSteps).toBe(5) // step 6 is the conclude phase
    expect(summary.claimsAccepted).toBe(1)
    expect(summary.claimsRejected).toBe(1)
    expect(summary.phaseChanges).toEqual([{ at: "main:6", from: "research", to: "conclude" }])
    expect(summary.coverage).toEqual([{ at: "main:3", reason: "unparsed" }])
    expect(summary.steps.at(-1)?.final_answer).toBe(true)
  })

  it("keeps sub-agent steps apart and orders the main agent first", () => {
    const summary = summarize(timelineReducer(initialTimeline, { type: "seed", steps: STEPS[RUN.on] }))
    const keys = summary.steps.map((s) => s.key)
    expect(keys).toContain("sub-01:6")
    expect(keys.indexOf("main:5")).toBeLessThan(keys.indexOf("sub-01:6"))
    expect(summary.claimsAccepted).toBe(7)
    expect(summary.claimsRejected).toBe(1)
  })

  it("marks the attach phase from the record's origin", () => {
    const attach = call(5, 4_000, "attach", { custom_metadata: { origin: "attach", seconds: 2 } })
    const state = fold([call(4, 2_000), attach])
    const summary = summarize(state)
    expect(summary.steps[1]).toMatchObject({ phase: "attach", origin: "attach" })
    expect(summary.phaseChanges).toEqual([{ at: "main:5", from: "research", to: "attach" }])
    expect(summary.researchSteps).toBe(1)
  })

  it("collects coverage reasons as a set and spawned agents", () => {
    const coverage = (task: string): EventRecord => ({
      subtype: "coverage", step_id: 2, task_id: task, agent_id: "main", status: "not_run",
      generated: { reason: "unparsed" }, custom_metadata: { phase: "research" },
    })
    const spawn: EventRecord = { subtype: "spawn", step_id: 2, task_id: "s1", generated: { agent_id: "sub-01" } }
    const summary = summarize(fold([coverage("c1"), coverage("c2"), spawn]))
    expect(summary.steps[0].coverage).toEqual(["unparsed"])
    expect(summary.steps[0].spawned).toEqual(["sub-01"])
  })

  it("falls back to prompt + completion tokens and ignores unknown subtypes", () => {
    expect(patchFromRecord({ subtype: "concept_pick", step_id: 0 })).toBeNull()
    const noTotal = call(1, 0, "research", { generated: { usage: { prompt_tokens: 90, completion_tokens: 10 } } })
    expect(summarize(fold([noTotal])).tokens).toBe(100)
  })

  it("marks done and resets", () => {
    const done = timelineReducer(fold([call(1, 10)]), { type: "done" })
    expect(done.done).toBe(true)
    expect(timelineReducer(done, { type: "reset" })).toEqual(initialTimeline)
  })

  it("seeds from the steps endpoint as they are", () => {
    const steps: Step[] = STEPS[RUN.off]
    const summary = summarize(timelineReducer(initialTimeline, { type: "seed", steps }))
    expect(summary.steps).toHaveLength(8)
    expect(summary.steps.filter((s) => s.origin === "attach")).toHaveLength(4)
    expect(summary.steps.find((s) => s.step === 8)).toMatchObject({ fact_id: "f4", coverage: ["no_source_found"] })
    expect(summary.steps.find((s) => s.step === 4)?.final_answer).toBe(true)
    expect(summary.tokens).toBe(48_900)
  })
})

describe("budget notices", () => {
  const research = (n: number, tokens: number) => call(n, tokens)
  const V2 = [50, 75, 90] // agent/loop.py LoopSettings().budget_warnings, as config.json records it

  it("marks where research passed 50, 75 and 90 % of the step budget, once each", () => {
    const state = fold([1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => research(n, 100)))
    const summary = summarize(state, { steps: 10, tokens: 1_000_000 }, V2)
    expect(summary.researchSteps).toBe(10)
    expect(summary.budgetNotices).toEqual([
      { at: "main:5", percent: 50 },
      { at: "main:8", percent: 75 },
      { at: "main:9", percent: 90 },
    ])
  })

  it("takes the higher of the two budgets and gives one notice, the highest, when a step passes several", () => {
    // one large prompt jumps from 40 % to 95 % of the token budget
    const summary = summarize(fold([research(1, 400), research(2, 550)]), { steps: 60, tokens: 1_000 }, V2)
    expect(summary.mainTokens).toBe(950)
    expect(summary.budgetNotices).toEqual([{ at: "main:2", percent: 90 }])
  })

  it("counts only the main agent's research steps, and gives no notice without a budget", () => {
    const sub: EventRecord = { ...call(2, 900), task_id: "sub2", agent_id: "sub-01" }
    const conclude = call(3, 900, "conclude", { task_id: "c3" })
    const summary = summarize(fold([research(1, 100), sub, conclude]), { steps: 2, tokens: 10_000 }, V2)
    expect(summary.researchSteps).toBe(1)
    expect(summary.mainTokens).toBe(1_000) // the conclude call counts toward the tokens, not the steps
    expect(summary.budgetNotices).toEqual([{ at: "main:1", percent: 50 }])
    expect(summarize(fold([research(1, 100)]), undefined, V2).budgetNotices).toEqual([])
  })

  it("follows the thresholds the run recorded, and draws none for a run that recorded none (prompt v1)", () => {
    const state = fold([1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => research(n, 100)))
    expect(summarize(state, { steps: 10, tokens: 1_000_000 }, [80]).budgetNotices).toEqual([{ at: "main:8", percent: 80 }])
    // agent/loop.py LEGACY_V1 has budget_warnings=(); older harnesses record no list: no notices
    expect(summarize(state, { steps: 10, tokens: 1_000_000 }, []).budgetNotices).toEqual([])
    expect(summarize(state, { steps: 10, tokens: 1_000_000 }).budgetNotices).toEqual([])
  })

  it("words each notice as the loop did, with the draft file only when the run had one", () => {
    expect(budgetNoticeAsk(90, "answer-draft.json")).toBe("conclude now")
    expect(budgetNoticeAsk(75, "answer-draft.json")).toBe("stop opening new leads, update answer-draft.json")
    expect(budgetNoticeAsk(50, "answer-draft.json")).toBe("bring answer-draft.json up to date")
    expect(budgetNoticeAsk(75, null)).toBe("stop opening new leads")
    expect(budgetNoticeAsk(50, null)).toBeNull()
  })
})
