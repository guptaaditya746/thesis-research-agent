/**
 * The evidence table: one row per paper (or per inventory entry), grouped into lanes by verdict, each lane
 * under its own header row with what it means. Columns are given per question kind (EvidenceColumns.tsx);
 * TanStack Table does the sorting (within a lane) and the column visibility. A cell that points at evidence
 * is a button that opens the source panel on that item's span (`onOpen`).
 *
 * `useEvidenceTable` (useEvidenceTable.ts) builds the table where the page can read its order; `EvidenceTable`
 * draws it and `ColumnsMenu` toggles its columns.
 */
import type { Table as TanTable } from "@tanstack/react-table"
import { ArrowDownIcon, ArrowUpDownIcon, ArrowUpIcon, Columns3Icon } from "lucide-react"
import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { byLane, type EvidenceRow, type Lane, type SourceTarget } from "@/lib/evidence"
import { cn } from "@/lib/utils"

import { LaneIcon } from "./CoverageBar"
import type { Opener } from "./useEvidenceTable"

export function ColumnsMenu<T>({ table }: { table: TanTable<EvidenceRow<T>> }) {
  const hideable = table.getAllLeafColumns().filter((c) => c.getCanHide())
  if (!hideable.length) return null
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm"><Columns3Icon data-icon="inline-start" />Columns</Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Show columns</DropdownMenuLabel>
        {hideable.map((c) => (
          <DropdownMenuCheckboxItem key={c.id} checked={c.getIsVisible()} onCheckedChange={(v) => c.toggleVisibility(!!v)} onSelect={(e) => e.preventDefault()}>
            {String(c.columnDef.header)}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** A cell that points at evidence: a button that opens the source panel there; plain text without a target. */
export function SourceButton({ target, onOpen, label, children, className }: {
  target: SourceTarget | null
  onOpen: Opener
  /** what the button does, for screen readers ("S001: treatment value 0.572, show in the paper") */
  label?: string
  children: ReactNode
  className?: string
}) {
  if (!target) return <span className={className}>{children}</span>
  return (
    <button type="button" data-cell="" aria-label={label} onClick={() => onOpen(target)}
      className={cn("-mx-1 cursor-pointer rounded-sm px-1 text-left underline decoration-muted-foreground/50 decoration-dotted underline-offset-4 hover:bg-muted hover:decoration-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none", className)}>
      {children}
    </button>
  )
}

const SORT_ICON = { asc: ArrowUpIcon, desc: ArrowDownIcon }

export function EvidenceTable<T>({ table, lanes, caption, active }: {
  table: TanTable<EvidenceRow<T>>
  lanes: Lane[]
  caption: string
  /** the key of the row the source panel shows */
  active?: string | null
}) {
  const groups = byLane(table.getRowModel().rows.map((r) => r.original), lanes)
  const cells = new Map(table.getRowModel().rows.map((r) => [r.id, r.getVisibleCells()]))
  const width = table.getVisibleLeafColumns().length
  return (
    <div className="overflow-x-auto rounded-md border">
      <Table aria-label={caption}>
        <TableHeader>
          <TableRow>
            {table.getHeaderGroups()[0].headers.map((h) => {
              const sorted = h.column.getIsSorted()
              const Icon = sorted ? SORT_ICON[sorted] : ArrowUpDownIcon
              const meta = h.column.columnDef.meta as { className?: string } | undefined
              return (
                <TableHead key={h.id} className={cn("text-xs", meta?.className)}
                  aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : h.column.getCanSort() ? "none" : undefined}>
                  {h.column.getCanSort() ? (
                    <button type="button" onClick={h.column.getToggleSortingHandler()}
                      className="-mx-1 inline-flex cursor-pointer items-center gap-1 rounded-sm px-1 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
                      {String(h.column.columnDef.header)}
                      <Icon aria-hidden="true" className={cn("size-3", !sorted && "opacity-40")} />
                    </button>
                  ) : String(h.column.columnDef.header)}
                </TableHead>
              )
            })}
          </TableRow>
        </TableHeader>
        {groups.map(({ lane, rows }) => (
          <TableBody key={lane.key} aria-label={`${lane.label}: ${rows.length}`}>
            <TableRow className="bg-muted/50 hover:bg-muted/50">
              <th scope="colgroup" colSpan={width} className="px-2 py-1.5 text-left text-xs font-medium">
                {/* sticks to the left edge while the table scrolls sideways, so the lane name stays in view */}
                <span className="sticky left-2 inline-flex max-w-[calc(100vw-3rem)] flex-wrap items-center gap-x-1.5">
                  <LaneIcon lane={lane} />
                  <span>{lane.label}</span>
                  <span className="font-mono tabular-nums">{rows.length}</span>
                  <span className="font-normal text-muted-foreground">· {lane.hint}</span>
                </span>
              </th>
            </TableRow>
            {rows.map((row) => (
              <TableRow key={row.key} data-state={active === row.key ? "selected" : undefined} aria-current={active === row.key ? "true" : undefined}
                className={cn(row.lane === "absent" || row.lane === "undetermined" ? "text-muted-foreground" : undefined)}>
                {(cells.get(row.key) ?? []).map((c) => {
                  const meta = c.column.columnDef.meta as { className?: string } | undefined
                  return (
                    <TableCell key={c.id} className={cn("align-top text-xs whitespace-normal", meta?.className)}>
                      {/* called, not rendered as a component (flexRender would): the column defs are made
                          anew each render, so as components every cell would remount and lose its focus */}
                      {typeof c.column.columnDef.cell === "function" ? c.column.columnDef.cell(c.getContext()) : null}
                    </TableCell>
                  )
                })}
              </TableRow>
            ))}
          </TableBody>
        ))}
      </Table>
    </div>
  )
}
