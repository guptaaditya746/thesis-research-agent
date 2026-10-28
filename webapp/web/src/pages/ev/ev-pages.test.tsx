/** The evidence-level pages against the mock backend, whose responses are the real backend's on a world made by the real tools. */
import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { beforeAll, describe, expect, it } from "vitest"

import type { CallDetail, CorpusDetail, EvRunDetail, ProposalDetail, Question, TracePage } from "@/api/ev"
import { routes } from "@/app/routes"
import { effectAnswer } from "@/lib/ev"
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
    import("@/pages/ev/ComparePage"), import("@/pages/ev/ShiftPage"), import("@/pages/ev/BenchmarkPage"), import("@/pages/flow/FlowPage"), import("@/pages/JobsPage"),
  ])
}, 180_000)

describe("home", () => {
  it("offers the questions to select, what is on disk and the directories", async () => {
    renderRoutes(routes, "/")
    expect(await screen.findByRole("heading", { name: "Evidence-level synthesis" }, T)).toBeInTheDocument()
    const question = await screen.findByRole("link", { name: "Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?" }, T)
    expect(question).toHaveAttribute("href", "/flow/rag-factuality")
    expect(await screen.findByText(/4 corpora/, {}, T)).toBeInTheDocument()
    expect(screen.getByText("hand-written protocol rag-factuality")).toBeInTheDocument()
    expect(screen.getByText("/srv/ev")).toBeInTheDocument()
    expect(screen.queryByText(/earlier work/i)).toBeNull()
  })
})

