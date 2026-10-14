/**
 * The paired differences behind a test: one bar per question, claim on minus claim off, around a
 * zero line. One series, so one neutral colour (not a condition's: a difference belongs to
 * neither); the sign is the bar's direction from zero. The per-question table carries the values.
 */
import { Bar, BarChart, CartesianGrid, ReferenceLine, XAxis, YAxis } from "recharts"

import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart"

const CONFIG = { difference: { label: "claim on − claim off", color: "var(--muted-foreground)" } } satisfies ChartConfig

interface TooltipProps {
  active?: boolean
  payload?: ReadonlyArray<{ payload?: unknown }>
}

export function DifferenceChart({ data, format, label, height = 220 }: {
  data: { qid: string; difference: number }[]
  format: (value: number) => string
  label: string
  height?: number
}) {
  const tooltip = ({ active, payload }: TooltipProps) => {
    const row = active ? (payload?.[0]?.payload as { qid: string; difference: number } | undefined) : undefined
    if (!row) return null
    return (
      <div className="rounded-lg border bg-background px-2.5 py-1.5 text-xs shadow-xl">
        <span className="font-mono">{row.qid}</span>: <span className="font-mono font-medium tabular-nums">{format(row.difference)}</span>
      </div>
    )
  }
  return (
    <ChartContainer config={CONFIG} className="aspect-auto w-full" style={{ height }} role="img" aria-label={label}>
      <BarChart data={data} margin={{ top: 12, right: 8, left: 0, bottom: 0 }} accessibilityLayer>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="qid" tickLine={false} axisLine={false} tickMargin={8} interval={0} fontSize={11} />
        <YAxis tickLine={false} axisLine={false} width={64} tickFormatter={(v: number) => format(v)} />
        <ReferenceLine y={0} stroke="var(--foreground)" strokeWidth={1} />
        <ChartTooltip cursor={{ fillOpacity: 0.4 }} content={tooltip} />
        <Bar dataKey="difference" fill="var(--color-difference)" radius={2} maxBarSize={20} isAnimationActive={false} />
      </BarChart>
    </ChartContainer>
  )
}
