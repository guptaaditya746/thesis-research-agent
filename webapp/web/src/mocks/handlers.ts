/**
 * MSW handlers: the backend API (webapp/app.py) for `npm run dev:mock` (service worker) and the tests (Node).
 *
 * The viewer's reads come from ev-fixtures.json (src/mocks/ev.ts, the backend's own responses on a world made
 * by the real tools). What the app starts and writes is mocked with one in-memory `db` so a started job, a
 * new proposal or written decisions show up on the next request; `resetDb()` restores it:
 * - POST /api/ev/jobs/<kind> validates like the backend (names, a run or corpus that exists: 409) and queues
 *   a job with the backend's refs; a job runs and then ends `done` after `timing.jobMs` (never on its own in
 *   the tests, which end it with `finishJob`);
 * - a propose job makes an unfrozen proposal (the fixtures' proposal with its decisions reset to the model's
 *   defaults) under the requested name; PUT decisions stores them and answers with what freeze would refuse
 *   (a missing reason, a choice other than the default by the model, an unknown choice); a freeze job freezes it.
 */
import { delay, http, HttpResponse } from "msw"

import type {
  Card,
  DecisionEntry,
  DecisionsRequest,
  Job,
  JobKind,
  JobRequests,
  ProposalDetail,
  ProposalSummary,
  Question,
} from "@/api/ev"
import { isName } from "@/lib/jobs"

import { EV_FIXTURES, evHandlers } from "./ev"

const FROZEN = "rag-factuality"

interface Db {
  jobs: Job[]
  logs: Record<string, string[]>
  proposals: Record<string, ProposalDetail>
  runs: Set<string>
  corpora: Set<string>
}

const fixture = <T,>(path: string) => structuredClone(EV_FIXTURES[path]) as T

/** The fixture key of a run-group answer (webapp/tests/evidence_world.py records it in this param order). */
const groupKey = (p: URLSearchParams) =>
  `/api/ev/run-group?source=${p.get("source")}&name=${p.get("name")}&extractors=${p.get("extractors")}&strategy=${p.get("strategy")}`
const groupOf = (r: { protocol: { source: string; name: string }; extractors?: string; strategy?: string }): string => {
  const params = new URLSearchParams({ source: r.protocol.source, name: r.protocol.name, extractors: r.extractors ?? "cascade", strategy: r.strategy ?? "all" })
  return (EV_FIXTURES[groupKey(params)] as { group: string } | undefined)?.group ?? `${r.protocol.source === "proposal" ? "proposal-" : ""}${r.protocol.name}-${r.extractors ?? "cascade"}${r.strategy === "gaps" && r.extractors !== "regex-only" ? "-gaps" : ""}`
}

function initialDb(): Db {
  const runs = fixture<{ id: string }[]>("/api/ev/runs").map((r) => r.id)
  const corpora = fixture<{ name: string }[]>("/api/ev/corpora").map((c) => c.name)
  return { jobs: [], logs: {}, proposals: {}, runs: new Set(runs), corpora: new Set(corpora) }
}

let db: Db = initialDb()

export function resetDb() {
  db = initialDb()
  mockGateway.ok = true
  for (const t of timers) clearTimeout(t)
  timers.clear()
}

/** jobMs: how long a mock job runs before it is done (null: until `finishJob`; the tests). */
export const timing: { jobMs: number | null } = { jobMs: 3_000 }
/** ok false: the backend refuses model jobs (no key or no gateway), as webapp/evjobs.py need_gateway does. */
export const mockGateway = { ok: true }
const timers = new Set<ReturnType<typeof setTimeout>>()

const now = () => new Date().toISOString()
const conflict = (detail: string) => HttpResponse.json({ detail }, { status: 409 })
const notFound = (detail: string) => HttpResponse.json({ detail }, { status: 404 })
const invalid = (msg: string, loc: string[]) => HttpResponse.json({ detail: [{ loc: ["body", ...loc], msg }] }, { status: 422 })