describe("home kinds", () => {
  it("question list shows kind chips", async () => {
    const base = evFixture<Question[]>("/api/ev/questions")[0]
    const kinds = ["effect", "inventory", "consistency", "best"] as const
    server.use(http.get("/api/ev/questions", () => HttpResponse.json(kinds.map((kind) => ({ ...base, id: `q-${kind}`, question: `A ${kind} question?`, kind })))))
    renderRoutes(routes, "/")
    for (const kind of kinds) {
      const link = await screen.findByRole("link", { name: `A ${kind} question?` }, T)
      expect(within(link.closest("[data-slot=card]") as HTMLElement).getByText(kind)).toBeInTheDocument()
    }
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

  it("a run's answer is the evidence table: a row per paper, each opening its source", async () => {
    const detail = evFixture<EvRunDetail>(`/api/ev/runs/cascade-gaps~${MIXED}`)
    renderRoutes(routes, run(`cascade-gaps~${MIXED}`))
    const table = await screen.findByRole("table", { name: "Evidence per paper" }, T)
    for (const s of effectAnswer(detail.answer)!.studies) {
      expect(within(table).getByRole("button", { name: `${s.document}: show the evidence in the paper` })).toBeInTheDocument()
    }
    expect(screen.getByRole("link", { name: `rag-baseline~${MIXED}` })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: `cascade-gaps~${MIXED}` })).toHaveAttribute("href", `/scores/reports/${encodeURIComponent(`cascade-gaps~${MIXED}`)}`)
  })

  it("the graph tab draws the evidence of one paper", async () => {
    renderRoutes(routes, `${run(`cascade~${EXPLICIT}`)}?tab=graph`)
    expect(await screen.findByRole("group", { name: "Evidence graph of S001" }, T)).toBeInTheDocument()
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
    expect(within(sheet).getAllByText(/not_found/).length).toBeGreaterThan(0)
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

describe("developer tools tab", () => {
  const id = `cascade~${EXPLICIT}`
  const row = (n: number, over: Partial<TracePage["rows"][number]> = {}): TracePage["rows"][number] => ({
    n, phase: "run", at: null, step: "extractor_call", document: "S001", evidence_type: "metric", extractor: "regex", status: "ok",
    source: "fresh", seconds: 1.5, input_tokens: 10, output_tokens: 5, call: null, ...over,
  })
  const traceUrl = `/api/ev/runs/${id}/trace`

  it("trace tab lists rows and opens call sheet", async () => {
    const user = userEvent.setup()
    const call = evFixture<CallDetail>(`/api/ev/runs/${id}/calls/t000002`)
    server.use(
      http.get(traceUrl, () => HttpResponse.json({ rows: [row(1, { step: "screen", seconds: null, input_tokens: null, output_tokens: null }),
        row(2, { call: "t000002", document: "S002" })], next: 2, done: true })),
      http.get(`/api/ev/runs/${id}/calls/t000002`, () => HttpResponse.json(call)),
    )
    renderRoutes(routes, `${run(id)}?tab=dev`)
    const table = await screen.findByRole("table", { name: "Run trace" }, T)
    expect(within(table).getAllByRole("row")).toHaveLength(3)
    expect(within(table).getAllByText("—").length).toBeGreaterThanOrEqual(2)
    await user.click(within(table).getByRole("button", { name: "extractor_call" }))
    const sheet = await screen.findByRole("dialog", {}, T)
    expect(await within(sheet).findByText("user prompt", {}, T)).toBeInTheDocument()
  })

  it("a skipped GLiNER call is a plain row that opens nothing", async () => {
    const user = userEvent.setup()
    server.use(http.get(traceUrl, () => HttpResponse.json({ rows: [row(1, { status: "skipped", extractor: "gliner_dataset@1#x",
      document: "S004", input_tokens: null, output_tokens: null })], next: 1, done: true })))
    renderRoutes(routes, `${run(id)}?tab=dev`)
    const table = await screen.findByRole("table", { name: "Run trace" }, T)
    expect(within(table).getByText("skipped: service unavailable")).toBeInTheDocument()
    expect(within(table).queryByRole("button", { name: "extractor_call" })).toBeNull()
    await user.click(within(table).getByText("S004"))
    expect(screen.queryByRole("dialog")).toBeNull()
  })

  it("trace polls while running and stops when done", async () => {
    const afters: string[] = []
    server.use(http.get(traceUrl, ({ request }) => {
      const after = new URL(request.url).searchParams.get("after") ?? "0"
      afters.push(after)
      return HttpResponse.json(after === "0" ? { rows: [row(1)], next: 1, done: false } : { rows: [row(2, { document: "S009" })], next: 2, done: true })
    }))
    renderRoutes(routes, `${run(id)}?tab=dev`)
    const table = await screen.findByRole("table", { name: "Run trace" }, T)
    await waitFor(() => expect(within(table).getAllByRole("row")).toHaveLength(3), T)
    expect(afters.slice(0, 2)).toEqual(["0", "1"])
    const calls = afters.length
    await new Promise((r) => setTimeout(r, 2600))
    expect(afters).toHaveLength(calls)
  }, 30_000)

  it("a click anywhere on a call row opens the sheet, and the time shows", async () => {
    const user = userEvent.setup()
    const call = evFixture<CallDetail>(`/api/ev/runs/${id}/calls/t000002`)
    server.use(
      http.get(traceUrl, () => HttpResponse.json({ rows: [row(1, { call: "t000002", document: "S002", at: "2026-10-25T10:00:07+00:00" })], next: 1, done: true })),
      http.get(`/api/ev/runs/${id}/calls/t000002`, () => HttpResponse.json(call)),
    )
    renderRoutes(routes, `${run(id)}?tab=dev`)
    const table = await screen.findByRole("table", { name: "Run trace" }, T)
    expect(within(table).getByText(/^\d\d:\d\d:07$/)).toBeInTheDocument()
    await user.click(within(table).getByText("S002"))
    expect(await screen.findByRole("dialog", {}, T)).toBeInTheDocument()
  })

  it("a failed poll keeps the rows and says so; a restarted trace starts over", async () => {
    let n = 0
    server.use(http.get(traceUrl, ({ request }) => {
      n += 1
      const after = new URL(request.url).searchParams.get("after")
      if (n === 1) return HttpResponse.json({ rows: [row(1), row(2), row(3, { document: "S003" })], next: 3, done: false })
      if (n === 2) return HttpResponse.json({ detail: "boom" }, { status: 500 })
      if (after === "3") return HttpResponse.json({ rows: [], next: 1, done: false })    // restarted: one row now
      return HttpResponse.json({ rows: [row(1, { document: "S100" })], next: 1, done: true })
    }))
    renderRoutes(routes, `${run(id)}?tab=dev`)
    const table = await screen.findByRole("table", { name: "Run trace" }, T)
    expect(within(table).getAllByRole("row")).toHaveLength(4)
    expect(await screen.findByRole("alert", {}, T)).toHaveTextContent(/latest poll failed/)
    expect(within(table).getAllByRole("row")).toHaveLength(4)
    await waitFor(() => expect(within(table).getByText("S100")).toBeInTheDocument(), T)
    expect(within(table).getAllByRole("row")).toHaveLength(2)
  }, 30_000)
  it("filter by status shows errors only", async () => {
    const user = userEvent.setup()
    server.use(http.get(traceUrl, () => HttpResponse.json({ rows: [row(1), row(2, { status: "error", document: "S007" }), row(3, { document: "S008" })], next: 3, done: true })))
    renderRoutes(routes, `${run(id)}?tab=dev`)
    const table = await screen.findByRole("table", { name: "Run trace" }, T)
    await user.selectOptions(screen.getByLabelText("Status"), "error")
    expect(within(table).getAllByRole("row")).toHaveLength(2)
    expect(within(table).getByText("S007")).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText("Status"), "")
    await user.selectOptions(screen.getByLabelText("Paper"), "S008")
    expect(within(table).getAllByRole("row")).toHaveLength(2)
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
    expect(screen.getByRole("figure", { name: "Direction accuracy per system with intervals" })).toBeInTheDocument()
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
