/**
 * The score charts (recharts through the shadcn chart container): a share per level and series (the
 * engine beside the baselines, or the evidence types), and a point with its 95 % interval per series. One
 * labelled axis from 0 to 1, a legend for two or more series, a tooltip per bar; the series colours are the
 * systems' (src/lib/ev.ts) and every chart has the table it is drawn from next to it on the page.
 */
import { Bar, BarChart, CartesianGrid, Cell, ErrorBar, XAxis, YAxis } from "recharts"

import type { Interval } from "@/api/ev"
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { num } from "@/lib/format"

const share = (v: number) => v.toFixed(2)
/** A series key as a CSS custom property name: the container writes `--color-<key>`, and a series such as
 * `evidence-engine:gaps` (compare.json) would break that rule, so config, rows and fills all use this key. */
const cssKey = (s: string) => s.replace(/[^\w-]/g, "_")
const yAxisLabel = (value: string) => ({ value, angle: -90, position: "insideLeft" as const, offset: 10, fontSize: 11, fill: "var(--muted-foreground)", style: { textAnchor: "middle" as const } })

export function LevelChart({ rows, series, label, colorOf, nameOf, height = 240, yLabel = "share" }: {
  rows: Record<string, unknown>[]
  series: string[]
  label: string
  colorOf: (s: string) => string
  nameOf: (s: string) => string
  height?: number
  /** the value axis' title */
  yLabel?: string
}) {
  const config = Object.fromEntries(series.map((s) => [cssKey(s), { label: nameOf(s), color: colorOf(s) }])) satisfies ChartConfig
  const data = rows.map((r) => ({ ...r, ...Object.fromEntries(series.map((s) => [cssKey(s), r[s]])) }))
  return (
    <ChartContainer config={config} className="aspect-auto w-full" style={{ height }} role="figure" aria-label={label}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }} accessibilityLayer barGap={2}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="level" tickLine={false} axisLine={false} tickMargin={8} fontSize={11} />
        <YAxis domain={[0, 1]} tickLine={false} axisLine={false} width={48} tickFormatter={share} label={yAxisLabel(yLabel)} />
        <ChartTooltip cursor={{ fillOpacity: 0.3 }} content={<ChartTooltipContent />} />
        {series.length > 1 && <ChartLegend verticalAlign="top" content={<ChartLegendContent />} />}
        {series.map((s) => (
          <Bar key={s} dataKey={cssKey(s)} name={nameOf(s)} fill={`var(--color-${cssKey(s)})`} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
        ))}
      </BarChart>
    </ChartContainer>
  )
}

/** One bar per row at its point, the interval as an error bar (a degenerate interval draws none). */
export function IntervalChart({ rows, label, colorOf, nameOf, height = 200, domain = [0, 1], yLabel = "share" }: {
  rows: (Interval & { key: string })[]
  label: string
  colorOf: (key: string) => string
  nameOf: (key: string) => string
  height?: number
  domain?: [number, number]
  /** the value axis' title */
  yLabel?: string
}) {
  const data = rows.map((r) => {
    const point = r.point ?? 0
    const bounded = r.low !== null && r.low !== undefined && r.high !== null && r.high !== undefined
    const err = bounded ? [point - r.low!, r.high! - point] : [0, 0]
    return { key: r.key, name: nameOf(r.key), point, err, fill: colorOf(r.key), interval: bounded ? `${num(r.low!, 2)}–${num(r.high!, 2)}` : "n/a" }
  })
  const config = { point: { label: "point" } } satisfies ChartConfig
  return (
    <ChartContainer config={config} className="aspect-auto w-full" style={{ height }} role="figure" aria-label={label}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }} accessibilityLayer>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} fontSize={11} interval={0} />
        <YAxis domain={domain} tickLine={false} axisLine={false} width={48} tickFormatter={share} label={yAxisLabel(yLabel)} />
        {/* The tooltip says the interval too: the error bar alone has no numbers. */}
        <ChartTooltip cursor={{ fillOpacity: 0.3 }} content={<ChartTooltipContent hideIndicator formatter={(value, _name, _item, _i, row) => (
          <div className="flex w-full justify-between gap-3 leading-none">
            <span className="text-muted-foreground">point (95 % interval)</span>
            <span className="font-mono font-medium text-foreground tabular-nums">{num(Number(value), 3)} [{String((row as { interval?: string }).interval ?? "n/a")}]</span>
          </div>
        )} />} />
        <Bar dataKey="point" radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false}>
          {data.map((d) => <Cell key={d.key} fill={d.fill} />)}
          <ErrorBar dataKey="err" width={6} strokeWidth={1.5} stroke="var(--foreground)" />
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}
