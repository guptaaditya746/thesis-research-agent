/**
 * Parts of a proposal (evidence propose, Part E) shown on the proposal page and in the flow's protocol step:
 * the steps done, the frame (each name's source, ontology or invented) and the critic's checks.
 */
import { CheckCircle2Icon, CircleDashedIcon, OctagonXIcon } from "lucide-react"

import type { Check } from "@/api/ev"
import { StatusBadge } from "@/components/badges"
import { KeyValues } from "@/components/ev/bits"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

const PROPOSAL_STEPS = ["frame", "draft", "critic", "cards", "freeze"]
type Named = { term?: string; label?: string; source?: string; vocab_id?: string | null }

export function ProposalSteps({ steps }: { steps: string[] }) {
  return (
    <ol className="flex flex-wrap items-center gap-2" aria-label="Proposal steps">
      {PROPOSAL_STEPS.map((s) => (
        <li key={s}>
          {steps.includes(s)
            ? <StatusBadge tone="good" icon={<CheckCircle2Icon />}>{s}<span className="sr-only"> (done)</span></StatusBadge>
            : <StatusBadge tone="neutral" icon={<CircleDashedIcon />}>{s}<span className="sr-only"> (pending)</span></StatusBadge>}
        </li>
      ))}
    </ol>
  )
}

function Source({ source, id }: { source?: string; id?: string | null }) {
  if (!source) return null
  return <Badge variant={source === "ontology" ? "secondary" : "outline"} className="font-normal" title={id ?? undefined}>{source}</Badge>
}

function Names({ items }: { items: Named[] | undefined }) {
  return (
    <ul className="flex flex-wrap gap-1.5">
      {(items ?? []).map((t, i) => (
        <li key={i} className="flex items-center gap-1 text-xs"><span className="font-mono">{t.term ?? t.label}</span><Source source={t.source} id={t.vocab_id} /></li>
      ))}
    </ul>
  )
}

export function Frame({ frame }: { frame: Record<string, unknown> }) {
  const population = (frame.population ?? {}) as Record<string, unknown>
  const side = (key: "treatment" | "control") => (frame[key] ?? {}) as Record<string, unknown> & Named
  const outcomes = (frame.outcomes ?? []) as (Record<string, unknown> & Named)[]
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader><CardTitle as="h3" className="text-base">Population and screen</CardTitle><CardDescription>{String(population.description ?? "")}</CardDescription></CardHeader>
        <CardContent><KeyValues items={[["screening question", String(population.screening_question ?? "—")], ["screen terms", <Names key="t" items={population.terms as Named[]} />]]} /></CardContent>
      </Card>
      {(["treatment", "control"] as const).map((k) => {
        const s = side(k)
        return (
          <Card key={k}>
            <CardHeader>
              <CardTitle as="h3" className="flex items-center gap-2 text-base">{k}: <span className="font-mono">{String(s.role)}</span> <Source source={s.source} id={s.vocab_id} /></CardTitle>
              <CardDescription>{String(s.label ?? "")}: {String(s.definition ?? "")}</CardDescription>
            </CardHeader>
            <CardContent><KeyValues items={[["synonyms", <Names key="s" items={s.synonyms as Named[]} />], ["vocabulary synonyms", ((s.vocab_synonyms as string[] | undefined) ?? []).join(", ") || "—"]]} /></CardContent>
          </Card>
        )
      })}
      <Card>
        <CardHeader><CardTitle as="h3" className="text-base">Outcomes</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {outcomes.map((o) => (
            <div key={String(o.canonical)} className="space-y-1 text-sm">
              <div className="flex items-center gap-2"><span className="font-mono">{String(o.canonical)}</span> <Source source={o.source} id={o.vocab_id} />
                <span className="text-xs text-muted-foreground">{o.higher_is_better ? "higher is better" : "lower is better"}{o.fraction ? ", a fraction" : ""}</span></div>
              <Names items={o.synonyms as Named[]} />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

export function CriticChecks({ checks }: { checks: Check[] }) {
  if (!checks.length) return <p className="text-sm text-muted-foreground">No critic.json yet.</p>
  return (
    <div className="space-y-2">
      <ul className="space-y-1" aria-label="Critic checks">
        {checks.map((c) => (
          <li key={c.id} className="flex items-start gap-2 text-sm">
            {c.ok ? <StatusBadge tone="good" icon={<CheckCircle2Icon />}>ok</StatusBadge> : <StatusBadge tone="critical" icon={<OctagonXIcon />}>fails</StatusBadge>}
            <span className="font-mono text-xs">{c.id}</span>
            <Badge variant="outline" className="font-normal">{c.kind ?? "llm"}</Badge>
            <span className="text-muted-foreground">{c.message}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">Only the deterministic checks decide whether the draft is ok; the model's checklist is advice.</p>
    </div>
  )
}
