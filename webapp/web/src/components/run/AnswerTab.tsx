/**
 * Answer tab: the answer's rows in the concept's shape (table columns, or graph edges), each
 * fact a badge with its support status; a badge opens the claim walk. The statuses come from
 * the facts' walks (judge verdict), fetched once per sourced fact and shared with the sheet.
 */
import { FileQuestionIcon } from "lucide-react"

import type { Answer, ConceptBrief } from "@/api/types"
import { EmptyState } from "@/components/states"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { FACT_STATUS_LABEL, isGraphRow, statusCounts, type FactStatus } from "@/lib/facts"
import { cell } from "@/lib/format"

import { FactBadge, FactStatusIcon } from "./FactBadge"
import { useFactStatuses } from "./use-fact-statuses"
import { useWalk } from "./walk-context"

export function AnswerTab({ runId, answer, concept, live }: { runId: string; answer: Answer | null; concept: ConceptBrief; live: boolean }) {
  const statuses = useFactStatuses(runId, answer)
  const { open } = useWalk()

  if (!answer || answer.rows.length === 0) {
    return (
      <EmptyState
        icon={<FileQuestionIcon />}
        title={live ? "No answer yet" : "The run has no answer"}
        description={live ? "The answer appears when the agent submits it; follow the Timeline tab meanwhile." : (answer?.notes ?? "answer.json has no rows.")}
      />
    )
  }

  const counts = statusCounts([...statuses.values()].map((s) => s.status))
  const columns =
    answer.kind === "table"
      ? concept.answer_shape.kind === "table"
        ? concept.answer_shape.columns.map((c) => c.name)
        : Object.keys((answer.rows[0] as { cells?: object }).cells ?? {})
      : []

  return (
    <div className="space-y-3">
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Facts by support status">
        {(Object.keys(counts) as FactStatus[]).filter((s) => counts[s] > 0).map((s) => (
          <li key={s} className="flex items-center gap-1.5">
            <FactStatusIcon status={s} />
            <span className="tabular-nums">{counts[s]}</span> {FACT_STATUS_LABEL[s]}
          </li>
        ))}
      </ul>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">Row</TableHead>
              {answer.kind === "table" ? (
                columns.map((c) => <TableHead key={c} className="font-mono">{c}</TableHead>)
              ) : (
                <>
                  <TableHead>Source</TableHead>
                  <TableHead>Predicate</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Attributes</TableHead>
                </>
              )}
              <TableHead>Facts</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {answer.rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell className="font-mono text-xs text-muted-foreground">{row.id}</TableCell>
                {isGraphRow(row) ? (
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
                ) : (
                  columns.map((c) => (
                    <TableCell key={c} className="max-w-64 whitespace-normal">{cell((row as { cells: Record<string, unknown> }).cells[c])}</TableCell>
                  ))
                )}
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {row.facts.map((fact) => {
                      const s = statuses.get(fact.id) ?? { status: "unjudged" as const, loading: false }
                      return (
                        <FactBadge
                          key={fact.id}
                          fact={fact}
                          status={s.status}
                          loading={s.loading}
                          onOpen={() => open({ kind: "fact", factId: fact.id })}
                        />
                      )
                    })}
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
