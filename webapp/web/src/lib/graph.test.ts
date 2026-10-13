import { describe, expect, it } from "vitest"

import type { GraphEdge, KnowledgeGraph } from "@/api/types"
import { GRAPHS } from "@/mocks/fixtures"

import { graphElements, NODE_HEIGHT, nodeWidth, toFlow } from "./graph"

describe("graph.json to React Flow", () => {
  const graph = GRAPHS["q01-on-s1"]

  it("keeps paper and entity nodes apart and gives literals their own node", () => {
    const { nodes } = graphElements(graph)
    const kinds = Object.fromEntries(nodes.map((n) => [n.id, n.type]))
    expect(kinds["paper:p1"]).toBe("paper")
    expect(kinds["entity:spider"]).toBe("entity")
    const literal = nodes.find((n) => n.type === "literal")
    expect(literal?.id).toBe("literal:edge-000007")
    expect(literal?.data.label).toBe("“MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval”")
    expect(nodes).toHaveLength(graph.nodes.length + 1)
  })

  it("makes one edge per claim, labelled by the predicate, with the claim kept", () => {
    const { edges } = graphElements(graph)
    expect(edges).toHaveLength(7)
    const spider = edges.find((e) => e.target === "entity:spider")!
    expect(spider).toMatchObject({ source: "paper:p1", label: "evaluatesOn" })
    expect(spider.data).toMatchObject({ claims: ["claim-000001"], origins: ["research"], curie: "ours:evaluatesOn" })
    expect(spider.data?.evidence[0]).toEqual({ file: "p1.md", paper: "p1", start: 3190, end: 3251 })
  })

  it("merges parallel edges of one triple and keeps every claim", () => {
    const twin: GraphEdge = { ...graph.edges[0], id: "edge-000099", claim: "claim-000099", origin: "attach" }
    const { edges } = graphElements({ ...graph, edges: [...graph.edges, twin] })
    const merged = edges.find((e) => e.target === "entity:spider")!
    expect(merged.data?.claims).toEqual(["claim-000001", "claim-000099"])
    expect(merged.data?.origins).toEqual(["research", "attach"])
    expect(merged.label).toBe("evaluatesOn ×2")
    expect(edges).toHaveLength(7)
  })

  it("counts the degree of each node", () => {
    const { nodes } = graphElements(graph)
    const degree = Object.fromEntries(nodes.map((n) => [n.id, n.data.degree]))
    expect(degree["paper:p1"]).toBe(3) // Spider, BIRD, Hanbing Liu
    expect(degree["paper:p4"]).toBe(2) // MegaPairs, title literal
    expect(degree["entity:gsm8k"]).toBe(1)
  })

  it("skips edges whose nodes are missing instead of crashing", () => {
    const broken: KnowledgeGraph = { ...graph, edges: [{ ...graph.edges[0], source: "paper:p404" }] }
    expect(graphElements(broken).edges).toEqual([])
  })

  it("lays the graph out left to right with dagre, papers before their objects", () => {
    const { nodes } = toFlow(graph)
    const at = (id: string) => nodes.find((n) => n.id === id)!
    for (const n of nodes) {
      expect(Number.isFinite(n.position.x) && Number.isFinite(n.position.y)).toBe(true)
      expect(n.width).toBe(nodeWidth(n.data.kind, n.data.label))
      expect(n.height).toBe(NODE_HEIGHT[n.data.kind])
    }
    expect(at("paper:p1").position.x).toBeLessThan(at("entity:spider").position.x)
    // no two nodes on the same spot
    const spots = new Set(nodes.map((n) => `${Math.round(n.position.x)},${Math.round(n.position.y)}`))
    expect(spots.size).toBe(nodes.length)
  })

  it("handles an empty graph", () => {
    expect(toFlow({ schema_version: 1, run_id: "x", nodes: [], edges: [] })).toEqual({ nodes: [], edges: [] })
  })

  it("sizes nodes by their label within limits", () => {
    expect(nodeWidth("entity", "A")).toBe(88)
    expect(nodeWidth("paper", "p1")).toBe(120)
    expect(nodeWidth("entity", "x".repeat(200))).toBe(260)
  })
})
