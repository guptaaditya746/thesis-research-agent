/**
 * Score tab: score.json against the answer key (docs/earlier-work.md, Scoring): the support of the answer's
 * facts (the primary outcome), the facts matched, missed and extra (with those reviewers
 * rejected as wrong) at the three matching levels, rows, vital recall, and the cost with and
 * without the attach step.
 */
import { CheckCircle2Icon, CircleDotIcon, CircleSlashIcon, GaugeIcon, HourglassIcon, PlusCircleIcon, XCircleIcon } from "lucide-react"
import type { ReactNode } from "react"

import { useGoldKey, useScore } from "@/api/hooks"
import type { Answer, AnswerKey, FactScores, FactTriple, KeyRow, Score, ScoreSupport } from "@/api/types"
import { ProvisionalBadge, StatusBadge } from "@/components/badges"
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { supportNote, term } from "@/lib/facts"
import { dateTime, duration, int, num, pct, tokens } from "@/lib/format"

export function ScoreTab({ runId, answer = null }: { runId: string; answer?: Answer | null }) {
  const score = useScore(runId)
  const key = useGoldKey(score.data?.qid ?? null)
  if (score.isPending) return <TableSkeleton rows={6} columns={6} />
  if (score.isError) return <ErrorState error={score.error} onRetry={() => void score.refetch()} />
  if (!score.data) {
    return (
      <EmptyState
        icon={<GaugeIcon />}
        title="Not scored yet"
        description="score.json appears when `score run` has compared the answer with the question's answer key (the reviewed key, or the draft before review)."
      />
    )
  }
  return <ScoreView score={score.data} answer={answer} answerKey={key.data ?? null} />
}

const spo = (t: FactTriple) => `(${term(t.s)}, ${term(t.p)}, ${term(t.o)})`

