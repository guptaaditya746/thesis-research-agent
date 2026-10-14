/**
 * Answer tab: the answer's rows in the concept's shape (table columns, or graph edges), each fact
 * a badge with its support status (scoring's label: supported, partial, not supported,
 * unsourced); a badge opens the claim walk. The legend counts the statuses and says how the
 * judge's "partial" counts in the support share.
 */
import { FileQuestionIcon, InfoIcon } from "lucide-react"

import type { Answer, AnswerRow, ConceptBrief, RunSummary } from "@/api/types"
import { ProvisionalBadge } from "@/components/badges"
import { EmptyState, ErrorState } from "@/components/states"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { FACT_STATUS_LABEL, FACT_STATUSES, isGraphRow, statusCounts, statusOf } from "@/lib/facts"
import { cell } from "@/lib/format"
import { ANSWER_FROM_LABEL } from "@/lib/run"

import { FactBadge, FactStatusIcon } from "./FactBadge"
import { useFactStatuses } from "./use-fact-statuses"
import { useWalk } from "./walk-context"

/** The table columns: the concept's, else the cells' keys in first-seen order. */
function tableColumns(answer: Answer, concept: ConceptBrief | null): string[] {
  const fromConcept = concept?.answer_shape.kind === "table" ? concept.answer_shape.columns?.map((c) => c.name) : undefined
  if (fromConcept?.length) return fromConcept
  return [...new Set(answer.rows.flatMap((r) => Object.keys(r.cells ?? {})))]
}

export function AnswerTab({ runId, answer, concept, summary }: {
  runId: string
  answer: Answer | null
  concept: ConceptBrief | null
  summary: RunSummary
}) {
  const { statuses, score, loading, error, retry } = useFactStatuses(runId, answer)
  const { open } = useWalk()

  if (!answer || answer.rows.length === 0) {
    return (
      <EmptyState
        icon={<FileQuestionIcon />}
        title={summary.live ? "No answer yet" : "The run has no answer"}
        description={summary.live ? "The answer appears when the agent submits it; follow the Timeline tab meanwhile." : (answer?.notes ?? "answer.json has no rows.")}
      />
    )
  }

  const counts = statusCounts(statuses.values())
  const graph = answer.kind === "graph"
  const columns = graph ? [] : tableColumns(answer, concept)
  const partial = score?.support?.partial_counts_as

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        {loading ? (
          <Skeleton className="h-5 w-72" />
        ) : (
          <ul className="flex flex-wrap gap-x-4 gap-y-1" aria-label="Facts by support status">
            {FACT_STATUSES.filter((s) => counts[s] > 0).map((s) => (
              <li key={s} className="flex items-center gap-1.5">
                <FactStatusIcon status={s} />
                <span className="tabular-nums">{counts[s]}</span> {FACT_STATUS_LABEL[s]}
              </li>
            ))}
          </ul>
        )}
        {score?.provisional && <ProvisionalBadge />}
        <span className="text-xs text-muted-foreground">
          {score
            ? `Verdicts as scored (key ${score.key_version ?? "?"})${partial ? `; partial counts as ${partial === "yes" ? "supported" : "not supported"}` : ""}.`
            : error
              ? "The verdicts could not be loaded: the badges show only whether a fact cites a claim."
              : "Not scored yet: a fact's walk can ask the judge."}{" "}
          Click a fact for its claim walk.
        </span>
      </div>
      {error ? <ErrorState error={error} title="Could not load score.json" onRetry={retry} /> : null}
      {summary.answer_from === "draft" && (
        <Alert>
          <InfoIcon />
          <AlertDescription>This answer is the agent's {ANSWER_FROM_LABEL.draft}: the run ended without a valid final answer.</AlertDescription>
        </Alert>
      )}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">Row</TableHead>
              {graph ? (
                <>
                  <TableHead>Source</TableHead>
                  <TableHead>Predicate</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Attributes</TableHead>
                </>
              ) : (
                columns.map((c) => <TableHead key={c} className="font-mono">{c}</TableHead>)
              )}
              <TableHead>Facts</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {answer.rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell className="font-mono text-xs text-muted-foreground">{row.id}</TableCell>
                {graph ? <GraphCells row={row} /> : columns.map((c) => (
                  <TableCell key={c} className="max-w-64 whitespace-normal">{cell(row.cells?.[c])}</TableCell>
                ))}
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {row.facts.map((fact) => (
                      <FactBadge key={fact.id} fact={fact} status={statusOf(statuses, row.id, fact)} onOpen={() => open({ kind: "fact", factId: fact.id })} />
                    ))}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {answer.notes && <p className="text-sm text-muted-foreground">Notes: {answer.notes}</p>}
    </div>
  )
}

function GraphCells({ row }: { row: AnswerRow }) {
  if (!isGraphRow(row)) return <TableCell colSpan={4} className="text-muted-foreground">{cell(row.cells)}</TableCell>
  return (
    <>
      <TableCell>
        {row.source} <span className="text-xs text-muted-foreground">{row.source_type}</span>
      </TableCell>
      <TableCell className="font-mono text-xs">{row.predicate}</TableCell>
      <TableCell>
        {row.target} <span className="text-xs text-muted-foreground">{row.target_type}</span>
      </TableCell>
      <TableCell className="text-xs">
        {Object.entries(row.attributes ?? {}).map(([k, v]) => (
          <div key={k}>
            <span className="text-muted-foreground">{k}:</span> {cell(v)}
          </div>
        ))}
      </TableCell>
    </>
  )
}
