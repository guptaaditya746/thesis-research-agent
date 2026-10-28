/**
 * The evidence table's TanStack Table instance, built where the page can read its order (the source panel's
 * previous / next follow what the table shows): sorting within lanes and column visibility.
 */
import {
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
  type Table as TanTable,
  type VisibilityState,
} from "@tanstack/react-table"
import { useState, type ReactNode } from "react"

import { byLane, type EvidenceRow, type Lane, type SourceTarget } from "@/lib/evidence"

export type Opener = (target: SourceTarget | null) => void

export interface EvidenceColumn<T> {
  id: string
  header: string
  cell: (row: EvidenceRow<T>, open: Opener) => ReactNode
  /** the value the column sorts by (none: not sortable) */
  sort?: (row: EvidenceRow<T>) => string | number | null | undefined
  /** the column can be hidden from the columns menu */
  hideable?: boolean
  /** false: hidden while the table is compact (beside the source panel, on a phone) unless the user shows it */
  compact?: boolean
  /** on a phone, moved next to the first column so it is seen without scrolling sideways (the verdict) */
  priority?: boolean
  className?: string
}

export function useEvidenceTable<T>({ rows, columns: given, onOpen, compact = false, phone = false }: {
  rows: EvidenceRow<T>[]
  columns: EvidenceColumn<T>[]
  onOpen: Opener
  compact?: boolean
  phone?: boolean
}) {
  const columns = phone ? [...given.slice(0, 1), ...given.slice(1).filter((c) => c.priority), ...given.slice(1).filter((c) => !c.priority)] : given
  const [sorting, setSorting] = useState<SortingState>([])
  // what the user chose in the columns menu wins over the compact defaults
  const [chosen, setChosen] = useState<VisibilityState>({})
  const visibility: VisibilityState = {
    ...Object.fromEntries(columns.filter((c) => c.compact === false).map((c) => [c.id, !compact])),
    ...chosen,
  }
  const defs: ColumnDef<EvidenceRow<T>>[] = columns.map((c) => ({
    id: c.id,
    header: c.header,
    accessorFn: c.sort ? (r) => c.sort!(r) ?? undefined : undefined,
    enableSorting: !!c.sort,
    enableHiding: !!c.hideable,
    sortUndefined: "last",
    cell: (info) => c.cell(info.row.original, onOpen),
    meta: { className: c.className },
  }))
  // TanStack Table returns functions the React Compiler cannot memoise; this component re-renders with it.
  // eslint-disable-next-line react-hooks/incompatible-library
  return useReactTable({
    data: rows,
    columns: defs,
    state: { sorting, columnVisibility: visibility },
    onSortingChange: setSorting,
    onColumnVisibilityChange: (update) => {
      const next = typeof update === "function" ? update(visibility) : update
      setChosen(Object.fromEntries(Object.entries(next).filter(([id, on]) => visibility[id] !== on || id in chosen)))
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getRowId: (r) => r.key,
  })
}

/** The rows as the table shows them: lane by lane, sorted within each lane. */
export function shownRows<T>(table: TanTable<EvidenceRow<T>>, lanes: Lane[]): EvidenceRow<T>[] {
  return byLane(table.getRowModel().rows.map((r) => r.original), lanes).flatMap((g) => g.rows)
}

