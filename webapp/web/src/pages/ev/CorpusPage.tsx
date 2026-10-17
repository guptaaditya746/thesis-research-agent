/**
 * Corpus `/corpora/:name`: how it was built (generator, renderer, seed, level, the knobs, the protocol it
 * takes its rules from), the answer it is built to have, a variant's prediction (variant.json: the changed
 * study, the measurements changed, the label before and after), every paper with its true direction and
 * flags, and the runs made on it.
 */
import { Link, useParams } from "react-router"

import { useCorpus, useEvRuns } from "@/api/ev"
import { DirectionBadge, JsonBlock, KeyValues, LabelBadge, QueryPage, SystemBadge } from "@/components/ev/bits"
import { PageHeader } from "@/components/layout/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { knobText } from "@/lib/ev"
import { num } from "@/lib/format"

export default function CorpusPage() {
  const { name = "" } = useParams()
  const corpus = useCorpus(name)
  const runs = useEvRuns()
  return (
    <QueryPage query={corpus} what={`corpus ${name}`} back={{ to: "/corpora", label: "All corpora" }}>
      {(c) => {
        const on = (runs.data ?? []).filter((r) => r.corpus === c.name)
        const expected = (c.variant?.expected ?? {}) as { before?: { label?: string }; after?: { label?: string } }
        return (
          <div className="space-y-6">
            <PageHeader title={<span className="font-mono">{c.name}</span>} description={c.question}>
              <div className="flex flex-wrap gap-2">
                <Badge variant="secondary">{c.level}</Badge>
                <Badge variant="outline">{c.renderer} renderer</Badge>
                <span className="text-sm text-muted-foreground">expected label</span> <LabelBadge label={c.answer?.label} />
              </div>
            </PageHeader>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader><CardTitle className="text-base">Build</CardTitle></CardHeader>
                <CardContent>
                  <KeyValues items={[
                    ["corpus id", <span key="i" className="font-mono text-xs">{c.corpus_id}</span>],
                    ["seed", String(c.seed ?? "—")],
                    ["studies asked", String(c.settings?.studies ?? "—")],
                    ["levels", ((c.settings?.levels as string[] | undefined) ?? []).join(", ") || "—"],
                    ["knobs", knobText(c.settings)],
                    ["papers", `${c.papers}${c.fidelity_ok !== null && c.fidelity_ok !== undefined ? `, ${c.fidelity_ok} pass every fidelity check` : ""}`],
                    ["excluded studies", c.excluded?.length ? c.excluded.join(", ") : "none"],
                    ["protocol", c.protocol ? <span key="p" className="font-mono text-xs">{String(c.protocol.id)} · {String(c.protocol.sha256).slice(0, 12)}</span> : "—"],
                    ["generator", c.generator ? `${String(c.generator.name)} ${String(c.generator.version)}` : "—"],
                    ["models", c.models ? <span key="m" className="font-mono text-xs">{JSON.stringify(c.models)}</span> : "none (template)"],
                  ]} />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Ground-truth answer</CardTitle>
                  <CardDescription>What a perfect system answers on this corpus (ground_truth.json).</CardDescription>
                </CardHeader>
                <CardContent>
                  {c.answer ? (
                    <KeyValues items={[
                      ["label", <LabelBadge key="l" label={c.answer.label} />],
                      ...(["supporting", "contradicting", "neutral", "undetermined", "duplicates"] as const).map((k): [string, string] => [k, (c.answer?.[k] ?? []).join(", ") || "—"]),
                      ...Object.entries(c.answer.flags ?? {}).map(([f, docs]): [string, string] => [`flag ${f.replaceAll("_", " ")}`, docs.join(", ") || "—"]),
                    ]} />
                  ) : "—"}
                </CardContent>
              </Card>
            </div>
            {c.variant && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Counterfactual variant</CardTitle>
                  <CardDescription>
                    Study {c.variant.study} changed from {String(c.variant.from ?? "?")} to {c.variant.to}; only its paper was written again.
                    {c.base && <> Base corpus: <Link to={`/corpora/${encodeURIComponent(c.base)}`} className="font-mono underline">{c.base}</Link>.</>}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <KeyValues items={[
                    ["expected label", `${expected.before?.label ?? "?"} → ${expected.after?.label ?? "?"}`],
                    ["changed values", (c.variant.changed ?? []).map((v) => `${String(v.measurement)}: ${num(v.from as number, 3)} → ${num(v.to as number, 3)}`).join("; ") || "—"],
                  ]} />
                  <details><summary className="cursor-pointer text-sm">variant.json</summary><JsonBlock value={c.variant} className="mt-1" /></details>
                </CardContent>
              </Card>
            )}
            <section className="space-y-2">
              <h2 className="text-base font-semibold">Papers</h2>
              <div className="overflow-auto rounded-md border">
                <Table aria-label="Papers">
                  <TableHeader>
                    <TableRow>
                      {["paper", "level", "true direction", "delta", "flags", "fidelity"].map((h) => <TableHead key={h} className="text-xs">{h}</TableHead>)}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {c.papers_list.map((p) => (
                      <TableRow key={p.id}>
                        <TableCell className="font-mono text-xs"><Link to={`/corpora/${encodeURIComponent(c.name)}/papers/${encodeURIComponent(p.id)}`} className="hover:underline">{p.id}</Link></TableCell>
                        <TableCell className="text-xs">{p.level ?? "—"}</TableCell>
                        <TableCell>{p.relevant ? <DirectionBadge direction={p.direction} /> : <Badge variant="outline">irrelevant</Badge>}</TableCell>
                        <TableCell className="font-mono text-xs tabular-nums">{num(p.delta ?? null, 3)}</TableCell>
                        <TableCell className="text-xs">
                          {(p.flags ?? []).map((f) => <Badge key={f} variant="outline" className="mr-1">{f.replaceAll("_", " ")}</Badge>)}
                          {p.duplicate_of && <span>of {p.duplicate_of} </span>}
                          {p.missing && <span>missing {p.missing}</span>}
                        </TableCell>
                        <TableCell className="text-xs">{p.fidelity_ok === null || p.fidelity_ok === undefined ? "—" : p.fidelity_ok ? "pass" : "fail"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </section>
            <section className="space-y-2">
              <h2 className="text-base font-semibold">Runs on this corpus</h2>
              {on.length ? (
                <ul className="flex flex-wrap gap-2">
                  {on.map((r) => (
                    <li key={r.id}>
                      <Link to={`/runs/${encodeURIComponent(r.id)}`} className="inline-flex items-center gap-2 rounded-md border px-2 py-1 text-sm hover:bg-muted">
                        <SystemBadge system={r.system} /> <span className="font-mono text-xs">{r.group}</span> <LabelBadge label={r.label} correct={c.answer ? r.label === c.answer.label : undefined} />
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-muted-foreground">No run under the runs root names this corpus.</p>}
            </section>
          </div>
        )
      }}
    </QueryPage>
  )
}
