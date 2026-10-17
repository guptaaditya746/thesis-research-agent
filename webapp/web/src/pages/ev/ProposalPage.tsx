/**
 * A proposal `/proposals/:name` (evidence propose, Part E; our design): the frame (population, treatment,
 * control, outcomes; each name's source, ontology or invented, by the code's lookup in the vocabulary), the
 * draft's sources, the critic's checks, the eight choice-point cards with the model's default, its rationale
 * and the decision taken (who decided, why), the frozen protocol with its hash and revision, and the
 * amendments log. Read-only: decisions are made in decisions.yaml and the steps run on the command line.
 */
import { CheckCircle2Icon, CircleDashedIcon, OctagonXIcon } from "lucide-react"
import { useParams } from "react-router"

import { useProposal, type Card as CardT } from "@/api/ev"
import { StatusBadge } from "@/components/badges"
import { JsonBlock, KeyValues, QueryPage, RowsTable } from "@/components/ev/bits"
import { ProtocolPanel } from "@/components/ev/ProtocolPanel"
import { PageHeader } from "@/components/layout/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const STEPS = ["frame", "draft", "critic", "cards", "freeze"]
type Named = { term?: string; label?: string; source?: string; vocab_id?: string | null }

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

function Frame({ frame }: { frame: Record<string, unknown> }) {
  const population = (frame.population ?? {}) as Record<string, unknown>
  const side = (key: "treatment" | "control") => (frame[key] ?? {}) as Record<string, unknown> & Named
  const outcomes = (frame.outcomes ?? []) as (Record<string, unknown> & Named)[]
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader><CardTitle className="text-base">Population and screen</CardTitle><CardDescription>{String(population.description ?? "")}</CardDescription></CardHeader>
        <CardContent><KeyValues items={[["screening question", String(population.screening_question ?? "—")], ["screen terms", <Names key="t" items={population.terms as Named[]} />]]} /></CardContent>
      </Card>
      {(["treatment", "control"] as const).map((k) => {
        const s = side(k)
        return (
          <Card key={k}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">{k}: <span className="font-mono">{String(s.role)}</span> <Source source={s.source} id={s.vocab_id} /></CardTitle>
              <CardDescription>{String(s.label ?? "")}: {String(s.definition ?? "")}</CardDescription>
            </CardHeader>
            <CardContent><KeyValues items={[["synonyms", <Names key="s" items={s.synonyms as Named[]} />], ["vocabulary synonyms", ((s.vocab_synonyms as string[] | undefined) ?? []).join(", ") || "—"]]} /></CardContent>
          </Card>
        )
      })}
      <Card>
        <CardHeader><CardTitle className="text-base">Outcomes</CardTitle></CardHeader>
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

function CardView({ card }: { card: CardT }) {
  const d = card.decision
  const changed = d && d.choice !== (d.default ?? card.default)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          {card.title ?? card.id}
          {d ? (
            <Badge variant={d.by === "model" ? "outline" : "secondary"}>decided by {d.by}</Badge>
          ) : <Badge variant="outline">undecided</Badge>}
          {changed && <Badge>changed from the default</Badge>}
          {card.problems.length > 0 && <Badge variant="destructive">freeze would refuse</Badge>}
        </CardTitle>
        <CardDescription>{card.ask}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {card.problems.length > 0 && (
          <ul className="space-y-0.5 text-xs text-destructive" aria-label={`Problems of ${card.id}`}>
            {card.problems.map((p) => <li key={p}>{p}</li>)}
          </ul>
        )}
        {card.raw_decision !== null && card.raw_decision !== undefined && (
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">decisions.yaml has, not in a decision's shape:</p>
            <JsonBlock value={card.raw_decision} className="max-h-32" label={`raw decision of ${card.id}`} />
          </div>
        )}
        <KeyValues items={[
          ["sets", <span key="s" className="font-mono text-xs">{(card.sets ?? []).join(", ")}</span>],
          ["model's default", <span key="d"><span className="font-mono">{card.default}</span>{card.rationale ? `: ${card.rationale}` : ""}</span>],
          ["decision", d ? <span key="c"><span className="font-mono">{d.choice}</span>{d.reason ? `, because ${d.reason}` : ""}</span> : "—"],
        ]} />
        <ul className="space-y-1">
          {(card.options ?? []).map((o, i) => {
            const id = String(o.id)
            return (
              <li key={i} className={`rounded border p-2 text-xs ${d?.choice === id ? "border-foreground" : ""}`}>
                <span className="font-mono font-medium">{id}</span> {String(o.summary ?? "")}
                {d?.choice === id && <span className="ml-1 text-muted-foreground">(chosen)</span>}
                <details><summary className="cursor-pointer text-muted-foreground">value</summary><JsonBlock value={o.value} className="mt-1 max-h-48" /></details>
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}

export default function ProposalPage() {
  const { name = "" } = useParams()
  const proposal = useProposal(name)
  return (
    <QueryPage query={proposal} what={`proposal ${name}`} back={{ to: "/protocol", label: "All protocols" }}>
      {(p) => (
        <div className="space-y-6">
          <PageHeader title={<span className="font-mono">{p.name}</span>} description={p.question}>
            <ol className="flex flex-wrap items-center gap-2" aria-label="Steps">
              {STEPS.map((s) => (
                <li key={s}>
                  {p.steps.includes(s)
                    ? <StatusBadge tone="good" icon={<CheckCircle2Icon />}>{s}</StatusBadge>
                    : <StatusBadge tone="neutral" icon={<CircleDashedIcon />}>{s}</StatusBadge>}
                </li>
              ))}
              {p.frozen && <li className="text-sm text-muted-foreground">revision {p.revision} · <span className="font-mono text-xs">{p.protocol_sha256?.slice(0, 16)}</span></li>}
            </ol>
          </PageHeader>
          <Tabs defaultValue="cards">
            <TabsList className="flex-wrap">
              <TabsTrigger value="frame">Frame</TabsTrigger>
              <TabsTrigger value="critic">Critic</TabsTrigger>
              <TabsTrigger value="cards">Cards and decisions</TabsTrigger>
              <TabsTrigger value="protocol">Frozen protocol</TabsTrigger>
              <TabsTrigger value="amendments">Amendments</TabsTrigger>
              <TabsTrigger value="sources">Draft sources</TabsTrigger>
            </TabsList>
            <TabsContent value="frame">{p.frame ? <Frame frame={p.frame} /> : <p className="text-sm text-muted-foreground">No frame.json.</p>}</TabsContent>
            <TabsContent value="critic" className="space-y-2">
              {p.checks.length ? (
                <ul className="space-y-1">
                  {p.checks.map((c) => (
                    <li key={c.id} className="flex items-start gap-2 text-sm">
                      {c.ok ? <StatusBadge tone="good" icon={<CheckCircle2Icon />}>ok</StatusBadge> : <StatusBadge tone="critical" icon={<OctagonXIcon />}>fails</StatusBadge>}
                      <span className="font-mono text-xs">{c.id}</span>
                      <Badge variant="outline" className="font-normal">{c.kind ?? "llm"}</Badge>
                      <span className="text-muted-foreground">{c.message}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-muted-foreground">No critic.json yet.</p>}
              <p className="text-xs text-muted-foreground">Only the deterministic checks decide whether the draft is ok; the model's checklist is advice.</p>
            </TabsContent>
            <TabsContent value="cards">
              {p.decision_problems.length > 0 && (
                <div role="status" className="mb-3 rounded-md border border-destructive/50 p-3 text-sm">
                  <p className="font-medium">decisions.yaml: freeze would refuse it</p>
                  <ul className="mt-1 list-disc pl-5 text-xs">{p.decision_problems.map((x) => <li key={x}>{x}</li>)}</ul>
                </div>
              )}
              {p.decided_by && Object.keys(p.decided_by).length > 0 && (
                <p className="mb-3 text-sm text-muted-foreground">
                  Decided by {Object.entries(p.decided_by).map(([who, cards]) => `${who} (${cards.length})`).join(", ")}.
                </p>
              )}
              <div className="grid gap-4 xl:grid-cols-2">{p.cards.map((c) => <CardView key={c.id} card={c} />)}</div>
            </TabsContent>
            <TabsContent value="protocol">
              {p.protocol ? <ProtocolPanel view={p.protocol} /> : <p className="text-sm text-muted-foreground">Not frozen yet (`evidence propose freeze`).</p>}
              {p.revisions.length > 0 && <p className="mt-2 text-xs text-muted-foreground">Revisions kept: {p.revisions.map((r) => `protocol.v${r}.yaml`).join(", ")}.</p>}
            </TabsContent>
            <TabsContent value="amendments">
              {p.amendment_log.length ? (
                <RowsTable caption="Amendments" rows={p.amendment_log as Record<string, unknown>[]} columns={["revision", "reason", "impact", "before_main_run", "at", "sha256", "amends_sha256"]}
                  render={(c, v) => (c.endsWith("sha256") ? <span className="font-mono">{String(v ?? "").slice(0, 12)}</span> : Array.isArray(v) ? v.join(", ") : typeof v === "boolean" ? (v ? "yes" : "no") : String(v ?? "—"))} />
              ) : <p className="text-sm text-muted-foreground">No amendments.</p>}
            </TabsContent>
            <TabsContent value="sources">
              {p.sources ? (
                <div className="space-y-3">
                  <RowsTable caption="Field sources" rows={(p.sources.fields as Record<string, unknown>[] | undefined) ?? []} columns={["path", "source", "vocab_id"]} />
                  <RowsTable caption="Term sources" rows={(p.sources.terms as Record<string, unknown>[] | undefined) ?? []} columns={["path", "term", "source", "vocab_id"]} />
                </div>
              ) : <p className="text-sm text-muted-foreground">No draft yet.</p>}
            </TabsContent>
          </Tabs>
        </div>
      )}
    </QueryPage>
  )
}
