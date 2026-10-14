import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { routes } from "@/app/routes"
import { PASSAGES, quoteOf } from "@/mocks/fixtures"
import { renderRoutes, renderWithProviders } from "@/test/render"

import { ClaimWalkSheet } from "./ClaimWalkSheet"

// The run page is a lazy chunk; load it up front so the timeouts below measure the UI.
beforeAll(() => import("@/pages/RunPage"), 180_000)
afterEach(() => vi.restoreAllMocks())

describe("claim walk", () => {
  it("walks a fact to its claim, the step and the passage with the quote highlighted and scrolled into view", async () => {
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView")
    renderWithProviders(<ClaimWalkSheet runId="q01-on-s1" target={{ kind: "fact", factId: "f4" }} onClose={() => {}} />)
    const sheet = await screen.findByRole("dialog")

    // fact and the judge's verdict
    expect(await within(sheet).findByText(/Judge: partial\./)).toBeInTheDocument()
    expect(within(sheet).getByText("Row r4 · 1 claim · origin research")).toBeInTheDocument()
    // claim -> step (made by the sub-agent), with the command and its output head
    expect(within(sheet).getByRole("heading", { name: "Claim claim-000005" })).toBeInTheDocument()
    expect(within(sheet).getByRole("heading", { name: "Step 6 · sub-01 · research" })).toBeInTheDocument()
    expect(within(sheet).getByText(/HotpotQA \\\(Yang et al/)).toBeInTheDocument()
    expect(within(sheet).getByRole("link", { name: /full output/ })).toHaveAttribute("href", "http://localhost:5173/api/runs/q01-on-s1/steps/6/output")
    // passage: the quote is the <mark>, inside the paper's text
    const mark = within(sheet).getByTestId("quote")
    expect(mark.tagName).toBe("MARK")
    expect(mark).toHaveTextContent(quoteOf(PASSAGES.hotpotqa))
    expect(mark.parentElement).toHaveTextContent("NQ (Kwiatkowski et al., 2019), and HotpotQA (Yang et al., 2018) datasets")
    expect(within(sheet).getByText(/How Do Large Vision-Language Models See Text in Image/)).toBeInTheDocument()
    await waitFor(() => expect(scroll.mock.contexts).toContain(mark))
  })

  it("says so when a fact has no claim behind it", async () => {
    renderWithProviders(<ClaimWalkSheet runId="q01-on-s1" target={{ kind: "fact", factId: "f5" }} onClose={() => {}} />)
    const sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByText("No claim behind this fact")).toBeInTheDocument()
    expect(within(sheet).getByText(/without recording a claim/)).toBeInTheDocument()
    expect(within(sheet).getByText("unsourced")).toBeInTheDocument()
  })

  it("explains an attach fact with no source found", async () => {
    renderWithProviders(<ClaimWalkSheet runId="q01-off-s1" target={{ kind: "fact", factId: "f4" }} onClose={() => {}} />)
    expect(await screen.findByText(/no source found/)).toBeInTheDocument()
  })

  it("assembles the walk of bare claims (a graph edge that no fact cites) from claims, steps and the corpus", async () => {
    renderWithProviders(
      <ClaimWalkSheet runId="q01-on-s1" target={{ kind: "claims", claimIds: ["claim-000007"], label: "title" }} onClose={() => {}} />,
    )
    const sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByText(/no answer fact cites it/)).toBeInTheDocument()
    expect(within(sheet).getByRole("heading", { name: "Step 6 · sub-01 · research" })).toBeInTheDocument()
    const mark = await within(sheet).findByTestId("quote")
    expect(mark).toHaveTextContent("MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval")
  })

  it("shows the error and a retry when the walk cannot be loaded", async () => {
    renderWithProviders(<ClaimWalkSheet runId="q01-on-s1" target={{ kind: "fact", factId: "f99" }} onClose={() => {}} />)
    expect(await screen.findByRole("alert")).toHaveTextContent("fact f99 not found")
    expect(screen.getByRole("button", { name: /Try again/ })).toBeInTheDocument()
  })

  it("opens from a fact badge on the run page, with the badge's support status", async () => {
    const user = userEvent.setup()
    renderRoutes(routes, "/runs/q01-on-s1")
    const supported = await screen.findByRole("button", { name: "Fact f1: supported. Open the claim walk." }, { timeout: 15_000 })
    expect(screen.getByRole("button", { name: "Fact f4: partial. Open the claim walk." })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Fact f5: unsourced. Open the claim walk." })).toBeInTheDocument()
    await user.click(supported)
    const sheet = await screen.findByRole("dialog")
    expect(await within(sheet).findByTestId("quote")).toHaveTextContent(quoteOf(PASSAGES.spider))
    expect(within(sheet).getByText(/Judge: supports\./)).toBeInTheDocument()
  })
})
