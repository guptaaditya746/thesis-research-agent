/**
 * The score charts (recharts through the shadcn chart container): a share per level and series (the
 * engine beside the baselines, or the evidence types), and a point with its 95 % interval per series. One
 * axis from 0 to 1, a legend for two or more series, a tooltip per bar; the series colours are the systems'
 * (src/lib/ev.ts) and every chart has the table it is drawn from next to it on the page.
 */
import { Bar, BarChart, CartesianGrid, Cell, ErrorBar, Legend, XAxis, YAxis } from "recharts"

import type { Interval } from "@/api/ev"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"

const share = (v: number) => v.toFixed(2)

export function LevelChart({ rows, series, label, colorOf, nameOf, height = 240 }: {
  rows: Record<string, unknown>[]
  series: string[]
  label: string
  colorOf: (s: string) => string
  nameOf: (s: string) => string
  height?: number
}) {
  const config = Object.fromEntries(series.map((s) => [s, { label: nameOf(s), color: colorOf(s) }])) satisfies ChartConfig
  return (
    <ChartContainer config={config} className="aspect-auto w-full" style={{ height }} role="img" aria-label={label}>
      <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} accessibilityLayer barGap={2}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="level" tickLine={false} axisLine={false} tickMargin={8} fontSize={11} />
        <YAxis domain={[0, 1]} tickLine={false} axisLine={false} width={40} tickFormatter={share} />
        <ChartTooltip cursor={{ fillOpacity: 0.3 }} content={<ChartTooltipContent />} />
        {series.length > 1 && <Legend verticalAlign="top" height={28} iconType="circle" iconSize={8} />}
        {series.map((s) => (
          <Bar key={s} dataKey={s} name={nameOf(s)} fill={`var(--color-${s})`} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
        ))}
      </BarChart>
    </ChartContainer>
  )
}

/** One bar per row at its point, the interval as an error bar (a degenerate interval draws none). */
export function IntervalChart({ rows, label, colorOf, nameOf, height = 200, domain = [0, 1] }: {
  rows: (Interval & { key: string })[]
  label: string
  colorOf: (key: string) => string
  nameOf: (key: string) => string
  height?: number
  domain?: [number, number]
}) {
  const data = rows.map((r) => {
    const point = r.point ?? 0
    const err = r.low !== null && r.low !== undefined && r.high !== null && r.high !== undefined ? [point - r.low, r.high - point] : [0, 0]
    return { key: r.key, name: nameOf(r.key), point, err, fill: colorOf(r.key) }
  })
  const config = { point: { label: "point" } } satisfies ChartConfig
  return (
    <ChartContainer config={config} className="aspect-auto w-full" style={{ height }} role="img" aria-label={label}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} accessibilityLayer>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} fontSize={11} interval={0} />
        <YAxis domain={domain} tickLine={false} axisLine={false} width={40} tickFormatter={share} />
        <ChartTooltip cursor={{ fillOpacity: 0.3 }} content={<ChartTooltipContent hideIndicator />} />
        <Bar dataKey="point" radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false}>
          {data.map((d) => <Cell key={d.key} fill={d.fill} />)}
          <ErrorBar dataKey="err" width={6} strokeWidth={1.5} stroke="var(--foreground)" />
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}
