/** The guided flow against the mock backend: the stepper, the jobs it starts, the cards form, the Jobs page. */
import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { afterEach, beforeAll, describe, expect, it } from "vitest"

import { evApi, type DecisionsRequest, type JobRequests } from "@/api/ev"
import { routes } from "@/app/routes"
import { finishJob } from "@/mocks/handlers"
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
  it("goes question → protocol → corpus → run → graph → answer → scores, keeping the choices in the URL", async () => {
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, "/flow/rag-factuality")
    expect(await screen.findByRole("heading", { name: QUESTION }, T)).toBeInTheDocument()
    const steps = screen.getByRole("navigation", { name: "Steps" })
    expect(within(steps).getAllByRole("link").map((a) => a.textContent)).toEqual([
      "Question", expect.stringContaining("Protocol"), expect.stringContaining("Corpus"), expect.stringContaining("Run"),
      expect.stringContaining("Evidence graph"), expect.stringContaining("Answer"), expect.stringContaining("Scores")])
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
    await user.click(within(steps).getByRole("link", { name: /Scores/ }))
    expect(await screen.findByRole("table", { name: "C. Synthesis per system" }, T)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "The full report" })).toHaveAttribute("href", `/scores/reports/cascade-gaps~${MIXED}`)
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
      model: "orch-model", group: null, name: null } satisfies JobRequests["run"])
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
    expect(within(card).getByRole("alert")).toHaveTextContent("a reason is required")
    expect(screen.getByRole("button", { name: "Save decisions" })).toBeDisabled()
    await user.type(reason, "two points is the noise between runs")
    expect(screen.getByRole("button", { name: "Freeze" })).toBeDisabled()   // unsaved
    await user.click(screen.getByRole("button", { name: "Save decisions" }))
    await waitFor(() => expect(puts).toHaveLength(1))
    expect(puts[0].decisions).toHaveLength(8)
    expect(puts[0].decisions.find((d) => d.card === "min_effect")).toEqual({ card: "min_effect", choice: "lenient", reason: "two points is the noise between runs", by: "user", value: null })
    expect(puts[0].decisions.find((d) => d.card === "screen")).toMatchObject({ by: "model" })
    await waitFor(() => expect(screen.getByRole("button", { name: "Freeze" })).toBeEnabled())
    await user.click(screen.getByRole("button", { name: "Freeze" }))
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
    expect(within(card).getByRole("alert")).toHaveTextContent("not JSON")
    await user.clear(value)
    await user.click(value)
    await user.paste('{"prefer": ["document_order"]}')
    await user.click(screen.getByRole("button", { name: "Save decisions" }))
    await waitFor(() => expect(puts).toHaveLength(1))
    expect(puts[0].decisions.find((d) => d.card === "pairing")).toMatchObject({ choice: "custom", value: { prefer: ["document_order"] }, by: "user" })
  })
})

describe("the Jobs page", () => {
  it("lists the jobs, opens one with its log and cancels it", async () => {
    const user = userEvent.setup()
    const job = await evApi.startJob("rag-baseline", { corpus: PARA })
    renderRoutes(routes, `/jobs/${job.id}`)
    const table = await screen.findByRole("table", { name: "Jobs" }, T)
    expect(within(table).getByText(`RAG baseline rag-baseline~${PARA}`)).toBeInTheDocument()
    const panels = await screen.findAllByLabelText(`Job RAG baseline rag-baseline~${PARA}`, {}, T)
    expect(await within(panels[0]).findByLabelText(/Log of job/, {}, T)).toHaveTextContent("mock rag-baseline working")
    await user.click(within(panels[0]).getByRole("button", { name: "Cancel" }))
    await waitFor(() => expect(within(table).getByText(/cancelled/)).toBeInTheDocument(), T)
  })
})
