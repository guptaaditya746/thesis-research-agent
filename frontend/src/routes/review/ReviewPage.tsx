/**
 * The review page (synth3): a domain picker and three tabs. Worlds: approve the drawn worlds. Answer sheets: check
 * and edit the drafted points. Judge test: hand-mark the answers without seeing the judge or the system.
 * The tab is in the address (/review/worlds, /review/sheets, /review/judge-test).
 */
import { useState } from "react"
import { useNavigate, useParams } from "react-router"

import { PageHeader } from "@/components/layout/PageHeader"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

import { useOverview } from "./api"
import { JudgeTestTab } from "./JudgeTestTab"
import { messageOf } from "./messageOf"
import { SheetsTab } from "./SheetsTab"
import { WorldsTab } from "./WorldsTab"

const TABS = ["worlds", "sheets", "judge-test"] as const
type Tab = (typeof TABS)[number]

export default function ReviewPage() {
  const { tab: param } = useParams()
  const tab: Tab = TABS.find((t) => t === param) ?? "worlds"
  const navigate = useNavigate()
  const overview = useOverview()
  const [picked, setPicked] = useState<string | null>(null)
  const domains = overview.data?.domains ?? []
  const domain = domains.find((d) => d.domain === picked) ?? domains.find((d) => !d.error) ?? null
  const broken = domains.filter((d) => d.error)

  return (
    <div className="space-y-4">
      <PageHeader title="Review" description="Approve worlds, check answer sheets and hand-mark the judge test." />
      {overview.error ? <Alert variant="destructive"><AlertDescription>{messageOf(overview.error)}</AlertDescription></Alert> : null}
      {broken.map((d) => (
        <Alert key={d.domain} variant="destructive"><AlertDescription>{d.domain}: {d.error}</AlertDescription></Alert>
      ))}
      {domains.length > 0 ? (
        <label className="flex items-center gap-2 text-sm">
          <span className="font-medium">Domain</span>
          <select className="h-9 rounded-md border bg-background px-2 text-sm" value={domain?.domain ?? ""} onChange={(e) => setPicked(e.target.value)}>
            {domains.map((d) => <option key={d.domain} value={d.domain} disabled={!!d.error}>{d.domain}{d.error ? " (does not load)" : ""}</option>)}
          </select>
        </label>
      ) : null}
      <Tabs value={tab} onValueChange={(t) => void navigate(`/review/${t}`)}>
        <TabsList>
          <TabsTrigger value="worlds">Worlds</TabsTrigger>
          <TabsTrigger value="sheets">Answer sheets</TabsTrigger>
          <TabsTrigger value="judge-test">Judge test</TabsTrigger>
        </TabsList>
      </Tabs>
      {tab === "judge-test" ? <JudgeTestTab /> : null}
      {tab === "worlds" && domain ? <WorldsTab key={domain.domain} domain={domain.domain} /> : null}
      {tab === "sheets" && domain ? <SheetsTab key={domain.domain} domain={domain.domain} /> : null}
      {tab !== "judge-test" && !domain && !overview.isLoading ? <p className="text-sm text-muted-foreground">No domain to review.</p> : null}
    </div>
  )
}
