/**
 * MSW handlers: the backend API (webapp/app.py) for `npm run dev:mock` (service worker) and the tests (Node).
 * What the writes answer is checked against the backend's own answers (write-contract.json, contract.test.ts).
 *
 * The viewer's reads come from ev-fixtures.json (src/mocks/ev.ts, the backend's own responses on a world made
 * by the real tools). What the app starts and writes is mocked with one in-memory `db` so a started job, a
 * new proposal or written decisions show up on the next request; `resetDb()` restores it:
 * - POST /api/ev/jobs/<kind> validates like the backend (names, a run or corpus that exists: 409) and queues
 *   a job with the backend's refs (a run's group from the backend's run-group answers in the fixtures); a job
 *   runs and then ends `done` after `timing.jobMs` (never on its own in the tests, which end it with `finishJob`);
 * - a propose job makes an unfrozen proposal (the fixtures' proposal with its decisions reset to the model's
 *   defaults) under the requested name; PUT decisions stores them and answers with what freeze would refuse
 *   (a missing reason, a choice other than the default by the model, an unknown choice, custom without a value);
 *   a freeze job freezes it. A run whose protocol and selection have no run-group answer in the fixtures (the
 *   repo's protocols and the world's proposals have them) is refused with 404, as GET /api/ev/run-group is.
 */
import { delay, http, HttpResponse } from "msw"

import type {
  Card,
  DecisionEntry,
  DecisionsRequest,
  Job,
  JobKind,
  KindRequest,
  JobRequests,
  ProposalDetail,
  CheckProblem,
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
  /** the waivers each proposal's decisions.yaml holds, by check */
  waivers: Record<string, Record<string, string>>
}

const fixture = <T,>(path: string) => structuredClone(EV_FIXTURES[path]) as T

/** The fixture key of a run-group answer (webapp/tests/evidence_world.py records it in this param order). */
const groupKey = (p: URLSearchParams) =>
  `/api/ev/run-group?source=${p.get("source")}&name=${p.get("name")}&extractors=${p.get("extractors")}&strategy=${p.get("strategy")}`
/** The run-group fixture key of a run request (its defaults as the backend's RunRequest has them). */
const groupKeyOf = (r: { protocol: { source: string; name: string }; extractors?: string; strategy?: string }) =>
  groupKey(new URLSearchParams({ source: r.protocol.source, name: r.protocol.name, extractors: r.extractors ?? "cascade", strategy: r.strategy ?? "all" }))

function initialDb(): Db {
  const runs = fixture<{ id: string }[]>("/api/ev/runs").map((r) => r.id)
  const corpora = fixture<{ name: string }[]>("/api/ev/corpora").map((c) => c.name)
  return { jobs: [], logs: {}, proposals: {}, runs: new Set(runs), corpora: new Set(corpora), waivers: {} }
}

let db: Db = initialDb()

export function resetDb() {
  db = initialDb()
  mockGateway.ok = true
  mockCheck.problems = []
  for (const t of timers) clearTimeout(t)
  timers.clear()
}

/** jobMs: how long a mock job runs before it is done (null: until `finishJob`; the tests). */
export const timing: { jobMs: number | null } = { jobMs: 3_000 }
/** ok false: the backend refuses model jobs (no key or no gateway), as webapp/evjobs.py need_gateway does. */
export const mockGateway = { ok: true }
/** What POST /proposals/{name}/check answers (the backend's CheckResult): the tests set the problems. */
export const mockCheck: { problems: CheckProblem[] } = { problems: [] }
const timers = new Set<ReturnType<typeof setTimeout>>()

const now = () => new Date().toISOString()
const conflict = (detail: string) => HttpResponse.json({ detail }, { status: 409 })
const notFound = (detail: string) => HttpResponse.json({ detail }, { status: 404 })
const invalid = (msg: string, loc: string[]) => HttpResponse.json({ detail: [{ loc: ["body", ...loc], msg }] }, { status: 422 })
const frozen = (name: string) => conflict(`proposal ${name} is frozen; change it with \`evidence propose amend\` (command line)`)
/** The model of a card's value (evidence/propose/cards.py: screen -> ScreenValue, min_effect -> MinEffectValue). */
const valueModel = (card: string) => `${card.replace(/(^|_)([a-z])/g, (_, __, c: string) => c.toUpperCase())}Value`

