/**
 * Corpora `/corpora`: a compact overview, with generation settings on demand.
 */
import { DatabaseIcon } from "lucide-react"
import { Link } from "react-router"

import { isActiveJob, useCorpora, useJobs } from "@/api/ev"
import { LabelBadge } from "@/components/ev/bits"
import { ArxivFetchDialog, DemoBadge } from "@/components/flow/ArxivFetchDialog"
import { JobPanel } from "@/components/jobs/JobPanel"
import { PageHeader } from "@/components/layout/PageHeader"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { knobText, levelOrder } from "@/lib/ev"

export default function CorporaPage() {
  const jobs = useJobs()
  const fetching = (jobs.data ?? []).filter((j) => j.kind === "fetch" && isActiveJob(j))
  const corpora = useCorpora(fetching.length > 0)
  const rows = [...(corpora.data ?? [])].sort((a, b) => a.name.localeCompare(b.name) || levelOrder(a.level ?? "", b.level ?? ""))
  return (
    <div className="space-y-4">
      <PageHeader title="Corpora" description="Paper collections available to run. Open a corpus for its papers, generation settings, and run history." actions={<ArxivFetchDialog />} />
      {fetching.map((j) => <JobPanel key={j.id} job={j} compact />)}
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
                {["corpus", "renderer", "level", "papers / fidelity", "expected label", "build details"].map((h) => <TableHead key={h} className="text-xs">{h}</TableHead>)}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((c) => (
                <TableRow key={c.name}>
                  <TableCell className="font-mono text-xs"><Link to={`/corpora/${encodeURIComponent(c.name)}`} className="hover:underline">{c.name}</Link><DemoBadge corpus={c} /></TableCell>
                  <TableCell>{c.renderer ?? "—"}</TableCell>
                  <TableCell>{c.level ?? "—"}</TableCell>
                  <TableCell className="tabular-nums">{c.papers} papers{c.fidelity_ok !== null && c.fidelity_ok !== undefined ? ` · ${c.fidelity_ok}/${c.papers} fidelity pass` : " · fidelity n/a"}</TableCell>
                  <TableCell><LabelBadge label={c.answer?.label} /></TableCell>
                  <TableCell className="text-xs">
                    <details>
                      <summary className="cursor-pointer">seed, knobs{c.variant ? ", variant" : ""}</summary>
                      <div className="mt-1 space-y-1 text-muted-foreground">
                        <div>seed: {c.seed ?? "—"}</div>
                        <div>knobs: {knobText(c.settings)}</div>
                        {c.variant && <Badge variant="outline">{c.variant.study}: {String(c.variant.from ?? "?")} → {c.variant.to ?? "?"}</Badge>}
                      </div>
                    </details>
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
