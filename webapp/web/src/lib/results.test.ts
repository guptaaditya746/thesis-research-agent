import { describe, expect, it } from "vitest"

import type { ResultsReport } from "@/api/types"
import { RESULTS } from "@/mocks/fixtures"

import { conditionBars, costGroups, metricGroups, questionRows, shareDomainMax } from "./results"

describe("results report to chart data", () => {
  it("gives one bar per condition with the interval as distances from the mean", () => {
    const [on, off] = conditionBars(RESULTS, "support_share")
    expect(on).toMatchObject({ condition: "claim_on", label: "claim on", mean: 0.71, low: 0.63, high: 0.78, n: 12 })
    expect(on.error![0]).toBeCloseTo(0.08)
    expect(on.error![1]).toBeCloseTo(0.07)
    expect(off.condition).toBe("claim_off")
    expect(off.mean).toBe(0.52)
  })

  it("keeps a condition without data, with no interval", () => {
    const report: ResultsReport = { ...RESULTS, conditions: { claim_on: RESULTS.conditions.claim_on, claim_off: {} } }
    const [, off] = conditionBars(report, "support_share")
    expect(off).toMatchObject({ mean: null, low: null, high: null, error: null, n: 0 })
  })

  it("clips a negative distance when the interval does not contain the mean", () => {
    const report: ResultsReport = {
      ...RESULTS,
      conditions: { ...RESULTS.conditions, claim_on: { support_share: { mean: 0.5, ci: { low: 0.55, high: 0.7 }, n: 12 } } },
    }
    expect(conditionBars(report, "support_share")[0].error).toEqual([0, expect.closeTo(0.2)])
  })

  it("groups several metrics with both conditions as series", () => {
    const groups = metricGroups(RESULTS, ["fact_f1", "row_f1"])
    expect(groups.map((g) => g.label)).toEqual(["Fact F1", "Row F1"])
    expect(groups[0]).toMatchObject({ claim_on: 0.54, claim_off: 0.53, claim_on_ci: [0.46, 0.62], claim_off_ci: [0.45, 0.61] })
    expect(groups[1].claim_off_error?.[0]).toBeCloseTo(0.08)
  })

  it("shows cost with and without attach, colour kept per condition", () => {
    const [withAttach, without] = costGroups(RESULTS, "tokens")
    expect(withAttach).toEqual({ measure: "with attach", claim_on: 1_284_000, claim_off: 1_398_000 })
    expect(without).toEqual({ measure: "without attach", claim_on: 1_284_000, claim_off: 1_102_000 })
    const [, seconds] = costGroups(RESULTS, "seconds")
    expect(seconds.claim_off).toBe(2_890)
  })

  it("falls back to the total for claim_on when the report has no without-attach value", () => {
    const report: ResultsReport = { ...RESULTS, conditions: { ...RESULTS.conditions, claim_on: { tokens: { mean: 10, ci: null, n: 1 } } } }
    expect(costGroups(report, "tokens")[1].claim_on).toBe(10)
  })

  it("lists the questions in order with on, off and their difference", () => {
    const rows = questionRows(RESULTS, "support_share")
    expect(rows.map((r) => r.qid)).toEqual(["q01", "q02", "q03", "q04", "q05", "q06", "q07", "q08", "q09", "q10", "q11", "q12"])
    expect(rows[0]).toMatchObject({ category: "corpus_wide", runs: "3 / 3", on: 0.74, off: 0.55 })
    expect(rows[0].diff).toBeCloseTo(0.19)
    const missing = questionRows({ ...RESULTS, per_question: [{ ...RESULTS.per_question[0], claim_off: {} }] }, "support_share")
    expect(missing[0].diff).toBeNull()
  })

  it("extends a share axis only when an interval goes past 1", () => {
    expect(shareDomainMax(conditionBars(RESULTS, "support_share"))).toBe(1)
    expect(shareDomainMax([{ condition: "claim_on", label: "", mean: 1, low: 0.9, high: 1.12, error: null, n: 1 }])).toBe(1.2)
  })
})
