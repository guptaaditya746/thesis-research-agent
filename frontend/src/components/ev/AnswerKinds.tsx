/**
 * The answer of a question kind other than effect (evidence/kinds/*.py): an inventory as a table of names, a
 * consistency answer as agree / disagree per paper, a best answer as the wins per kind and the winner per paper.
 * A paper's name opens the run's paper view.
 */
import type { ReactNode } from "react"
import { Link } from "react-router"

import type { BestAnswer, ConsistencyAnswer, InventoryAnswer } from "@/api/ev"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { KindAnswer } from "@/lib/ev"
import { DASH, num } from "@/lib/format"

import { DirectionBadge, SystemBadge } from "./bits"

type Href = (doc: string) => string

function PaperChips({ papers, paperHref }: { papers: string[]; paperHref: Href }) {
  return (
    <ul className="flex flex-wrap gap-1">
      {papers.map((p) => (
        <li key={p}><Link to={paperHref(p)} className="rounded-md border px-1.5 py-0.5 font-mono text-xs hover:bg-muted">{p}</Link></li>
      ))}
    </ul>
  )
}

function KindCard({ answer, title, children }: { answer: KindAnswer; title: string; children?: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle as="h3" className="flex flex-wrap items-center gap-2 text-base">
          <SystemBadge system={answer.system} />
          <span>{title}</span>
        </CardTitle>
      </CardHeader>
      {children && <CardContent className="space-y-3">{children}</CardContent>}
    </Card>
  )
}

const reasonText = (r: { code: string; text?: string | null } | null | undefined) => (r ? (r.text ?? r.code) : DASH)

export function InventoryPanel({ answer, paperHref }: { answer: InventoryAnswer; paperHref: Href }) {
  return (
    <div className="space-y-4">
      <KindCard answer={answer} title={`${answer.entries.length} distinct ${answer.target ?? "item"} names`} />
      <div className="overflow-auto rounded-md border">
        <Table aria-label="Inventory">
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">name</TableHead>
              <TableHead className="text-xs">other names</TableHead>
              <TableHead className="text-xs">papers</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {answer.entries.map((e, n) => (
              <TableRow key={`${e.name}-${n}`}>
                <TableCell className="text-sm font-medium">{e.name}</TableCell>
                <TableCell className="text-xs">{e.aliases.length ? e.aliases.join(", ") : DASH}</TableCell>
                <TableCell><PaperChips papers={e.papers} paperHref={paperHref} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

export function ConsistencyPanel({ answer, paperHref }: { answer: ConsistencyAnswer; paperHref: Href }) {
  const counts = [["agreeing", answer.agreeing], ["disagreeing", answer.disagreeing], ["undetermined", answer.undetermined]] as const
  return (
    <div className="space-y-4">
      <KindCard answer={answer} title="Do the authors' claims agree with their results?">
        <ul className="flex flex-wrap gap-2" aria-label="Counts">
          {counts.map(([k, docs]) => (
            <li key={k}><Badge variant="outline" className="font-normal">{k} <span className="ml-1 font-mono tabular-nums">{docs.length}</span></Badge></li>
          ))}
        </ul>
      </KindCard>
      <div className="overflow-auto rounded-md border">
        <Table aria-label="Claims against data">
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">paper</TableHead>
              <TableHead className="text-xs">author claim</TableHead>
              <TableHead className="text-xs">data show</TableHead>
              <TableHead className="text-xs">verdict</TableHead>
              <TableHead className="text-xs">reason</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {answer.studies.map((s) => (
              <TableRow key={s.document}>
                <TableCell className="font-mono text-xs"><Link to={paperHref(s.document)} className="underline underline-offset-2">{s.document}</Link></TableCell>
                <TableCell><DirectionBadge direction={s.claim} /></TableCell>
                <TableCell><DirectionBadge direction={s.direction} /></TableCell>
                <TableCell className="text-xs">
                  {s.agrees === true ? <Badge>agrees</Badge> : s.agrees === false ? <Badge variant="destructive">disagrees</Badge> : <Badge variant="outline">undetermined</Badge>}
                </TableCell>
                <TableCell className="text-xs">{reasonText(s.reason)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

export function BestPanel({ answer, paperHref }: { answer: BestAnswer; paperHref: Href }) {
  const wins = Object.entries(answer.wins)
  const kinds = [...new Set(answer.studies.flatMap((s) => Object.keys(s.values)))]
  return (
    <div className="space-y-4">
      <KindCard answer={answer} title="Which method kind is best?">
        <p className="text-sm">
          Winner: {answer.winner ? <Badge>{answer.winner}</Badge> : answer.tied.length ? <span>none, tied: {answer.tied.join(", ")}</span> : <span>none</span>}
          {answer.metric && <span className="ml-2 text-muted-foreground">on <span className="font-mono">{answer.metric}</span></span>}
        </p>
        <Table aria-label="Wins per kind">
          <TableHeader>
            <TableRow><TableHead className="text-xs">kind</TableHead><TableHead className="text-xs">papers won</TableHead></TableRow>
          </TableHeader>
          <TableBody>
            {wins.length === 0 && <TableRow><TableCell colSpan={2} className="text-xs text-muted-foreground">no paper has a winner</TableCell></TableRow>}
            {wins.map(([kind, n]) => (
              <TableRow key={kind}><TableCell className="text-sm">{kind}</TableCell><TableCell className="font-mono text-xs tabular-nums">{n}</TableCell></TableRow>
            ))}
          </TableBody>
        </Table>
      </KindCard>
      <div className="overflow-auto rounded-md border">
        <Table aria-label="Winner per paper">
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">paper</TableHead>
              <TableHead className="text-xs">winner</TableHead>
              {kinds.map((k) => <TableHead key={k} className="text-xs">{k}</TableHead>)}
              <TableHead className="text-xs">reason</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {answer.studies.map((s) => (
              <TableRow key={s.document}>
                <TableCell className="font-mono text-xs"><Link to={paperHref(s.document)} className="underline underline-offset-2">{s.document}</Link></TableCell>
                <TableCell className="text-xs">
                  {s.winner ? <Badge data-winner>{s.winner}</Badge> : s.tied.length ? <span>tie: {s.tied.join(", ")}</span> : DASH}
                </TableCell>
                {kinds.map((k) => <TableCell key={k} className="font-mono text-xs tabular-nums">{num(s.values[k] ?? null, 3)}</TableCell>)}
                <TableCell className="text-xs">{reasonText(s.reason)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
