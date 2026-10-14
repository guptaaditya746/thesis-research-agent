/**
 * graph.json (agent/kg.py, row 2.6) -> React Flow nodes and edges, laid out with dagre.
 *
 * - Nodes keep their kg.py kind: `paper` (a corpus paper) and `entity` (anything else). An edge
 *   whose object is a literal (title, year, number) gets its own `literal` node, one per edge,
 *   because kg.py keeps literals per claim rather than as shared nodes.
 * - kg.py writes one edge per accepted claim, so the same triple claimed twice gives parallel
 *   edges that would be drawn on top of each other. Edges with the same source, predicate
 *   and target merge into one flow edge that keeps every claim id (`data.claims`); clicking it
 *   opens the claim walk of all of them.
 * - Layout: dagre, left to right; node widths are estimated from the label length so long
 *   entity names do not overlap.
 */
import dagre, { type GraphLabel, type NodeLabel } from "@dagrejs/dagre"
import type { Edge, Node } from "@xyflow/react"

import type { GraphEdge, KnowledgeGraph } from "@/api/types"

export type FlowNodeKind = "paper" | "entity" | "literal"

export type FlowNodeData = {
  label: string
  kind: FlowNodeKind
  paper?: string | null
  /** number of edges touching the node (shown on papers) */
  degree: number
}

export type FlowEdgeData = {
  predicate: string
  curie: string
  claims: string[]
  origins: string[]
  evidence: GraphEdge["evidence"][]
}

export type FlowNode = Node<FlowNodeData, FlowNodeKind>
export type FlowEdge = Edge<FlowEdgeData>

export const NODE_HEIGHT: Record<FlowNodeKind, number> = { paper: 48, entity: 36, literal: 32 }

/** Width from the label: about 7 px per character plus padding and the icon, within limits. */
export function nodeWidth(kind: FlowNodeKind, label: string): number {
  const min = kind === "paper" ? 120 : 88
  return Math.min(260, Math.max(min, Math.round(label.length * 7 + (kind === "paper" ? 56 : 40))))
}

function literalLabel(value: unknown): string {
  return typeof value === "string" ? `“${value}”` : String(value)
}

/** Nodes and merged edges, without positions; `skipped`: claims whose edge has an end that is no node. */
export function graphElements(graph: KnowledgeGraph): { nodes: FlowNode[]; edges: FlowEdge[]; skipped: number } {
  let skipped = 0
  const degree = new Map<string, number>()
  const bump = (id: string) => degree.set(id, (degree.get(id) ?? 0) + 1)
  const nodes: FlowNode[] = graph.nodes.map((n) => ({
    id: n.id,
    type: n.kind,
    position: { x: 0, y: 0 },
    data: { label: n.label, kind: n.kind, paper: n.paper, degree: 0 },
  }))
  const known = new Set(nodes.map((n) => n.id))
  const merged = new Map<string, FlowEdge>()
  for (const e of graph.edges) {
    let target = e.target
    if (target === null) {
      target = `literal:${e.id}`
      nodes.push({
        id: target, type: "literal", position: { x: 0, y: 0 },
        data: { label: literalLabel(e.literal), kind: "literal", degree: 0 },
      })
      known.add(target)
    }
    if (!known.has(e.source) || !known.has(target)) {
      skipped += 1 // dangling edge: skip rather than crash, and count it
      continue
    }
    bump(e.source)
    bump(target)
    const key = `${e.source}|${e.predicate.curie}|${target}`
    const existing = merged.get(key)
    if (existing?.data) {
      existing.data.claims.push(e.claim)
      if (!existing.data.origins.includes(e.origin)) existing.data.origins.push(e.origin)
      existing.data.evidence.push(e.evidence)
      existing.label = `${e.predicate.text} ×${existing.data.claims.length}`
      continue
    }
    merged.set(key, {
      id: e.id,
      source: e.source,
      target,
      label: e.predicate.text,
      data: { predicate: e.predicate.text, curie: e.predicate.curie, claims: [e.claim], origins: [e.origin], evidence: [e.evidence] },
    })
  }
  for (const n of nodes) n.data.degree = degree.get(n.id) ?? 0
  return { nodes, edges: [...merged.values()], skipped }
}

/** dagre layout: positions are top-left corners, as React Flow expects. */
export function layout(nodes: FlowNode[], edges: FlowEdge[], direction: "LR" | "TB" = "LR"): FlowNode[] {
  const g = new dagre.graphlib.Graph<GraphLabel, NodeLabel, object>()
  g.setGraph({ rankdir: direction, nodesep: 28, ranksep: 120, marginx: 16, marginy: 16 })
  g.setDefaultEdgeLabel(() => ({}))
  for (const n of nodes) {
    g.setNode(n.id, { width: nodeWidth(n.data.kind, n.data.label), height: NODE_HEIGHT[n.data.kind] })
  }
  for (const e of edges) g.setEdge(e.source, e.target)
  dagre.layout(g)
  return nodes.map((n) => {
    const p = g.node(n.id)
    const width = nodeWidth(n.data.kind, n.data.label)
    const height = NODE_HEIGHT[n.data.kind]
    return { ...n, width, height, position: { x: (p.x ?? 0) - width / 2, y: (p.y ?? 0) - height / 2 } }
  })
}

/** The knowledge graph as laid-out React Flow elements. */
export function toFlow(graph: KnowledgeGraph, direction: "LR" | "TB" = "LR"): { nodes: FlowNode[]; edges: FlowEdge[]; skipped: number } {
  const { nodes, edges, skipped } = graphElements(graph)
  return { nodes: layout(nodes, edges, direction), edges, skipped }
}
