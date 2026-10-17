/** The evidence-level pages against the mock backend, whose responses are the real backend's on a world made by the real tools. */
import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { beforeAll, describe, expect, it } from "vitest"

import type { CallDetail, CorpusDetail, EvRunDetail, ProposalDetail } from "@/api/ev"
import { routes } from "@/app/routes"
import { evFixture } from "@/mocks/ev"
import { server } from "@/mocks/node"
import { renderRoutes } from "@/test/render"

const T = { timeout: 15_000 }
const MIXED = "rag-tpl-w1-mixed"
const EXPLICIT = "rag-tpl-w1-explicit"
const VARIANT = "rag-tpl-w1-mixed-cf-S002-contradicts"
const run = (id: string) => `/runs/${encodeURIComponent(id)}`

beforeAll(async () => {
  await Promise.all([
    import("@/pages/ev/HomePage"), import("@/pages/ev/CorporaPage"), import("@/pages/ev/CorpusPage"), import("@/pages/ev/CorpusPaperPage"),
    import("@/pages/ev/ProtocolsPage"), import("@/pages/ev/ProtocolPage"), import("@/pages/ev/ProposalPage"), import("@/pages/ev/RunsPage"),
    import("@/pages/ev/RunPage"), import("@/pages/ev/RunPaperPage"), import("@/pages/ev/ScoresPage"), import("@/pages/ev/ReportPage"),
    import("@/pages/ev/ComparePage"), import("@/pages/ev/ShiftPage"), import("@/pages/ev/BenchmarkPage"), import("@/pages/OverviewPage"),
  ])
}, 180_000)

describe("the flow", () => {
  it("home maps the steps with what is on disk, and the earlier work apart", async () => {
    renderRoutes(routes, "/")
    expect(await screen.findByRole("heading", { name: "Evidence-level flow" }, T)).toBeInTheDocument()
    expect(await screen.findByText("Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?", {}, T)).toBeInTheDocument()
    for (const step of ["Protocol", "Corpora", "Runs", "Scores"]) expect(screen.getAllByRole("link", { name: step }).length).toBeGreaterThan(0)
    expect(await screen.findByText(/4 corpora/, {}, T)).toBeInTheDocument()
    const nav = screen.getAllByRole("link", { name: /Earlier work|Questions/ })
    expect(nav.some((a) => a.getAttribute("href") === "/earlier")).toBe(true)
    expect(screen.getByText("/srv/ev")).toBeInTheDocument()
  })

  it("the earlier work keeps its pages under /earlier, framed as such", async () => {
    renderRoutes(routes, "/earlier")
    expect(await screen.findByRole("heading", { name: "Overview" }, T)).toBeInTheDocument()
    expect(screen.getByText(/dropped as a study on 16 Oct/)).toBeInTheDocument()
    const links = await screen.findAllByRole("link", { name: /q01/ }, T)
    expect(links.every((a) => a.getAttribute("href")?.startsWith("/earlier/"))).toBe(true)
  })
})

describe("corpora", () => {
  it("lists every corpus with level, knobs and the variant", async () => {
    renderRoutes(routes, "/corpora")
    const table = await screen.findByRole("table", { name: "Corpora" }, T)
    expect(within(table).getByRole("link", { name: MIXED })).toHaveAttribute("href", `/corpora/${MIXED}`)
    expect(within(table).getAllByText("duplicates 1, missing 1, irrelevant 1").length).toBeGreaterThan(0)
    expect(within(table).getByText(/S002: supports → contradicts/)).toBeInTheDocument()
  })

  it("a corpus shows its papers, the expected answer and the runs on it", async () => {
    const corpus = evFixture<CorpusDetail>(`/api/ev/corpora/${MIXED}`)
    renderRoutes(routes, `/corpora/${MIXED}`)
    const papers = await screen.findByRole("table", { name: "Papers" }, T)
    expect(within(papers).getAllByRole("row")).toHaveLength(corpus.papers_list.length + 1)
    expect(within(papers).getByText("irrelevant")).toBeInTheDocument()
    expect(await screen.findAllByRole("link", { name: /cascade-gaps/ }, T)).not.toHaveLength(0)
  })

  it("a variant names its base and its prediction", async () => {
    renderRoutes(routes, `/corpora/${VARIANT}`)
    expect(await screen.findByText("Counterfactual variant", {}, T)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: MIXED })).toHaveAttribute("href", `/corpora/${MIXED}`)
    expect(screen.getByText("mixed → refuted")).toBeInTheDocument()
  })

  it("a paper marks every placement of the ground truth", async () => {
    const { container } = renderRoutes(routes, `/corpora/${MIXED}/papers/S001`)
    await screen.findByLabelText("Text of S001", {}, T)
    const marks = container.querySelectorAll("mark")
    expect(marks.length).toBeGreaterThan(3)
    expect([...marks].some((m) => m.getAttribute("data-marks")?.includes("S001.m"))).toBe(true)
    expect(screen.getByRole("table", { name: "Fidelity checks" })).toBeInTheDocument()
  })
})

