import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { MockBanner } from "./MockBanner"

afterEach(() => vi.unstubAllEnvs())

describe("MockBanner", () => {
  it("says the data is fixtures in mock mode", () => {
    vi.stubEnv("VITE_MOCK", "1")
    render(<MockBanner />)
    expect(screen.getByRole("note", { name: "Mock data" })).toHaveTextContent("not a result")
  })

  it("is not there against the real backend", () => {
    vi.stubEnv("VITE_MOCK", "")
    const { container } = render(<MockBanner />)
    expect(container).toBeEmptyDOMElement()
  })
})
