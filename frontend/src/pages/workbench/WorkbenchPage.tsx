/** The Workbench: 1 Dataset · 2 Run · 3 Evaluation (mockup https://claude.ai/artifact/7rXgofLwWtzYNfgbqtvdMo). */
import { useState } from "react"

import { useDomains } from "@/api/evqa"
import { PageHeader } from "@/components/layout/PageHeader"
import { ErrorState } from "@/components/states"
import { cn } from "@/lib/utils"

import { DatasetPane } from "./DatasetPane"
import { EvalPane } from "./EvalPane"
import { PaperPane } from "./PaperPane"
import { QuestionsPane } from "./QuestionsPane"
import { RunPane } from "./RunPane"

const PANES = [
  { id: "dataset", label: "1 · Dataset", ready: true },
  { id: "questions", label: "1b · Questions", ready: true },
  { id: "paper", label: "1c · Papers", ready: true },
  { id: "run", label: "2 · Run", ready: true },
  { id: "eval", label: "3 · Evaluation", ready: true },
] as const

const HOLDOUT = "_holdout"
/** One menu entry per field: "medical_holdout" is the locked test set of "medical", so it is a set choice, not a domain. */
export function groupDomains(all: string[]): { base: string; holdout: string | null }[] {
  return all.filter((d) => !(d.endsWith(HOLDOUT) && all.includes(d.slice(0, -HOLDOUT.length))))
    .map((d) => ({ base: d, holdout: all.includes(d + HOLDOUT) ? d + HOLDOUT : null }))
}

export default function WorkbenchPage() {
  const domains = useDomains()
  const [pane, setPane] = useState<string>("dataset")
  const [domain, setDomain] = useState("")
  const [runId, setRunId] = useState("")
  const [qid, setQid] = useState("")
  const pick = (r: string, q: string) => { setRunId(r); setQid(q) }
  const groups = groupDomains(domains.data ?? [])
  const current = domain || groups[0]?.base || ""
  const group = groups.find((g) => g.base === current || g.holdout === current)
  return (
    <div className="space-y-4">
      <PageHeader title="Workbench" description="Made-up papers with a known truth: the seed graph, the run, the layered evaluation." />
      <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label="Workbench panes">
        {PANES.map((p) => (
          <button key={p.id} type="button" role="tab" aria-selected={pane === p.id} disabled={!p.ready}
            onClick={() => setPane(p.id)}
            className={cn("min-h-11 rounded-md border px-4 text-sm disabled:opacity-50",
              pane === p.id ? "border-primary bg-primary/10 font-semibold" : "hover:bg-muted")}>
            {p.label}
          </button>
        ))}
        <div className="ml-auto flex flex-wrap items-center gap-2 text-sm">
          {groups.length > 1 && (
            <label>Domain{" "}
              <select className="rounded border bg-background p-2" value={group?.base ?? current}
                onChange={(e) => setDomain(e.target.value)}>
                {groups.map((g) => <option key={g.base}>{g.base}</option>)}
              </select>
            </label>
          )}
          {group?.holdout && (
            <label>Set{" "}
              <select aria-label="Set" className="rounded border bg-background p-2" value={current}
                onChange={(e) => setDomain(e.target.value)}>
                <option value={group.base}>practice</option>
                <option value={group.holdout}>holdout (locked)</option>
              </select>
            </label>
          )}
        </div>
      </div>
      {domains.isError && <ErrorState error={domains.error} />}
      {pane === "dataset" && current && <DatasetPane domain={current} />}
      {pane === "questions" && current && <QuestionsPane domain={current} />}
      {pane === "paper" && current && <PaperPane domain={current} />}
      {pane === "run" && <RunPane domain={current} runId={runId} qid={qid} onPick={pick} />}
      {pane === "eval" && <EvalPane domain={current} runId={runId} onRun={(r) => pick(r, "")}
        onOpen={(r, q) => { pick(r, q); setPane("run") }} />}
      {domains.data?.length === 0 && <p className="text-sm">No seed yet: run <code>evqa seed build medical</code>.</p>}
    </div>
  )
}
