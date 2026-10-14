/**
 * Grouped bars of claim on vs claim off (shadcn chart on recharts), with the report's interval
 * as error bars where it has one. Colour follows the condition (series 1 and 2 of the validated
 * palette); bars are at most 24 px wide with rounded data ends; one y axis; hairline grid; the
 * tooltip shows the mean and its interval, the legend names the conditions, and the page's
 * tables carry every value too.
 */
import { Bar, BarChart, CartesianGrid, ErrorBar, XAxis, YAxis } from "recharts"

import type { Condition } from "@/api/types"
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, type ChartConfig } from "@/components/ui/chart"
import { CONDITION_LABEL } from "@/lib/format"

export interface ConditionRow {
  label: string
  claim_on: number | null
  claim_off: number | null
  claim_on_error?: [number, number] | null
  claim_off_error?: [number, number] | null
  claim_on_ci?: [number, number] | null
  claim_off_ci?: [number, number] | null
}

const CONFIG = {
  claim_on: { label: CONDITION_LABEL.claim_on, color: "var(--chart-1)" },
  claim_off: { label: CONDITION_LABEL.claim_off, color: "var(--chart-2)" },
} satisfies ChartConfig

interface TooltipProps {
  active?: boolean
  label?: unknown
  payload?: ReadonlyArray<{ dataKey?: unknown; payload?: unknown }>
}

export function ConditionChart({ data, format, domain, height = 240, label }: {
  data: ConditionRow[]
  format: (value: number) => string
  domain?: [number, number | "auto"]
  height?: number
  /** accessible name of the chart */
  label: string
}) {
  const hasErrors = data.some((d) => d.claim_on_error || d.claim_off_error)
  const tooltip = ({ active, payload, label: group }: TooltipProps) => {
    if (!active || !payload?.length) return null
    const row = payload[0]?.payload as ConditionRow | undefined
    if (!row) return null
    return (
      <div className="grid min-w-40 gap-1 rounded-lg border bg-background px-2.5 py-1.5 text-xs shadow-xl">
        <p className="font-medium">{String(group)}</p>
        {(["claim_on", "claim_off"] as Condition[]).map((c) => {
          const ci = row[`${c}_ci`]
          const value = row[c]
          return (
            <div key={c} className="flex items-center gap-2">
              <span className="size-2.5 shrink-0 rounded-[2px]" style={{ background: CONFIG[c].color }} aria-hidden="true" />
              <span className="text-muted-foreground">{CONFIG[c].label}</span>
              <span className="ml-auto font-mono font-medium tabular-nums">
                {value === null ? "—" : format(value)}
                {ci ? ` [${format(ci[0])}, ${format(ci[1])}]` : ""}
              </span>
            </div>
          )
        })}
      </div>
    )
  }
  return (
    <ChartContainer config={CONFIG} className="aspect-auto w-full" style={{ height }} role="img" aria-label={label}>
      <BarChart data={data} margin={{ top: 12, right: 8, left: 0, bottom: 0 }} barGap={2} accessibilityLayer>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
        <YAxis tickLine={false} axisLine={false} width={56} tickFormatter={(v: number) => format(v)} domain={domain ?? [0, "auto"]} />
        <ChartTooltip cursor={{ fillOpacity: 0.4 }} content={tooltip} />
        <ChartLegend content={<ChartLegendContent />} />
        {(["claim_on", "claim_off"] as const).map((c) => (
          <Bar key={c} dataKey={c} fill={`var(--color-${c})`} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false}>
            {hasErrors && <ErrorBar dataKey={`${c}_error`} width={6} strokeWidth={1.5} stroke="var(--foreground)" direction="y" />}
          </Bar>
        ))}
      </BarChart>
    </ChartContainer>
  )
}
