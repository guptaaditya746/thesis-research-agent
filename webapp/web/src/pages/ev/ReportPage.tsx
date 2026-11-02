/**
 * A score report `/report/reports/:id` (evaluate score, evaluation/report.py; the supervisor's A/B/C, §5):
 *
 * - C synthesis first: per system the label against the expected one, direction accuracy, completeness,
 *   accuracy over the answered studies and traceability (baselines), with the 95 % intervals and the paired
 *   engine-minus-baseline difference, per level, and the flags (F1);
 * - A extraction: precision, recall, F1 and span accuracy per evidence type and level, F1 with intervals;
 * - B integration: association and the true treatment/control pair per level;
 * - the funnel (calls per document, where it stopped, the screen's precision and recall), locate recall,
 *   cascade contribution and cost; report.md as written.
 * Every chart has its table beside it.
 */
import { Link, useParams } from "react-router"

import { useReport, type Report } from "@/api/ev"
import { JsonBlock, KeyValues, LabelBadge, QueryPage, RowsTable, SystemBadge } from "@/components/ev/bits"
import { IntervalChart, LevelChart } from "@/components/ev/ScoreCharts"
import { PageHeader } from "@/components/layout/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ENGINE,
  EVIDENCE_TYPES,
  evCell,
  extractionByLevel,
  extractionRows,
  intervalsOf,
  intervalText,
  splitRef,
  synthesisByLevel,
  synthesisSummary,
  systemColor,
  systemLabel,
  systemOrder,
  TYPE_COLOR,
  typeLabel,
} from "@/lib/ev"

const C_COLUMNS = ["system", "label", "expected", "label_correct", "studies", "determined", "direction_accuracy", "completeness", "accuracy_answered", "traceability"]

function Synthesis({ report }: { report: Report }) {
  const systems = (report.synthesis ?? []).map((s) => s.system).sort(systemOrder)
  const accuracy = intervalsOf(report, "synthesis")
  const paired = intervalsOf(report, "paired")
  const flagged = (report.synthesis ?? []).filter((s) => s.flags)
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">C. Synthesis</h2>
      <RowsTable caption="Synthesis per system" rows={synthesisSummary(report)} columns={C_COLUMNS}
        render={(c, v, row) => c === "system" ? <SystemBadge system={String(v)} />
          : c === "label" ? <LabelBadge label={String(v ?? "")} correct={row.label_correct as boolean | undefined} />
            : evCell(v)} />
      <p className="text-xs text-muted-foreground">
        Direction accuracy is over every scored study (an undeterminable one is right when the system says undetermined); completeness and
        accuracy over the answered studies are over the studies with a determined true direction; traceability is the share of a baseline's
        cited passages that overlap a ground-truth placement.
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-base">Direction accuracy, 95 % interval</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <IntervalChart rows={accuracy} label="Direction accuracy per system with intervals" colorOf={systemColor} nameOf={systemLabel} />
            <KeyValues items={accuracy.map((r) => [systemLabel(r.key), intervalText(r)])} />
          </CardContent>
        </Card>
        {paired.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Engine minus baseline (paired, per study)</CardTitle>
              <CardDescription>Above zero: the engine is right more often on the same studies.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <IntervalChart rows={paired} domain={[-1, 1]} label="Paired difference in direction accuracy" colorOf={systemColor} nameOf={(k) => `− ${systemLabel(k)}`} />
              <KeyValues items={paired.map((r) => [`engine − ${systemLabel(r.key)}`, intervalText(r)])} />
            </CardContent>
          </Card>
        )}
      </div>
      <Card>
        <CardHeader><CardTitle className="text-base">Direction accuracy per level</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <LevelChart rows={synthesisByLevel(report.synthesis, "direction_accuracy")} series={systems} colorOf={systemColor} nameOf={systemLabel} label="Direction accuracy per level and system" />
          <RowsTable caption="Direction accuracy per level" rows={synthesisByLevel(report.synthesis, "direction_accuracy")} columns={["level", ...systems]} headers={Object.fromEntries(systems.map((s) => [s, systemLabel(s)]))} />
          <RowsTable caption="Completeness per level" rows={synthesisByLevel(report.synthesis, "completeness")} columns={["level", ...systems]} headers={Object.fromEntries(systems.map((s) => [s, `${systemLabel(s)} completeness`]))} />
        </CardContent>
      </Card>
      {flagged.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Flags</CardTitle><CardDescription>Duplicates, unusually large effects, author claims that disagree with the data (F1).</CardDescription></CardHeader>
          <CardContent className="space-y-2">
            <RowsTable caption="Flags" rows={flagged.flatMap((s) => (((s.flags?.rows as Record<string, unknown>[] | undefined) ?? []).map((r) => ({ system: s.system, ...r }))))}
              columns={["system", "flag", "expected", "given", "tp", "fp", "fn", "precision", "recall"]}
              render={(c, v) => (c === "system" ? <SystemBadge system={String(v)} /> : evCell(v))} />
            <KeyValues items={flagged.map((s) => [systemLabel(s.system), `counts ${s.flags?.counts_correct ? "correct" : "wrong"}, duplicates ${s.flags?.duplicates_correct ? "correct" : "wrong"}`])} />
          </CardContent>
        </Card>
      )}
    </section>
  )
}

