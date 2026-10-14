/** Rows of a query result as a table, one column per key (or per variable, in `columns` order). */
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cell } from "@/lib/format"

export function ResultTable({ rows, columns, caption }: { rows: Record<string, unknown>[]; columns?: string[]; caption?: string }) {
  const cols = columns?.length ? columns : [...new Set(rows.flatMap((r) => Object.keys(r)))]
  return (
    <div className="max-h-[28rem] overflow-auto rounded-md border">
      <Table aria-label={caption}>
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
              {cols.map((c) => (
                <TableCell key={c} className="max-w-80 align-top font-mono text-xs whitespace-pre-wrap">{cell(row[c])}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
