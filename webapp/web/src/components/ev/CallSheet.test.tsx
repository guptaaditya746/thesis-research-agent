/** A recorded call in the call sheet: an LLM call, and a GLiNER service call (evidence/extractors/gliner.py). */
import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import type { ModelCallRecord } from "@/api/ev"
import { renderWithProviders } from "@/test/render"

import { ModelCallView } from "./CallSheet"

describe("ModelCallView", () => {
  it("shows a GLiNER call's text, labels, threshold and entities", () => {
    const record: ModelCallRecord = {
      id: "gl-1", usage: null, error: null, agent_run: null,
      request: { service: "gliner", endpoint: "/predict", model_from_info: "urchade/gliner_medium-v2.1",
        text: "We report factual accuracy.", labels: ["evaluation metric"], threshold: 0.5 },
      response: { entities: [{ start: 10, end: 26, text: "factual accuracy", label: "evaluation metric", score: 0.9 }] },
    }
    renderWithProviders(<ModelCallView record={record} />)
    expect(screen.getByText(/GLiNER urchade\/gliner_medium-v2\.1/)).toHaveTextContent("labels evaluation metric · threshold 0.5")
    expect(screen.getByRole("region", { name: "text" })).toHaveTextContent("We report factual accuracy.")
    expect(screen.getByRole("region", { name: "entities" })).toHaveTextContent('"label": "evaluation metric"')
    expect(screen.queryByText("instructions")).not.toBeInTheDocument()
  })

  it("shows a failed GLiNER call's error", () => {
    renderWithProviders(<ModelCallView record={{ id: "gl-2", usage: null, agent_run: null, response: null,
      error: "timeout after 10 s", request: { service: "gliner", text: "x", labels: ["dataset"], threshold: 0.5 } }} />)
    expect(screen.getByText("timeout after 10 s")).toBeInTheDocument()
  })

  it("keeps an LLM call's instructions, prompt and output", () => {
    renderWithProviders(<ModelCallView record={{ id: "mc-1", error: null, agent_run: null,
      request: { model: "orch-model", instructions: "Extract.", user_prompt: "Paper P1" },
      response: { output: { items: [] } }, usage: { input_tokens: 10, output_tokens: 2 } }} />)
    expect(screen.getByText("instructions")).toBeInTheDocument()
    expect(screen.getByText(/orch-model/)).toBeInTheDocument()
    expect(screen.getByRole("region", { name: "model output" })).toHaveTextContent('"items": []')
  })
})