/** An unfrozen proposal made from the fixtures' frozen one: decisions back to the model's defaults. */
export function unfrozenProposal(name: string): ProposalDetail {
  const p = fixture<ProposalDetail>(`/api/ev/proposals/${FROZEN}`)
  return {
    ...p, name, frozen: false, revision: null, protocol_sha256: null, decided_by: {}, amendments: 0, proposal: null, protocol: null,
    revisions: [], amendment_log: [], decision_problems: [], decisions_sha256: "sha-0", steps: ["frame", "draft", "critic", "cards"],
    cards: p.cards.map((c) => ({
      ...c, problems: [], raw_decision: null,
      decision: { card: c.id, choice: c.default ?? "draft", reason: `default: ${c.rationale ?? ""}`, by: "model", value: null, default: c.default },
    })),
  }
}

/** What `cards.validate` refuses, with its messages (evidence/propose/cards.py). */
export function decisionProblems(cards: Card[], entries: DecisionEntry[]): string[] {
  const problems: string[] = []
  const seen = new Set<string>()
  for (const e of entries) {
    const card = cards.find((c) => c.id === e.card)
    if (!card) { problems.push(`entry: unknown card '${e.card}'`); continue }
    seen.add(card.id)
    if (!e.reason.trim()) problems.push(`${card.id}: a decision without a reason is refused`)
    const ids = card.options.map((o) => String(o.id))
    if (e.choice === "custom") {
      if (e.value === null || e.value === undefined || typeof e.value !== "object") problems.push(`${card.id}: choice custom needs a \`value\` in the card's shape`)
    } else if (!ids.includes(e.choice)) {
      problems.push(`${card.id}: choice '${e.choice}' is not an option of the card (${ids.join(", ")}) nor \`custom\` with a value`)
      continue
    }
    if (e.choice !== card.default && e.by === "model") problems.push(`${card.id}: choice '${e.choice}' is not the model's default ('${card.default}'); set \`by\` to who decided`)
  }
  for (const c of cards) if (!seen.has(c.id)) problems.push(`${c.id}: no decision`)
  return problems
}

function refsOf<K extends JobKind>(kind: K, body: JobRequests[K]): Record<string, string> | Response {
  switch (kind) {
    case "synth": {
      const b = body as JobRequests["synth"]
      if (!isName(b.name)) return invalid("String should match pattern", ["name"])
      const names = [...(b.levels ?? []).map((l) => `${b.name}-${l}`), `${b.name}-mixed`]
      const taken = names.filter((n) => db.corpora.has(n))
      if (taken.length) return conflict(`corpora ${taken.join(", ")} exist; choose another name`)
      return { corpus_set: b.name, corpus: `${b.name}-mixed` }
    }
    case "run": {
      const b = body as JobRequests["run"]
      if (!db.corpora.has(b.corpus)) return notFound(`no such corpus: '${b.corpus}'`)
      const group = b.group ?? groupOf(b)
      const id = `${group}~${b.name ?? b.corpus}`
      if (db.runs.has(id)) return conflict(`run ${group}/${b.name ?? b.corpus} exists; give the run another name`)
      return { run: id, corpus: b.corpus }
    }
    case "rag-baseline":
    case "agent-baseline": {
      const b = body as JobRequests["rag-baseline"]
      if (!db.corpora.has(b.corpus)) return notFound(`no such corpus: '${b.corpus}'`)
      const id = `${kind}~${b.corpus}`
      if (db.runs.has(id)) return conflict(`${kind}/${b.corpus} has an answer.json; move it away to run the baseline again`)
      return { run: id, corpus: b.corpus }
    }
    case "score": return { score: (body as JobRequests["score"]).run }
    case "compare": return { score: (body as JobRequests["compare"]).name }
    case "propose": {
      const b = body as JobRequests["propose"]
      if (b.proposal === FROZEN || db.proposals[b.proposal]?.frozen) return conflict(`proposal ${b.proposal} is frozen`)
      if (db.proposals[b.proposal]) return conflict(`proposal ${b.proposal} has its cards: decide them and freeze it`)
      return { proposal: b.proposal }
    }
    case "freeze": {
      const name = (body as JobRequests["freeze"]).proposal
      const p = db.proposals[name]
      if (!p) return conflict(`proposal ${name} has no cards yet (run the proposal flow first)`)
      if (p.frozen) return conflict(`proposal ${name} is frozen`)
      if (p.decision_problems.length) return conflict(`decisions.yaml refused:\n  ${p.decision_problems.join("\n  ")}`)
      return { proposal: name }
    }
  }
  return {}
}

