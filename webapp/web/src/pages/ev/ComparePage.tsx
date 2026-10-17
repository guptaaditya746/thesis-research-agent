/**
 * A comparison `/scores/compares/:id` (evaluate compare): one row per corpus (level) and system with the
 * headline numbers of A, B and C; over corpora it shows how the systems fare per level, on one corpus with
 * an `all` and a `gaps` run it is the funnel's cost against its accuracy (Part D). The intervals of each row
 * are listed beneath.
 */
import { useParams } from "react-router"

import { useCompare } from "@/api/ev"
import { JsonBlock, QueryPage, RowsTable, SystemBadge } from "@/components/ev/bits"
import { LevelChart } from "@/components/ev/ScoreCharts"
import { PageHeader } from "@/components/layout/PageHeader"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { evCell, intervalText, levelOrder, seriesOf, systemColor, systemLabel } from "@/lib/ev"

type Row = Record<string, unknown>

export default function ComparePage() {
  const { id = "" } = useParams()
  const compare = useCompare(id)
  return (
    <QueryPage query={compare} what={`comparison ${id}`} back={{ to: "/scores", label: "All scores" }}>
      {(c) => {
        const strategies = new Set(c.rows.map((r) => r.strategy).filter(Boolean)).size > 1
        const series = [...new Set(c.rows.map((r) => seriesOf(r, strategies)))]
        const byLevel = new Map<string, Row>()
        for (const r of c.rows) {
          const level = `${String(r.level)}${new Set(c.rows.filter((x) => x.level === r.level).map((x) => x.corpus_id)).size > 1 ? ` ${String(r.corpus_id).slice(-8)}` : ""}`
          const row = byLevel.get(level) ?? { level }
          row[seriesOf(r, strategies)] = r.direction_accuracy
          byLevel.set(level, row)
        }
        const chart = [...byLevel.values()].sort((a, b) => levelOrder(String(a.level), String(b.level)))
        const base = (s: string) => s.split(":")[0]
        const name = (s: string) => `${systemLabel(base(s))}${s.includes(":") ? ` (${s.split(":")[1]})` : ""}`
        // the same system in two strategies: the second one drawn lighter so both stay apart
        const color = (s: string) => (s.endsWith(":gaps") ? `color-mix(in oklab, ${systemColor(base(s))} 55%, var(--background))` : systemColor(base(s)))
        return (
          <div className="space-y-6">
            <PageHeader title={<span className="font-mono">{c.ref.id.replace("~", " / ")}</span>}
              description={strategies ? "The engine in all and in gaps on the same corpus: accuracy against calls and tokens per document." : "Per level and system: the headline numbers of each report."} />
            <Card>
              <CardHeader><CardTitle className="text-base">Direction accuracy</CardTitle></CardHeader>
              <CardContent><LevelChart rows={chart} series={series} colorOf={color} nameOf={name} label="Direction accuracy per level and system" /></CardContent>
            </Card>
            <RowsTable caption="Comparison" rows={c.rows}
              columns={["level", "corpus_id", "system", "strategy", "extraction_f1", "span_accuracy", "association_accuracy", "true_pair", "direction_accuracy", "completeness", "accuracy_answered", "traceability", "label_correct", "calls_per_document", "tokens_per_document", "screen_precision", "screen_recall"]}
              render={(col, v) => (col === "system" ? <SystemBadge system={String(v)} /> : evCell(v))} />
            {c.intervals.length > 0 && (
              <RowsTable caption="Intervals" rows={c.intervals.map((r) => ({ ...r, extraction_f1: intervalText(r.extraction_f1 as never), direction_accuracy: intervalText(r.direction_accuracy as never), engine_minus_system: intervalText(r.engine_minus_system as never) }))}
                columns={["level", "corpus_id", "system", "strategy", "extraction_f1", "direction_accuracy", "engine_minus_system"]}
                render={(col, v) => (col === "system" ? <SystemBadge system={String(v)} /> : evCell(v))} />
            )}
            {c.markdown && <details><summary className="cursor-pointer text-sm">compare.md</summary><JsonBlock value={c.markdown} className="mt-1" /></details>}
          </div>
        )
      }}
    </QueryPage>
  )
}
