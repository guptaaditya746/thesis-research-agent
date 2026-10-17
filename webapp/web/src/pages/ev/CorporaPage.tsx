/**
 * Corpora `/corpora` (synth build, synth variant; docs/evidence-system.md A1, F2, F3): per corpus its level,
 * renderer, seed, the knobs, the fidelity checks passed, the label it is built to have, and whether it is a
 * counterfactual variant of another corpus.
 */
import { DatabaseIcon } from "lucide-react"
import { Link } from "react-router"

import { useCorpora } from "@/api/ev"
import { LabelBadge } from "@/components/ev/bits"
import { PageHeader } from "@/components/layout/PageHeader"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { knobText, levelOrder } from "@/lib/ev"

export default function CorporaPage() {
  const corpora = useCorpora()
  const rows = [...(corpora.data ?? [])].sort((a, b) => a.name.localeCompare(b.name) || levelOrder(a.level ?? "", b.level ?? ""))
  return (
    <div className="space-y-4">
      <PageHeader title="Corpora" description="Synthetic corpora written from structured ground truth (synth build), one per difficulty level and a mixed one; variants change one study (synth variant)." />
      {corpora.isPending && <TableSkeleton />}
      {corpora.isError && <ErrorState error={corpora.error} onRetry={() => void corpora.refetch()} />}
      {corpora.data && !rows.length && (
        <EmptyState icon={<DatabaseIcon />} title="No corpora" description="Nothing under the corpora root ($CORPORA, default $EV/corpora). Build one with `uv run synth build`." />
      )}
      {rows.length > 0 && (
        <div className="overflow-auto rounded-md border">
          <Table aria-label="Corpora">
            <TableHeader>
              <TableRow>
                {["corpus", "level", "renderer", "seed", "papers", "fidelity", "knobs", "expected label", "variant"].map((h) => <TableHead key={h} className="text-xs">{h}</TableHead>)}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((c) => (
                <TableRow key={c.name}>
                  <TableCell className="font-mono text-xs"><Link to={`/corpora/${encodeURIComponent(c.name)}`} className="hover:underline">{c.name}</Link></TableCell>
                  <TableCell>{c.level ?? "—"}</TableCell>
                  <TableCell>{c.renderer ?? "—"}</TableCell>
                  <TableCell className="tabular-nums">{c.seed ?? "—"}</TableCell>
                  <TableCell className="tabular-nums">{c.papers}</TableCell>
                  <TableCell className="tabular-nums">{c.fidelity_ok === null || c.fidelity_ok === undefined ? "—" : `${c.fidelity_ok}/${c.papers} pass`}</TableCell>
                  <TableCell className="text-xs">{knobText(c.settings)}</TableCell>
                  <TableCell><LabelBadge label={c.answer?.label} /></TableCell>
                  <TableCell className="text-xs">
                    {c.variant ? <Badge variant="outline">{c.variant.study}: {String(c.variant.from ?? "?")} → {c.variant.to ?? "?"}</Badge> : ""}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
