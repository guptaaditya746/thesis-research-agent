/**
 * Provenance tab: the five provenance queries of agent/queries.py (row 2.8) as buttons, each
 * with its parameters, and a read-only SPARQL editor over the pyoxigraph store of all runs
 * (scoring/store.py; one named graph per run, scoped to this run by default).
 */
import { PlayIcon } from "lucide-react"
import { useId, useState, type FormEvent, type KeyboardEvent } from "react"

import { useProvQuery, useSparql } from "@/api/hooks"
import type { ProvQueryNumber, ProvQueryParams } from "@/api/types"
import { ResultTable } from "@/components/ResultTable"
import { EmptyState, ErrorState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Kbd } from "@/components/ui/kbd"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"

const QUERIES: { n: ProvQueryNumber; title: string; text: string; params: (keyof ProvQueryParams)[] }[] = [
  { n: 1, title: "Edge → passage", text: "Every graph edge (or one) with its claim, the step that made it and the exact passage.", params: ["edge"] },
  { n: 2, title: "Who produced a fact", text: "The command and the model call behind each claim of a fact (or of one claim).", params: ["fact", "claim"] },
  { n: 3, title: "Claims of a step or agent", text: "All claims made at one step, by one (sub)agent, or both.", params: ["step", "agent"] },
  { n: 4, title: "Broken anchors", text: "Claims whose anchor no longer resolves at its offsets in today's corpus.", params: [] },
  { n: 5, title: "Unsourced facts", text: "Answer facts with no claim behind them.", params: [] },
]

const PLACEHOLDER: Record<keyof ProvQueryParams, string> = {
  edge: "edge-000001", fact: "f1", claim: "claim-000001", step: "3", agent: "main",
}

const DEFAULT_SPARQL = `PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX ours: <urn:thesis-agent:vocab#>

SELECT ?claim_id ?s ?p ?o ?step_id WHERE {
  ?claim a ours:Claim ; ours:claimId ?claim_id ; ours:s ?s ; ours:p ?p ; ours:o ?o ;
         prov:wasGeneratedBy ?step .
  ?step ours:stepId ?step_id .
} ORDER BY ?claim_id
LIMIT 200`

export function ProvenanceTab({ runId }: { runId: string }) {
  return (
    <div className="space-y-6">
      <section className="space-y-3" aria-labelledby="prov-queries">
        <h2 id="prov-queries" className="text-base font-semibold">Provenance queries</h2>
        <div className="grid gap-3 lg:grid-cols-2">
          {QUERIES.map((q) => (
            <QueryCard key={q.n} runId={runId} query={q} />
          ))}
        </div>
      </section>
      <SparqlEditor runId={runId} />
    </div>
  )
}

function QueryCard({ runId, query }: { runId: string; query: (typeof QUERIES)[number] }) {
  const run = useProvQuery(runId)
  const [params, setParams] = useState<ProvQueryParams>({})
  const id = useId()
  const submit = (event: FormEvent) => {
    event.preventDefault()
    const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v && v.trim())) as ProvQueryParams
    run.mutate({ n: query.n, params: clean })
  }
  return (
    <Card className="gap-3">
      <CardHeader>
        <CardTitle className="text-sm">
          {query.n}. {query.title}
        </CardTitle>
        <CardDescription>{query.text}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
          {query.params.map((p) => (
            <div key={p} className="space-y-1">
              <Label htmlFor={`${id}-${p}`} className="text-xs text-muted-foreground">{p}</Label>
              <Input
                id={`${id}-${p}`}
                className="h-8 w-32 font-mono text-xs"
                placeholder={PLACEHOLDER[p]}
                value={params[p] ?? ""}
                onChange={(e) => setParams({ ...params, [p]: e.target.value })}
              />
            </div>
          ))}
          <Button type="submit" size="sm" disabled={run.isPending}>
            {run.isPending ? <Spinner data-icon="inline-start" /> : <PlayIcon data-icon="inline-start" />}
            Run query {query.n}
          </Button>
        </form>
        {run.isError && <ErrorState error={run.error} title={`Query ${query.n} failed`} />}
        {run.data &&
          (run.data.length === 0 ? (
            <p className="text-sm text-muted-foreground" role="status">No rows{query.n === 4 ? ": every anchor still resolves." : query.n === 5 ? ": every fact has a claim." : "."}</p>
          ) : (
            <ResultTable rows={run.data} caption={`Query ${query.n} results`} />
          ))}
      </CardContent>
    </Card>
  )
}

function SparqlEditor({ runId }: { runId: string }) {
  const sparql = useSparql()
  const [query, setQuery] = useState(DEFAULT_SPARQL)
  const [scoped, setScoped] = useState(true)
  const run = () => sparql.mutate({ query, ...(scoped ? { run_id: runId } : {}) })
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      run()
    }
  }
  return (
    <section className="space-y-3" aria-labelledby="prov-sparql">
      <h2 id="prov-sparql" className="text-base font-semibold">SPARQL</h2>
      <p className="text-sm text-muted-foreground">
        Read-only (SELECT, ASK, CONSTRUCT) over every run's graph.ttl, one named graph per run.
      </p>
      <Label htmlFor="sparql-query" className="sr-only">SPARQL query</Label>
      <Textarea
        id="sparql-query"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={onKeyDown}
        rows={10}
        spellCheck={false}
        className="font-mono text-xs"
      />
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={run} disabled={sparql.isPending || !query.trim()}>
          {sparql.isPending ? <Spinner data-icon="inline-start" /> : <PlayIcon data-icon="inline-start" />}
          Run
        </Button>
        <span className="text-xs text-muted-foreground"><Kbd>Ctrl</Kbd> + <Kbd>Enter</Kbd></span>
        <div className="flex items-center gap-2">
          <Switch id="sparql-scope" checked={scoped} onCheckedChange={setScoped} />
          <Label htmlFor="sparql-scope" className="text-sm">Only this run ({runId})</Label>
        </div>
      </div>
      {sparql.isError && <ErrorState error={sparql.error} title="The query failed" />}
      {sparql.data &&
        (sparql.data.rows.length === 0 ? (
          <EmptyState title="No results" description="The query matched nothing." />
        ) : (
          <>
            <p className="text-xs text-muted-foreground" role="status">{sparql.data.rows.length} rows</p>
            <ResultTable rows={sparql.data.rows} columns={sparql.data.vars} caption="SPARQL results" />
          </>
        ))}
    </section>
  )
}
