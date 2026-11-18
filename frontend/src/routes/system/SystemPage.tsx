/**
 * The system on one page, top to bottom: the folder, the question, the protocol, the run and the answer. Each box
 * shows its content only when the box above is done. A fact number chosen in the answer box opens the Pull out
 * row and marks that fact.
 */
import { useState } from "react"

import { PageHeader } from "@/components/layout/PageHeader"

import { usePlanResult, type PlanView } from "../plan/api"
import { AnswerBox } from "./AnswerBox"
import { runFailure, useSteps, useSystemDomains } from "./api"
import { PickBox } from "./PickBox"
import { ProtocolBox } from "./ProtocolBox"
import { QuestionBox } from "./QuestionBox"
import { RunBox, type RowName } from "./RunBox"

const CLOSED: Record<RowName, boolean> = { find: false, pull: false, combine: false, answer: false }

export default function SystemPage() {
  const domains = useSystemDomains()
  const [domain, setDomain] = useState<string | null>(null)
  const [seed, setSeed] = useState<number | null>(null)
  const [view, setView] = useState<PlanView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [opened, setOpened] = useState(CLOSED)
  const folderDone = domain !== null && seed !== null
  const chosen = domains.data?.find((d) => d.domain === domain)
  const run = view?.run ?? null
  const result = usePlanResult(view?.id ?? null, run !== null)

  const finished = result.data !== undefined && result.data.status !== "running" && runFailure(result.data) === null
  const steps = useSteps(run, finished)
  const reset = () => { setView(null); setSelected(null); setOpened(CLOSED) }
  const pick = (n: number) => { setSelected(n); setOpened((o) => ({ ...o, pull: true })) }

  return (
    <div className="space-y-4">
      <PageHeader title="System" description="Choose a folder, ask a question, check the protocol, run it." />
      <PickBox domains={domains.data ?? []} domain={domain} seed={seed} error={domains.isError ? "The folders could not be read." : undefined}
        onPick={(d, s) => { setDomain(d); setSeed(s); reset() }} />
      <QuestionBox key={domain ?? ""} open={folderDone} domain={chosen} seed={seed} onView={setView} onError={setError} />
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <ProtocolBox view={view} domain={domain} seed={seed} onView={setView} onError={setError} />
      <RunBox planId={view?.id ?? null} run={run} selected={selected} onSelect={(n) => setSelected(n)} steps={steps.data}
        opened={opened} onToggle={(row) => setOpened((o) => ({ ...o, [row]: !o[row] }))} />
      <AnswerBox open={steps.data?.status === "done"} steps={steps.data} onSelect={pick} />
    </div>
  )
}
