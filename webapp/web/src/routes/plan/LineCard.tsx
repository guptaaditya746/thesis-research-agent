/** One evidence line of the plan: its question, "how?" (plain sentences, closed by default, never SPARQL), a × to remove
 * it (none on the oversell line), and its result in place after the run. */
import { XIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

import type { LineResult, PlanLine } from "./api"

function Result({ result }: { result: LineResult }) {
  if (result.status === "failed") {
    return <p role="alert" className="text-sm font-medium text-destructive">{result.text}</p>
  }
  if (result.rows.length === 0) return <p className="text-sm text-muted-foreground">No evidence found</p>
  const columns = Object.keys(result.rows[0])
  return (
    <div className="space-y-1">
      <p className="text-sm">{result.text}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead><tr>{columns.map((c) => <th key={c} className="pr-3 font-medium">{c}</th>)}</tr></thead>
          <tbody>
            {result.rows.slice(0, 10).map((row, i) => (
              <tr key={i}>{columns.map((c) => <td key={c} className="pr-3 font-mono">{String(row[c] ?? "")}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function LineCard({ line, how, result, onRemove, busy }: {
  line: PlanLine
  /** Plain sentences from the backend (a template's header or an explain step); never the query. */
  how?: string[]
  result?: LineResult
  onRemove?: (id: string) => void
  busy?: boolean
}) {
  return (
    <Card data-line={line.id}>
      <CardHeader className="flex flex-row items-start justify-between gap-2">
        <CardTitle className="text-base">
          {line.question}
          {!line.removable && <Badge variant="outline" className="ml-2">always checked</Badge>}
        </CardTitle>
        {line.removable && onRemove && (
          <Button variant="ghost" size="icon-sm" aria-label={`Remove line: ${line.question}`} disabled={busy} onClick={() => onRemove(line.id)}>
            <XIcon />
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-2">
        <details>
          <summary className="cursor-pointer text-sm text-muted-foreground">how?</summary>
          <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm">
            {(how && how.length > 0 ? how : ["No explanation yet."]).map((s) => <li key={s}>{s}</li>)}
          </ol>
        </details>
        {result && <Result result={result} />}
      </CardContent>
    </Card>
  )
}
