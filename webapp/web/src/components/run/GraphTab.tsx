/**
 * Graph tab: the run's knowledge graph (graph.json, row 2.6) in React Flow, laid out by dagre
 * (src/lib/graph.ts). Papers are blue rectangles with a document icon, entities rounded pills,
 * literal values dashed; an edge drawn dashed came from the attach step. Clicking an edge opens
 * the claim walk (of the answer fact that cites its claim, else of the claim itself). Below the
 * canvas the same edges as a list, for keyboard use and screen readers.
 */
import "@xyflow/react/dist/style.css"

import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type EdgeMouseHandler,
  type NodeProps,
} from "@xyflow/react"
import { FileTextIcon, NetworkIcon, TagIcon } from "lucide-react"
import { useTheme } from "next-themes"
import { useMemo } from "react"

import { isNotFound } from "@/api/client"
import { useGraph } from "@/api/hooks"
import type { Answer } from "@/api/types"
import { EmptyState, ErrorState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { factsByClaim } from "@/lib/facts"
import { toFlow, type FlowEdge, type FlowNode } from "@/lib/graph"

import { useWalk, type WalkTarget } from "./walk-context"

function PaperNode({ data }: NodeProps<FlowNode>) {
  return (
    <div className="flex h-full items-center gap-2 rounded-md border-2 border-chart-1 bg-card px-3 text-sm font-medium shadow-sm" title={`paper ${data.label}`}>
      <FileTextIcon className="size-4 shrink-0 text-chart-1" aria-hidden="true" />
      <span className="truncate font-mono">{data.label}</span>
      <span className="ml-auto text-xs text-muted-foreground tabular-nums" aria-label={`${data.degree} edges`}>{data.degree}</span>
      <Handle type="target" position={Position.Left} className="!size-1.5 !border-0 !bg-muted-foreground" />
      <Handle type="source" position={Position.Right} className="!size-1.5 !border-0 !bg-muted-foreground" />
    </div>
  )
}

function EntityNode({ data }: NodeProps<FlowNode>) {
  return (
    <div className="flex h-full items-center gap-1.5 rounded-full border bg-background px-3 text-sm" title={data.label}>
      <TagIcon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      <span className="truncate">{data.label}</span>
      <Handle type="target" position={Position.Left} className="!size-1.5 !border-0 !bg-muted-foreground" />
      <Handle type="source" position={Position.Right} className="!size-1.5 !border-0 !bg-muted-foreground" />
    </div>
  )
}

function LiteralNode({ data }: NodeProps<FlowNode>) {
  return (
    <div className="flex h-full items-center rounded-sm border border-dashed bg-muted/40 px-2 text-xs text-muted-foreground italic" title={data.label}>
      <span className="truncate">{data.label}</span>
      <Handle type="target" position={Position.Left} className="!size-1.5 !border-0 !bg-muted-foreground" />
    </div>
  )
}

const NODE_TYPES = { paper: PaperNode, entity: EntityNode, literal: LiteralNode }

/** Open the walk of the fact citing the edge's first claim, or of the bare claims. */
function walkTargetOf(edge: FlowEdge, answer: Answer | null): WalkTarget {
  const claims = edge.data?.claims ?? []
  const facts = factsByClaim(answer)
  const fact = claims.map((c) => facts.get(c)?.[0]).find(Boolean)
  return fact ? { kind: "fact", factId: fact.fact.id } : { kind: "claims", claimIds: claims, label: edge.data?.predicate }
}

export function GraphTab({ runId, answer }: { runId: string; answer: Answer | null }) {
  const graph = useGraph(runId)
  const { open } = useWalk()
  const { resolvedTheme } = useTheme()
  const flow = useMemo(() => (graph.data ? toFlow(graph.data) : null), [graph.data])
  const labels = useMemo(() => new Map(flow?.nodes.map((n) => [n.id, n.data.label])), [flow])
  const describe = (e: FlowEdge) => `${labels.get(e.source) ?? e.source} —${e.data?.predicate ?? ""}→ ${labels.get(e.target) ?? e.target}`

  const edges = useMemo(
    () =>
      flow?.edges.map((e) => ({
        ...e,
        style: e.data?.origins.includes("attach") && e.data.origins.length === 1 ? { strokeDasharray: "6 4" } : undefined,
        labelStyle: { fontSize: 11 },
        labelBgPadding: [4, 2] as [number, number],
        labelBgBorderRadius: 4,
        interactionWidth: 24,
        ariaLabel: `${labels.get(e.source) ?? e.source} ${e.data?.predicate} ${labels.get(e.target) ?? e.target}`,
      })) ?? [],
    [flow, labels],
  )

  if (graph.isPending) return <Skeleton className="h-[60vh] w-full" />
  if (isNotFound(graph.error)) {
    return (
      <EmptyState
        icon={<NetworkIcon />}
        title="No graph yet"
        description="graph.json is built by `agent graph` once the run (and, for claim off, the attach step) has finished."
      />
    )
  }
  if (graph.isError) return <ErrorState error={graph.error} title="Could not load graph.json" onRetry={() => void graph.refetch()} />
  if (!flow || flow.nodes.length === 0) {
    return (
      <EmptyState
        icon={<NetworkIcon />}
        title="The graph is empty"
        description="graph.json has one edge per accepted claim; this run has none yet (or `agent graph` has not run)."
      />
    )
  }

  const onEdgeClick: EdgeMouseHandler<FlowEdge> = (_, edge) => open(walkTargetOf(edge, answer))

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-label="Legend">
        <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-5 rounded-sm border-2 border-chart-1" aria-hidden="true" /> paper</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-5 rounded-full border" aria-hidden="true" /> entity</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-5 rounded-sm border border-dashed" aria-hidden="true" /> literal value</span>
        <span className="flex items-center gap-1.5"><svg width="24" height="6" aria-hidden="true"><line x1="0" y1="3" x2="24" y2="3" stroke="currentColor" strokeWidth="1.5" strokeDasharray="6 4" /></svg> from the attach step</span>
        <span>{flow.nodes.length} nodes · {graph.data.edges.length} claims as {edges.length} edges · click an edge for its claim walk</span>
      </div>
      <div className="h-[60vh] min-h-96 overflow-hidden rounded-md border" role="region" aria-label="Knowledge graph">
        <ReactFlow<FlowNode, FlowEdge>
          nodes={flow.nodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          onEdgeClick={onEdgeClick}
          colorMode={resolvedTheme === "dark" ? "dark" : "light"}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          minZoom={0.2}
          nodesConnectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={20} size={1} />
          <Controls showInteractive={false} />
          <MiniMap pannable zoomable nodeColor={(n) => (n.type === "paper" ? "var(--chart-1)" : "var(--muted-foreground)")} />
        </ReactFlow>
      </div>
      <details className="rounded-md border p-3 text-sm">
        <summary className="cursor-pointer font-medium">Edges as a list ({edges.length})</summary>
        <ul className="mt-2 space-y-1">
          {flow.edges.map((e) => (
            <li key={e.id}>
              <Button variant="link" size="sm" className="h-auto p-0 font-mono text-xs" onClick={() => open(walkTargetOf(e, answer))}>
                {describe(e)}
              </Button>
              <span className="ml-2 text-xs text-muted-foreground">{e.data?.claims.join(", ")}</span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  )
}