describe("protocol and proposals", () => {
  it("lists the hand-written protocols and the proposals", async () => {
    renderRoutes(routes, "/protocol")
    expect(await screen.findByText("frozen, revision 2", {}, T)).toBeInTheDocument()
    const links = (await screen.findAllByRole("link", { name: "rag-factuality" }, T)).map((a) => a.getAttribute("href"))
    expect(links).toEqual(expect.arrayContaining(["/protocol/rag-factuality", "/proposals/rag-factuality"]))
  })

  it("shows a protocol's types, cascade and synthesis rules", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, "/protocol/rag-factuality")
    expect(await screen.findByText("0: regex_condition", {}, T)).toBeInTheDocument()
    await user.click(screen.getByRole("tab", { name: "Synthesis" }))
    const table = await screen.findByRole("table", { name: "Label decision table" })
    expect(within(table).getByText("supporting >0 and contradicting >0")).toBeInTheDocument()
    expect(within(table).getByText("otherwise")).toBeInTheDocument()
    expect(screen.getByText("factual_accuracy")).toBeInTheDocument()
  })

  it("a proposal shows each card's decision, who took it and why", async () => {
    const p = evFixture<ProposalDetail>("/api/ev/proposals/rag-factuality")
    const reason = p.cards.find((c) => c.id === "min_effect")!.decision!.reason!
    renderRoutes(routes, "/proposals/rag-factuality")
    expect(await screen.findByText("decided by aditya", {}, T)).toBeInTheDocument()
    expect(screen.getAllByText("decided by model")).toHaveLength(7)
    expect(screen.getByText(new RegExp(reason.slice(0, 30)))).toBeInTheDocument()
    expect(screen.getByText("changed from the default")).toBeInTheDocument()
  })

  it("a hand-edited decisions.yaml freeze would refuse: the problems and the raw entry, not an error", async () => {
    const p = evFixture<ProposalDetail>("/api/ev/proposals/rag-factuality")
    const problem = "min_effect: choice must be an option id (draft, strict) or `custom`, not 5"
    const edited: ProposalDetail = {
      ...p, frozen: false, proposal: null, protocol: null, decision_problems: [problem],
      cards: p.cards.map((c) => (c.id === "min_effect" ? { ...c, decision: null, raw_decision: { card: "min_effect", choice: 5 }, problems: [problem] } : c)),
    }
    server.use(http.get("/api/ev/proposals/rag-factuality", () => HttpResponse.json(edited)))
    renderRoutes(routes, "/proposals/rag-factuality")
    expect(await screen.findByText("decisions.yaml: freeze would refuse it", {}, T)).toBeInTheDocument()
    expect(screen.getByRole("list", { name: "Problems of min_effect" })).toHaveTextContent(problem)
    expect(screen.getByLabelText("raw decision of min_effect")).toHaveTextContent('"choice": 5')
    expect(screen.getByText("freeze would refuse")).toBeInTheDocument()
  })

  it("a proposal's amendments", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, "/proposals/rag-factuality")
    await user.click(await screen.findByRole("tab", { name: "Amendments" }, T))
    const table = await screen.findByRole("table", { name: "Amendments" })
    expect(within(table).getByText("synthesis.flags.large_effect.factor")).toBeInTheDocument()
  })
})

