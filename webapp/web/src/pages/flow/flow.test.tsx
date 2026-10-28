/** The guided flow against the mock backend: the stepper, the jobs it starts, the cards form, the Jobs page. */
import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { afterEach, beforeAll, describe, expect, it } from "vitest"

import { evApi, type DecisionsRequest, type EvRunDetail, type JobRequests } from "@/api/ev"
import { routes } from "@/app/routes"
import { evFixture } from "@/mocks/ev"
import { finishJob, mockCheck, mockGateway, unfrozenProposal } from "@/mocks/handlers"
import { server } from "@/mocks/node"
import { renderRoutes } from "@/test/render"

const T = { timeout: 15_000 }
const QUESTION = "Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?"
const MIXED = "rag-tpl-w1-mixed"
const PARA = "rag-tpl-w1-paraphrased"

beforeAll(async () => {
  await Promise.all([import("@/pages/flow/FlowPage"), import("@/pages/JobsPage"), import("@/pages/ev/HomePage")])
}, 180_000)

afterEach(() => server.events.removeAllListeners())

/** Every POST body a job endpoint got, by kind. */
function recordJobs() {
  const bodies: { kind: string; body: unknown }[] = []
  server.events.on("request:start", async ({ request }) => {
    const m = /\/api\/ev\/jobs\/([a-z-]+)$/.exec(new URL(request.url).pathname)
    if (request.method === "POST" && m && m[1] !== "cancel") bodies.push({ kind: m[1], body: await request.clone().json() })
  })
  return bodies
}

async function choose(user: ReturnType<typeof userEvent.setup>, label: string, option: RegExp | string) {
  await user.click(screen.getByRole("combobox", { name: label }))
  await user.click(await screen.findByRole("option", { name: option }))
}