/** Facts of an answer or key by `row/fact`, for the matched pairs' triples. */
function triples(rows: { id: string; facts?: { id: string; s: unknown; p: unknown; o: unknown }[] }[] | null | undefined): Map<string, FactTriple> {
  const map = new Map<string, FactTriple>()
  for (const row of rows ?? []) for (const f of row.facts ?? []) map.set(`${row.id}/${f.id}`, { s: f.s, p: f.p, o: f.o })
  return map
}
export function ScoreView({ score, answer = null, answerKey = null }: { score: Score; answer?: Answer | null; answerKey?: AnswerKey | null }) {
  const s = score.support ?? {}
  // the key is the one scored against only if its version is the score's
  const keyRows = answerKey && answerKey.version === score.key_version ? (answerKey.rows as unknown as KeyRow[]) : null
  const runFacts = triples(answer?.rows)
  const keyFacts = triples(keyRows)
  const soft = score.facts?.soft ?? {}
  const pairs = score.detail?.facts?.pairs ?? []
  const missed = score.detail?.facts?.missed ?? []
  const extra = score.detail?.facts?.extra ?? []
  const pendingVerdicts = (score.pending?.support ?? 0) + (score.pending?.same_fact ?? 0) + (score.pending?.same_row ?? 0)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        key <Badge variant="outline" className="font-mono">{score.key_version ?? "?"}</Badge>
        {score.provisional && <ProvisionalBadge />}
        {score.verify_ok === false && <Badge variant="destructive">verify failed: scored anyway</Badge>}
        {pendingVerdicts > 0 && (
          <StatusBadge tone="warning" icon={<HourglassIcon />} title="judge decisions that could not be made yet; `score batch` asks again">
            {pendingVerdicts} judge decisions pending
          </StatusBadge>
        )}
        {score.scored_at && <span>scored {dateTime(score.scored_at)}</span>}
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Tile label="Support share" value={pct(s.support_share)} note={supportNote(s)} />
        <Tile label="Fact F1 (soft)" value={num(soft.f1)} note={`precision ${num(soft.precision)} · recall ${num(soft.recall)}`} />
        <Tile label="Row F1" value={num(score.rows?.f1)} note={`${int(score.rows?.tp)} matched of ${int((score.rows?.tp ?? 0) + (score.rows?.fn ?? 0))} key rows`} />
        <Tile label="Vital recall" value={pct(score.vital_recall)} note="key facts marked vital that the answer has" />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Support of the answer's facts</CardTitle>
          <CardDescription>
            The judge's verdict on each fact's quotes (the best one counts); unsourced facts cite no accepted claim.
            {s.partial_counts_as ? ` By the judge's calibration, partial counts as ${s.partial_counts_as === "yes" ? "supported" : "not supported"}.` : ""}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <SupportBar support={s} />
          <p className="text-xs text-muted-foreground">
            Sensitivity: partial the other way {pct(s.partial_counts_as === "yes" ? s.support_share_partial_no : s.support_share_partial_yes)} · first claim only {pct(s.support_share_first_claim)} · unsourced share {pct(s.unsourced_share)}
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Against the key</CardTitle>
          <CardDescription>
            Matched: in the answer and the key (one to one), the run's fact ≈ the key's at the level it matched; extra: in the answer
            only; missed: in the key only.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Unit</TableHead>
                <TableHead className="text-right">Matched</TableHead>
                <TableHead className="text-right">Extra</TableHead>
                <TableHead className="text-right">Missed</TableHead>
                <TableHead className="text-right">Precision</TableHead>
                <TableHead className="text-right">Recall</TableHead>
                <TableHead className="text-right">F1</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <PrfRow label="Rows (soft)" prf={score.rows} />
              <PrfRow label="Rows, normalised" prf={score.rows_by_level?.normalised} />
              <PrfRow label="Facts, strict" prf={score.facts?.strict} />
              <PrfRow label="Facts, normalised" prf={score.facts?.normalised} />
              <PrfRow label="Facts, soft (judge)" prf={score.facts?.soft} />
            </TableBody>
          </Table>
          {score.judged_precision?.precision != null && (
            <p className="text-sm text-muted-foreground">
              Judged precision {num(score.judged_precision.precision)}: {int(score.judged_precision.correct)} correct, {int(score.judged_precision.wrong)} rejected by reviewers ({pct(score.judged_precision.coverage, 0)} of the facts judged).
            </p>
          )}
          {score.detail?.facts && (
            <div className="grid gap-4 text-sm md:grid-cols-3">
              <FactList
                title="Matched"
                icon={<CheckCircle2Icon className="text-status-good" />}
                items={pairs.map((p) => {
                  const run = runFacts.get(`${p.run.row}/${p.run.fact}`)
                  const key = keyFacts.get(`${p.key.row}/${p.key.fact}`)
                  return {
                    key: `${p.run.row}/${p.run.fact}`,
                    text: run && key ? `${spo(run)} ≈ ${spo(key)}` : `${p.run.fact} = ${p.key.fact}`,
                    note: `${run && key ? `${p.run.fact} = ${p.key.fact} · ` : ""}${p.level}${p.vital ? " · vital" : ""}`,
                  }
                })}
              />
              <FactList
                title="Extra"
                icon={<PlusCircleIcon className="text-status-serious" />}
                items={extra.map((e) => ({ key: `${e.run.row}/${e.run.fact}`, text: `${e.run.fact} ${spo(e.spo)}`, note: e.wrong ? "rejected by reviewers: wrong" : "not in the key" }))}
              />
              <FactList
                title="Missed"
                icon={<CircleSlashIcon className="text-status-critical" />}
                items={missed.map((m) => ({ key: `${m.key.row}/${m.key.fact}`, text: `${m.key.fact} ${spo(m.spo)}`, note: m.vital ? "vital" : undefined }))}
              />
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Cost</CardTitle>
          <CardDescription>“Without attach” leaves out the baseline's attach step (equal for claim on). Time is active time.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <Pair label="Steps" value={int(score.cost?.steps)} />
            <Pair label="Model calls" value={int(score.cost?.model_calls)} />
            <Pair label="Tokens" value={tokens(score.cost?.tokens)} />
            <Pair label="Tokens without attach" value={tokens(score.cost?.tokens_without_attach)} />
            <Pair label="Time" value={duration(score.cost?.seconds)} />
            <Pair label="Time without attach" value={duration(score.cost?.seconds_without_attach)} />
            <Pair label="Claim steps" value={int(score.cost?.claim_steps)} />
            <Pair label="Tokens of claim steps" value={tokens(score.cost?.claim_step_tokens)} />
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
        <CardTitle className="text-2xl font-semibold tabular-nums">{value}</CardTitle>
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
  { key: "pending", label: "pending", color: "var(--status-neutral)", icon: HourglassIcon, tone: "text-muted-foreground" },
] as const

/** Part-to-whole of the facts by support status: one stacked bar (2 px surface gaps), legend with counts. */
export function SupportBar({ support }: { support: ScoreSupport }) {
  const count = (k: (typeof SEGMENTS)[number]["key"]) => support[k] ?? 0
  const total = support.facts || 1
  const shown = SEGMENTS.filter((s) => s.key !== "pending" || count(s.key) > 0)
  return (
    <figure className="space-y-3">
      <div className="flex h-6 w-full gap-0.5 overflow-hidden rounded-sm bg-muted" role="img" aria-label={shown.map((s) => `${count(s.key)} ${s.label}`).join(", ")}>
        {shown.filter((s) => count(s.key) > 0).map((s) => (
          <div key={s.key} title={`${count(s.key)} ${s.label}`} style={{ width: `${(count(s.key) / total) * 100}%`, background: s.color }} />
        ))}
      </div>
      <figcaption>
        <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
          {shown.map(({ key, label, icon: Icon, tone }) => (
            <li key={key} className="flex items-center gap-1.5">
              <Icon className={`size-3.5 ${tone}`} aria-hidden="true" />
              <span className="tabular-nums">{count(key)}</span> {label}
            </li>
          ))}
          <li className="text-muted-foreground">of {int(support.facts)} facts ({int(support.with_claims)} with claims)</li>
        </ul>
      </figcaption>
    </figure>
  )
}

function PrfRow({ label, prf }: { label: string; prf: FactScores | null | undefined }) {
  if (!prf) return null
  return (
    <TableRow>
      <TableCell>{label}</TableCell>
      <TableCell className="text-right tabular-nums">{int(prf.tp)}</TableCell>
      <TableCell className="text-right tabular-nums">{int(prf.fp)}</TableCell>
      <TableCell className="text-right tabular-nums">{int(prf.fn)}</TableCell>
      <TableCell className="text-right tabular-nums">{num(prf.precision)}</TableCell>
      <TableCell className="text-right tabular-nums">{num(prf.recall)}</TableCell>
      <TableCell className="text-right font-medium tabular-nums">{num(prf.f1)}</TableCell>
    </TableRow>
  )
}

function FactList({ title, icon, items }: { title: string; icon: ReactNode; items: { key: string; text: string; note?: string }[] }) {
  return (
    <section className="min-w-0 space-y-1" aria-label={`${title} facts`}>
      <h3 className="flex items-center gap-1.5 font-medium [&>svg]:size-3.5">{icon}{title} ({items.length})</h3>
      {items.length === 0 ? (
        <p className="text-muted-foreground">none</p>
      ) : (
        <ul className="space-y-1 text-xs">
          {items.map((i) => (
            <li key={i.key}>
              <span className="font-mono break-words">{i.text}</span>
              {i.note && <span className="text-muted-foreground"> · {i.note}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
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