const LANE: Record<JobKind, Job["lane"]> = {
  synth: "cpu", run: "model", "rag-baseline": "model", "agent-baseline": "model", score: "cpu", compare: "cpu", propose: "model", freeze: "cpu",
}

/** End a mock job (the tests' clock): its effect on the db, then `done` (or `failed`). */
export function finishJob(id: string, state: "done" | "failed" = "done", failedCalls: number | null = null) {
  const job = db.jobs.find((j) => j.id === id)
  if (!job || (job.state !== "running" && job.state !== "queued")) return
  job.state = state
  job.failed_calls = failedCalls
  job.ended_at = now()
  job.exit_code = state === "done" ? 0 : 1
  job.steps = job.steps.map((s) => ({ ...s, state: state === "done" ? "done" : "failed", exit_code: job.exit_code, ended_at: now() }))
  db.logs[id].push(`# ${job.steps.at(-1)?.name ?? job.kind} exit ${job.exit_code}`)
  if (state !== "done") return
  if (job.refs.run) db.runs.add(job.refs.run)
  if (job.kind === "synth") for (const l of [...((job.args.levels as string[]) ?? []), "mixed"]) db.corpora.add(`${job.refs.corpus_set}-${l}`)
  if (job.kind === "propose") db.proposals[job.refs.proposal] = unfrozenProposal(job.refs.proposal)
  if (job.kind === "freeze") {
    const p = db.proposals[job.refs.proposal]
    p.frozen = true
    p.steps = [...p.steps, "freeze"]
    p.protocol = fixture<ProposalDetail>(`/api/ev/proposals/${FROZEN}`).protocol
  }
}

function submit<K extends JobKind>(kind: K, body: JobRequests[K]): Response {
  if (LANE[kind] === "model" && !(kind === "run" && (body as JobRequests["run"]).extractors === "regex-only") && !mockGateway.ok) {
    return conflict("model job refused: no $LITELLM_MASTER_KEY in the server's environment: start `webapp serve` after sourcing llm-setup's .env")
  }
  const refs = refsOf(kind, body)
  if (refs instanceof Response) return refs
  const active = db.jobs.find((j) => (j.state === "queued" || j.state === "running") && Object.entries(refs).some(([k, v]) => j.refs[k] === v))
  if (active) return conflict(`job ${active.id} (${active.kind}) is ${active.state}; wait for it or cancel it`)
  const id = `20261018T120000-${kind}-${(db.jobs.length + 1).toString(16).padStart(6, "0")}`
  const argv = ["python", "-m", "webapp.tool", kind, ...Object.entries(body).flatMap(([k, v]) => [`--${k}`, typeof v === "object" ? JSON.stringify(v) : String(v)])]
  const job: Job = {
    id, kind, lane: LANE[kind], args: body as unknown as Record<string, unknown>, refs, state: "running", created_at: now(), started_at: now(),
    ended_at: null, exit_code: null, error: null, warnings: [], failed_calls: null, orphaned: false,
    steps: [{ name: kind, argv, command: argv.join(" "), required: true, needs: [], state: "running", exit_code: null, started_at: now(), ended_at: null, pid: 4242, pid_start: "1" }],
  }
  db.jobs.unshift(job)
  db.logs[id] = [`$ ${job.steps[0].command}`, `mock ${kind} working…`]
  if (timing.jobMs !== null) {
    const t = setTimeout(() => { timers.delete(t); finishJob(id) }, timing.jobMs)
    timers.add(t)
  }
  return HttpResponse.json(job, { status: 202 })
}

function proposalSummary(p: ProposalDetail): ProposalSummary {
  const { name, question, steps, frozen, revision, protocol_sha256, decided_by, amendments } = p
  return { name, question, steps, frozen, revision, protocol_sha256, decided_by, amendments }
}

