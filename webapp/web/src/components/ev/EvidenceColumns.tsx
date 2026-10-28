/**
 * The evidence table's columns per question kind. Effect (engine): paper, treatment, control, metric, dataset,
 * effect, verdict with its rule, author claim, found by. Effect (baseline): paper, verdict, the passages it
 * cited. Inventory: name, other names, papers, the papers that name it. Consistency: paper, what it says,
 * what its numbers say, agree or not. Best: paper, winner, one column per method kind, wins per kind as the
 * total row. Every cell that rests on an item opens the source panel on that item's span.
 */
import { CheckIcon, CircleHelpIcon, TrophyIcon, XIcon } from "lucide-react"

import type { BestAnswer, ConsistencyAnswer, EffectAnswer, InventoryAnswer } from "@/api/ev"
import { StatusBadge } from "@/components/badges"
import { Badge } from "@/components/ui/badge"
import { focusOn, type BestData, type ConsistencyData, type EffectData, type EvidenceRow, type InventoryData } from "@/lib/evidence"
import { DASH, num } from "@/lib/format"
import { cn } from "@/lib/utils"

import { DirectionBadge } from "./bits"
import { EffectMark, FoundByCell, PaperChips, SideCell } from "./EvidenceCells"
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

/** Inventory: one row per distinct name; its papers open the paper with the name's items marked. */
export function inventoryColumns(answer: InventoryAnswer): EvidenceColumn<InventoryData>[] {
  return [
    {
      id: "name",
      header: answer.target ?? "name",
      sort: (r) => r.data.entry.name.toLowerCase(),
      cell: (r, open) => (
        <SourceButton target={r.target} onOpen={open} label={`${r.data.entry.name}: show in the first paper`} className="text-sm font-medium">
          {r.data.entry.name}
        </SourceButton>
      ),
    },
    {
      id: "aliases",
      header: "other names",
      hideable: true,
      compact: false,
      cell: (r) => (r.data.entry.aliases.length ? r.data.entry.aliases.join(", ") : <span className="text-muted-foreground">{DASH}</span>),
    },
    { id: "count", header: "papers", sort: (r) => r.data.papers.length, className: "w-16", cell: (r) => <span className="font-mono tabular-nums">{r.data.papers.length}</span> },
    { id: "papers", header: "named in", cell: (r, open) => <PaperChips row={r} open={open} /> },
    { id: "found_by", header: "found by", hideable: true, compact: false, cell: (r) => <FoundByCell ids={r.data.foundBy} /> },
  ]
}

const reasonOf = (r: { code: string; text?: string | null } | null | undefined) => (r ? (r.text ?? r.code) : null)

/** Consistency: one row per paper, what the paper says against what its numbers say. */
export function consistencyColumns(answer: ConsistencyAnswer): EvidenceColumn<ConsistencyData>[] {
  return [
    paperColumn<ConsistencyData>(),
    {
      id: "claim",
      header: "paper says",
      sort: (r) => r.data.study?.claim,
      cell: (r, open) => (r.data.study?.claim
        ? <SourceButton target={focusOn(r, r.data.claimItem)} onOpen={open} label={`${r.key}: the author claim, show in the paper`}><DirectionBadge direction={r.data.study.claim} /></SourceButton>
        : <span className="text-muted-foreground">no claim</span>),
    },
    {
      id: "numbers",
      header: `numbers say${answer.metric ? ` (${answer.metric})` : ""}`,
      sort: (r) => r.data.study?.direction,
      cell: (r, open) => (r.data.study?.direction
        ? <SourceButton target={focusOn(r, r.data.numberItems[0])} onOpen={open} label={`${r.key}: the measurements, show in the paper`}><DirectionBadge direction={r.data.study.direction} /></SourceButton>
        : <span className="text-muted-foreground">{DASH}</span>),
    },
    {
      id: "verdict",
      header: "agree?",
      sort: (r) => r.lane,
      className: "min-w-40",
      cell: (r) => {
        const s = r.data.study
        if (!s) return <Badge variant="outline" className="font-normal">not used</Badge>
        return (
          <span className="flex flex-col items-start gap-1">
            {s.agrees === true ? <StatusBadge tone="good" icon={<CheckIcon />}>agrees</StatusBadge>
              : s.agrees === false ? <StatusBadge tone="critical" icon={<XIcon />}>disagrees</StatusBadge>
                : <StatusBadge tone="warning" icon={<CircleHelpIcon />}>undetermined</StatusBadge>}
            {reasonOf(s.reason) && <span className="text-muted-foreground">{reasonOf(s.reason)}</span>}
          </span>
        )
      },
    },
    { id: "found_by", header: "found by", hideable: true, compact: false, cell: (r) => <FoundByCell ids={r.data.foundBy} /> },
  ]
}

/** Best: one row per paper, a column per method kind with its value (the top one marked), wins per kind below. */
export function bestColumns(rows: EvidenceRow<BestData>[], order?: string[]): EvidenceColumn<BestData>[] {
  const seen = new Set(rows.flatMap((r) => Object.keys(r.data.values)))
  const kinds = [...(order ?? []).filter((k) => seen.has(k)), ...[...seen].filter((k) => !(order ?? []).includes(k)).sort()]
  return [
    paperColumn<BestData>(),
    {
      id: "winner",
      header: "winner",
      sort: (r) => r.data.study?.winner ?? (r.data.study?.tied.length ? "~tie" : undefined),
      cell: (r) => {
        const s = r.data.study
        if (!s) return <Badge variant="outline" className="font-normal">not used</Badge>
        if (s.winner) return <StatusBadge tone="good" icon={<TrophyIcon />}>{s.winner}</StatusBadge>
        if (s.tied.length) return <span>tie: {s.tied.join(", ")}</span>
        return <span className="text-muted-foreground">{reasonOf(s.reason) ?? DASH}</span>
      },
    },
    ...kinds.map((k): EvidenceColumn<BestData> => ({
      id: `kind:${k}`,
      header: k,
      sort: (r) => r.data.values[k]?.value,
      cell: (r, open) => {
        const v = r.data.values[k]
        if (!v) return <span className="text-muted-foreground">{DASH}</span>
        const top = r.data.study?.winner === k || !!r.data.study?.tied.includes(k)
        return (
          <SourceButton target={v.item ? focusOn(r, v.item) : null} onOpen={open}
            label={`${r.key}: ${k} ${num(v.value, 3)}${top ? ", the top value" : ""}, show in the paper`}
            className={cn("font-mono tabular-nums", top && "font-semibold")}>
            {num(v.value, 3)}
            {top && <TrophyIcon aria-hidden="true" className="ml-1 inline size-3 align-[-1px] text-status-good" />}
          </SourceButton>
        )
      },
    })),
    { id: "found_by", header: "found by", hideable: true, compact: false, cell: (r) => <FoundByCell ids={r.data.foundBy} /> },
  ]
}

/** The wins-per-kind total row under a best table, by column id. */
export function bestFooter(answer: BestAnswer): Record<string, string> {
  return {
    paper: "papers won",
    winner: answer.winner ? `overall: ${answer.winner}` : answer.tied.length ? `overall tie: ${answer.tied.join(", ")}` : "no overall winner",
    ...Object.fromEntries(Object.entries(answer.wins).map(([k, n]) => [`kind:${k}`, String(n)])),
  }
}