function Extraction({ report }: { report: Report }) {
  if (!report.extraction) return null
  const byLevel = extractionByLevel(report)
  const types = EVIDENCE_TYPES.filter((t) => byLevel.some((r) => t in r))
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">A. Extraction</h2>
      <RowsTable caption="Extraction over all levels" rows={extractionRows(report)} columns={["evidence_type", "items", "facts", "matched", "precision", "recall", "f1", "span_accuracy"]}
        render={(c, v) => (c === "evidence_type" ? typeLabel(String(v)) : evCell(v))} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-base">F1 per level and evidence type</CardTitle></CardHeader>
          <CardContent>
            <LevelChart rows={byLevel} series={types} colorOf={(t) => TYPE_COLOR[t]} nameOf={typeLabel} label="Extraction F1 per level and evidence type" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">F1, 95 % interval</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <IntervalChart rows={intervalsOf(report, "extraction")} colorOf={(t) => TYPE_COLOR[t] ?? "var(--muted-foreground)"} nameOf={typeLabel} label="Extraction F1 per evidence type with intervals" />
            <KeyValues items={intervalsOf(report, "extraction").map((r) => [typeLabel(r.key), intervalText(r)])} />
          </CardContent>
        </Card>
      </div>
      <RowsTable caption="Extraction F1 per level" rows={byLevel} columns={["level", ...types, "all"]} headers={Object.fromEntries(types.map((t) => [t, typeLabel(t)]))} />
    </section>
  )
}

function Rest({ report }: { report: Report }) {
  const funnel = report.funnel as Record<string, unknown> | null | undefined
  return (
    <>
      {report.integration && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">B. Integration</h2>
          <RowsTable caption="Integration per level" rows={(report.integration.rows as Record<string, unknown>[] | undefined) ?? []}
            columns={["level", "matched_measurements", "association_accuracy", "condition_role_accuracy", "metric_accuracy", "studies", "true_pair"]} />
        </section>
      )}
      {funnel && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Funnel</h2>
          <KeyValues items={[
            ["strategy", String(funnel.strategy ?? "—")],
            ["per document", Object.entries((funnel.per_document ?? {}) as Record<string, number>).map(([k, v]) => `${k.replaceAll("_", " ")} ${evCell(v)}`).join(", ")],
            ["stopped", Object.entries((funnel.stop_positions ?? {}) as Record<string, number>).map(([k, v]) => `${k}: ${v}`).join(", ")],
            ["screen", funnel.screen ? (() => { const s = funnel.screen as Record<string, unknown>; return `precision ${evCell(s.precision)}, recall ${evCell(s.recall)} (tp ${String(s.tp)}, fp ${String(s.fp)}, fn ${String(s.fn)}, tn ${String(s.tn)})` })() : "—"],
          ]} />
          <RowsTable caption="Funnel per document" rows={(funnel.rows as Record<string, unknown>[] | undefined) ?? []}
            columns={["document", "level", "expected_relevant", "relevant", "skipped", "stop", "calls", "model_calls", "tokens"]} />
        </section>
      )}
      {report.cascade && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Cascade contribution</h2>
          <RowsTable caption="Cascade contribution" rows={(report.cascade.rows as Record<string, unknown>[] | undefined) ?? []} columns={["extractor", "found", "found_matched", "only", "only_matched"]} />
        </section>
      )}
      {report.locate && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Locate recall</h2>
          <RowsTable caption="Locate recall" rows={((report.locate.rows as Record<string, unknown>[] | undefined) ?? []).filter((r) => r.level === "all")} columns={["evidence_type", "placements", "inside", "recall"]} />
        </section>
      )}
      {report.cost && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Cost</h2>
          <RowsTable caption="Cost" rows={Object.entries((report.cost.total ?? {}) as Record<string, unknown>).map(([k, v]) => ({ measure: k, total: v, per_paper: ((report.cost?.per_paper ?? {}) as Record<string, unknown>)[k] }))} columns={["measure", "total", "per_paper"]} />
        </section>
      )}
    </>
  )
}

export default function ReportPage() {
  const { id = "" } = useParams()
  const report = useReport(id)
  return (
    <QueryPage query={report} what={`report ${id}`} back={{ to: "/report", label: "Report" }}>
      {({ ref, report: r, markdown }) => {
        const { group, name } = splitRef(ref.id)
        const runId = name ? `${group}~${name}` : null
        return (
          <div className="space-y-8">
            <PageHeader title={<span className="font-mono">{group}{name ? ` / ${name}` : ""}</span>} description={r.question}>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-mono text-xs">{r.corpus_id}</span>
                <span className="text-muted-foreground">levels {r.levels.join(", ")}</span>
                {ref.strategy && <Badge variant="outline">strategy {ref.strategy}</Badge>}
                {r.run_id && runId && <Link to={`/runs/${encodeURIComponent(runId)}`} className="underline">the run</Link>}
                {(r.synthesis ?? []).some((s) => s.system !== ENGINE) && <span className="text-muted-foreground">baselines beside the engine</span>}
              </div>
            </PageHeader>
            <Synthesis report={r} />
            <Extraction report={r} />
            <Rest report={r} />
            {markdown && <details><summary className="cursor-pointer text-sm">report.md</summary><JsonBlock value={markdown} className="mt-1 max-h-[60vh]" /></details>}
          </div>
        )
      }}
    </QueryPage>
  )
}
