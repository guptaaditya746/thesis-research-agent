import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { routes } from "@/app/routes"
import { PASSAGES, quoteOf, RUN } from "@/mocks/fixtures"
import { server } from "@/mocks/node"
import { renderRoutes, renderWithProviders } from "@/test/render"

import { ClaimWalkSheet } from "./ClaimWalkSheet"
import { WalkContext } from "./walk-context"

// The run page is a lazy chunk; load it up front so the timeouts below measure the UI.
beforeAll(() => import("@/pages/RunPage"), 180_000)
afterEach(() => vi.restoreAllMocks())

const runPath = (runId: string, tab?: string) => `/earlier/runs/${encodeURIComponent(runId)}${tab ? `?tab=${tab}` : ""}`

describe("claim walk", () => {
  it("walks a fact to its claim, the step and the passage with the quote highlighted and scrolled into view", async () => {
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView")
    renderWithProviders(<ClaimWalkSheet runId={RUN.on} target={{ kind: "fact", factId: "f4" }} onClose={() => {}} />)
    const sheet = await screen.findByRole("dialog")

    // fact, its label and the verdict scoring counted: the fact's best one and the quote's own
    expect(await within(sheet).findAllByText(/Judge: partial\./)).toHaveLength(2)
    expect(within(sheet).getByText("Best verdict over the fact's quotes")).toBeInTheDocument()
    expect(within(sheet).getByText("Row r4 · 1 claim · origin research")).toBeInTheDocument()
    expect(within(sheet).getAllByText(/as scored/).length).toBeGreaterThan(0)
    // claim -> step (made by the sub-agent), with the command, its output head and the subagent's output link
    expect(within(sheet).getByRole("heading", { name: "Claim claim-000005" })).toBeInTheDocument()
    expect(within(sheet).getByRole("heading", { name: "Step 6 · sub-01 · research" })).toBeInTheDocument()
    expect(within(sheet).getByText(/HotpotQA \\\(Yang et al/)).toBeInTheDocument()
    expect(within(sheet).getByRole("link", { name: /full output/ })).toHaveAttribute(
      "href", `http://localhost:5173/api/runs/${RUN.on}/steps/6/output?agent_id=sub-01`,
    )
    // passage: the quote is the <mark>, inside the paper's text
    const mark = within(sheet).getByTestId("quote")
    expect(mark.tagName).toBe("MARK")
    expect(mark).toHaveTextContent(quoteOf(PASSAGES.hotpotqa))
    expect(mark.parentElement).toHaveTextContent("NQ (Kwiatkowski et al., 2019), and HotpotQA (Yang et al., 2018) datasets")
    expect(within(sheet).getByText(/How Do Large Vision-Language Models See Text in Image/)).toBeInTheDocument()
    await waitFor(() => expect(scroll.mock.contexts).toContain(mark))
  })

  it("shows each claim's recorded quote next to today's passage", async () => {
    renderWithProviders(<ClaimWalkSheet runId={RUN.on} target={{ kind: "fact", factId: "f4" }} onClose={() => {}} />)
    const sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByTestId("recorded-quote")).toHaveTextContent(quoteOf(PASSAGES.hotpotqa))
    expect(within(sheet).getByText(/the exact text the broker anchored and accepted/)).toBeInTheDocument()
    expect(within(sheet).getByTestId("quote")).toBeInTheDocument()
    // the highlight is the recorded quote: no warning
    expect(within(sheet).queryByText(/is not the recorded quote/)).not.toBeInTheDocument()
  })

  it("shows the recorded quote, and what the agent sent, when the passage cannot be shown", async () => {
    const quote = quoteOf(PASSAGES.hotpotqa)
    // no $CORPUS on the backend: no passage, but the quote the judge read is still there
    server.use(
      http.get("/api/runs/:run/facts/:fact/walk", () => {
        const claim = {
          claim_id: "claim-000005", task_id: "t5", status: "accepted", s: "p6", p: "evaluatesOn", o: "HotpotQA", step: 6, agent_id: "sub-01",
          origin: "research", file: "p6.md", paper_id: "p6", quote, quote_submitted: "and  HotpotQA  (Yang et al", anchor: { start: 19702, end: 19726 },
        }
        return HttpResponse.json({
          run_id: RUN.on, row_id: "r4", row: { id: "r4", facts: [] },
          fact: { id: "f4", s: "p6", p: "evaluatesOn", o: "HotpotQA", claims: ["claim-000005"], origin: "research" },
          claims: [{ claim_id: "claim-000005", claim, step: null, passage: null, anchor_status: "unknown", support: null }],
          support: null, label: null,
        })
      }),
    )
    renderWithProviders(<ClaimWalkSheet runId={RUN.on} target={{ kind: "fact", factId: "f4" }} onClose={() => {}} />)
    const sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByText(/no corpus configured/)).toBeInTheDocument()
    expect(within(sheet).queryByTestId("quote")).not.toBeInTheDocument()
    expect(within(sheet).getByTestId("recorded-quote")).toHaveTextContent(quote)
    // the agent typed extra spaces; the broker matched it to the exact text above
    expect(within(sheet).getByTestId("quote-submitted").textContent).toContain("“and  HotpotQA  (Yang et al”")
  })

  it("warns when today's highlighted text is not the claim's recorded quote (the file changed)", async () => {
    server.use(
      http.get("/api/corpus/:paper", () =>
        HttpResponse.json({ ...PASSAGES.megapairs, text: PASSAGES.megapairs.text.replace("MegaPairs: Massive", "MegaPairs - Massive") })),
    )
    renderWithProviders(
      <ClaimWalkSheet runId={RUN.on} target={{ kind: "claims", claimIds: ["claim-000007"], label: "title" }} onClose={() => {}} />,
    )
    const sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByText(/The highlighted text is not the recorded quote/)).toBeInTheDocument()
    expect(within(sheet).getByTestId("recorded-quote")).toHaveTextContent("MegaPairs: Massive Data Synthesis")
  })

  it("walks every claim of a merged edge, each naming the facts that cite it", async () => {
    const user = userEvent.setup()
    const open = vi.fn()
    renderWithProviders(
      <WalkContext.Provider value={{ runId: RUN.on, open }}>
        <ClaimWalkSheet
          runId={RUN.on}
          target={{ kind: "claims", claimIds: ["claim-000001", "claim-000007"], label: "evaluatesOn", citedBy: { "claim-000001": ["f1"], "claim-000007": [] } }}
          onClose={() => {}}
        />
      </WalkContext.Provider>,
    )
    const sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByText("2 claims; 1 cited by answer facts (each claim names its facts).")).toBeInTheDocument()
    expect(within(sheet).getByRole("heading", { name: "Claim claim-000001" })).toBeInTheDocument()
    expect(within(sheet).getByRole("heading", { name: "Claim claim-000007" })).toBeInTheDocument()
    expect(within(sheet).getByText("No answer fact cites this claim.")).toBeInTheDocument()
    await user.click(within(sheet).getByRole("button", { name: "Open the walk of fact f1" }))
    expect(open).toHaveBeenCalledWith({ kind: "fact", factId: "f1" })
  })

  it("says so when a fact has no claim behind it", async () => {
    renderWithProviders(<ClaimWalkSheet runId={RUN.on} target={{ kind: "fact", factId: "f5" }} onClose={() => {}} />)
    const sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByText("No claim behind this fact")).toBeInTheDocument()
    expect(within(sheet).getByText(/without recording a claim/)).toBeInTheDocument()
    expect(within(sheet).getByText("unsourced")).toBeInTheDocument()
  })

  it("explains an attach fact with no source found", async () => {
    renderWithProviders(<ClaimWalkSheet runId={RUN.off} target={{ kind: "fact", factId: "f4" }} onClose={() => {}} />)
    expect(await screen.findByText(/no source found/)).toBeInTheDocument()
  })

  it("asks the judge for a quote that has no verdict yet", async () => {
    const user = userEvent.setup()
    // the run is not scored: the walk has the claim but no verdict
    server.use(http.get("/api/runs/:run/score", () => HttpResponse.json({ detail: "no score.json yet" }, { status: 404 })))
    const walkUrls: string[] = []
    server.events.on("request:start", ({ request }) => {
      if (request.url.includes("/walk")) walkUrls.push(request.url)
    })
    server.use(
      http.get("/api/runs/:run/facts/:fact/walk", ({ request }) => {
        const judge = new URL(request.url).searchParams.get("judge") === "true"
        const verdict = judge ? { label: "supports", rationale: "(mock judge) The quote states the fact.", model: "sub-model-2", cached: false, source: "judge" } : null
        const claim = {
          claim_id: "claim-000001", task_id: "t1", status: "accepted", s: "p1", p: "evaluatesOn", o: "Spider", step: 3, agent_id: "main",
          origin: "research", file: "p1.md", paper_id: "p1", quote: quoteOf(PASSAGES.spider),
        }
        return HttpResponse.json({
          run_id: RUN.on, row_id: "r1", row: { id: "r1", facts: [] },
          fact: { id: "f1", s: "p1", p: "evaluatesOn", o: "Spider", claims: ["claim-000001"], origin: "research" },
          claims: [{ claim_id: "claim-000001", claim, step: null, passage: PASSAGES.spider, anchor_status: "ok", support: verdict }],
          support: verdict, label: judge ? "supports" : null,
        })
      }),
    )
    renderWithProviders(<ClaimWalkSheet runId={RUN.on} target={{ kind: "fact", factId: "f1" }} onClose={() => {}} />)
    const sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByText("not judged yet")).toBeInTheDocument()
    await user.click(within(sheet).getByRole("button", { name: "Ask the judge" }))
    expect(await within(sheet).findByText("supported")).toBeInTheDocument()
    expect(within(sheet).getAllByText(/asked now/).length).toBeGreaterThan(0)
    expect(walkUrls.some((u) => u.endsWith("judge=true"))).toBe(true)
    server.events.removeAllListeners("request:start")
  })

  it("assembles the walk of bare claims (a graph edge that no fact cites) from claims, steps and the corpus", async () => {
    renderWithProviders(
      <ClaimWalkSheet runId={RUN.on} target={{ kind: "claims", claimIds: ["claim-000007"], label: "title" }} onClose={() => {}} />,
    )
    const sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByText(/no answer fact cites it/)).toBeInTheDocument()
    expect(within(sheet).getByRole("heading", { name: "Step 6 · sub-01 · research" })).toBeInTheDocument()
    const mark = await within(sheet).findByTestId("quote")
    expect(mark).toHaveTextContent("MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval")
  })

  it("shows the error and a retry when the walk cannot be loaded", async () => {
    renderWithProviders(<ClaimWalkSheet runId={RUN.on} target={{ kind: "fact", factId: "f99" }} onClose={() => {}} />)
    expect(await screen.findByRole("alert")).toHaveTextContent("has no fact 'f99'")
    expect(screen.getByRole("button", { name: /Try again/ })).toBeInTheDocument()
  })

  it("opens from a fact badge on the run page, with the status scoring gave the fact", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, runPath(RUN.on))
    const supported = await screen.findByRole("button", { name: "Fact f1: supported. Open the claim walk." }, { timeout: 15_000 })
    expect(screen.getByRole("button", { name: "Fact f4: partial. Open the claim walk." })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Fact f5: unsourced. Open the claim walk." })).toBeInTheDocument()
    await user.click(supported)
    const sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByTestId("quote")).toHaveTextContent(quoteOf(PASSAGES.spider))
    expect(within(sheet).getAllByText(/Judge: supports\./).length).toBeGreaterThan(0)
  })

  it("opens from a graph edge: the fact citing the edge's claim, else the bare claim", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, runPath(RUN.on, "graph"))
    expect(await screen.findByRole("region", { name: "Knowledge graph" }, { timeout: 15_000 })).toBeInTheDocument()
    await user.click(screen.getByText("Edges as a list (7)"))
    await user.click(screen.getByRole("button", { name: "p1 —evaluatesOn→ Spider" }))
    let sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByRole("heading", { name: "Claim walk · f1" })).toBeInTheDocument()
    await user.keyboard("{Escape}")
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    await user.click(screen.getByRole("button", { name: "p4 —title→ “MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval”" }))
    sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByTestId("quote")).toHaveTextContent(quoteOf(PASSAGES.megapairs))
    expect(within(sheet).getByText(/no answer fact cites it/)).toBeInTheDocument()
  })
})
