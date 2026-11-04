import { describe, expect, it } from "vitest"

import type { EvGraph, EvRunDetail, ReportView, RunPaper } from "@/api/ev"
import { evFixture } from "@/mocks/ev"

import {
  evCell,
  extractionByLevel,
  extractionRows,
  funnelStop,
  intervalsOf,
  intervalText,
  itemLabel,
  knobText,
  levelOrder,
  runsByCorpus,
  seriesOf,
  splitExtractor,
  splitRef,
  synthesisByLevel,
  synthesisSummary,
  systemLabel,
  systemOrder,
} from "./ev"
import { toEvFlow } from "./evgraph"

const MIXED = "rag-tpl-w1-mixed"
const EXPLICIT = "rag-tpl-w1-explicit"

describe("names and formats", () => {
  it("splits extractor ids and run ids", () => {
    expect(splitExtractor("regex_condition@2#a0c64d9b6305")).toEqual({ name: "regex_condition", version: "2", hash: "a0c64d9b6305" })
    expect(splitExtractor("agentic")).toEqual({ name: "agentic", version: null, hash: null })
    expect(splitRef(`cascade-gaps~${MIXED}`)).toEqual({ group: "cascade-gaps", name: MIXED })
    expect(splitRef("compare-cascade")).toEqual({ group: "compare-cascade", name: null })
  })

  it("writes intervals as the report does", () => {
    expect(intervalText({ point: 0.8123, low: 0.74, high: 0.88 })).toBe("0.812 [0.74, 0.88]")
    expect(intervalText({ point: 0.5, low: null, high: null })).toBe("0.500 [n/a]")
    expect(intervalText(null)).toBe("—")
  })

  it("formats cells, knobs and series", () => {
    expect([evCell(0.33333), evCell(3), evCell(true), evCell(null), evCell(["a", "b"])]).toEqual(["0.333", "3", "yes", "—", "a, b"])
    expect(knobText({ duplicates: 1, missing: 0, irrelevant: 2 })).toBe("duplicates 1, irrelevant 2")
    expect(knobText(null)).toBe("none")
    expect(seriesOf({ system: "evidence-engine", strategy: "gaps" }, true)).toBe("evidence-engine:gaps")
    expect(seriesOf({ system: "rag-baseline", strategy: null }, true)).toBe("rag-baseline")
    expect(seriesOf({ system: "evidence-engine", strategy: "gaps" }, false)).toBe("evidence-engine")
  })

  it("orders systems engine first and levels by difficulty", () => {
    expect(["agent-baseline", "zeta", "rag-baseline", "evidence-engine"].sort(systemOrder)).toEqual(["evidence-engine", "rag-baseline", "agent-baseline", "zeta"])
    expect(["all", "mixed", "explicit", "complex"].sort(levelOrder)).toEqual(["explicit", "complex", "mixed", "all"])
  })

  it("labels the BM25 answer baseline under its old id (rag-baseline) and its new id", () => {
    expect([systemLabel("rag-baseline"), systemLabel("bm25-answer-baseline")]).toEqual(["RAG baseline", "BM25 answer baseline"])
    expect(["agent-baseline", "bm25-answer-baseline", "evidence-engine"].sort(systemOrder)).toEqual(["evidence-engine", "bm25-answer-baseline", "agent-baseline"])
  })

  it("labels items by their fields", () => {
    expect(itemLabel({ evidence_type: "condition", fields: { label: "closed-book model", role: "baseline" } })).toBe("closed-book model (baseline)")
    expect(itemLabel({ evidence_type: "measurement", fields: { value: 0.62, dataset: "NQ" } })).toBe("0.62 on NQ")
    expect(itemLabel({ evidence_type: "author_claim", fields: { direction: "improves" } })).toBe("claims: improves")
  })
})