describe("the stepper", () => {
  it("flow has no scores step", async () => {
    renderRoutes(routes, "/flow/rag-factuality/scores")
    expect(await screen.findByRole("heading", { name: QUESTION }, T)).toBeInTheDocument()
    const steps = screen.getByRole("navigation", { name: "Steps" })
    expect(within(steps).queryByRole("link", { name: /Scores/ })).toBeNull()
    // an old link to the step lands on the first step
    expect(await screen.findByText(/Chosen: hand-written rag-factuality./, {}, T)).toBeInTheDocument()
  })

  it("says which step this is and offers Next only once the step's choice is made", async () => {
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, "/flow/rag-factuality/corpus")
    expect(await screen.findByRole("heading", { level: 2, name: "Choose a corpus" }, T)).toBeInTheDocument()
    expect(screen.getByText("Step 3 of 6")).toBeInTheDocument()
    const steps = screen.getByRole("navigation", { name: "Steps" })
    expect(within(steps).getByRole("link", { name: "Corpus" })).toHaveAttribute("aria-current", "step")
    const footer = screen.getByRole("navigation", { name: "Step navigation" })
    expect(within(footer).getByRole("button", { name: "Next: Run" })).toBeDisabled()
    expect(within(footer).getByText("Choose a corpus to go on.")).toBeInTheDocument()
    const table = await screen.findByRole("table", { name: "Corpora" }, T)
    await user.click(within(table).getByRole("button", { name: `Use ${MIXED}` }))
    // the stepper names the chosen corpus, and Next goes on to the run step with the choice kept
    expect(await within(steps).findByRole("link", { name: `Corpus: ${MIXED}` }, T)).toBeInTheDocument()
    await user.click(within(footer).getByRole("link", { name: "Next: Run" }))
    await waitFor(() => expect(router.state.location.pathname).toBe("/flow/rag-factuality/run"))
    expect(new URLSearchParams(router.state.location.search).get("corpus")).toBe(MIXED)
    expect(within(footer).getByRole("link", { name: "Back: Corpus" })).toBeInTheDocument()
  })

  it("a non-effect baseline shows its summary beside the answer", async () => {
    const id = `rag-baseline~${MIXED}`
    const detail = evFixture<EvRunDetail>(`/api/ev/runs/${id}`)
    server.use(http.get(`/api/ev/runs/${encodeURIComponent(id)}`, () => HttpResponse.json({ ...detail,
      answer: { kind: "inventory", system: "rag-baseline", target: "dataset", entries: [
        { name: "SQuAD", aliases: [], papers: ["S001"], items: [] }, { name: "NQ", aliases: [], papers: ["S002"], items: [] }] } })))
    renderRoutes(routes, `/flow/rag-factuality/answer?corpus=${MIXED}&run=cascade-gaps~${MIXED}`)
    expect(await screen.findByText("2 entries", {}, T)).toBeInTheDocument()
  })

  it("goes question → protocol → corpus → run → graph → answer, keeping the choices in the URL", async () => {
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, "/flow/rag-factuality")
    expect(await screen.findByRole("heading", { name: QUESTION }, T)).toBeInTheDocument()
    const steps = screen.getByRole("navigation", { name: "Steps" })
    expect(within(steps).getAllByRole("link").map((a) => a.textContent)).toEqual([
      "Question", expect.stringContaining("Protocol"), expect.stringContaining("Corpus"), expect.stringContaining("Run"),
      expect.stringContaining("Evidence graph"), expect.stringContaining("Answer")])
    // the hand-written protocol is the default; the agentic variant and the frozen proposal can be chosen
    expect(await screen.findByText(/Chosen: hand-written rag-factuality./, {}, T)).toBeInTheDocument()
    await user.click(await screen.findByRole("button", { name: "Use protocol rag-factuality-agentic" }, T))
    await waitFor(() => expect(new URLSearchParams(router.state.location.search).get("protocol")).toBe("repo:rag-factuality-agentic"))
    await user.click(screen.getByRole("button", { name: "Use protocol rag-factuality" }))
    // the run step needs a corpus
    await user.click(within(steps).getByRole("link", { name: /Run/ }))
    expect(await screen.findByText("Choose a protocol and a corpus first", {}, T)).toBeInTheDocument()
    await user.click(within(steps).getByRole("link", { name: /Corpus/ }))
    const table = await screen.findByRole("table", { name: "Corpora" }, T)
    await user.click(within(table).getByRole("button", { name: `Use ${MIXED}` }))
    await waitFor(() => expect(new URLSearchParams(router.state.location.search).get("corpus")).toBe(MIXED))
    expect(within(steps).getByRole("link", { name: /Corpus/ })).toHaveTextContent(MIXED)
    // the run step lists the runs on the corpus; choosing one feeds the last three steps
    await user.click(within(steps).getByRole("link", { name: /Run/ }))
    const runs = await screen.findByRole("table", { name: "Runs on the corpus" }, T)
    expect(within(runs).getByRole("link", { name: `rag-baseline~${MIXED}` })).toBeInTheDocument()
    await user.click(within(runs).getByRole("button", { name: `Choose cascade-gaps~${MIXED}` }))
    await waitFor(() => expect(new URLSearchParams(router.state.location.search).get("run")).toBe(`cascade-gaps~${MIXED}`))
    await user.click(within(steps).getByRole("link", { name: /Answer/ }))
    expect(await screen.findByText(/Beside it: the baselines on/, {}, T)).toBeInTheDocument()
    await user.click(within(steps).getByRole("link", { name: /Evidence graph/ }))
    expect(await screen.findByText(/Open in the run page/, {}, T)).toBeInTheDocument()
  })

  it("starts a run with the form's choices, follows its job and fills the run in", async () => {
    const user = userEvent.setup()
    const bodies = recordJobs()
    const { router } = renderRoutes(routes, `/flow/rag-factuality/run?corpus=${PARA}`)
    await screen.findByRole("form", { name: "Start the engine" }, T)
    await choose(user, "Strategy", /gaps: the funnel/)
    expect(screen.getByText(`runs/cascade-gaps/${PARA}`)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Start run" }))
    await waitFor(() => expect(bodies.map((b) => b.kind)).toEqual(["run"]))
    expect(bodies[0].body).toEqual({ corpus: PARA, protocol: { source: "repo", name: "rag-factuality" }, extractors: "cascade", strategy: "gaps",
      model: "orch-model", group: null, name: null, retry_errors: false } satisfies JobRequests["run"])
    await waitFor(() => expect(new URLSearchParams(router.state.location.search).get("run")).toBe(`cascade-gaps~${PARA}`))
    const job = await screen.findByLabelText(`Job engine run cascade-gaps~${PARA}`, {}, T)
    expect(within(job).getAllByText("running").length).toBeGreaterThan(0)
    expect(await within(job).findByLabelText(/Log of job/, {}, T)).toHaveTextContent("$ python -m webapp.tool run")
  })

  it("starts both baselines and scores a finished engine run", async () => {
    const user = userEvent.setup()
    const bodies = recordJobs()
    renderRoutes(routes, `/flow/rag-factuality/run?corpus=${MIXED}`)
    const rag = await screen.findByRole("button", { name: /RAG baseline/ }, T)
    expect(rag).toBeDisabled()   // the world has its answer on this corpus
    await user.click(screen.getByRole("button", { name: `Score cascade~${MIXED}` }))
    await waitFor(() => expect(bodies).toEqual([{ kind: "score", body: { run: `cascade~${MIXED}` } }]))
    await user.click(screen.getByRole("button", { name: /Compare the scored runs/ }))
    await waitFor(() => expect(bodies.at(-1)?.kind).toBe("compare"))
    expect((bodies.at(-1)?.body as JobRequests["compare"]).name).toBe(`compare-${MIXED}`)
  })

  it("starts the baselines of the selected question, in a run of their own", async () => {
    const user = userEvent.setup()
    const bodies = recordJobs()
    server.use(http.get("/api/ev/questions/inv-metrics", () => HttpResponse.json({ id: "inv-metrics",
      question: "Which evaluation metrics do the papers report?", kind: "inventory", protocol: "rag-factuality",
      agentic_protocol: null, proposals: [] })))
    renderRoutes(routes, `/flow/inv-metrics/run?corpus=${MIXED}`)
    const rag = await screen.findByRole("button", { name: /RAG baseline/ }, T)
    expect(rag).toBeEnabled()   // the world's answer on this corpus is the factuality question's
    expect(screen.getByText(new RegExp(`runs/<baseline>/${MIXED}\\.inv-metrics`))).toBeInTheDocument()
    await user.click(rag)
    await waitFor(() => expect(bodies).toEqual([{ kind: "rag-baseline", body: { corpus: MIXED, question: "inv-metrics",
      model: "orch-model", retrieval: "global", k: 8 } satisfies JobRequests["rag-baseline"] }]))
  })

  it("builds a template corpus with the knobs and no LLM renderer", async () => {
    const user = userEvent.setup()
    const bodies = recordJobs()
    renderRoutes(routes, "/flow/rag-factuality/corpus")
    const form = await screen.findByRole("form", { name: "Build a template corpus" }, T)
    expect(within(form).getByText(/build them on Slurm/)).toBeInTheDocument()
    await user.type(within(form).getByLabelText("Name"), "ui-set")
    await user.click(within(form).getByRole("button", { name: "complex" }))
    await user.click(within(form).getByRole("button", { name: "contradictory" }))
    await user.clear(within(form).getByLabelText("duplicates"))
    await user.type(within(form).getByLabelText("duplicates"), "2")
    await user.click(within(form).getByRole("button", { name: "Build template corpus" }))
    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0].body).toEqual({ name: "ui-set", seed: 1, studies: 20, levels: ["explicit", "paraphrased", "distributed"],
      duplicates: 2, missing: 0, outliers: 0, irrelevant: 0 })
  })
})

