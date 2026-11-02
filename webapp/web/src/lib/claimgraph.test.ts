import { describe, expect, it } from "vitest"

import type { EvGraph, RunAnswer } from "@/api/ev"

import { claimItems, claimsOf, toClaimFlow, verdictOf } from "./claimgraph"

/** Neutral names on purpose: the web code and its tests carry no topic words. */
const DISPLAY = { treatment: "Arm T", control: "Arm C" }

const node = (id: string, type: string, document: string | null, fields: Record<string, unknown> | null = null, links: Record<string, string> = {}) =>
  ({ id, type, document, fields, found_by: ["regex_x"], links })
const GRAPH = {
  nodes: [
    node("P1", "document", null), node("P2", "document", null), node("P3", "document", null),
    node("c-t1", "condition", "P1", { label: "with it", role: "treatment" }),
    node("c-c1", "condition", "P1", { label: "without it", role: "control" }),
    node("k-1", "metric", "P1", { name: "score", canonical: "score" }),
    node("m-t1", "measurement", "P1", { value: 0.8 }, { condition: "c-t1", metric: "k-1" }),
    node("m-c1", "measurement", "P1", { value: 0.6 }, { condition: "c-c1", metric: "k-1" }),
    node("m-t2", "measurement", "P2", { value: 0.5 }),
    node("m-c2", "measurement", "P2", { value: 0.7 }),
  ],
  edges: [
    { src: "m-t1", dst: "P1", rel: "in_document" }, { src: "m-t1", dst: "c-t1", rel: "condition" },
    { src: "m-t1", dst: "k-1", rel: "metric" }, { src: "m-t1", dst: "m-c1", rel: "supports" },
    { src: "m-t2", dst: "m-c2", rel: "contradicts" },
  ],
} as unknown as EvGraph

const study = (document: string, direction: string, t: [string, number] | null, c: [string, number] | null) => ({
  document, direction, delta: null, metric: "score",
  treatment: t && { condition: null, measurement: t[0], value: t[1] },
  control: c && { condition: null, measurement: c[0], value: c[1] },
  author_claim: null, reason: null, flags: [], duplicate_of: null, funnel: null,
})
const EFFECT_ANSWER = {
  kind: "effect", system: "engine", label: "mixed",
  studies: [study("P1", "supports", ["m-t1", 0.8], ["m-c1", 0.6]), study("P2", "contradicts", ["m-t2", 0.5], ["m-c2", 0.7]),
    study("P3", "undetermined", null, null)],
} as unknown as RunAnswer

const step = (comparison: string, document: string, from: string, to: string) =>
  ({ comparison, document, from, to, metric: "score", direction: "better", context: null })
const CHAIN_ANSWER = {
  kind: "chaining", system: "engine", source: "A", target: "C", metric: "score", verdict: "better", inferred: true,
  via: ["B"], studies: ["P1", "P2"], reason: null, note: "inferred through B, not tested directly",
  paths: [{ via: ["B"], verdict: "better", reason: null, steps: [step("cmp-1", "P1", "A", "B"), step("cmp-2", "P2", "B", "C")] }],
} as unknown as RunAnswer
const LIMITATIONS_ANSWER = {
  kind: "limitations", system: "engine", thing: null, counts: {}, unlinked: {},
  entries: [{ thing: "A", category: "small_sample", papers: ["P1", "P2"], items: ["l-1", "l-2"] }],
} as unknown as RunAnswer
const BUILDS_ON_ANSWER = {
  kind: "builds_on", system: "engine", thing: null, origins: { A: "P1" }, followers: { A: ["P2"] }, influence: { A: 1 },
  ranking: ["A"], unresolved: [], links: [{ from: "P2", to: "P1", reuses: "method", items: ["d-1"] }],
} as unknown as RunAnswer

