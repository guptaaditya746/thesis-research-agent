import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Markdown } from "./Markdown"

describe("Markdown (assistant replies)", () => {
  it("renders GFM tables, lists, bold and code", () => {
    render(<Markdown text={"| run | support |\n|---|---|\n| q01 | 60% |\n\n- one\n- two\n\n**bold** and `code`"} />)
    expect(screen.getByRole("table")).toBeInTheDocument()
    expect(screen.getByRole("cell", { name: "60%" })).toBeInTheDocument()
    expect(screen.getAllByRole("listitem")).toHaveLength(2)
    expect(screen.getByText("bold").tagName).toBe("STRONG")
    expect(screen.getByText("code").tagName).toBe("CODE")
  })

  it("never renders raw HTML or unsafe links; safe links open in a new tab", () => {
    render(<Markdown text={'<img src=x onerror="alert(1)"> <script>alert(1)</script> [bad](javascript:alert(1)) [docs](https://example.org/x)'} />)
    const root = screen.getByTestId("markdown")
    expect(root.querySelector("img, script")).toBeNull()
    expect(screen.getByText("bad").getAttribute("href") ?? "").not.toMatch(/javascript/i)
    const docs = screen.getByRole("link", { name: "docs" })
    expect(docs).toHaveAttribute("href", "https://example.org/x")
    expect(docs).toHaveAttribute("target", "_blank")
    expect(docs).toHaveAttribute("rel", "noreferrer noopener")
  })
})
