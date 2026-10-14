/** Rows of a query result as a table: objects keyed by column, or arrays in `columns` order. */
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cell } from "@/lib/format"

export function ResultTable({ rows, columns, caption }: { rows: (Record<string, unknown> | unknown[])[]; columns?: string[]; caption?: string }) {
  const cols = columns ?? [...new Set(rows.flatMap((r) => (Array.isArray(r) ? [] : Object.keys(r))))]
  const value = (row: Record<string, unknown> | unknown[], col: string, i: number) => (Array.isArray(row) ? row[i] : row[col])
  return (
    <div className="max-h-[28rem] overflow-auto rounded-md border">
      <Table>
        {caption && <caption className="sr-only">{caption}</caption>}
        <TableHeader className="sticky top-0 bg-background">
          <TableRow>
            {cols.map((c) => (
              <TableHead key={c} className="font-mono text-xs">{c}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, r) => (
            <TableRow key={r}>
              {cols.map((c, i) => (
                <TableCell key={c} className="max-w-80 align-top font-mono text-xs whitespace-pre-wrap">{cell(value(row, c, i))}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
