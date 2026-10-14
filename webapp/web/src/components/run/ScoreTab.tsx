/**
 * Score tab: score.json against the answer key (scoring contract): support of the answer's
 * facts (the primary measure), matched / wrong / missed rows and facts at the three matching
 * levels, vital recall, and the cost with and without the attach step.
 */
import { CheckCircle2Icon, CircleDotIcon, CircleSlashIcon, GaugeIcon, XCircleIcon } from "lucide-react"
import type { ReactNode } from "react"

import { useScore } from "@/api/hooks"
import type { PRF, Score } from "@/api/types"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { duration, int, num, pct, tokens } from "@/lib/format"

export function ScoreTab({ runId }: { runId: string }) {
  const score = useScore(runId)
  if (score.isPending) return <TableSkeleton rows={6} columns={6} />
  if (score.isError) return <ErrorState error={score.error} onRetry={() => void score.refetch()} />
  if (!score.data) {
    return (
      <EmptyState
        icon={<GaugeIcon />}
        title="Not scored yet"
        description="score.json appears when `score run` has compared the answer with the question's answer key (a reviewed key, or the draft)."
      />
    )
  }
  return <ScoreView score={score.data} />
}

export function ScoreView({ score }: { score: Score }) {
  const s = score.support
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        key <Badge variant="outline" className="font-mono">{score.key_version}</Badge>
        {!score.verify_ok && <Badge variant="destructive">verify failed: scored anyway</Badge>}
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Tile label="Support share" value={pct(s.support_share)} note={`${s.supports} of ${s.facts} facts supported by their quote`} />
        <Tile label="Fact F1 (soft)" value={num(score.facts.soft.f1)} note={`precision ${num(score.facts.soft.precision)} · recall ${num(score.facts.soft.recall)}`} />
        <Tile label="Row F1" value={num(score.rows.f1)} note={`${score.rows.tp} matched of ${score.rows.tp + score.rows.fn} key rows`} />
        <Tile label="Vital recall" value={pct(score.vital_recall)} note="key facts marked vital that the answer has" />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Support of the answer's facts</CardTitle>
          <CardDescription>The judge's verdict on each sourced fact's quote; unsourced facts have no claim.</CardDescription>
        </CardHeader>
        <CardContent>
          <SupportBar support={s} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Against the key</CardTitle>
          <CardDescription>Matched = in the answer and the key; wrong = in the answer only; missed = in the key only.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Unit</TableHead>
                <TableHead className="text-right">Matched</TableHead>
                <TableHead className="text-right">Wrong</TableHead>
                <TableHead className="text-right">Missed</TableHead>
                <TableHead className="text-right">Precision</TableHead>
                <TableHead className="text-right">Recall</TableHead>
                <TableHead className="text-right">F1</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <PrfRow label="Rows" prf={score.rows} />
              <PrfRow label="Facts, strict" prf={score.facts.strict} />
              <PrfRow label="Facts, normalised" prf={score.facts.normalised} />
              <PrfRow label="Facts, soft (judge)" prf={score.facts.soft} />
            </TableBody>
          </Table>
          {score.matches && (
            <div className="grid gap-4 md:grid-cols-3 text-sm">
              <FactList title="Matched" icon={<CheckCircle2Icon className="text-status-good" />} items={score.matches.matched.map((m) => `${m.fact_id} = ${m.key_fact_id}`)} />
              <FactList title="Wrong" icon={<XCircleIcon className="text-status-critical" />} items={score.matches.wrong} />
              <FactList title="Missed" icon={<CircleSlashIcon className="text-status-serious" />} items={score.matches.missed} />
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Cost</CardTitle>
          <CardDescription>“Without attach” leaves out the baseline's attach step (equal for claim on).</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <Pair label="Steps" value={int(score.cost.steps)} />
            <Pair label="Model calls" value={int(score.cost.model_calls)} />
            <Pair label="Tokens" value={tokens(score.cost.tokens)} />
            <Pair label="Tokens without attach" value={tokens(score.cost.tokens_without_attach)} />
            <Pair label="Time" value={duration(score.cost.seconds)} />
            <Pair label="Time without attach" value={duration(score.cost.seconds_without_attach)} />
            <Pair label="Claim steps" value={int(score.cost.claim_steps)} />
            <Pair label="Tokens of claim steps" value={tokens(score.cost.claim_step_tokens)} />
          </dl>
        </CardContent>
      </Card>
    </div>
  )
}

function Tile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <Card className="gap-1">
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-2xl font-semibold">{value}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground">{note}</p>
      </CardContent>
    </Card>
  )
}

const SEGMENTS = [
  { key: "supports", label: "supported", color: "var(--status-good)", icon: CheckCircle2Icon, tone: "text-status-good" },
  { key: "partial", label: "partial", color: "var(--status-warning)", icon: CircleDotIcon, tone: "text-status-warning" },
  { key: "no", label: "not supported", color: "var(--status-critical)", icon: XCircleIcon, tone: "text-status-critical" },
  { key: "unsourced", label: "unsourced", color: "var(--status-serious)", icon: CircleSlashIcon, tone: "text-status-serious" },
] as const

/** Part-to-whole of the facts by support status: one stacked bar (2 px surface gaps), legend with counts. */
export function SupportBar({ support }: { support: Score["support"] }) {
  const total = support.facts || 1
  return (
    <figure className="space-y-3">
      <div className="flex h-6 w-full gap-0.5 overflow-hidden rounded-sm bg-muted" role="img" aria-label={SEGMENTS.map((s) => `${support[s.key]} ${s.label}`).join(", ")}>
        {SEGMENTS.filter((s) => support[s.key] > 0).map((s) => (
          <div key={s.key} title={`${support[s.key]} ${s.label}`} style={{ width: `${(support[s.key] / total) * 100}%`, background: s.color }} />
        ))}
      </div>
      <figcaption>
        <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
          {SEGMENTS.map(({ key, label, icon: Icon, tone }) => (
            <li key={key} className="flex items-center gap-1.5">
              <Icon className={`size-3.5 ${tone}`} aria-hidden="true" />
              <span className="tabular-nums">{support[key]}</span> {label}
            </li>
          ))}
          <li className="text-muted-foreground">of {support.facts} facts ({support.with_claims} with claims)</li>
        </ul>
      </figcaption>
    </figure>
  )
}

function PrfRow({ label, prf }: { label: string; prf: PRF }) {
  return (
    <TableRow>
      <TableCell>{label}</TableCell>
      <TableCell className="text-right tabular-nums">{prf.tp}</TableCell>
      <TableCell className="text-right tabular-nums">{prf.fp}</TableCell>
      <TableCell className="text-right tabular-nums">{prf.fn}</TableCell>
      <TableCell className="text-right tabular-nums">{num(prf.precision)}</TableCell>
      <TableCell className="text-right tabular-nums">{num(prf.recall)}</TableCell>
      <TableCell className="text-right font-medium tabular-nums">{num(prf.f1)}</TableCell>
    </TableRow>
  )
}

function FactList({ title, icon, items }: { title: string; icon: ReactNode; items: string[] }) {
  return (
    <div className="space-y-1">
      <h3 className="flex items-center gap-1.5 font-medium [&>svg]:size-3.5">{icon}{title} ({items.length})</h3>
      {items.length === 0 ? (
        <p className="text-muted-foreground">none</p>
      ) : (
        <ul className="space-y-0.5 font-mono text-xs">
          {items.map((i) => <li key={i}>{i}</li>)}
        </ul>
      )}
    </div>
  )
}

function Pair({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2 border-b py-1">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium tabular-nums">{value}</dd>
    </div>
  )
}
