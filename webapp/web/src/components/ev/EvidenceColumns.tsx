/**
 * The evidence table's columns per question kind. Effect (engine): paper, treatment, control, metric, dataset,
 * effect, verdict with its rule, author claim, found by. Effect (baseline): paper, verdict, the passages it
 * cited. Every cell that rests on an item opens the source panel on that item's span.
 */
import type { EffectAnswer } from "@/api/ev"
import { Badge } from "@/components/ui/badge"
import { focusOn, type EffectData, type EvidenceRow } from "@/lib/evidence"
import { DASH } from "@/lib/format"

import { DirectionBadge } from "./bits"
import { EffectMark, FoundByCell, SideCell } from "./EvidenceCells"
import { SourceButton } from "./EvidenceTable"
import type { EvidenceColumn } from "./useEvidenceTable"

const paperColumn = <T,>(): EvidenceColumn<T> => ({
  id: "paper",
  header: "paper",
  sort: (r) => r.document ?? r.key,
  className: "w-16",
  cell: (r, open) => (
    <SourceButton target={r.target} onOpen={open} label={`${r.key}: show the evidence in the paper`} className="font-mono">{r.key}</SourceButton>
  ),
})

export function effectColumns(answer: EffectAnswer, rows: EvidenceRow<EffectData>[], engine: boolean): EvidenceColumn<EffectData>[] {
  const verdict: EvidenceColumn<EffectData> = {
    id: "verdict",
    header: "verdict and rule",
    sort: (r) => r.data.direction,
    className: "min-w-40",
    cell: (r) => (
      <span className="flex flex-col items-start gap-1">
        {r.data.study ? <DirectionBadge direction={r.data.direction} /> : <Badge variant="outline" className="font-normal">not used</Badge>}
        <span className="text-muted-foreground" title={r.data.rule}>{r.data.ruleShort}</span>
        {(r.data.study?.flags ?? []).filter((f) => f !== "duplicate").map((f) => (
          <span key={f} className="rounded-sm border px-1 text-[11px]">{f.replaceAll("_", " ")}</span>
        ))}
      </span>
    ),
  }
  if (!engine) {
    const cited = new Map<string, number>()
    for (const c of answer.citations ?? []) cited.set(c.document, (cited.get(c.document) ?? 0) + 1)
    return [
      paperColumn<EffectData>(),
      verdict,
      {
        id: "cited",
        header: "cited passages",
        sort: (r) => cited.get(r.key) ?? 0,
        cell: (r, open) => (cited.get(r.key)
          ? <SourceButton target={r.target} onOpen={open} label={`${r.key}: show the cited passages`} className="font-mono tabular-nums">{cited.get(r.key)}</SourceButton>
          : <span className="text-muted-foreground">none</span>),
      },
    ]
  }
  const scale = new Map<string, number>()
  for (const r of rows) {
    if (r.data.delta === null || !r.data.study?.metric) continue
    scale.set(r.data.study.metric, Math.max(scale.get(r.data.study.metric) ?? 0, Math.abs(r.data.delta)))
  }
  return [
    paperColumn<EffectData>(),
    { id: "treatment", header: "treatment", sort: (r) => r.data.treatment?.value, cell: (r, open) => <SideCell row={r} side="treatment" open={open} /> },
    { id: "control", header: "control", sort: (r) => r.data.control?.value, cell: (r, open) => <SideCell row={r} side="control" open={open} /> },
    {
      id: "metric",
      header: "metric",
      sort: (r) => r.data.metric?.name,
      hideable: true,
      cell: (r, open) => {
        const m = r.data.metric
        if (!m) return <span className="text-muted-foreground">{DASH}</span>
        return (
          <SourceButton target={m.item ? focusOn(r, m.item) : null} onOpen={open} label={`${r.key}: metric ${m.name}, show in the paper`}>
            {m.name}
            {m.higherIsBetter !== null && <span className="block text-muted-foreground">{m.higherIsBetter ? "higher is better" : "lower is better"}</span>}
          </SourceButton>
        )
      },
    },
    {
      id: "dataset",
      header: "dataset",
      sort: (r) => r.data.dataset,
      hideable: true,
      compact: false,
      cell: (r, open) => (r.data.dataset
        ? <SourceButton target={focusOn(r, r.data.treatment?.measurement)} onOpen={open} label={`${r.key}: dataset ${r.data.dataset}, show in the paper`}>{r.data.dataset}</SourceButton>
        : <span className="text-muted-foreground">{DASH}</span>),
    },
    {
      id: "effect",
      header: "effect (Δ)",
      sort: (r) => r.data.delta,
      cell: (r) => <EffectMark delta={r.data.delta} direction={r.data.direction} scale={scale.get(r.data.study?.metric ?? "") ?? 0} />,
    },
    verdict,
    {
      id: "claim",
      header: "author claim",
      sort: (r) => r.data.claim?.direction,
      hideable: true,
      compact: false,
      cell: (r, open) => {
        const c = r.data.claim
        if (!c) return <span className="text-muted-foreground">{DASH}</span>
        return (
          <SourceButton target={focusOn(r, c.item)} onOpen={open} label={`${r.key}: author claim ${c.direction}, show in the paper`}>
            {c.direction.replaceAll("_", " ")}
            {c.agrees === false && <span className="block font-medium text-status-critical">disagrees with the numbers</span>}
            {c.agrees === true && <span className="block text-muted-foreground">agrees with the numbers</span>}
          </SourceButton>
        )
      },
    },
    { id: "found_by", header: "found by", hideable: true, compact: false, cell: (r) => <FoundByCell ids={r.data.foundBy} /> },
  ]
}
