/**
 * Gold `/gold` (plan "Frontend pages" 7): per question the screening coverage, the candidate
 * and key counts, review progress in Argilla, Cohen's kappa with its interval, the triage miss
 * and screening false-negative estimates, and the answer key itself.
 */
import { AwardIcon, ExternalLinkIcon, KeyRoundIcon } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"

import { useConfig, useGold, useGoldKey } from "@/api/hooks"
import type { GoldSummary } from "@/api/types"
import { GoldBadge } from "@/components/badges"
import { PageHeader } from "@/components/layout/PageHeader"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cell, int, num, pct } from "@/lib/format"

export default function GoldPage() {
  const gold = useGold()
  const config = useConfig()
  const [keyOf, setKeyOf] = useState<string | null>(null)
  const argilla = config.data?.argilla_url

  return (
    <div className="space-y-4">
      <PageHeader
        title="Gold standard"
        description="Per question: every paper screened, facts extracted and triaged, a stratified sample reviewed by people in Argilla, then the answer key."
        actions={
          argilla ? (
            <Button asChild variant="outline">
              <a href={argilla} target="_blank" rel="noreferrer">
                Open Argilla <ExternalLinkIcon data-icon="inline-end" />
              </a>
            </Button>
          ) : null
        }
      />
      {gold.isError ? (
        <ErrorState error={gold.error} onRetry={() => void gold.refetch()} />
      ) : gold.isPending ? (
        <TableSkeleton rows={8} columns={8} />
      ) : gold.data.length === 0 ? (
        <EmptyState icon={<AwardIcon />} title="No gold data yet" description="`gold build <qid>` screens the corpus and drafts a key for a question with a picked concept." />
      ) : (
        <Card className="py-0">
          <CardContent className="px-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-4">Question</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Screening coverage</TableHead>
                  <TableHead className="text-right">Candidates</TableHead>
                  <TableHead className="text-right">Key rows / facts</TableHead>
                  <TableHead className="min-w-36">Review</TableHead>
                  <TableHead className="text-right">κ [95%]</TableHead>
                  <TableHead className="text-right">Triage miss</TableHead>
                  <TableHead className="text-right">Screening FN</TableHead>
                  <TableHead className="pr-4"><span className="sr-only">Key</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {gold.data.map((g) => (
                  <GoldRow key={g.qid} gold={g} onKey={() => setKeyOf(g.qid)} />
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
      <KeySheet qid={keyOf} onClose={() => setKeyOf(null)} />
    </div>
  )
}

function GoldRow({ gold: g, onKey }: { gold: GoldSummary; onKey: () => void }) {
  const pool = g.counts.pool ?? 0
  const reviewed = g.counts.reviewed ?? 0
  const kappa = g.report?.kappa
  return (
    <TableRow>
      <TableCell className="pl-4">
        <Link to={`/questions/${g.qid}`} className="font-mono hover:underline">{g.qid}</Link>
      </TableCell>
      <TableCell>
        <GoldBadge status={g.status} />
        {g.key_version && <div className="mt-1 font-mono text-xs text-muted-foreground">{g.key_version}</div>}
      </TableCell>
      <TableCell className="text-xs">
        {g.coverage ? (
          <>
            <div className="tabular-nums">{g.coverage.relevant} relevant of {g.coverage.papers} papers</div>
            <div className="text-muted-foreground tabular-nums">
              {g.coverage.not_relevant} not relevant · {g.coverage.no_text} no text · {g.coverage.error} errors
            </div>
          </>
        ) : (
          "—"
        )}
      </TableCell>
      <TableCell className="text-right tabular-nums">{int(g.counts.candidates)}</TableCell>
      <TableCell className="text-right tabular-nums">{g.counts.rows != null ? `${g.counts.rows} / ${int(g.counts.facts)}` : "—"}</TableCell>
      <TableCell>
        {pool > 0 ? (
          <div className="space-y-1">
            <Progress value={Math.round((reviewed / pool) * 100)} aria-label={`${reviewed} of ${pool} reviewed`} />
            <div className="text-xs text-muted-foreground tabular-nums">{reviewed} of {pool} reviewed{g.counts.overlap ? ` · ${g.counts.overlap} overlap` : ""}</div>
          </div>
        ) : (
          <span className="text-xs text-muted-foreground">no review pool yet</span>
        )}
      </TableCell>
      <TableCell className="text-right text-xs tabular-nums">
        {kappa?.value != null ? (
          <>
            <span className="text-sm font-medium">{num(kappa.value)}</span> [{num(kappa.low)}, {num(kappa.high)}]
          </>
        ) : "—"}
      </TableCell>
      <TableCell className="text-right text-xs tabular-nums">
        {g.report?.triage_miss?.rate != null ? `${pct(g.report.triage_miss.rate)} [${pct(g.report.triage_miss.low)}, ${pct(g.report.triage_miss.high)}]` : "—"}
      </TableCell>
      <TableCell className="text-right text-xs tabular-nums">
        {g.report?.screening_false_negative?.rate != null
          ? `${pct(g.report.screening_false_negative.rate)} [${pct(g.report.screening_false_negative.low)}, ${pct(g.report.screening_false_negative.high)}]`
          : "—"}
      </TableCell>
      <TableCell className="pr-4">
        <Button variant="ghost" size="xs" onClick={onKey} disabled={g.status === "none" || g.status === "building"}>
          <KeyRoundIcon data-icon="inline-start" />
          Key
        </Button>
      </TableCell>
    </TableRow>
  )
}

function KeySheet({ qid, onClose }: { qid: string | null; onClose: () => void }) {
  const key = useGoldKey(qid)
  return (
    <Sheet open={qid !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="gap-0 p-0 data-[side=right]:w-full data-[side=right]:sm:max-w-2xl">
        <SheetHeader className="border-b pr-12">
          <SheetTitle>Answer key · {qid}</SheetTitle>
          <SheetDescription asChild>
            <div className="flex flex-wrap items-center gap-2">
              {key.data ? (
                <>
                  <Badge variant="outline" className="font-mono">{key.data.version}</Badge>
                  {key.data.reviewed ? "reviewed" : "draft from triage alone"} · {key.data.rows.length} rows
                </>
              ) : (
                "key.json, or key.draft.json before review"
              )}
            </div>
          </SheetDescription>
        </SheetHeader>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {key.isPending ? (
            <Skeleton className="h-64 w-full" />
          ) : key.isError ? (
            <ErrorState error={key.error} />
          ) : !key.data ? (
            <EmptyState icon={<KeyRoundIcon />} title="No key yet" />
          ) : (
            <ol className="space-y-3">
              {key.data.rows.map((row) => (
                <li key={row.id} className="rounded-md border p-3 text-sm">
                  <p className="font-medium">
                    <span className="mr-2 font-mono text-xs text-muted-foreground">{row.id}</span>
                    {"source" in row
                      ? `${row.source} ${row.predicate} ${row.target}`
                      : Object.values(row.cells).map(cell).join(" · ")}
                  </p>
                  <ul className="mt-2 space-y-2">
                    {row.facts.map((f) => (
                      <li key={f.id} className="text-xs">
                        <span className="font-mono">{f.id}</span> ({f.s}, {f.p}, {String(f.o)}) {f.vital && <Badge className="ml-1 h-4 text-[10px]">vital</Badge>}
                        <blockquote className="mt-1 border-l-2 pl-2 text-muted-foreground">“{f.quote}” — {f.paper_id}</blockquote>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
