/**
 * A corpus paper `/corpora/:name/papers/:paper`: the text with every placement of the ground truth marked
 * (where each condition, metric, value and claim is written; the contradictory level's wrong values as
 * decoys), the study it was written from, and its fidelity checks.
 */
import { useMemo, useState } from "react"
import { useParams } from "react-router"

import { useCorpusPaper } from "@/api/ev"
import { DirectionBadge, JsonBlock, KeyValues, QueryPage, RowsTable } from "@/components/ev/bits"
import { MarkLegend, PaperText } from "@/components/ev/PaperText"
import { PageHeader } from "@/components/layout/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { TYPE_COLOR } from "@/lib/ev"

/** A placement role's mark colour: the evidence type it is the ground truth of. */
const ROLE_COLOR: Record<string, string> = {
  condition_label: TYPE_COLOR.condition,
  metric_label: TYPE_COLOR.metric,
  value: TYPE_COLOR.measurement,
  claim: TYPE_COLOR.author_claim,
  decoy: "var(--status-critical)",
}
const ROLE_LABEL: Record<string, string> = { condition_label: "condition", metric_label: "metric", value: "value", claim: "author claim", decoy: "decoy (a wrong value)" }

export default function CorpusPaperPage() {
  const { name = "", paper = "" } = useParams()
  const query = useCorpusPaper(name, paper)
  const [selected, setSelected] = useState<string | null>(null)
  const roles = useMemo(() => {
    const out = new Map<string, string>()
    for (const p of query.data?.placements ?? []) out.set(p.fact, p.role)
    for (const s of query.data?.segments ?? []) for (const m of s.marks ?? []) if (m.startsWith("decoy:")) out.set(m, "decoy")
    return out
  }, [query.data])
  return (
    <QueryPage query={query} what={`paper ${paper} in ${name}`} back={{ to: `/corpora/${encodeURIComponent(name)}`, label: "The corpus" }}>
      {(d) => {
        const study = (d.study ?? {}) as Record<string, unknown>
        const effect = (study.effect ?? {}) as Record<string, unknown>
        const checks = ((d.fidelity?.checks as Record<string, unknown>[] | undefined) ?? [])
        const real = d.paper.relevant === null   // no ground_truth.json: a real paper, no study to show
        return (
          <div className="space-y-6">
            <PageHeader title={<span className="font-mono">{d.paper.id}</span>} description={<>in <span className="font-mono">{d.corpus}</span>{d.paper.level && `, level ${d.paper.level}`}</>}>
              <div className="flex flex-wrap items-center gap-2">
                {real ? null : d.paper.relevant ? <DirectionBadge direction={d.paper.direction} title="the study's true effect" /> : <Badge variant="outline">irrelevant</Badge>}
                {(d.paper.flags ?? []).map((f) => <Badge key={f} variant="outline">{f.replaceAll("_", " ")}</Badge>)}
              </div>
            </PageHeader>
            <div className="grid gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
              <div className="space-y-2">
                <MarkLegend entries={Object.entries(ROLE_COLOR).map(([r, color]) => ({ label: ROLE_LABEL[r], color }))} />
                <PaperText label={`Text of ${d.paper.id}`} segments={d.segments} colorOf={(m) => ROLE_COLOR[roles.get(m) ?? ""] ?? null}
                  selected={selected} onSelect={(marks) => setSelected(marks[0] ?? null)} />
              </div>
              <div className="space-y-4">
                {real ? (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">Paper</CardTitle>
                      <CardDescription>A real paper: no ground truth, so no study or truth label.</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <KeyValues items={[
                        ["title", d.paper.title ?? "—"],
                        ["authors", d.paper.authors?.length ? d.paper.authors.join(", ") : "—"],
                        ["published", d.paper.published?.slice(0, 10) ?? "—"],
                        ["link", d.paper.url ? <a key="u" href={d.paper.url} target="_blank" rel="noreferrer" className="underline">{d.paper.url}</a> : "—"],
                        ["text from", d.paper.route ?? "—"],
                      ]} />
                    </CardContent>
                  </Card>
                ) : <Card>
                  <CardHeader><CardTitle className="text-base">Study (ground truth)</CardTitle></CardHeader>
                  <CardContent className="space-y-3">
                    <KeyValues items={[
                      ["effect", effect.direction ? `${String(effect.direction)}${effect.delta !== null && effect.delta !== undefined ? `, delta ${String(effect.delta)}` : ""}` : "—"],
                      ["missing", String(study.missing ?? "none")],
                      ["duplicate of", String(study.duplicate_of ?? "—")],
                      ["author claim", String((study.author_claim as Record<string, unknown> | null)?.direction ?? "—")],
                    ]} />
                    {Array.isArray(study.conditions) && study.conditions.length > 0 && (
                      <RowsTable caption="Conditions" rows={study.conditions as Record<string, unknown>[]} columns={["id", "role", "label"]} />
                    )}
                    {Array.isArray(study.measurements) && study.measurements.length > 0 && (
                      <RowsTable caption="Measurements" rows={study.measurements as Record<string, unknown>[]} columns={["id", "condition", "metric", "value", "dataset"]}
                        render={(c, v) => c === "id" ? <button type="button" className="font-mono underline decoration-dotted underline-offset-2 hover:decoration-solid" onClick={() => setSelected(String(v))}>{String(v)}</button> : String(v ?? "—")} />
                    )}
                  </CardContent>
                </Card>}
                {!real && <Card>
                  <CardHeader><CardTitle className="text-base">Fidelity checks</CardTitle></CardHeader>
                  <CardContent>
                    {checks.length ? <RowsTable caption="Fidelity checks" rows={checks} columns={["name", "ok", "detail"]} /> : <p className="text-sm text-muted-foreground">None recorded.</p>}
                  </CardContent>
                </Card>}
                <details><summary className="cursor-pointer text-sm">Placements ({d.placements.length})</summary><JsonBlock value={d.placements} className="mt-1" /></details>
              </div>
            </div>
          </div>
        )
      }}
    </QueryPage>
  )
}
