/**
 * What a job writes and how the flow names things (the run group is named by the backend only: useRunGroup).
 */
import type { Job, ProtocolRef } from "@/api/ev"

/** "repo:rag-factuality" <-> {source, name}: how the flow keeps the chosen protocol in the URL. */
export function protocolParam(ref: ProtocolRef): string {
  return `${ref.source}:${ref.name}`
}

export function parseProtocolParam(value: string | null | undefined): ProtocolRef | null {
  const m = /^(repo|proposal):([A-Za-z0-9][A-Za-z0-9._-]{0,127})$/.exec(value ?? "")
  return m ? { source: m[1] as ProtocolRef["source"], name: m[2] } : null
}

/** A plain name as the backend accepts it (webapp/files.py ID): no separator, no leading dot or dash. */
export const NAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/
export const isName = (value: string) => NAME_PATTERN.test(value)

const KIND_LABEL: Record<string, string> = {
  synth: "template corpus",
  run: "engine run",
  "rag-baseline": "RAG baseline",
  "agent-baseline": "agent baseline",
  score: "score",
  compare: "comparison",
  propose: "proposal",
  freeze: "freeze",
}

/** "engine run cascade~c1", "template corpus c1", ... */
export function jobTitle(job: Pick<Job, "kind" | "refs">): string {
  const what = job.refs.run ?? job.refs.score ?? job.refs.proposal ?? job.refs.corpus_set ?? job.refs.corpus ?? ""
  return `${KIND_LABEL[job.kind] ?? job.kind}${what ? ` ${what}` : ""}`
}

/** Where the job's result is shown in the viewer, when there is a page for it. */
export function jobTarget(job: Pick<Job, "kind" | "refs">): string | null {
  if (job.refs.run) return `/runs/${encodeURIComponent(job.refs.run)}`
  if (job.kind === "score" && job.refs.score) return `/scores/reports/${encodeURIComponent(job.refs.score)}`
  if (job.kind === "compare" && job.refs.score) return `/scores/compares/${encodeURIComponent(job.refs.score)}`
  if (job.refs.proposal) return `/proposals/${encodeURIComponent(job.refs.proposal)}`
  if (job.refs.corpus) return `/corpora/${encodeURIComponent(job.refs.corpus)}`
  return null
}
