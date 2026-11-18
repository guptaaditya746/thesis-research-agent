/**
 * The system on one page, top to bottom: the folder, the question, the protocol. Each box shows its content only
 * when the box above is done (the later boxes, the run's four rows, come with the next task).
 */
import { useState } from "react"

import { PageHeader } from "@/components/layout/PageHeader"

import type { PlanView } from "../plan/api"
import { useSystemDomains } from "./api"
import { PickBox } from "./PickBox"
import { ProtocolBox } from "./ProtocolBox"
import { QuestionBox } from "./QuestionBox"

export default function SystemPage() {
  const domains = useSystemDomains()
  const [domain, setDomain] = useState<string | null>(null)
  const [seed, setSeed] = useState<number | null>(null)
  const [view, setView] = useState<PlanView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const folderDone = domain !== null && seed !== null
  const chosen = domains.data?.find((d) => d.domain === domain)

  return (
    <div className="space-y-4">
      <PageHeader title="System" description="Choose a folder, ask a question, check the protocol, run it." />
      <PickBox domains={domains.data ?? []} domain={domain} seed={seed} error={domains.isError ? "The folders could not be read." : undefined}
        onPick={(d, s) => { setDomain(d); setSeed(s); setView(null) }} />
      <QuestionBox key={domain ?? ""} open={folderDone} domain={chosen} seed={seed} onView={setView} onError={setError} />
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <ProtocolBox view={view} domain={domain} seed={seed} onView={setView} onError={setError} />
    </div>
  )
}