describe("the cards form", () => {
  async function openProposal() {
    const job = await evApi.startJob("propose", { proposal: "p1", question: "rag-factuality" })
    finishJob(job.id)
    return renderRoutes(routes, "/flow/rag-factuality/protocol?proposal=p1")
  }

  it("proposes a protocol as one job for the selected question", async () => {
    const user = userEvent.setup()
    const bodies = recordJobs()
    const { router } = renderRoutes(routes, "/flow/rag-factuality/protocol")
    await user.click(await screen.findByRole("button", { name: "Propose a protocol" }, T))
    await waitFor(() => expect(bodies).toEqual([{ kind: "propose", body: { proposal: "rag-factuality-p1", question: "rag-factuality", model: "orch-model" } }]))
    await waitFor(() => expect(new URLSearchParams(router.state.location.search).get("proposal")).toBe("rag-factuality-p1"))
    expect(await screen.findByLabelText("Job proposal rag-factuality-p1", {}, T)).toBeInTheDocument()
  })

  it("decides cards with reasons, saves decisions.yaml's entries and freezes", async () => {
    const user = userEvent.setup()
    const puts: DecisionsRequest[] = []
    server.events.on("request:start", async ({ request }) => {
      if (request.method === "PUT") puts.push((await request.clone().json()) as DecisionsRequest)
    })
    const bodies = recordJobs()
    await openProposal()
    const card = await screen.findByRole("group", { name: /Smallest effect that counts/ }, T)
    expect(within(card).getByText("model's default")).toBeInTheDocument()
    await choose(user, "Choice for min_effect", /^lenient/)
    expect(within(card).getByText("decided by aditya")).toBeInTheDocument()
    const reason = within(card).getByLabelText("Reason (required)")
    await user.clear(reason)
    expect(reason).toHaveAccessibleDescription(/a reason is required/)   // under the field, no alert
    expect(screen.getByRole("button", { name: "Save decisions" })).toBeDisabled()
    await user.type(reason, "two points is the noise between runs")
    expect(screen.getByRole("button", { name: "Freeze" })).toBeDisabled()   // unsaved
    await user.click(screen.getByRole("button", { name: "Save decisions" }))
    await waitFor(() => expect(puts).toHaveLength(1))
    expect(puts[0].decisions).toHaveLength(8)
    expect(puts[0].decisions.find((d) => d.card === "min_effect")).toEqual({ card: "min_effect", choice: "lenient", reason: "two points is the noise between runs", by: "aditya", value: null })
    expect(puts[0].decisions.find((d) => d.card === "screen")).toMatchObject({ by: "model" })
    await waitFor(() => expect(screen.getByRole("button", { name: "Freeze" })).toBeEnabled())
    await user.click(screen.getByRole("button", { name: "Freeze" }))
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Freeze" }))   // confirmed
    await waitFor(() => expect(bodies.at(-1)).toEqual({ kind: "freeze", body: { proposal: "p1" } }))
  })

  it("shows what freeze would refuse and keeps Freeze off", async () => {
    const user = userEvent.setup()
    server.use(http.put("/api/ev/proposals/p1/decisions", () =>
      HttpResponse.json({ written: "/srv/ev/proposals/p1/decisions.yaml", problems: ["min_effect: choice 'lenient' is not the model's default ('draft'); set `by` to who decided"] })))
    await openProposal()
    await screen.findByRole("group", { name: /Smallest effect that counts/ }, T)
    await user.click(screen.getByRole("button", { name: "Save decisions" }))
    expect(await screen.findByText("decisions.yaml: freeze would refuse it", {}, T)).toBeInTheDocument()
    expect(screen.getByText(/not the model's default/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Freeze" })).toBeDisabled()
  })

  it("a custom value is JSON in the card's shape", async () => {
    const user = userEvent.setup()
    const puts: DecisionsRequest[] = []
    server.events.on("request:start", async ({ request }) => {
      if (request.method === "PUT") puts.push((await request.clone().json()) as DecisionsRequest)
    })
    await openProposal()
    const card = await screen.findByRole("group", { name: /Pairing preference/ }, T)
    await choose(user, "Choice for pairing", /^custom/)
    const value = within(card).getByLabelText(/Custom value/)
    await user.clear(value)
    await user.type(value, "not json")
    expect(within(card).queryByText(/not JSON/)).toBeNull()   // not while typing
    await user.tab()
    expect(value).toHaveAccessibleDescription(/not JSON/)
    await user.clear(value)
    await user.click(value)
    await user.paste('{"prefer": ["document_order"]}')
    await user.click(screen.getByRole("button", { name: "Save decisions" }))
    await waitFor(() => expect(puts).toHaveLength(1))
    expect(puts[0].decisions.find((d) => d.card === "pairing")).toMatchObject({ choice: "custom", value: { prefer: ["document_order"] }, by: "aditya" })
  })
})

describe("what the review asked for", () => {
  it("a decisions.yaml changed since the form loaded it is not overwritten unseen", async () => {
    const user = userEvent.setup()
    const puts: DecisionsRequest[] = []
    server.events.on("request:start", async ({ request }) => {
      if (request.method === "PUT") puts.push((await request.clone().json()) as DecisionsRequest)
    })
    const job = await evApi.startJob("propose", { proposal: "p1", question: "rag-factuality" })
    finishJob(job.id)
    renderRoutes(routes, "/flow/rag-factuality/protocol?proposal=p1")
    await screen.findByRole("group", { name: /Smallest effect that counts/ }, T)
    // another tab writes the file after this form loaded it
    const loaded = await evApi.proposal("p1")
    await evApi.putDecisions("p1", { decisions: [], base_sha256: loaded.decisions_sha256 })
    await choose(user, "Choice for min_effect", /^lenient/)
    await user.click(screen.getByRole("button", { name: "Save decisions" }))
    expect(await screen.findByText(/changed since this form loaded it/, {}, T)).toBeInTheDocument()
    expect(puts.at(-1)).toMatchObject({ base_sha256: "sha-0", force: false })
    await user.click(screen.getByRole("button", { name: /Overwrite it/ }))
    await waitFor(() => expect(puts.at(-1)).toMatchObject({ force: true }))
    await waitFor(() => expect(screen.queryByText(/changed since this form loaded it/)).toBeNull())
  })

  it("an untouched card keeps the name decisions.yaml has for it", async () => {
    const user = userEvent.setup()
    const puts: DecisionsRequest[] = []
    server.events.on("request:start", async ({ request }) => {
      if (request.method === "PUT") puts.push((await request.clone().json()) as DecisionsRequest)
    })
    const p = unfrozenProposal("p1")
    p.cards = p.cards.map((c) => (c.id === "pairing" ? { ...c, decision: { ...c.decision!, by: "tim", reason: "hand edit" } } : c))
    server.use(http.get("/api/ev/proposals/p1", () => HttpResponse.json(p)))
    renderRoutes(routes, "/flow/rag-factuality/protocol?proposal=p1")
    const card = await screen.findByRole("group", { name: /Pairing preference/ }, T)
    expect(within(card).getByText("decided by tim")).toBeInTheDocument()
    server.use(http.put("/api/ev/proposals/p1/decisions", () => HttpResponse.json({ written: "x", sha256: "s", problems: [] })))
    await user.click(screen.getByRole("button", { name: "Save decisions" }))
    await waitFor(() => expect(puts).toHaveLength(1))
    expect(puts[0].decisions.find((d) => d.card === "pairing")).toMatchObject({ by: "tim", reason: "hand edit" })
  })

  it("a model job the backend refuses (no key, no gateway) says why; regex-only still starts", async () => {
    const user = userEvent.setup()
    mockGateway.ok = false
    renderRoutes(routes, `/flow/rag-factuality/run?corpus=${PARA}`)
    await screen.findByRole("form", { name: "Start the engine" }, T)
    expect(screen.getByText(/model jobs are refused/)).toBeInTheDocument()   // the mock config has no key
    await user.click(screen.getByRole("button", { name: "Start run" }))
    expect(await screen.findByText(/model job refused: no \$LITELLM_MASTER_KEY/, {}, T)).toBeInTheDocument()
    await choose(user, "Extractors", /regex only/)
    await user.click(screen.getByRole("button", { name: "Start run" }))
    expect(await screen.findByLabelText(`Job engine run regex-only~${PARA}`, {}, T)).toBeInTheDocument()
  })

  it("retry errors maps to the flag, and a run done with failed calls says so", async () => {
    const user = userEvent.setup()
    const bodies = recordJobs()
    renderRoutes(routes, `/flow/rag-factuality/run?corpus=${PARA}`)
    await screen.findByRole("form", { name: "Start the engine" }, T)
    await user.click(screen.getByRole("switch", { name: "Retry errors" }))
    await user.click(screen.getByRole("button", { name: "Start run" }))
    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0].body).toMatchObject({ retry_errors: true })
    const job = (await evApi.jobs())[0]
    finishJob(job.id, "done", 3)
    renderRoutes(routes, `/jobs/${job.id}`)
    expect((await screen.findAllByText("done with 3 failed calls", {}, T)).length).toBeGreaterThan(0)
    expect(await screen.findByText(/3 extractor call\(s\) ended in an error/, {}, T)).toHaveAttribute("role", "alert")
  })

  it("choosing another protocol clears the chosen run", async () => {
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, `/flow/rag-factuality/protocol?corpus=${MIXED}&run=cascade~${MIXED}`)
    await user.click(await screen.findByRole("button", { name: "Use protocol rag-factuality-agentic" }, T))
    await waitFor(() => expect(new URLSearchParams(router.state.location.search).get("protocol")).toBe("repo:rag-factuality-agentic"))
    const params = new URLSearchParams(router.state.location.search)
    expect(params.get("run")).toBeNull()
    expect(params.get("corpus")).toBe(MIXED)
  })
})

