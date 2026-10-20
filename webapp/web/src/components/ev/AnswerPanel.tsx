/**
 * answer.json (A4 with C3 and F1): the label from the protocol's decision table, the counts, the flags, and
 * per study the direction with its reason: the treatment and control values the effect rests on, the
 * author's claim and whether it agrees with the data, why a study is undetermined, duplicates. A baseline's
 * answer has its own text, its citations and the passages it retrieved instead; its studies carry only a
 * direction. A study's paper opens on the run's paper view.
 */
import { Link } from "react-router"

import type { EvAnswer, FunnelDoc, Study } from "@/api/ev"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ENGINE, funnelStop } from "@/lib/ev"
import { DASH, num } from "@/lib/format"

import { DirectionBadge, KeyValues, LabelBadge, SystemBadge } from "./bits"

const COUNT_KEYS = ["supporting", "contradicting", "neutral", "undetermined", "duplicates"] as const

function pair(study: Study): string {
  if (!study.treatment || !study.control) return DASH
  return `${num(study.treatment.value ?? null, 3)} vs ${num(study.control.value ?? null, 3)}`
}

export function AnswerSummary({ answer, expected }: { answer: EvAnswer; expected?: string | null }) {
  const counts = (answer.counts ?? {}) as Record<string, number | undefined>
  const flags = Object.entries(answer.flags ?? {}).filter(([, docs]) => docs.length)
  return (
    <Card>
      <CardHeader>
        <CardTitle as="h3" className="flex flex-wrap items-center gap-2 text-base">
          <SystemBadge system={answer.system} />
          <LabelBadge label={answer.label} correct={expected ? expected === answer.label : undefined} />
          {expected && <span className="text-sm font-normal text-muted-foreground">expected <span className="font-mono">{expected}</span></span>}
        </CardTitle>
        {answer.question && <CardDescription>{answer.question}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-3">
        <ul className="flex flex-wrap gap-2" aria-label="Counts">
          {COUNT_KEYS.filter((k) => counts[k] !== undefined).map((k) => (
            <li key={k}><Badge variant="outline" className="font-normal">{k} <span className="ml-1 font-mono tabular-nums">{counts[k]}</span></Badge></li>
          ))}
        </ul>
        {flags.length > 0 && (
          <KeyValues items={flags.map(([flag, docs]) => [flag.replaceAll("_", " "), <span key={flag} className="font-mono text-xs">{docs.join(", ")}</span>])} />
        )}
        {answer.answer_text && <blockquote className="border-l-2 pl-3 text-sm italic">{answer.answer_text}</blockquote>}
      </CardContent>
    </Card>
  )
}

export function StudiesTable({ answer, paperHref, funnel, strategy }: {
  answer: EvAnswer
  paperHref: (doc: string) => string
  funnel?: Record<string, FunnelDoc> | null
  strategy?: string | null
}) {
  const engine = answer.system === ENGINE
  return (
    <div className="overflow-auto rounded-md border">
      <Table aria-label="Studies">
        <TableHeader>
          <TableRow>
            <TableHead className="text-xs">paper</TableHead>
            <TableHead className="text-xs">direction</TableHead>
            {engine && <TableHead className="text-xs">metric</TableHead>}
            {engine && <TableHead className="text-xs">treatment vs control</TableHead>}
            {engine && <TableHead className="text-xs">delta</TableHead>}
            {engine && <TableHead className="text-xs">author claim</TableHead>}
            {engine && <TableHead className="text-xs">reason / flags</TableHead>}
            {funnel && <TableHead className="text-xs">funnel</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {answer.studies.map((s) => (
            <TableRow key={s.document}>
              <TableCell className="font-mono text-xs"><Link to={paperHref(s.document)} className="underline underline-offset-2">{s.document}</Link></TableCell>
              <TableCell><DirectionBadge direction={s.direction} /></TableCell>
              {engine && <TableCell className="font-mono text-xs">{s.metric ?? DASH}</TableCell>}
              {engine && <TableCell className="font-mono text-xs tabular-nums">{pair(s)}</TableCell>}
              {engine && <TableCell className="font-mono text-xs tabular-nums">{num(s.delta ?? null, 3)}</TableCell>}
              {engine && (
                <TableCell className="text-xs">
                  {s.author_claim ? (
                    <span>
                      {String(s.author_claim.direction ?? DASH)}
                      {s.author_claim.agrees_with_data === false && <Badge variant="destructive" className="ml-1">disagrees with the data</Badge>}
                    </span>
                  ) : DASH}
                </TableCell>
              )}
              {engine && (
                <TableCell className="text-xs">
                  {s.reason && <span title={s.reason.code}>{s.reason.text ?? s.reason.code}</span>}
                  {(s.flags ?? []).map((f) => <Badge key={f} variant="outline" className="ml-1">{f.replaceAll("_", " ")}</Badge>)}
                  {s.duplicate_of && <span className="ml-1 text-muted-foreground">of {s.duplicate_of}</span>}
                </TableCell>
              )}
              {funnel && <TableCell className="text-xs">{funnelStop(funnel[s.document], strategy)}</TableCell>}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

/** A baseline's citations and the passages it retrieved (Part G.1): which papers its answer rests on. */
export function BaselineEvidence({ answer, paperHref }: { answer: EvAnswer; paperHref: (doc: string) => string }) {
  const cited = new Set((answer.citations ?? []).map((c) => `${c.document}:${c.start}-${c.end}`))
  return (
    <Card>
      <CardHeader>
        <CardTitle as="h3" className="text-base">Retrieved passages</CardTitle>
        <CardDescription>
          {(answer.retrieved ?? []).length} passages retrieved, {(answer.citations ?? []).length} cited
          {(answer.dropped_citations ?? []).length ? `, ${answer.dropped_citations!.length} citations dropped (no such passage)` : ""}.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Table aria-label="Retrieved passages">
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">paper</TableHead>
              <TableHead className="text-xs">range</TableHead>
              <TableHead className="text-xs">score</TableHead>
              <TableHead className="text-xs">cited</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(answer.retrieved ?? []).map((r) => (
              <TableRow key={`${r.document}:${r.start}`}>
                <TableCell className="font-mono text-xs"><Link to={paperHref(r.document)} className="underline underline-offset-2">{r.document}</Link></TableCell>
                <TableCell className="font-mono text-xs tabular-nums">{r.start}–{r.end}</TableCell>
                <TableCell className="font-mono text-xs tabular-nums">{num(r.score ?? null, 2)}</TableCell>
                <TableCell className="text-xs">{cited.has(`${r.document}:${r.start}-${r.end}`) ? "cited" : ""}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
