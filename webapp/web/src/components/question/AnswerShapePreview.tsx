/**
 * A concept's answer shape as a template of the answer it asks for: a table header with the
 * column types, or the graph's edge types as node -predicate-> node with their attributes.
 */
import { ArrowRightIcon } from "lucide-react"

import type { AnswerShape } from "@/api/types"

export function AnswerShapePreview({ shape }: { shape: AnswerShape }) {
  if (shape.kind === "table") {
    const columns = shape.columns ?? []
    return (
      <div className="overflow-x-auto rounded-md border" role="figure" aria-label="Answer shape: table">
        <table className="w-full text-xs">
          <thead className="bg-muted/50">
            <tr>
              {columns.map((c) => (
                <th key={c.name} scope="col" className="px-2 py-1 text-left font-mono font-medium">{c.name}</th>
              ))}
            </tr>
          </thead>
          <tbody className="text-muted-foreground">
            <tr className="border-t">
              {columns.map((c) => (
                <td key={c.name} className="px-2 py-1 italic">{c.type}</td>
              ))}
            </tr>
            <tr className="border-t">
              {columns.map((c) => (
                <td key={c.name} className="px-2 py-1" aria-hidden="true">…</td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    )
  }
  return (
    <div className="space-y-2 rounded-md border p-2" role="figure" aria-label="Answer shape: graph">
      {(shape.edges ?? []).map((e) => (
        <div key={`${e.source}-${e.predicate}-${e.target}`} className="space-y-1">
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <NodeChip type={e.source} />
            <span className="inline-flex items-center gap-1 font-mono text-muted-foreground">
              {e.predicate}
              <ArrowRightIcon className="size-3" aria-hidden="true" />
            </span>
            <NodeChip type={e.target} />
          </div>
          {e.attributes && e.attributes.length > 0 && (
            <div className="pl-2 text-xs text-muted-foreground">
              with {e.attributes.map((a) => `${a.name}: ${a.type}`).join(", ")}
            </div>
          )}
        </div>
      ))}
      {shape.nodes && shape.nodes.length > 0 && (
        <div className="text-xs text-muted-foreground">
          node types: {shape.nodes.map((n) => n.type).join(", ")}
        </div>
      )}
    </div>
  )
}

function NodeChip({ type }: { type: string }) {
  const paper = type === "Paper"
  return (
    <span className={paper ? "rounded-md border border-chart-1/50 bg-chart-1/10 px-1.5 py-0.5 font-medium" : "rounded-full border px-1.5 py-0.5"}>
      {type}
    </span>
  )
}
