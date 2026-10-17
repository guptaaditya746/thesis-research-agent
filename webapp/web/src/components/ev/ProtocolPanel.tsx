/**
 * One protocol, version 2 (evidence/protocol.py; docs/evidence-system.md Part C): the evidence types with
 * their fields, roles, links and cascade; the screen; the synthesis block (compared roles, question metrics
 * with their direction, min_effect, pairing, the author-claim map, the label decision table, the flags);
 * locate; and the YAML as written. A file that does not validate shows the YAML and the reason.
 */
import { ArrowDownIcon, ArrowUpIcon, TriangleAlertIcon } from "lucide-react"

import type { EvidenceTypeSpec, ProtocolView, Synthesis } from "@/api/ev"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { typeLabel } from "@/lib/ev"

import { JsonBlock, KeyValues } from "./bits"

type Schema = { properties?: Record<string, { type?: unknown; enum?: unknown[]; description?: string }>; required?: string[] }

function FieldsTable({ spec }: { spec: EvidenceTypeSpec }) {
  const schema = spec.fields as Schema
  const props = Object.entries(schema.properties ?? {})
  return (
    <Table aria-label="Fields">
      <TableHeader>
        <TableRow>
          <TableHead className="text-xs">field</TableHead>
          <TableHead className="text-xs">type</TableHead>
          <TableHead className="text-xs">values</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {props.map(([name, p]) => (
          <TableRow key={name}>
            <TableCell className="font-mono text-xs">
              {name}
              {schema.required?.includes(name) && <span className="text-muted-foreground" title="required">*</span>}
            </TableCell>
            <TableCell className="font-mono text-xs">{Array.isArray(p.type) ? p.type.join(" | ") : String(p.type ?? "")}</TableCell>
            <TableCell className="text-xs">
              {p.enum ? p.enum.map((v) => <Badge key={String(v)} variant="outline" className="mr-1 font-mono">{String(v)}</Badge>) : p.description}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function EvidenceTypes({ types, phases }: { types: Record<string, EvidenceTypeSpec>; phases: string[] }) {
  const names = [...phases, ...Object.keys(types).filter((t) => !phases.includes(t))]
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {names.map((name, i) => {
        const spec = types[name]
        if (!spec) return null
        return (
          <Card key={name}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <span className="text-muted-foreground tabular-nums">{i + 1}.</span> {typeLabel(name)}
              </CardTitle>
              <CardDescription>{spec.description}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <FieldsTable spec={spec} />
              <KeyValues items={[
                ["span roles", spec.roles.join(", ")],
                ["context", spec.context?.length ? spec.context.join(", ") : "none"],
                ["links", Object.keys(spec.links ?? {}).length ? Object.entries(spec.links ?? {}).map(([k, v]) => `${k} → ${v}`).join(", ") : "none"],
                ["bounds", spec.bounds?.length ? spec.bounds.map((b) => `${b.field} in [${b.min ?? "-∞"}, ${b.max ?? "∞"}]${b.when ? ` when ${b.when.link}.${b.when.field} ∈ {${b.when.values.join(", ")}}` : ""}`).join("; ") : "none"],
                ["merge key", spec.merge_key?.join(", ") ?? "all fields"],
                ["cascade", (
                  <ol key="c" className="flex flex-wrap items-center gap-1">
                    {spec.extractors.map((e, p) => (
                      <li key={p} className="flex items-center gap-1">
                        {p > 0 && <span aria-hidden="true" className="text-muted-foreground">→</span>}
                        <Badge variant="secondary" className="font-mono" title={Object.keys(e.config ?? {}).length ? JSON.stringify(e.config) : undefined}>
                          {p}: {e.name}
                        </Badge>
                      </li>
                    ))}
                    <span className="ml-1 text-xs text-muted-foreground">({spec.cascade ?? "all"})</span>
                  </ol>
                )],
              ]} />
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

export function SynthesisBlock({ synthesis }: { synthesis: Synthesis }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Comparison and metrics</CardTitle>
          <CardDescription>A study's effect is the treatment against the control on the first question metric with a usable pair.</CardDescription>
        </CardHeader>
        <CardContent>
          <KeyValues items={[
            ["treatment role", <span key="t" className="font-mono">{synthesis.compare.treatment}</span>],
            ["control role", <span key="c" className="font-mono">{synthesis.compare.control}</span>],
            ["question metrics", (
              <ol key="m" className="space-y-0.5">
                {synthesis.metrics.map((m) => (
                  <li key={m.canonical} className="flex items-center gap-1.5 font-mono">
                    {m.higher_is_better ? <ArrowUpIcon className="size-3.5" aria-hidden="true" /> : <ArrowDownIcon className="size-3.5" aria-hidden="true" />}
                    {m.canonical}
                    <span className="font-sans text-xs text-muted-foreground">{m.higher_is_better ? "higher is better" : "lower is better"}</span>
                  </li>
                ))}
              </ol>
            )],
            ["min_effect", <span key="e" className="font-mono">{synthesis.min_effect}</span>],
            ["pairing", `${synthesis.pairing?.rule ?? "same_dataset"}; prefer ${(synthesis.pairing?.prefer ?? []).join(", then ")}`],
            ["author claim map", (
              <span key="cm" className="font-mono text-xs">
                {Object.entries(synthesis.claim_map).map(([k, v]) => `${k} → ${v}`).join(", ")}
              </span>
            )],
            ["flags", `duplicates ${synthesis.flags?.duplicates === false ? "off" : "on"}; large effect at ${synthesis.flags?.large_effect?.factor ?? 3}× the median of ≥ ${synthesis.flags?.large_effect?.min_studies ?? 3} studies`],
          ]} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Label decision table</CardTitle>
          <CardDescription>The first row whose conditions hold on the counts gives the label.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table aria-label="Label decision table">
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">#</TableHead>
                <TableHead className="text-xs">when</TableHead>
                <TableHead className="text-xs">then</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {synthesis.label.map((row, i) => (
                <TableRow key={i}>
                  <TableCell className="text-xs tabular-nums">{i + 1}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {Object.keys(row.when ?? {}).length ? Object.entries(row.when ?? {}).map(([k, v]) => `${k} ${v}`).join(" and ") : "otherwise"}
                  </TableCell>
                  <TableCell><Badge variant="secondary" className="font-mono">{row.then}</Badge></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

export function ProtocolPanel({ view }: { view: ProtocolView }) {
  const p = view.protocol
  return (
    <div className="space-y-4">
      <KeyValues items={[
        ["id", <span key="id" className="font-mono">{p?.id ?? view.name}</span>],
        ["version", p ? `${p.version} (format)${p.revision ? `, revision ${p.revision}` : ", hand-written (no revision)"}` : "—"],
        ["question", p?.question ?? "—"],
        ["sha256", <span key="sha" className="font-mono text-xs break-all">{view.sha256}</span>],
        ["phases", view.phases.join(" → ") || "—"],
        ["file", <span key="f" className="font-mono text-xs break-all">{view.path}</span>],
      ]} />
      {view.error && (
        <Alert variant="destructive">
          <TriangleAlertIcon />
          <AlertTitle>The protocol does not validate</AlertTitle>
          <AlertDescription className="font-mono text-xs whitespace-pre-wrap">{view.error}</AlertDescription>
        </Alert>
      )}
      <Tabs defaultValue={p ? "types" : "yaml"}>
        <TabsList>
          {p && <TabsTrigger value="types">Evidence types</TabsTrigger>}
          {p && <TabsTrigger value="screen">Screen and locate</TabsTrigger>}
          {p && <TabsTrigger value="synthesis">Synthesis</TabsTrigger>}
          <TabsTrigger value="yaml">YAML</TabsTrigger>
        </TabsList>
        {p && (
          <TabsContent value="types">
            <EvidenceTypes types={p.evidence_types as Record<string, EvidenceTypeSpec>} phases={view.phases} />
          </TabsContent>
        )}
        {p && (
          <TabsContent value="screen" className="space-y-4">
            {p.screen ? (
              <KeyValues items={[
                ["screening question", p.screen.question],
                ["terms", <span key="t" className="font-mono text-xs">{(p.screen.terms ?? []).join(", ")}</span>],
                ["cascade", p.screen.extractors.map((e) => e.name).join(" → ")],
                ["on fail", p.screen.on_fail === "skip" ? "skip the paper (in gaps; all records it and extracts anyway)" : "extract anyway"],
              ]} />
            ) : (
              <p className="text-sm text-muted-foreground">No screen: every paper is extracted.</p>
            )}
            <KeyValues items={[["locate", p.locate?.strategy ?? "exhaustive"], ["locate params", <JsonBlock key="lp" value={p.locate?.params ?? {}} className="max-h-40" />]]} />
          </TabsContent>
        )}
        {p && (
          <TabsContent value="synthesis">
            <SynthesisBlock synthesis={p.synthesis} />
          </TabsContent>
        )}
        <TabsContent value="yaml">
          <JsonBlock value={view.yaml} label="protocol YAML" className="max-h-[70vh]" />
        </TabsContent>
      </Tabs>
    </div>
  )
}
