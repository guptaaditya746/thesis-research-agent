/**
 * The run's evidence graph (graph.json) in React Flow, laid out by dagre (src/lib/evgraph.ts): papers and
 * the merged items, coloured by evidence type, with the links between them and the supports / contradicts
 * edge of every determined study. One paper at a time by default (a whole corpus is hundreds of nodes);
 * clicking an item's paper opens it. Below the canvas the same edges as a list, for keyboard use and screen
 * readers.
 */
import "@xyflow/react/dist/style.css"

import { Background, Controls, Handle, MarkerType, Position, ReactFlow, type NodeProps } from "@xyflow/react"
import { FileTextIcon } from "lucide-react"
import { useTheme } from "next-themes"
import { useMemo, useState } from "react"

import type { EvGraph } from "@/api/ev"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { TYPE_COLOR, typeLabel } from "@/lib/ev"
import { EV_NODE_HEIGHT, evNodeWidth, toEvFlow, type EvFlowNode } from "@/lib/evgraph"

import { MarkLegend } from "./PaperText"

function EvidenceNode({ data }: NodeProps<EvFlowNode>) {
  const paper = data.type === "document"
  return (
    <div
      className="flex items-center gap-1.5 rounded-md border-2 bg-card px-2 text-xs shadow-sm"
      style={{ width: evNodeWidth(data.label), height: EV_NODE_HEIGHT, borderColor: paper ? "var(--foreground)" : TYPE_COLOR[data.type] }}
      title={`${typeLabel(data.type)}: ${data.label}${data.foundBy.length ? `\nfound by ${data.foundBy.join(", ")}` : ""}`}
    >
      {paper && <FileTextIcon className="size-3.5 shrink-0" aria-hidden="true" />}
      <span className="truncate">{data.label}</span>
      <Handle type="target" position={Position.Left} className="!size-1.5 !border-0 !bg-muted-foreground" />
      <Handle type="source" position={Position.Right} className="!size-1.5 !border-0 !bg-muted-foreground" />
    </div>
  )
}

const NODE_TYPES = { evidence: EvidenceNode }
const EDGE_COLOR: Record<string, string> = { supports: "var(--status-good)", contradicts: "var(--status-critical)", duplicate_of: "var(--status-warning)" }

export function EvidenceGraph({ graph, documents }: { graph: EvGraph; documents: string[] }) {
  const { resolvedTheme } = useTheme()
  const [document, setDocument] = useState<string>(documents[0] ?? "__all")
  const [withDocs, setWithDocs] = useState(false)
  const flow = useMemo(() => toEvFlow(graph, { document: document === "__all" ? null : document, withDocumentEdges: withDocs }),
    [graph, document, withDocs])
  const labels = useMemo(() => new Map(flow.nodes.map((n) => [n.id, n.data.label])), [flow])
  const edges = flow.edges.map((e) => ({
    ...e,
    markerEnd: { type: MarkerType.ArrowClosed },
    style: { stroke: EDGE_COLOR[e.data?.rel ?? ""] ?? "var(--muted-foreground)", strokeWidth: EDGE_COLOR[e.data?.rel ?? ""] ? 2 : 1 },
    labelStyle: { fontSize: 10 },
  }))
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <Label htmlFor="graph-doc" className="text-sm">Paper</Label>
          <Select value={document} onValueChange={setDocument}>
            <SelectTrigger id="graph-doc" className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">all papers</SelectItem>
              {documents.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <Switch id="graph-docs" checked={withDocs} onCheckedChange={setWithDocs} />
          <Label htmlFor="graph-docs" className="text-sm">item → paper edges</Label>
        </div>
        <span className="text-xs text-muted-foreground">{flow.nodes.length} nodes, {flow.edges.length} edges{flow.hidden ? `, ${flow.hidden} to other papers not shown` : ""}</span>
      </div>
      <MarkLegend entries={["condition", "metric", "measurement", "author_claim"].map((t) => ({ label: typeLabel(t), color: TYPE_COLOR[t] }))} />
      <div className="h-[60vh] rounded-md border" role="img" aria-label={`Evidence graph${document !== "__all" ? ` of ${document}` : ""}`}>
        <ReactFlow nodes={flow.nodes} edges={edges} nodeTypes={NODE_TYPES} fitView minZoom={0.1} nodesDraggable={false}
          colorMode={resolvedTheme === "dark" ? "dark" : "light"} proOptions={{ hideAttribution: true }}>
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <details>
        <summary className="cursor-pointer text-sm">Edges as a list</summary>
        <ul className="mt-2 space-y-0.5 text-xs" aria-label="Edges">
          {flow.edges.map((e) => (
            <li key={e.id}>{labels.get(e.source) ?? e.source} —{e.data?.rel}→ {labels.get(e.target) ?? e.target}</li>
          ))}
        </ul>
      </details>
    </div>
  )
}
