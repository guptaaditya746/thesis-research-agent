/** The answer panel for each question kind (webapp/evmodels.py's answer union). */
import { screen, within } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import type { RunAnswer } from "@/api/ev"
import { renderWithProviders } from "@/test/render"

import { AnswerPanel } from "./AnswerPanel"

const href = (d: string) => `/p/${d}`
const show = (answer: RunAnswer) => renderWithProviders(<AnswerPanel answer={answer} paperHref={href} />)

describe("AnswerPanel", () => {
  it("renders inventory answer", () => {
    show({ kind: "inventory", system: "evidence-engine", target: "dataset",
      entries: [{ name: "SQuAD", aliases: ["Squad v1"], papers: ["S001", "S002"], items: ["i1", "i2"] }] })
    const table = screen.getByRole("table", { name: "Inventory" })
    expect(within(table).getByText("SQuAD")).toBeInTheDocument()
    expect(within(table).getByText("Squad v1")).toBeInTheDocument()
    expect(within(table).getByRole("link", { name: "S001" })).toHaveAttribute("href", "/p/S001")
    expect(within(table).getByRole("link", { name: "S002" })).toBeInTheDocument()
  })

  it("renders best winner and tie", () => {
    show({ kind: "best", system: "evidence-engine", metric: "factual_accuracy", wins: { rag: 1 }, winner: "rag", tied: [],
      studies: [
        { document: "S001", winner: "rag", tied: [], values: { rag: 0.8, plain: 0.6 }, reason: null },
        { document: "S002", winner: null, tied: ["plain", "rag"], values: { rag: 0.7, plain: 0.7 }, reason: null },
        { document: "S003", winner: null, tied: [], values: {}, reason: { code: "too_few_kinds", text: "conditions of fewer than two method kinds found" } },
      ] })
    expect(screen.getByText(/Winner/)).toHaveTextContent("rag")
    const table = screen.getByRole("table", { name: "Winner per paper" })
    expect(within(screen.getByRole("row", { name: /S001/ })).getByText("rag", { selector: "[data-winner]" })).toBeInTheDocument()
    expect(within(screen.getByRole("row", { name: /S002/ })).getByText(/tie: plain, rag/)).toBeInTheDocument()
    expect(within(table).getByText(/fewer than two method kinds/)).toBeInTheDocument()
    expect(screen.getByRole("table", { name: "Wins per kind" })).toBeInTheDocument()
  })

  it("renders consistency agree and disagree", () => {
    show({ kind: "consistency", system: "evidence-engine", metric: "factual_accuracy", agreeing: ["S001"], disagreeing: ["S002"], undetermined: ["S003"],
      studies: [
        { document: "S001", claim: "supports", direction: "supports", agrees: true, reason: null },
        { document: "S002", claim: "supports", direction: "contradicts", agrees: false, reason: null },
        { document: "S003", claim: null, direction: "undetermined", agrees: null, reason: { code: "no_claim", text: "no author claim found" } },
      ] })
    const table = screen.getByRole("table", { name: "Claims against data" })
    expect(within(within(table).getByRole("row", { name: /S001/ })).getByText("agrees")).toBeInTheDocument()
    expect(within(within(table).getByRole("row", { name: /S002/ })).getByText("disagrees")).toBeInTheDocument()
    expect(within(table).getByText("no author claim found")).toBeInTheDocument()
  })

  it("renders an effect answer as before", () => {
    show({ system: "evidence-engine", kind: "effect", label: "supports", counts: { supporting: 1 }, studies: [{ document: "S001", direction: "supports" }] } as RunAnswer)
    expect(screen.getByRole("table", { name: "Studies" })).toBeInTheDocument()
  })
})
