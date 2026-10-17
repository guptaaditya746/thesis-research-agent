/**
 * Small pieces every evidence-level page uses: system, direction and label badges (an icon and a label,
 * never colour alone), a key/value list, a JSON block, a generic rows table, and the query state of a page.
 */
import type { UseQueryResult } from "@tanstack/react-query"
import {
  ArrowDownRightIcon,
  ArrowUpRightIcon,
  CircleHelpIcon,
  EqualIcon,
  SearchXIcon,
} from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router"

import { isNotFound } from "@/api/client"
import type { Direction } from "@/api/ev"
import { StatusBadge } from "@/components/badges"
import { CardsSkeleton, EmptyState, ErrorState } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { DIRECTION_LABEL, DIRECTION_TONE, evCell, systemColor, systemLabel } from "@/lib/ev"
import { cn } from "@/lib/utils"

export function SystemBadge({ system }: { system: string }) {
  return (
    <Badge variant="outline" className="gap-1.5 font-normal">
      <span className="size-2 rounded-full" style={{ background: systemColor(system) }} aria-hidden="true" />
      {systemLabel(system)}
    </Badge>
  )
}

const DIRECTION_ICON: Record<Direction, ReactNode> = {
  supports: <ArrowUpRightIcon />,
  contradicts: <ArrowDownRightIcon />,
  neutral: <EqualIcon />,
  undetermined: <CircleHelpIcon />,
}

export function DirectionBadge({ direction, title }: { direction: string | null | undefined; title?: string }) {
  const d = (direction ?? "undetermined") as Direction
  if (!(d in DIRECTION_LABEL)) return <Badge variant="outline">{String(direction)}</Badge>
  return <StatusBadge tone={DIRECTION_TONE[d]} icon={DIRECTION_ICON[d]} title={title}>{DIRECTION_LABEL[d]}</StatusBadge>
}

/** The answer's label (supported, refuted, mixed, no_effect, insufficient), as the protocol's table names it. */
export function LabelBadge({ label, correct }: { label: string | null | undefined; correct?: boolean | null }) {
  return (
    <Badge variant={correct === false ? "destructive" : "secondary"} className="font-mono" title={correct === undefined || correct === null ? undefined : correct ? "the expected label" : "not the expected label"}>
      {label ?? "—"}
      {correct === true && <span className="sr-only"> (correct)</span>}
      {correct === false && <span className="sr-only"> (wrong)</span>}
    </Badge>
  )
}

export function KeyValues({ items, className }: { items: [ReactNode, ReactNode][]; className?: string }) {
  return (
    <dl className={cn("grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm", className)}>
      {items.map(([k, v], i) => (
        <div key={i} className="contents">
          <dt className="text-muted-foreground">{k}</dt>
          <dd className="min-w-0 break-words">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

export function JsonBlock({ value, className, label }: { value: unknown; className?: string; label?: string }) {
  return (
    <pre aria-label={label} className={cn("max-h-96 overflow-auto rounded-md border bg-muted/40 p-3 font-mono text-xs whitespace-pre-wrap", className)}>
      {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
    </pre>
  )
}

/** Rows as a table, one column per key (or `columns`), cells formatted by `render` or `evCell`. */
export function RowsTable({
  rows,
  columns,
  caption,
  render,
  headers,
}: {
  rows: Record<string, unknown>[]
  columns?: string[]
  caption: string
  render?: (column: string, value: unknown, row: Record<string, unknown>) => ReactNode
  headers?: Record<string, string>
}) {
  const cols = columns?.length ? columns : [...new Set(rows.flatMap((r) => Object.keys(r)))]
  return (
    <div className="overflow-auto rounded-md border">
      <Table aria-label={caption}>
        <TableHeader>
          <TableRow>
            {cols.map((c) => (
              <TableHead key={c} className="text-xs whitespace-nowrap">{headers?.[c] ?? c.replaceAll("_", " ")}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, r) => (
            <TableRow key={r}>
              {cols.map((c) => (
                <TableCell key={c} className="max-w-96 align-top text-xs tabular-nums">
                  {render ? render(c, row[c], row) : evCell(row[c])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

/**
 * A page's query: a skeleton while it loads, "not there" with a way back for a 404 (no such directory under
 * the root), the backend's reason otherwise; the content once there.
 */
export function QueryPage<T>({ query, what, back, children }: {
  query: UseQueryResult<T>
  what: string
  back: { to: string; label: string }
  children: (data: T) => ReactNode
}) {
  if (query.isPending) return <CardsSkeleton count={2} />
  if (query.isError) {
    return isNotFound(query.error) ? (
      <EmptyState icon={<SearchXIcon />} title={`No ${what}`} description={query.error instanceof Error ? query.error.message : undefined}>
        <Button asChild variant="outline"><Link to={back.to}>{back.label}</Link></Button>
      </EmptyState>
    ) : (
      <ErrorState error={query.error} onRetry={() => void query.refetch()} />
    )
  }
  return <>{children(query.data)}</>
}
