/**
 * The engine's evidence graph (graph.json, evidence/graph.py) -> React Flow nodes and edges, laid out by dagre.
 *
 * Nodes are the documents and the merged evidence items; edges `in_document` (item -> its paper),
 * `condition` and `metric` (a measurement -> the items it links), `supports` / `contradicts` (the treatment
 * measurement a study's effect rests on -> the control measurement, as synthesis decided) and
 * `duplicate_of` (paper -> the earlier paper it repeats). `in_document` edges are many and say little once
 * the nodes sit in their paper's column, so they are optional (`withDocumentEdges`). A document filter keeps
 * one paper's items (and the duplicate edges that touch it), since a whole corpus is hundreds of nodes.
 */
import dagre from "@dagrejs/dagre"
import type { Edge, Node } from "@xyflow/react"

import type { EvGraph, EvGraphNode } from "@/api/ev"

import { itemLabel } from "./ev"

export type EvNodeData = { label: string; type: string; document: string | null; foundBy: string[] }
export type EvEdgeData = { rel: string }
export type EvFlowNode = Node<EvNodeData, "evidence">
export type EvFlowEdge = Edge<EvEdgeData>

export const EV_NODE_HEIGHT = 40
const REVERSED = new Set(["in_document", "condition", "metric"])
export const evNodeWidth = (label: string) => Math.min(280, Math.max(96, Math.round(label.length * 7 + 40)))

export function nodeLabel(node: EvGraphNode): string {
  if (node.type === "document") return node.id
  return itemLabel({ evidence_type: node.type as never, fields: (node.fields ?? {}) as Record<string, unknown> })
}

export interface EvGraphOptions {
  /** keep only this document's nodes */
  document?: string | null
  /** draw item -> paper edges too */
  withDocumentEdges?: boolean
}

/** Nodes and edges of the graph, positioned; edges whose ends are not shown are left out and counted. */
export function toEvFlow(graph: EvGraph, { document = null, withDocumentEdges = false }: EvGraphOptions = {}) {
  const kept = graph.nodes.filter((n) => !document || n.id === document || n.document === document)
  const ids = new Set(kept.map((n) => n.id))
  let hidden = 0
  const edges: EvFlowEdge[] = []
  for (const e of graph.edges) {
    if (e.rel === "in_document" && !withDocumentEdges) continue
    if (!ids.has(e.src) || !ids.has(e.dst)) {
      hidden += 1
      continue
    }
    edges.push({ id: `${e.src}|${e.rel}|${e.dst}`, source: e.src, target: e.dst, data: { rel: e.rel }, label: e.rel === "in_document" ? undefined : e.rel })
  }
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: "LR", nodesep: 14, ranksep: 56, marginx: 8, marginy: 8 })
  g.setDefaultEdgeLabel(() => ({}))
  const nodes: EvFlowNode[] = kept.map((n) => {
    const label = nodeLabel(n)
    g.setNode(n.id, { width: evNodeWidth(label), height: EV_NODE_HEIGHT })
    return {
      id: n.id,
      type: "evidence",
      position: { x: 0, y: 0 },
      data: { label, type: n.type, document: n.document ?? (n.type === "document" ? n.id : null), foundBy: n.found_by ?? [] },
    }
  })
  // Layout from every edge between shown nodes, drawn or not, so items sit beside their paper. The paper,
  // then conditions and metrics, then the measurements that link them: links are laid out target first.
  for (const e of graph.edges) {
    if (!ids.has(e.src) || !ids.has(e.dst)) continue
    if (REVERSED.has(e.rel)) g.setEdge(e.dst, e.src)
    else g.setEdge(e.src, e.dst)
  }
  dagre.layout(g)
  for (const node of nodes) {
    const at = g.node(node.id)
    node.position = { x: at.x - at.width / 2, y: at.y - at.height / 2 }
  }
  return { nodes, edges, hidden }
}
