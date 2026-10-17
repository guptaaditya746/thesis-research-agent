/**
 * Runs `/earlier/runs` (plan "Frontend pages" 3): every run with its cost, claims, verify state and
 * headline score; filters by question and condition live in the URL (?qid=&condition=&stale=1),
 * so a filtered list can be linked. The list polls while a run is live or still being scored.
 */
import { FlaskConicalIcon, ListChecksIcon, Loader2Icon, XIcon } from "lucide-react"
import { Link, useNavigate, useSearchParams } from "react-router"

import { useQuestions, useRuns } from "@/api/hooks"
import type { RunFilters } from "@/api/types"
import { ConditionBadge, ExitBadge, LiveDot, SandboxBadge, VerifyBadge } from "@/components/badges"
import { PageHeader } from "@/components/layout/PageHeader"
import { NewRunDialog } from "@/components/new-run/NewRunDialog"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { dateTime, duration, int, num, pct, tokens } from "@/lib/format"
import { splitRunId } from "@/lib/run"
import { cn } from "@/lib/utils"

const ALL = "all"

export default function RunsPage() {
  const [params, setParams] = useSearchParams()
  const filters: RunFilters = {
    qid: params.get("qid") || undefined,
    condition: params.get("condition") || undefined,
    include_stale: params.get("stale") === "1" || undefined,
  }
  const runs = useRuns(filters)
  const questions = useQuestions()
  const navigate = useNavigate()

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params)
    if (value === null || value === ALL) next.delete(key)
    else next.set(key, value)
    setParams(next, { replace: true })
  }
  const filtered = !!(filters.qid || filters.condition)

  return (
    <div className="space-y-4">
      <PageHeader
        title="Runs"
        description="One row per run directory: the cluster's batches and the runs started here. Open a run for its answer, graph, timeline, claims, provenance and score."
        actions={<NewRunDialog defaultQid={filters.qid} />}
      />
      <div className="flex flex-wrap items-end gap-3" role="search" aria-label="Filter runs">
        <div className="space-y-1">
          <Label htmlFor="runs-qid" className="text-xs text-muted-foreground">Question</Label>
          <Select value={filters.qid ?? ALL} onValueChange={(v) => setParam("qid", v)}>
            <SelectTrigger id="runs-qid" className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All questions</SelectItem>
              {questions.data?.map((q) => (
                <SelectItem key={q.id} value={q.id}>{q.id}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="runs-condition" className="text-xs text-muted-foreground">Condition</Label>
          <Select value={filters.condition ?? ALL} onValueChange={(v) => setParam("condition", v)}>
            <SelectTrigger id="runs-condition" className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Both conditions</SelectItem>
              <SelectItem value="claim_on">claim on</SelectItem>
              <SelectItem value="claim_off">claim off</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {filters.qid && (
          <div className="flex h-9 items-center gap-2">
            <Switch id="runs-stale" checked={!!filters.include_stale} onCheckedChange={(v) => setParam("stale", v ? "1" : null)} />
            <Label htmlFor="runs-stale" className="text-sm">Also runs on a replaced concept</Label>
          </div>
        )}
        {filtered && (
          <Button variant="ghost" size="sm" onClick={() => setParams(new URLSearchParams(), { replace: true })}>
            <XIcon data-icon="inline-start" />
            Clear filters
          </Button>
        )}
      </div>
      {runs.isError ? (
        <ErrorState error={runs.error} onRetry={() => void runs.refetch()} />
      ) : runs.isPending ? (
        <TableSkeleton rows={8} columns={9} />
      ) : runs.data.length === 0 ? (
        <EmptyState
          icon={<ListChecksIcon />}
          title={filtered ? "No runs match these filters" : "No runs yet"}
          description={filtered ? "Clear the filters or start a run for this question." : "Start one with New run; it appears here when its directory exists."}
        >
          <NewRunDialog defaultQid={filters.qid} />
        </EmptyState>
      ) : (
        <Card className={cn("py-0 transition-opacity", runs.isPlaceholderData && "opacity-60")}>
          <CardContent className="px-0">
            <Table>
              <caption className="sr-only">Runs</caption>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-4">Run</TableHead>
                  <TableHead>Condition</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Exit</TableHead>
                  <TableHead className="text-right">Steps</TableHead>
                  <TableHead className="text-right">Tokens</TableHead>
                  <TableHead className="text-right">Time</TableHead>
                  <TableHead className="text-right">Rows / facts</TableHead>
                  <TableHead className="text-right">Claims ✓ / ✗</TableHead>
                  <TableHead>Verify</TableHead>
                  <TableHead className="text-right">Support</TableHead>
                  <TableHead className="pr-4 text-right">Fact F1</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.data.map((r) => {
                  const { batch, name } = splitRunId(r.run_id)
                  const href = `/earlier/runs/${encodeURIComponent(r.run_id)}`
                  return (
                    <TableRow key={r.run_id} className="cursor-pointer" onClick={() => navigate(href)}>
                      <TableCell className="pl-4">
                        <div className="flex items-center gap-2">
                          {r.live && <LiveDot />}
                          <Link to={href} className="font-mono text-xs font-medium hover:underline" onClick={(e) => e.stopPropagation()}>
                            {name}
                          </Link>
                          {r.post_processing && <Loader2Icon className="size-3 animate-spin text-muted-foreground motion-reduce:animate-none" aria-label="verifying and scoring" />}
                          <SandboxBadge mode={r.sandbox} />
                        </div>
                        <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                          {batch && <Badge variant="secondary" className="h-4 px-1 font-mono text-[10px] font-normal">{batch}</Badge>}
                          {r.qid ?? "no question"} · seed {r.seed ?? "—"} · T {r.temperature ?? "—"}
                          {r.concept_current === false && <span className="text-status-serious">· replaced concept</span>}
                        </div>
                      </TableCell>
                      <TableCell><ConditionBadge condition={r.condition} /></TableCell>
                      <TableCell className="text-xs whitespace-nowrap">{dateTime(r.created_at)}</TableCell>
                      <TableCell><ExitBadge status={r.exit_status} live={r.live} /></TableCell>
                      <TableCell className="text-right tabular-nums">{r.steps}</TableCell>
                      <TableCell className="text-right tabular-nums">{tokens(r.tokens)}</TableCell>
                      <TableCell className="text-right tabular-nums whitespace-nowrap">{duration(r.seconds)}</TableCell>
                      <TableCell className="text-right tabular-nums">{int(r.rows)} / {int(r.facts)}</TableCell>
                      <TableCell className="text-right tabular-nums">{r.claims_accepted} / {r.claims_rejected}</TableCell>
                      <TableCell><VerifyBadge verify={r.verify} /></TableCell>
                      <TableCell className="text-right tabular-nums">
                        <span className="inline-flex items-center gap-1">
                          {r.score?.provisional && <FlaskConicalIcon className="size-3 text-status-warning" aria-label="provisional: scored against the draft key" />}
                          {pct(r.score?.support_share, 0)}
                        </span>
                      </TableCell>
                      <TableCell className="pr-4 text-right tabular-nums">{num(r.score?.fact_f1)}</TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