/** An unfrozen proposal made from the fixtures' frozen one: decisions back to the model's defaults. */
export function unfrozenProposal(name: string, kind: KindRequest["kind"] = "effect"): ProposalDetail {
  const p = fixture<ProposalDetail>(`/api/ev/proposals/${FROZEN}`)
  // a kind's own card set (evidence/propose/cards.yaml): the effect cards all; the others without pairing and label;
  // cascade and locate are the advanced cards of every kind
  const mine = p.cards.filter((c) => kind === "effect" || !["pairing", "label"].includes(c.id))
  return {
    ...p, name, frame: { ...p.frame, kind, kind_by: "model" }, frozen: false, revision: null, protocol_sha256: null, decided_by: {}, amendments: 0, proposal: null, protocol: null,
    revisions: [], amendment_log: [], decision_problems: [], decisions_sha256: "sha-0", steps: ["frame", "draft", "critic", "cards"],
    cards: mine.map((c) => ({
      ...c, advanced: ["cascade", "locate"].includes(c.id), kinds: [kind], problems: [], raw_decision: null,
      decision: { card: c.id, choice: c.default ?? "draft", reason: `default: ${c.rationale ?? ""}`, by: "model", value: null, default: c.default },
    })),
  }
}

/** What `cards.validate` refuses, with its messages (evidence/propose/cards.py), for the entries the form sends
 * (one per card): a missing reason, a choice that is no option, custom without a value (an object; its shape is
 * not checked), a choice other than the default by the model. */
function decisionProblems(cards: Card[], entries: DecisionEntry[]): string[] {
  const problems: string[] = []
  for (const e of entries) {
    const card = cards.find((c) => c.id === e.card)
    if (!card) continue
    if (!e.reason.trim()) problems.push(`${card.id}: a decision without a reason is refused`)
    const ids = card.options.map((o) => String(o.id))
    if (e.choice === "custom") {
      if (e.value === null || typeof e.value !== "object" || Array.isArray(e.value)) {
        problems.push(`${card.id}: choice custom needs a \`value\` in the card's shape: Input should be a valid dictionary or instance of ${valueModel(card.id)} at value`)
        continue
      }
    } else if (!ids.includes(e.choice)) {
      problems.push(`${card.id}: choice '${e.choice}' is not an option of the card (${ids.join(", ")}) nor \`custom\` with a value`)
      continue
    }
    if (e.choice !== card.default && e.by === "model") problems.push(`${card.id}: choice '${e.choice}' is not the model's default ('${card.default}'); set \`by\` to who decided`)
  }
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
      const group = b.group ?? (EV_FIXTURES[groupKeyOf(b)] as { group: string } | undefined)?.group
      if (!group) return notFound(`not in the mock fixtures: ${groupKeyOf(b)}`)
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
      if (!b.question === !b.text) return invalid("give either `question` or `text`", ["question"])
      if (b.proposal === FROZEN || db.proposals[b.proposal]?.frozen) return frozen(b.proposal)
      if (db.proposals[b.proposal]) return conflict(`proposal ${b.proposal} has its cards: decide them and freeze it`)
      return { proposal: b.proposal }
    }
    case "freeze": {
      const name = (body as JobRequests["freeze"]).proposal
      const p = db.proposals[name]
      if (!p) return conflict(`proposal ${name} has no cards yet (run the proposal flow first)`)
      if (p.frozen) return frozen(name)
      if (p.decision_problems.length) return conflict(`decisions.yaml refused:\n  ${p.decision_problems.join("\n  ")}`)
      const unwaived = mockCheck.problems.filter((x) => x.severity === "serious" && x.check !== "decision" && !db.waivers[name]?.[x.check])
      if (unwaived.length) return conflict(`decisions.yaml refused:\n  ${unwaived.map((x) => `${x.check}: ${x.message} (waive it in decisions.yaml)`).join("\n  ")}`)
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
  if (job.kind === "propose") {
    const made = unfrozenProposal(job.refs.proposal, (job.args.kind as KindRequest["kind"] | undefined) ?? "effect")
    // a typed question is what the frame asks, and stays so when the kind is changed
    const typed = (job.args.text as string | undefined) ?? (db.proposals[job.refs.proposal]?.question || undefined)
    db.proposals[job.refs.proposal] = typed ? { ...made, question: typed, frame: { ...made.frame, question: typed } } : made
  }
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
  // busy as the backend's `free(ref, value)` checks it: what the job writes (corpus_set, run, score, proposal),
  // never the corpus a run or baseline only reads
  const busy = Object.entries(refs).filter(([k]) => k !== "corpus")
  const active = db.jobs.find((j) => (j.state === "queued" || j.state === "running") && busy.some(([k, v]) => j.refs[k] === v))
  const [ref, value] = busy.find(([k, v]) => active?.refs[k] === v) ?? []
  if (active) return conflict(`job ${active.id} (${active.kind}) is ${active.state} on ${ref} ${value}; wait for it or cancel it`)
  return makeJob(kind, body, refs)
}

