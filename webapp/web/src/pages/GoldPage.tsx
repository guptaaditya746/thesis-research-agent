/**
 * Gold `/gold` (plan "Frontend pages" 7): per question the screening coverage of D, the
 * candidate and key counts, review progress in Argilla, Cohen's kappa of the overlap, the triage
 * miss and screening false-negative estimates (gold/README.md, Review), the answer key itself, and the
 * gold build job for a question whose concept is picked.
 */
import { AwardIcon, ExternalLinkIcon, HammerIcon, KeyRoundIcon } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate } from "react-router"

import { isActiveJob, useBuildGold, useConfig, useGold, useGoldKey, useJobs, useQuestions } from "@/api/hooks"
import type { GoldEntry, KeyFact, KeyRow } from "@/api/types"
import { GoldBadge } from "@/components/badges"
import { PageHeader } from "@/components/layout/PageHeader"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { term } from "@/lib/facts"
import { cell, int, num, pct } from "@/lib/format"
import { goldView, stageText } from "@/lib/gold"
import { announceError, announceJob } from "@/lib/toasts"

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
        <EmptyState icon={<AwardIcon />} title="No gold data yet" description="Pick a concept for a question, then build its gold standard (screening, extraction, triage, review pool, draft key)." />
      ) : (
        <Card className="py-0">
          <CardContent className="px-0">
            <Table>
              <caption className="sr-only">Gold standard per question</caption>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-4">Question</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Screening coverage</TableHead>
                  <TableHead className="text-right">Candidates</TableHead>
                  <TableHead className="text-right">Key rows / facts</TableHead>
                  <TableHead className="min-w-36">Review</TableHead>
                  <TableHead className="text-right">κ (keep)</TableHead>
                  <TableHead className="text-right">Triage missed [95%]</TableHead>
                  <TableHead className="text-right">Screening FN [95%]</TableHead>
                  <TableHead className="pr-4"><span className="sr-only">Actions</span></TableHead>
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

function GoldRow({ gold: g, onKey }: { gold: GoldEntry; onKey: () => void }) {
  const v = goldView(g)
  const stage = stageText(g)
  const coverage = v.coverage
  return (
    <TableRow>
      <TableCell className="pl-4">
        <Link to={`/questions/${g.qid}`} className="font-mono hover:underline">{g.qid}</Link>
      </TableCell>
      <TableCell>
        <GoldBadge status={g.status} />
        {g.key_version && <div className="mt-1 font-mono text-xs text-muted-foreground">{g.key_version}</div>}
        {stage && <div className="mt-1 max-w-40 text-xs whitespace-normal text-muted-foreground">{stage}</div>}
      </TableCell>
      <TableCell className="text-xs">
        {coverage ? (
          <>
            <div className="tabular-nums">
              {int(coverage.relevant)} relevant of {int(coverage.papers)} papers
              {coverage.partial && coverage.papers_in_corpus ? ` (partial: corpus has ${int(coverage.papers_in_corpus)})` : ""}
            </div>
            <div className="text-muted-foreground tabular-nums">
              {int(coverage.not_relevant)} not relevant · {int(coverage.no_text)} no text · {int(coverage.error)} errors
            </div>
          </>
        ) : (
          "—"
        )}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {int(v.counts?.candidates)}
        {v.counts?.anchored != null && <div className="text-xs text-muted-foreground">{int(v.counts.anchored)} anchored</div>}
      </TableCell>
      <TableCell className="text-right tabular-nums">{g.rows != null ? `${int(g.rows)} / ${int(g.facts)}` : "—"}</TableCell>
      <TableCell>
        {v.review && v.review.records > 0 ? (
          <div className="space-y-1">
            <Progress value={Math.round((v.review.decided / v.review.records) * 100)} aria-label={`${v.review.decided} of ${v.review.records} review records decided`} />
            <div className="text-xs text-muted-foreground tabular-nums">
              {v.review.decided} of {v.review.records} decided{v.review.disagreements ? ` · ${v.review.disagreements} disagreements` : ""}
            </div>
          </div>
        ) : (
          <span className="text-xs text-muted-foreground">{g.status === "draft" ? "review not pulled yet" : "no review yet"}</span>
        )}
      </TableCell>
      <TableCell className="text-right text-xs tabular-nums">
        {v.kappa?.value != null ? (
          <span title={`${v.kappa.items ?? "?"} overlap records${v.kappa.independent === false ? "; not all from the independent round" : ""}`}>
            <span className="text-sm font-medium">{num(v.kappa.value)}</span>
            {v.kappa.bar != null && <span className="text-muted-foreground"> {v.kappa.meetsBar ? "≥" : "<"} {num(v.kappa.bar)}</span>}
            <div className="text-muted-foreground">{int(v.kappa.items)} items</div>
          </span>
        ) : "—"}
      </TableCell>
      <TableCell className="text-right text-xs tabular-nums">
        {v.triageMissed?.estimate != null ? `${num(v.triageMissed.estimate, 1)} [${num(v.triageMissed.low, 1)}, ${num(v.triageMissed.high, 1)}]` : "—"}
      </TableCell>
      <TableCell className="text-right text-xs tabular-nums">
        {v.screeningFalseNegative?.rate != null
          ? `${pct(v.screeningFalseNegative.rate)} [${pct(v.screeningFalseNegative.low)}, ${pct(v.screeningFalseNegative.high)}]`
          : "—"}
      </TableCell>
      <TableCell className="pr-4">
        {g.status === "none" ? (
          <BuildButton qid={g.qid} />
        ) : (
          <Button variant="ghost" size="xs" onClick={onKey} disabled={g.status === "building"}>
            <KeyRoundIcon data-icon="inline-start" />
            Key
          </Button>
        )}
      </TableCell>
    </TableRow>
  )
}

/** Start the gold build (POST /api/gold/{qid}/build) for a question with a picked concept. */
function BuildButton({ qid }: { qid: string }) {
  const questions = useQuestions()
  const jobs = useJobs()
  const build = useBuildGold()
  const navigate = useNavigate()
  const picked = questions.data?.find((q) => q.id === qid)?.concept.status === "picked"
  const running = jobs.data?.some((j) => j.kind === "gold" && j.qid === qid && isActiveJob(j))
  if (!picked) return <span className="text-xs text-muted-foreground">pick a concept first</span>
  return (
    <Button
      variant="outline"
      size="xs"
      disabled={build.isPending || running}
      onClick={() =>
        build.mutate(qid, {
          onSuccess: (job) => announceJob(job, navigate, `Building the gold standard of ${qid}`),
          onError: (error) => announceError("Could not start the gold build", error),
        })
      }
    >
      {build.isPending || running ? <Spinner data-icon="inline-start" /> : <HammerIcon data-icon="inline-start" />}
      {running ? "Building" : "Build"}
    </Button>
  )
}

function KeySheet({ qid, onClose }: { qid: string | null; onClose: () => void }) {
  const key = useGoldKey(qid)
  const rows = (key.data?.rows ?? []) as unknown as KeyRow[]
  return (
    <Sheet open={qid !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="gap-0 p-0 data-[side=right]:w-full data-[side=right]:sm:max-w-2xl">
        <SheetHeader className="border-b pr-12">
          <SheetTitle>Answer key · {qid}</SheetTitle>
          <SheetDescription asChild>
            <div className="flex flex-wrap items-center gap-2">
              {key.data ? (
                <>
                  <Badge variant="outline" className="font-mono">{key.data.version ?? "?"}</Badge>
                  {key.data.reviewed ? "reviewed" : "draft from triage alone"} · {rows.length} rows
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
              {rows.map((row) => (
                <li key={row.id} className="rounded-md border p-3 text-sm">
                  <p className="font-medium">
                    <span className="mr-2 font-mono text-xs text-muted-foreground">{row.id}</span>
                    {row.source != null ? `${row.source} ${row.predicate ?? ""} ${row.target ?? ""}` : Object.values(row.cells ?? {}).map(cell).join(" · ")}
                  </p>
                  <ul className="mt-2 space-y-2">
                    {(row.facts ?? []).map((f: KeyFact) => (
                      <li key={f.id} className="text-xs">
                        <span className="font-mono">{f.id}</span> ({term(f.s)}, {term(f.p)}, {term(f.o)}) {f.vital && <Badge className="ml-1 h-4 text-[10px]">vital</Badge>}
                        {f.quote && <blockquote className="mt-1 border-l-2 pl-2 text-muted-foreground">“{f.quote}” — {f.paper_id}</blockquote>}
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