describe("the Jobs page", () => {
  it("lists the jobs, opens one with its log and cancels it", async () => {
    const user = userEvent.setup()
    const job = await evApi.startJob("rag-baseline", { corpus: PARA, question: "rag-factuality" })
    renderRoutes(routes, `/jobs/${job.id}`)
    const table = await screen.findByRole("table", { name: "Jobs" }, T)
    expect(within(table).getByText(`RAG baseline rag-baseline~${PARA}`)).toBeInTheDocument()
    const panels = await screen.findAllByLabelText(`Job RAG baseline rag-baseline~${PARA}`, {}, T)
    expect(await within(panels[0]).findByLabelText(/Log of job/, {}, T)).toHaveTextContent("mock rag-baseline working")
    await user.click(within(panels[0]).getByRole("button", { name: "Cancel" }))
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Cancel job" }))
    await waitFor(() => expect(within(table).getByText(/cancelled/)).toBeInTheDocument(), T)
  })
})

describe("the question-first flow", () => {
  const SERIOUS = { check: "screen_terms", severity: "serious", message: "no screen term appears in any paper", card: "screen" } as const
  const ADVISORY = { check: "metric_names", severity: "advisory", message: "one metric has no synonym", card: "metrics" } as const

  async function openProposal(kind?: "inventory") {
    const job = await evApi.startJob("propose", { proposal: "p1", question: "rag-factuality" })
    finishJob(job.id)
    if (kind) {
      const k = await evApi.putKind("p1", { kind })
      finishJob(k.id)
    }
    return renderRoutes(routes, "/flow/rag-factuality/protocol?proposal=p1")
  }

  it("typed question starts propose job", async () => {
    const user = userEvent.setup()
    const bodies = recordJobs()
    const { router } = renderRoutes(routes, "/")
    const form = await screen.findByRole("form", { name: "Your own question" }, T)
    const send = within(form).getByRole("button", { name: "Propose a protocol" })
    expect(send).toBeDisabled()   // too short to be a question
    await user.type(within(form).getByLabelText("Question"), "Which retriever is best on long documents?")
    await user.click(send)
    await waitFor(() => expect(bodies).toEqual([{ kind: "propose", body: { proposal: "typed-p1", text: "Which retriever is best on long documents?", model: "orch-model" } }]))
    await waitFor(() => expect(router.state.location.pathname).toBe("/flow/typed/protocol"))
    expect(new URLSearchParams(router.state.location.search).get("proposal")).toBe("typed-p1")
    expect(await screen.findByLabelText("Job proposal typed-p1", {}, T)).toBeInTheDocument()
  })

  it("kind change reloads cards", async () => {
    const user = userEvent.setup()
    const kinds: unknown[] = []
    server.events.on("request:start", async ({ request }) => {
      if (request.method === "PUT" && request.url.endsWith("/kind")) kinds.push(await request.clone().json())
    })
    await openProposal()
    expect(await screen.findByRole("group", { name: /Pairing preference/ }, T)).toBeInTheDocument()
    const confirm = screen.getByRole("region", { name: "Kind of question" })
    expect(within(confirm).getByText(/The model reads this as an effect question/)).toBeInTheDocument()
    await choose(user, "Kind", /inventory/)
    await user.click(within(confirm).getByRole("button", { name: "Use this kind" }))
    await waitFor(() => expect(kinds).toEqual([{ kind: "inventory", model: "orch-model" }]))
    expect(await screen.findByLabelText(/Job proposal p1/, {}, T)).toBeInTheDocument()
    expect(screen.queryByRole("group", { name: /Pairing preference/ })).toBeNull()   // the old cards are gone while it drafts again
    finishJob((await evApi.jobs())[0].id)
    expect(await screen.findByText(/You said this is an inventory question/, {}, T)).toBeInTheDocument()
    expect(await screen.findByRole("group", { name: /Smallest effect that counts/ }, T)).toBeInTheDocument()
    expect(screen.queryByRole("group", { name: /Pairing preference/ })).toBeNull()   // the inventory card set has no pairing card
  })

  it("keeps the advanced cards collapsed and shows the checker's problems, advisory ones apart", async () => {
    mockCheck.problems = [SERIOUS, ADVISORY]
    await openProposal()
    const advanced = (await screen.findByText(/Advanced cards/, {}, T)).closest("details")!
    expect(advanced).not.toHaveAttribute("open")
    expect(within(advanced).getByRole("group", { name: /cascade/i, hidden: true })).toBeInTheDocument()
    const panel = await screen.findByRole("region", { name: "Checker" }, T)
    expect(await within(panel).findByText(/no screen term appears in any paper/, {}, T)).toBeInTheDocument()
    expect(within(panel).getByText("must be fixed or waived")).toBeInTheDocument()
    expect(within(panel).getByText(/one metric has no synonym/)).toBeInTheDocument()
    expect(within(panel).getByText("worth a look")).toBeInTheDocument()
  })

  it("serious problem blocks freeze until waiver reason", async () => {
    const user = userEvent.setup()
    mockCheck.problems = [SERIOUS, ADVISORY]
    const puts: DecisionsRequest[] = []
    server.events.on("request:start", async ({ request }) => {
      if (request.method === "PUT") puts.push((await request.clone().json()) as DecisionsRequest)
    })
    const bodies = recordJobs()
    await openProposal()
    const panel = await screen.findByRole("region", { name: "Checker" }, T)
    await within(panel).findByText(/no screen term appears/, {}, T)
    await user.click(screen.getByRole("button", { name: "Save decisions" }))
    await waitFor(() => expect(screen.getByRole("button", { name: "Freeze" })).toBeEnabled())
    await user.click(screen.getByRole("button", { name: "Freeze" }))
    const dialog = await screen.findByRole("dialog", { name: /Waive/ }, T)
    expect(within(dialog).getByText(/no screen term appears in any paper/)).toBeInTheDocument()
    expect(within(dialog).queryByText(/one metric has no synonym/)).toBeNull()   // advisory problems need no waiver
    const go = within(dialog).getByRole("button", { name: "Waive and freeze" })
    expect(go).toBeDisabled()
    const reason = within(dialog).getByLabelText("Reason for waiving screen_terms")
    await user.type(reason, "too short")   // 9 characters
    expect(go).toBeDisabled()
    expect(reason).toHaveAccessibleDescription(/at least 10 characters/)
    await user.type(reason, "!")
    await waitFor(() => expect(go).toBeEnabled())
    await user.click(go)
    await waitFor(() => expect(bodies.at(-1)).toEqual({ kind: "freeze", body: { proposal: "p1" } }))
    expect(puts.at(-1)?.waivers).toEqual([{ check: "screen_terms", reason: "too short!" }])
  })

  it("a plain save keeps the waivers decisions.yaml already holds", async () => {
    const user = userEvent.setup()
    mockCheck.problems = [ADVISORY]
    const job = await evApi.startJob("propose", { proposal: "p1", question: "rag-factuality" })
    finishJob(job.id)
    const loaded = await evApi.proposal("p1")
    await evApi.putDecisions("p1", { decisions: [], waivers: [{ check: "screen_terms", reason: "accepted earlier on" }], base_sha256: loaded.decisions_sha256 })
    const puts: DecisionsRequest[] = []
    server.events.on("request:start", async ({ request }) => {
      if (request.method === "PUT") puts.push((await request.clone().json()) as DecisionsRequest)
    })
    renderRoutes(routes, "/flow/rag-factuality/protocol?proposal=p1")
    await screen.findByRole("group", { name: /Smallest effect that counts/ }, T)
    await user.click(screen.getByRole("button", { name: "Save decisions" }))
    await waitFor(() => expect(puts.length).toBeGreaterThan(0))
    expect(puts.at(-1)?.waivers).toEqual([{ check: "screen_terms", reason: "accepted earlier on" }])
  })

  it("a proposal with no serious problem freezes without the waiver dialog", async () => {
    const user = userEvent.setup()
    mockCheck.problems = [ADVISORY]
    await openProposal()
    await screen.findByRole("group", { name: /Smallest effect that counts/ }, T)
    await user.click(screen.getByRole("button", { name: "Save decisions" }))
    await waitFor(() => expect(screen.getByRole("button", { name: "Freeze" })).toBeEnabled())
    await user.click(screen.getByRole("button", { name: "Freeze" }))
    expect(await screen.findByRole("alertdialog")).toBeInTheDocument()
    expect(screen.queryByRole("dialog", { name: /Waive/ })).toBeNull()
  })

  it("preview highlights hits", async () => {
    const user = userEvent.setup()
    await openProposal()
    const panel = await screen.findByRole("region", { name: "Paper preview" }, T)
    await choose(user, "Corpus", MIXED)
    await choose(user, "Paper", /S001/)
    const hit = await within(panel).findByText("Retrieval", { selector: "mark" }, T)
    expect(hit).toHaveAttribute("title", "screen: Retrieval")
    expect(panel).toHaveTextContent("Paper S001. Retrieval raised accuracy in this study.")
  })
})
