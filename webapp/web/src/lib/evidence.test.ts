/** The evidence table's rows: lanes, the rule in words, found-by from graph.json, the panel's target. */
import { describe, expect, it } from "vitest"

import type { EffectAnswer, EvGraph, Study, Synthesis } from "@/api/ev"

import { byLane, EFFECT_LANES, effectRows, effectRule, effectRuleShort, extractorFamily, indexGraph, laneCounts } from "./evidence"

const graph: EvGraph = {
  nodes: [
    { id: "S001", type: "document", document: null, fields: null, found_by: [] },
    { id: "c-t", type: "condition", document: "S001", fields: { label: "RAG", role: "rag" }, found_by: ["regex_condition@2#a"] },
    { id: "c-c", type: "condition", document: "S001", fields: { label: "closed-book", role: "baseline" }, found_by: ["llm_condition@1#b"] },
    { id: "k-1", type: "metric", document: "S001", fields: { name: "EM", canonical: "factual_accuracy" }, found_by: ["regex_metric@2#c"] },
    { id: "m-t", type: "measurement", document: "S001", fields: { value: 0.71, dataset: "TriviaQA" }, links: { condition: "c-t", metric: "k-1" }, found_by: ["regex_measurement@2#d"] },
    { id: "m-c", type: "measurement", document: "S001", fields: { value: 0.62, dataset: "TriviaQA" }, links: { condition: "c-c", metric: "k-1" }, found_by: ["gliner_measurement@1#e", "regex_measurement@2#d"] },
    { id: "a-1", type: "author_claim", document: "S001", fields: { direction: "improves" }, found_by: ["regex_author_claim@2#f"] },
  ],
  edges: [],
}

/** A study with the fields answer.json gives every study, `over` on top. */
const study = (over: Partial<Study> & Pick<Study, "document" | "direction">): Study => ({
  delta: null, metric: null, treatment: null, control: null, author_claim: null, reason: null, flags: [], duplicate_of: null, funnel: null, ...over,
})

const synthesis = { min_effect: 0.01, metrics: [{ canonical: "factual_accuracy", higher_is_better: true }] } as unknown as Synthesis

const answer = {
  kind: "effect", system: "evidence-engine", label: "supported", counts: { supporting: 1, contradicting: 0, neutral: 0, undetermined: 1, duplicates: 0 },
  supporting: ["S001"], contradicting: [], neutral: [], undetermined: ["S002"], duplicates: [], flags: {},
  studies: [
    study({ document: "S001", direction: "supports", delta: 0.09, metric: "factual_accuracy",
      treatment: { condition: "c-t", measurement: "m-t", value: 0.71 }, control: { condition: "c-c", measurement: "m-c", value: 0.62 },
      author_claim: { direction: "improves", agrees_with_data: true, item: "a-1" } }),
    study({ document: "S002", direction: "undetermined", reason: { code: "no_pair", text: "no rag and baseline measurement on a question metric" } }),
  ],
} as unknown as EffectAnswer

describe("effect rows", () => {
  const rows = effectRows(answer, ["S001", "S002", "S003"], indexGraph(graph), synthesis)

  it("one row per paper, a paper without a study is not in the answer", () => {
    expect(rows.map((r) => [r.key, r.lane])).toEqual([["S001", "supports"], ["S002", "undetermined"], ["S003", "absent"]])
  })

  it("names the conditions, metric and dataset from the graph and the extractors that found them", () => {
    const d = rows[0].data
    expect(d.treatment).toMatchObject({ label: "RAG", value: 0.71, measurement: "m-t" })
    expect(d.control).toMatchObject({ label: "closed-book", value: 0.62 })
    expect(d.metric).toEqual({ name: "EM", item: "k-1", higherIsBetter: true })
    expect(d.dataset).toBe("TriviaQA")
    expect(d.foundBy).toHaveLength(6)
    expect([...new Set(d.foundBy.map(extractorFamily))].sort()).toEqual(["gliner", "llm", "regex"])
  })

  it("the panel target highlights the study's items and starts at the treatment value", () => {
    expect(rows[0].target).toMatchObject({ document: "S001", focus: "m-t", lane: "supports" })
    expect(rows[0].target!.items).toEqual(["m-t", "c-t", "m-c", "c-c", "k-1", "a-1"])
    expect(rows[0].target!.why.map((w) => w.role)).toEqual(["treatment", "control", "metric", "rule", "author claim"])
    expect(rows[1].target!.items).toEqual([])
  })

  it("lanes keep their order and every lane is counted", () => {
    expect(byLane(rows, EFFECT_LANES).map((g) => g.lane.key)).toEqual(["supports", "undetermined", "absent"])
    expect(laneCounts(rows, EFFECT_LANES).find((c) => c.lane.key === "contradicts")!.count).toBe(0)
  })
})

describe("the rule in words", () => {
  it("says which way is better, the difference and the margin", () => {
    expect(effectRule(answer.studies[0], synthesis, "evidence-engine"))
      .toBe("factual_accuracy: higher is better; Δ = treatment − control = +0.090; |Δ| ≥ margin 0.01 → supports")
    expect(effectRuleShort(answer.studies[0], synthesis, "evidence-engine")).toBe("|Δ| 0.090 ≥ margin 0.01")
  })

  it("a lower-is-better metric flips the difference; below the margin is no effect", () => {
    const lower = { min_effect: 0.05, metrics: [{ canonical: "hallucination_rate", higher_is_better: false }] } as unknown as Synthesis
    expect(effectRule(study({ document: "S", direction: "neutral", delta: 0.02, metric: "hallucination_rate" }), lower, "evidence-engine"))
      .toBe("hallucination_rate: lower is better; Δ = control − treatment = +0.020; |Δ| < margin 0.05 → no effect")
  })

  it("an undetermined study gives its reason; a baseline and a missing study say so", () => {
    expect(effectRule(answer.studies[1], synthesis, "evidence-engine")).toBe("no rag and baseline measurement on a question metric")
    expect(effectRule(study({ document: "S", direction: "supports" }), null, "rag-baseline")).toBe("the baseline's reading of the cited passages")
    expect(effectRule(null, null, "rag-baseline")).toBe("not cited by the baseline")
  })
})
