/**
 * Benchmark records `/report/benchmarks/:id` (evaluate benchmark, B11): per extractor id, pooled over the
 * reports given, precision, recall, F1 and span accuracy per evidence type and level, the cost per call and
 * the re-execution stability where a report had one; the corpora each record rests on.
 */
import { useParams } from "react-router"

import { useBenchmark } from "@/api/ev"
import { JsonBlock, KeyValues, QueryPage, RowsTable } from "@/components/ev/bits"
import { PageHeader } from "@/components/layout/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { evCell, splitExtractor } from "@/lib/ev"

export default function BenchmarkPage() {
  const { id = "" } = useParams()
  const benchmark = useBenchmark(id)
  return (
    <QueryPage query={benchmark} what={`benchmark ${id}`} back={{ to: "/report", label: "Report" }}>
      {({ ref, records, markdown }) => (
        <div className="space-y-6">
          <PageHeader title={<span className="font-mono">{ref.id}</span>} description={`${records.length} extractor records, pooled over the reports given to evaluate benchmark.`} />
          <div className="grid gap-4 xl:grid-cols-2">
            {[...records].sort((a, b) => String(a.extractor_id).localeCompare(String(b.extractor_id))).map((r) => {
              const id = String(r.extractor_id)
              const { name, version, hash } = splitExtractor(id)
              const cost = (r.cost ?? {}) as Record<string, unknown>
              const perCall = (cost.per_call ?? {}) as Record<string, unknown>
              const stability = r.stability as Record<string, unknown> | null
              return (
                <Card key={id}>
                  <CardHeader>
                    <CardTitle className="flex flex-wrap items-center gap-2 text-base"><span className="font-mono">{name}</span>{version && <Badge variant="secondary">v{version}</Badge>}{hash && <span className="font-mono text-xs text-muted-foreground">#{hash}</span>}</CardTitle>
                    <CardDescription>{((r.corpora ?? []) as Record<string, unknown>[]).map((c) => `${String(c.corpus_id)} (${((c.levels ?? []) as string[]).join(", ")})`).join("; ")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <RowsTable caption={`${name} per type and level`} rows={((r.rows ?? []) as Record<string, unknown>[])} columns={["evidence_type", "level", "items", "facts", "precision", "recall", "f1", "span_accuracy", "only"]} />
                    <KeyValues items={[
                      ["calls", evCell(cost.calls)],
                      ["per call", Object.entries(perCall).map(([k, v]) => `${k.replaceAll("_", " ")} ${evCell(v)}`).join(", ") || "—"],
                      ["stability", stability ? Object.entries(stability).filter(([, v]) => typeof v !== "object").map(([k, v]) => `${k.replaceAll("_", " ")} ${evCell(v)}`).join(", ") : "no re-execution"],
                    ]} />
                  </CardContent>
                </Card>
              )
            })}
          </div>
          {markdown && <details><summary className="cursor-pointer text-sm">benchmark.md</summary><JsonBlock value={markdown} className="mt-1" /></details>}
        </div>
      )}
    </QueryPage>
  )
}
