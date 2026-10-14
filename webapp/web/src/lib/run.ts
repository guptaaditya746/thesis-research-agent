/**
 * Reading a run's open parts: config.json (RunDetail.config, agent/rundir.py run_config) and the
 * labels of its states. The backend passes config.json through as it is, so every field is
 * checked before use; a run of an older agent may lack the budget or the prompt version.
 */
import type { RunConfig, RunSummary } from "@/api/types"

const obj = (v: unknown): Record<string, unknown> | undefined =>
  v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : undefined
const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : undefined)
const str = (v: unknown) => (typeof v === "string" ? v : undefined)

export function runConfig(config: Record<string, unknown> | null | undefined): RunConfig {
  const c = obj(config) ?? {}
  const budget = obj(c.budget)
  const prompt = obj(c.prompt)
  const sampling = obj(c.sampling)
  const orchestrator = obj(obj(c.models)?.orchestrator)
  return {
    run_id: str(c.run_id),
    created_at: str(c.created_at),
    condition: str(c.condition),
    budget: budget && { steps: num(budget.steps), tokens: num(budget.tokens), announced: budget.announced === true },
    sampling: sampling && { temperature: num(sampling.temperature), seed: num(sampling.seed) },
    prompt: prompt && { version: str(prompt.version), sha256: str(prompt.sha256) },
    models: orchestrator && { orchestrator: { alias: str(orchestrator.alias), name: str(orchestrator.name), revision: str(orchestrator.revision) } },
    git_commit: str(c.git_commit),
  }
}

/** The baseline's attach step (agent/rundir.py attach_state) in words. */
export const ATTACH_LABEL: Record<RunSummary["attach"], string> = {
  not_applicable: "no attach step",
  pending: "attach pending",
  cut: "attach cut",
  done: "attached",
}

export const ANSWER_FROM_LABEL: Record<string, string> = {
  final: "final answer",
  draft: "draft answer (taken by the harness)",
  none: "no answer",
}

/** A run of the batch (m4-72~q01-claim_on-r1-a1) in two parts for display: batch and name. */
export function splitRunId(runId: string): { batch: string | null; name: string } {
  const at = runId.indexOf("~")
  return at < 0 ? { batch: null, name: runId } : { batch: runId.slice(0, at), name: runId.slice(at + 1) }
}