describe("claim graph", () => {
  it("places papers, claims and the verdict in three columns", () => {
    const { nodes } = toClaimFlow(GRAPH, EFFECT_ANSWER, "effect", DISPLAY)
    const x = (k: string) => Math.max(...nodes.filter((n) => n.data.column === k).map((n) => n.position.x))
    expect(x("paper")).toBeLessThan(Math.min(...nodes.filter((n) => n.data.column === "claim").map((n) => n.position.x)))
    expect(x("claim")).toBeLessThan(nodes.find((n) => n.data.column === "verdict")!.position.x)
  })

  it("hides internal items until a claim is clicked", () => {
    expect(toClaimFlow(GRAPH, EFFECT_ANSWER, "effect", DISPLAY).nodes.some((n) => ["condition", "metric", "measurement"].includes(n.data.type))).toBe(false)
  })

  it("draws chains and dependencies dashed and labelled", () => {
    const { edges } = toClaimFlow(GRAPH, CHAIN_ANSWER, "chaining", DISPLAY)
    const chain = edges.filter((e) => e.data?.rel === "chain")
    expect(chain).toHaveLength(2)
    expect(chain.every((e) => e.style?.strokeDasharray === "6 4" && String(e.label).startsWith("inferred through"))).toBe(true)
    const deps = toClaimFlow(GRAPH, BUILDS_ON_ANSWER, "builds_on", DISPLAY).edges.filter((e) => e.data?.rel === "builds_on")
    expect(deps).toHaveLength(1)
    expect(deps[0].style?.strokeDasharray).toBe("6 4")
    expect(deps[0].label).toBe("builds on")
  })

  it("uses the topic's names for the two sides", () => {
    expect(claimsOf(EFFECT_ANSWER, "effect", DISPLAY)[0].label).toContain(DISPLAY.treatment)
    expect(claimsOf(EFFECT_ANSWER, "effect", DISPLAY)[0].label).toBe("Arm T 0.8 vs Arm C 0.6 on score")
    expect(claimsOf(EFFECT_ANSWER, "effect")[0].label).toBe("treatment 0.8 vs control 0.6 on score")
  })

  it("makes one claim per determined study, limitation entry, dependency link and chain step", () => {
    expect(claimsOf(EFFECT_ANSWER, "effect", DISPLAY).map((c) => c.rel)).toEqual(["supports", "contradicts"])
    expect(claimsOf(LIMITATIONS_ANSWER, "limitations")).toHaveLength(1)
    expect(claimsOf(LIMITATIONS_ANSWER, "limitations")[0].sources.map((s) => s.document)).toEqual(["P1", "P2"])
    expect(claimsOf(BUILDS_ON_ANSWER, "builds_on")[0].label).toBe("P2 builds on P1 (method)")
    expect(claimsOf(CHAIN_ANSWER, "chaining").map((c) => c.label)).toEqual(["A better than B on score", "B better than C on score"])
  })

  it("colours supports and contradicts, and every edge carries a label", () => {
    const { edges } = toClaimFlow(GRAPH, EFFECT_ANSWER, "effect", DISPLAY)
    expect(edges.find((e) => e.data?.rel === "supports")?.style?.stroke).toBe("var(--status-good)")
    expect(edges.find((e) => e.data?.rel === "contradicts")?.style?.stroke).toBe("var(--status-critical)")
    expect(edges.every((e) => typeof e.label === "string" && e.label.length > 0)).toBe(true)
  })

  it("the verdict is the answer's text and the rule that decided it", () => {
    expect(verdictOf(EFFECT_ANSWER, "effect").text).toBe("mixed")
    expect(verdictOf(CHAIN_ANSWER, "chaining")).toEqual({ text: "A better than C", rule: "inferred through B, not tested directly" })
    const verdict = toClaimFlow(GRAPH, EFFECT_ANSWER, "effect", DISPLAY).nodes.filter((n) => n.data.column === "verdict")
    expect(verdict).toHaveLength(1)
    expect(verdict[0].data.label).toBe("mixed")
  })

  it("a claim's items are its own and the ones they link", () => {
    const claim = claimsOf(EFFECT_ANSWER, "effect", DISPLAY)[0]
    expect(claimItems(GRAPH, claim).map((n) => n.id)).toEqual(["m-t1", "c-t1", "k-1", "m-c1", "c-c1"])
  })
})