describe("runs", () => {
  it("lists runs by corpus, the baselines beside the engine", async () => {
    renderRoutes(routes, "/runs")
    const table = await screen.findByRole("table", { name: `Runs on ${MIXED}` }, T)
    expect(within(table).getByRole("link", { name: "cascade-gaps" })).toHaveAttribute("href", run(`cascade-gaps~${MIXED}`))
    expect(within(table).getByText("RAG baseline")).toBeInTheDocument()
  })

  it("a run's answer lists every study with its direction and the funnel", async () => {
    const detail = evFixture<EvRunDetail>(`/api/ev/runs/cascade-gaps~${MIXED}`)
    renderRoutes(routes, run(`cascade-gaps~${MIXED}`))
    const studies = await screen.findByRole("table", { name: "Studies" }, T)
    expect(within(studies).getAllByRole("row")).toHaveLength(detail.answer!.studies.length + 1)
    expect(within(studies).getByRole("link", { name: "S001" })).toHaveAttribute("href", `${run(`cascade-gaps~${MIXED}`)}/papers/S001`)
    expect(screen.getByRole("link", { name: `rag-baseline~${MIXED}` })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: `cascade-gaps~${MIXED}` })).toHaveAttribute("href", `/scores/reports/${encodeURIComponent(`cascade-gaps~${MIXED}`)}`)
  })

  it("the graph tab draws the evidence of one paper", async () => {
    renderRoutes(routes, `${run(`cascade~${EXPLICIT}`)}?tab=graph`)
    expect(await screen.findByRole("img", { name: "Evidence graph of S001" }, T)).toBeInTheDocument()
    expect(screen.getByText(/nodes, \d+ edges/)).toBeInTheDocument()
  })

  it("a run paper: the funnel, items with their spans, a call's model records", async () => {
    const user = userEvent.setup()
    const { container } = renderRoutes(routes, `${run(`cascade~${EXPLICIT}`)}/papers/S001`)
    await screen.findByLabelText("Text of S001", {}, T)
    expect(container.querySelectorAll("mark").length).toBeGreaterThan(0)
    expect(screen.getByText("Funnel")).toBeInTheDocument()
    const calls = screen.getByRole("table", { name: "Calls" })
    await user.click(within(calls).getByRole("button", { name: "t000002" }))
    const sheet = await screen.findByRole("dialog", {}, T)
    expect(await within(sheet).findByText(/Model calls \(1\)/, {}, T)).toBeInTheDocument()
    expect(within(sheet).getByText("user prompt")).toBeInTheDocument()
  })

  it("an agentic call drills down to the agent's trace", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, `${run(`agentic-gaps~${MIXED}`)}/papers/S001`)
    const calls = await screen.findByRole("table", { name: "Calls" }, T)
    await user.click(within(calls).getByRole("button", { name: "t000020" }))
    const sheet = await screen.findByRole("dialog", {}, T)
    expect(await within(sheet).findByText("the agent's run directory", {}, T)).toBeInTheDocument()
    expect(within(sheet).getAllByText(/claim rejected: not_found/).length).toBeGreaterThan(0)
    expect(within(sheet).getByRole("list", { name: "Steps" })).toBeInTheDocument()
  })

  it("a baseline shows its text, citations and the agent baseline's trace", async () => {
    renderRoutes(routes, run(`rag-baseline~${MIXED}`))
    expect(await screen.findByRole("table", { name: "Retrieved passages" }, T)).toBeInTheDocument()
    expect(screen.getAllByText("cited").length).toBeGreaterThan(0)
    const user = userEvent.setup()
    renderRoutes(routes, `${run(`agent-baseline~${MIXED}`)}?tab=trace`)
    expect(await screen.findByRole("list", { name: "Steps" }, T)).toBeInTheDocument()
    await user.click(screen.getAllByText("The agent's answer")[0])
  })

  it("a fresh re-executed call says it has no record, and an incomplete run says so", async () => {
    const user = userEvent.setup()
    const path = `/api/ev/runs/cascade~${EXPLICIT}/calls/t000002`
    const call = evFixture<CallDetail>(path)
    server.use(http.get(path, () => HttpResponse.json({ ...call, cached: false, model_calls: [],
      record_note: "no record of this call: re-executed fresh, and a re-execution stores nothing in the cache" })))
    renderRoutes(routes, `${run(`cascade~${EXPLICIT}`)}/papers/S001`)
    await user.click(within(await screen.findByRole("table", { name: "Calls" }, T)).getByRole("button", { name: "t000002" }))
    const sheet = await screen.findByRole("dialog", {}, T)
    expect(await within(sheet).findByText(/No record of this call: re-executed fresh/, {}, T)).toBeInTheDocument()
    expect(within(sheet).queryByText(/Model calls/)).not.toBeInTheDocument()
  })

  it("an incomplete run is marked", async () => {
    const id = `cascade-gaps~${MIXED}`
    const detail = evFixture<EvRunDetail>(`/api/ev/runs/${id}`)
    server.use(http.get(`/api/ev/runs/${id}`, () => HttpResponse.json({ ...detail, complete: false, answer: null, label: null, counts: null })))
    renderRoutes(routes, run(id))
    expect(await screen.findByText(/incomplete: no run.json/, {}, T)).toBeInTheDocument()
    expect(screen.getByText("No answer.json.")).toBeInTheDocument()
  })

  it("an unknown run says so", async () => {
    renderRoutes(routes, run("cascade~nope"))
    expect(await screen.findByText("No run cascade~nope", {}, T)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "All runs" })).toHaveAttribute("href", "/runs")
  })
})