export const handlers = [
  http.get("/api/health", () => HttpResponse.json({ ok: true, version: "mock" })),
  http.get("/api/ev/questions", () => {
    const questions = fixture<Question[]>("/api/ev/questions")
    return HttpResponse.json(questions.map((q) => ({ ...q, proposals: [...q.proposals, ...Object.keys(db.proposals)] })))
  }),
  http.get("/api/ev/questions/:id", ({ params }) => {
    const q = fixture<Question[]>("/api/ev/questions").find((x) => x.id === params.id)
    return q ? HttpResponse.json({ ...q, proposals: [...q.proposals, ...Object.keys(db.proposals)] }) : notFound(`no such question: '${String(params.id)}'`)
  }),
  http.get("/api/ev/proposals", () =>
    HttpResponse.json([...fixture<ProposalSummary[]>("/api/ev/proposals"), ...Object.values(db.proposals).map(proposalSummary)])),
  http.get("/api/ev/proposals/:name", ({ params }) => {
    const p = db.proposals[String(params.name)]
    return p ? HttpResponse.json(p) : undefined   // the fixtures answer the rest
  }),
  http.put("/api/ev/proposals/:name/decisions", async ({ params, request }) => {
    const p = db.proposals[String(params.name)]
    if (!p) return conflict(`proposal ${String(params.name)} has no cards yet (run the proposal flow first)`)
    if (p.frozen) return conflict(`proposal ${p.name} is frozen; change it with \`evidence propose amend\` (command line)`)
    const body = (await request.json()) as DecisionsRequest
    if (body.base_sha256 !== p.decisions_sha256 && !body.force) return conflict("decisions.yaml changed since the form loaded it (edited by hand or in another tab): reload to see it, or overwrite it")
    const problems = decisionProblems(p.cards, body.decisions)
    p.decision_problems = problems
    p.cards = p.cards.map((c) => {
      const d = body.decisions.find((e) => e.card === c.id)
      return {
        ...c, problems: problems.filter((x) => x.startsWith(`${c.id}:`)),
        decision: d ? { card: c.id, choice: d.choice, reason: d.reason.trim(), by: d.by, value: d.choice === "custom" ? d.value : null, default: c.default } : null,
      }
    })
    p.decisions_sha256 = `sha-${Number(p.decisions_sha256?.slice(4) ?? 0) + 1}`
    return HttpResponse.json({ written: `/srv/ev/proposals/${p.name}/decisions.yaml`, sha256: p.decisions_sha256, problems })
  }),
  http.get("/api/ev/jobs", () => HttpResponse.json(db.jobs)),
  http.get("/api/ev/jobs/:id", ({ params }) => {
    const job = db.jobs.find((j) => j.id === params.id)
    return job ? HttpResponse.json(job) : notFound(`no such job: '${String(params.id)}'`)
  }),
  http.get("/api/ev/jobs/:id/log", ({ params, request }) => {
    const lines = db.logs[String(params.id)]
    if (!lines) return notFound(`no such job: '${String(params.id)}'`)
    const n = Number(new URL(request.url).searchParams.get("lines") ?? 200)
    return new HttpResponse(lines.slice(-n).join("\n") + "\n", { headers: { "Content-Type": "text/plain" } })
  }),
  http.post("/api/ev/jobs/:id/cancel", ({ params }) => {
    const job = db.jobs.find((j) => j.id === params.id)
    if (!job) return notFound(`no such job: '${String(params.id)}'`)
    if (job.state === "queued" || job.state === "running") {
      job.state = "failed"
      job.error = "cancelled"
      job.ended_at = now()
      job.steps = job.steps.map((s) => ({ ...s, state: s.state === "running" ? "failed" : "skipped" }))
    }
    return HttpResponse.json(job)
  }),
  http.post("/api/ev/jobs/:kind", async ({ params, request }) => {
    await delay(timing.jobMs === null ? 0 : 150)
    const kind = String(params.kind) as JobKind
    if (!(kind in LANE)) return notFound(`no such API endpoint: /api/ev/jobs/${kind}`)
    return submit(kind, (await request.json()) as JobRequests[typeof kind])
  }),
  http.get("/api/ev/run-group", ({ request }) => {
    const key = groupKey(new URL(request.url).searchParams)
    return key in EV_FIXTURES
      ? HttpResponse.json(EV_FIXTURES[key] as Record<string, unknown>)
      : HttpResponse.json({ detail: `not in the mock fixtures: ${key}` }, { status: 404 })
  }),
  ...evHandlers,
]