describe("the funnel", () => {
  it("says where a document stopped", () => {
    const gaps = evFixture<EvRunDetail>(`/api/ev/runs/cascade-gaps~${MIXED}`)
    const doc = gaps.funnel![gaps.documents[0]]
    expect(funnelStop(doc, "gaps")).toMatch(/^(complete after position \d|exhausted, gap \w+|skipped)/)
    const all = evFixture<EvRunDetail>(`/api/ev/runs/cascade~${EXPLICIT}`)
    const first = all.funnel![all.documents[0]]
    expect(funnelStop(first, "all")).toBe("every extractor ran (all)")
    expect(funnelStop({ skipped: true, steps: [], decisions: [], screen: null, stopped_after: null }, "gaps")).toBe("skipped (screened out)")
    expect(funnelStop(undefined)).toBe("—")
  })
})

describe("scores from a real report", () => {
  const view = evFixture<ReportView>(`/api/ev/scores/reports/cascade-gaps~${MIXED}`)

  it("arranges C per level with every system as a column", () => {
    const rows = synthesisByLevel(view.report.synthesis, "direction_accuracy")
    expect(rows.map((r) => r.level)).toEqual([...rows.map((r) => String(r.level))].sort(levelOrder))
    expect(rows.at(-1)!.level).toBe("all")
    for (const s of view.report.synthesis) expect(rows.at(-1)).toHaveProperty(s.system)
    const summary = synthesisSummary(view.report)
    expect(summary[0].system).toBe("evidence-engine")
    expect(summary[0]).toHaveProperty("direction_accuracy")
  })

  it("arranges A per level and type, the overall row last", () => {
    const all = extractionRows(view.report)
    expect(all.at(-1)!.evidence_type).toBe("all")
    const byLevel = extractionByLevel(view.report)
    expect(byLevel.some((r) => "condition" in r)).toBe(true)
  })

  it("reads the intervals by system and type", () => {
    const synthesis = intervalsOf(view.report, "synthesis")
    expect(synthesis.map((r) => r.key)).toContain("evidence-engine")
    expect(intervalsOf(view.report, "paired").every((r) => r.key !== "evidence-engine")).toBe(true)
    expect(intervalsOf(view.report, "extraction").map((r) => r.key)).toContain("condition")
  })

  it("groups runs by corpus", () => {
    const runs = evFixture<EvRunDetail[]>("/api/ev/runs")
    const groups = runsByCorpus(runs)
    expect(groups.get(MIXED)!.map((r) => r.system)).toEqual(expect.arrayContaining(["evidence-engine", "rag-baseline"]))
  })
})

describe("the evidence graph", () => {
  const graph = evFixture<EvGraph>(`/api/ev/runs/cascade~${EXPLICIT}/graph`)

  it("keeps one paper's nodes and counts the edges it hides", () => {
    const one = toEvFlow(graph, { document: "S001" })
    expect(one.nodes.every((n) => n.id === "S001" || n.data.document === "S001")).toBe(true)
    expect(one.nodes.some((n) => n.data.type === "document")).toBe(true)
    expect(one.edges.some((e) => e.data?.rel === "in_document")).toBe(false)
    const withDocs = toEvFlow(graph, { document: "S001", withDocumentEdges: true })
    expect(withDocs.edges.filter((e) => e.data?.rel === "in_document")).toHaveLength(one.nodes.length - 1)
    const all = toEvFlow(graph, { withDocumentEdges: true })
    expect(all.nodes).toHaveLength(graph.nodes.length)
    expect(all.edges).toHaveLength(graph.edges.length)
    expect(all.hidden).toBe(0)
  })

  it("lays papers out before their items", () => {
    const one = toEvFlow(graph, { document: "S001" })
    const paper = one.nodes.find((n) => n.id === "S001")!
    expect(one.nodes.filter((n) => n.id !== "S001").every((n) => n.position.x > paper.position.x)).toBe(true)
  })
})

describe("a run paper's segments", () => {
  it("cover the text exactly once, in order", () => {
    const paper = evFixture<RunPaper>(`/api/ev/runs/cascade~${EXPLICIT}/papers/S001`)
    expect(paper.segments.map((s) => s.text).join("")).toBe(paper.text)
    expect(paper.segments.every((s, i) => i === 0 || s.start === paper.segments[i - 1].end)).toBe(true)
    const ids = new Set(paper.items.map((i) => i.item_id))
    expect(paper.segments.flatMap((s) => s.marks).every((m) => ids.has(m))).toBe(true)
  })
})