describe("scores", () => {
  it("indexes reports, comparisons, shifts and benchmarks", async () => {
    renderRoutes(routes, "/scores")
    const reports = await screen.findByRole("table", { name: "Reports" }, T)
    expect(within(reports).getAllByRole("link", { name: "cascade-gaps" }).length).toBeGreaterThan(0)
    expect(screen.getByText("compare-funnel / rag-tpl-w1-mixed")).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Shift of a controlled variant" })).toBeInTheDocument()
    expect(screen.getByText("benchmark-tpl")).toBeInTheDocument()
  })

  it("a report: C with the baselines and intervals, A per type, the funnel", async () => {
    renderRoutes(routes, `/scores/reports/${encodeURIComponent(`cascade-gaps~${MIXED}`)}`)
    const c = await screen.findByRole("table", { name: "Synthesis per system" }, T)
    expect(within(c).getByText("evidence engine")).toBeInTheDocument()
    expect(within(c).getByText("RAG baseline")).toBeInTheDocument()
    expect(screen.getByRole("img", { name: "Direction accuracy per system with intervals" })).toBeInTheDocument()
    expect(screen.getByRole("table", { name: "Extraction over all levels" })).toBeInTheDocument()
    expect(screen.getByRole("table", { name: "Funnel per document" })).toBeInTheDocument()
    expect(screen.getByText(/engine − RAG baseline/)).toBeInTheDocument()
  })

  it("all against gaps on one corpus", async () => {
    renderRoutes(routes, `/scores/compares/${encodeURIComponent(`compare-funnel~${MIXED}`)}`)
    const table = await screen.findByRole("table", { name: "Comparison" }, T)
    expect(within(table).getByText("gaps")).toBeInTheDocument()
    expect(within(table).getByText("all")).toBeInTheDocument()
    expect(screen.getByText(/accuracy against calls and tokens per document/)).toBeInTheDocument()
  })

  it("the shift of a variant per system", async () => {
    renderRoutes(routes, `/scores/shifts/${encodeURIComponent(`shift-cascade~${VARIANT}`)}`)
    const table = await screen.findByRole("table", { name: "Shift per system" }, T)
    expect(within(table).getByText("evidence engine")).toBeInTheDocument()
    expect(screen.getByText(/mixed → refuted/)).toBeInTheDocument()
  })

  it("benchmark records per extractor", async () => {
    renderRoutes(routes, "/scores/benchmarks/benchmark-tpl")
    expect(await screen.findByText("regex_condition", {}, T)).toBeInTheDocument()
    await waitFor(() => expect(screen.getAllByRole("table").length).toBeGreaterThan(5))
  })
})
