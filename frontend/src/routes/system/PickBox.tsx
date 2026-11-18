/** Box 1: the folder (domain and seed) the system runs on. Done when both are chosen. */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

import type { SystemDomain } from "./api"

const SELECT = "h-9 rounded-md border bg-background px-2 text-sm"

export function Box({ title, open, children }: { title: string; open: boolean; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader>
      <CardContent>{open ? children : <p className="text-sm text-muted-foreground">Finish the box above first.</p>}</CardContent>
    </Card>
  )
}

export function PickBox({ domains, domain, seed, onPick, error }: {
  domains: SystemDomain[]
  domain: string | null
  seed: number | null
  onPick: (domain: string | null, seed: number | null) => void
  error?: string
}) {
  const chosen = domains.find((d) => d.domain === domain)
  return (
    <Box title="1. Folder" open>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">
          <span className="font-medium">Domain</span>
          <select aria-label="Domain" className={SELECT} value={domain ?? ""} onChange={(e) => onPick(e.target.value || null, null)}>
            <option value="">Choose a domain</option>
            {domains.map((d) => <option key={d.domain} value={d.domain}>{d.domain}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2">
          <span className="font-medium">Seed</span>
          <select aria-label="Seed" className={SELECT} disabled={!chosen} value={seed ?? ""}
            onChange={(e) => onPick(domain, e.target.value === "" ? null : Number(e.target.value))}>
            <option value="">Choose a seed</option>
            {(chosen?.seeds ?? []).map((n) => <option key={n} value={n}>s{n}</option>)}
          </select>
        </label>
      </div>
      {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
      {chosen?.error && <p role="alert" className="mt-2 text-sm text-destructive">{chosen.error}</p>}
    </Box>
  )
}
