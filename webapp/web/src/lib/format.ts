/** Number, time and label formatting shared by every page (one place, so tables and charts agree). */

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 })
const whole = new Intl.NumberFormat("en")

export const DASH = "—"

/** 0.734 -> "73.4%"; null -> "—". */
export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH
  return `${(value * 100).toFixed(digits)}%`
}

/** Signed percentage points for a difference of shares: 0.12 -> "+12.0 pp". */
export function pp(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH
  const sign = value > 0 ? "+" : value < 0 ? "−" : "±"
  return `${sign}${Math.abs(value * 100).toFixed(digits)} pp`
}

/** 0.4123 -> "0.41". */
export function num(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH
  return value.toFixed(digits)
}

/** 1234 -> "1,234". */
export function int(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH
  return whole.format(Math.round(value))
}

/** 1_234_567 -> "1.2M"; below 10,000 the full number. */
export function tokens(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH
  return Math.abs(value) < 10_000 ? whole.format(Math.round(value)) : compact.format(value)
}

/** Seconds as "42 s", "12 min 5 s" or "3 h 4 min". */
export function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return DASH
  const s = Math.round(seconds)
  if (s < 60) return `${s} s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m} min ${s % 60} s`
  return `${Math.floor(m / 60)} h ${m % 60} min`
}

/** p-values: "< 0.001" below a thousandth, else three decimals. */
export function pValue(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH
  return value < 0.001 ? "< 0.001" : value.toFixed(3)
}

/** ISO time -> "13 Oct, 14:05" (local); invalid or null -> "—". */
export function dateTime(iso: string | null | undefined): string {
  if (!iso) return DASH
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
}

/** Seconds between two ISO times (end defaults to now), or null. */
export function elapsed(start: string | null | undefined, end?: string | null): number | null {
  if (!start) return null
  const from = new Date(start).getTime()
  const to = end ? new Date(end).getTime() : Date.now()
  return Number.isNaN(from) || Number.isNaN(to) ? null : Math.max(0, (to - from) / 1000)
}

export const CONDITION_LABEL = { claim_on: "claim on", claim_off: "claim off" } as const

/** Any value of an answer cell or a SPARQL binding as one line of text. */
export function cell(value: unknown): string {
  if (value === null || value === undefined) return DASH
  if (Array.isArray(value)) return value.map(cell).join(", ")
  if (typeof value === "object") return JSON.stringify(value)
  return String(value)
}