function makeJob<K extends JobKind>(kind: K, body: JobRequests[K] | Record<string, unknown>, refs: Record<string, string>): Response {
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
  http.post("/api/ev/proposals/:name/check", ({ params }) =>
    db.proposals[String(params.name)] ? HttpResponse.json({ problems: mockCheck.problems }) : undefined),
  http.get("/api/ev/proposals/:name/preview", ({ params, request }) => {
    const q = new URL(request.url).searchParams
    if (!db.proposals[String(params.name)]) return undefined
    const text = `Paper ${q.get("paper")}. Retrieval raised accuracy in this study.`
    const start = text.indexOf("Retrieval")
    return HttpResponse.json({ text, hits: [{ start, end: start + "Retrieval".length, card: "screen", what: "Retrieval" }] })
  }),
  http.put("/api/ev/proposals/:name/kind", async ({ params, request }) => {
    const p = db.proposals[String(params.name)]
    if (!p) return notFound(`proposal ${String(params.name)} has no frame yet (run the proposal flow first)`)
    if (p.frozen) return frozen(p.name)
    const body = (await request.json()) as KindRequest
    const active = db.jobs.find((j) => (j.state === "queued" || j.state === "running") && j.refs.proposal === p.name)
    if (active) return conflict(`job ${active.id} (${active.kind}) is ${active.state} on proposal ${p.name}; wait for it or cancel it`)
    p.frame = { ...p.frame, kind: body.kind, kind_by: "user" }
    p.steps = ["frame"]
    p.cards = []
    return makeJob("propose", { proposal: p.name, kind: body.kind, model: body.model ?? "orch-model" }, { proposal: p.name })
  }),
  http.put("/api/ev/proposals/:name/decisions", async ({ params, request }) => {
    const p = db.proposals[String(params.name)]
    if (!p) return conflict(`proposal ${String(params.name)} has no cards yet (run the proposal flow first)`)
    if (p.frozen) return frozen(p.name)
    const body = (await request.json()) as DecisionsRequest
    if (body.base_sha256 !== p.decisions_sha256 && !body.force) return conflict("decisions.yaml changed since the form loaded it (edited by hand or in another tab): reload to see it, or overwrite it")
    const problems = decisionProblems(p.cards, body.decisions)
    db.waivers[p.name] = Object.fromEntries((body.waivers ?? []).map((w) => [w.check, w.reason]))
    for (const w of body.waivers ?? []) if (w.reason.trim().length < 10) return HttpResponse.json({ detail: `waiver (${w.check}): the reason must be at least 10 characters` }, { status: 400 })
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
