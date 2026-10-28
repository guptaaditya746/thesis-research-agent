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
import type { KeyboardEvent, ReactNode } from "react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table"
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
      className={cn("-mx-1 inline-block min-h-6 cursor-pointer rounded-sm px-1 text-left underline decoration-muted-foreground/50 decoration-dotted underline-offset-4 hover:bg-muted hover:decoration-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none", className)}>
      {children}
    </button>
  )
}

const SORT_ICON = { asc: ArrowUpIcon, desc: ArrowDownIcon }

/**
 * Arrow keys between the cells that open the paper (the buttons marked `data-cell`): left and right within
 * a row, up and down to the nearest such cell in the rows above and below, Home and End to a row's ends.
 * Tab still reaches every cell in order; this only makes a long table quicker to cross.
 */
function moveBetweenCells(e: KeyboardEvent<HTMLDivElement>) {
  if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(e.key)) return
  const from = (e.target as HTMLElement).closest<HTMLElement>("[data-cell]")
  const row = from?.closest<HTMLElement>("tr[data-row]")
  if (!from || !row) return
  const rows = [...e.currentTarget.querySelectorAll<HTMLElement>("tr[data-row]")]
  const cellsOf = (r: HTMLElement) => [...r.querySelectorAll<HTMLElement>("[data-cell]")]
  const colOf = (el: HTMLElement) => Number(el.closest<HTMLElement>("td")?.dataset.col ?? 0)
  const here = cellsOf(row)
  let next: HTMLElement | undefined
  if (e.key === "ArrowRight") next = here[here.indexOf(from) + 1]
  else if (e.key === "ArrowLeft") next = here[here.indexOf(from) - 1]
  else if (e.key === "Home") next = here[0]
  else if (e.key === "End") next = here.at(-1)
  else {
    const by = e.key === "ArrowDown" ? 1 : -1
    const col = colOf(from)
    for (let i = rows.indexOf(row) + by; i >= 0 && i < rows.length && !next; i += by) {
      next = cellsOf(rows[i]).sort((a, b) => Math.abs(colOf(a) - col) - Math.abs(colOf(b) - col))[0]
    }
  }
  if (next) {
    e.preventDefault()
    next.focus()
  }
}

export function EvidenceTable<T>({ table, lanes, caption, active, footer, compact = false }: {
  table: TanTable<EvidenceRow<T>>
  lanes: Lane[]
  caption: string
  /** the key of the row the source panel shows */
  active?: string | null
  /** a total row: its text per column id */
  footer?: Record<string, string>
  /** narrow: cells drop their pictures (the effect dot), keeping the words */
  compact?: boolean
}) {
  const groups = byLane(table.getRowModel().rows.map((r) => r.original), lanes)
  const cells = new Map(table.getRowModel().rows.map((r) => [r.id, r.getVisibleCells()]))
  const width = table.getVisibleLeafColumns().length
  return (
    // the keys are handled here, on the cells' container; the cells themselves are buttons
    <div className="group/evtable overflow-x-auto rounded-md border" data-compact={compact} onKeyDown={moveBetweenCells}>
      <Table aria-label={caption} aria-describedby={`${caption.replaceAll(" ", "-")}-keys`}>
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
                      className="-mx-1 inline-flex min-h-6 cursor-pointer items-center gap-1 rounded-sm px-1 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
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
              // selected: a bar at the start and a light tint (the full muted fill is 4.3:1 under muted text)
              <TableRow key={row.key} data-row="" data-state={active === row.key ? "selected" : undefined} aria-current={active === row.key ? "true" : undefined}
                className={cn("data-[state=selected]:bg-muted/50 data-[state=selected]:shadow-[inset_3px_0_0_var(--foreground)]",
                  (row.lane === "absent" || row.lane === "undetermined") && "text-muted-foreground")}>
                {(cells.get(row.key) ?? []).map((c, col) => {
                  const meta = c.column.columnDef.meta as { className?: string } | undefined
                  return (
                    <TableCell key={c.id} data-col={col} className={cn("align-top text-xs whitespace-normal", meta?.className)}>
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
        {footer && (
          <TableFooter>
            <TableRow>
              {table.getVisibleLeafColumns().map((c, n) => (n === 0
                ? <th key={c.id} scope="row" className="p-2 text-left text-xs font-medium">{footer[c.id] ?? ""}</th>
                : <TableCell key={c.id} className="text-xs font-medium tabular-nums">{footer[c.id] ?? ""}</TableCell>))}
            </TableRow>
          </TableFooter>
        )}
      </Table>
      <p id={`${caption.replaceAll(" ", "-")}-keys`} className="border-t px-2 py-1.5 text-xs text-muted-foreground">
        Underlined cells open the paper at that sentence. Arrow keys move between them; Enter opens.
      </p>
    </div>
  )
}
