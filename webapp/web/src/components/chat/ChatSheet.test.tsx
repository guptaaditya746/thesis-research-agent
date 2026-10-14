import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeAll, describe, expect, it } from "vitest"

import { routes } from "@/app/routes"
import { server } from "@/mocks/node"
import { renderRoutes } from "@/test/render"

beforeAll(async () => {
  await Promise.all([import("./ChatPanel"), import("@/pages/RunPage")])
}, 180_000)

describe("chat", () => {
  it("is scoped to the run in view, sends its id and shows the streamed reply with the tool call", async () => {
    const bodies: unknown[] = []
    const record = ({ request }: { request: Request }) => {
      if (request.url.endsWith("/api/chat")) void request.clone().json().then((body) => bodies.push(body))
    }
    server.events.on("request:start", record)
    const user = userEvent.setup()
    renderRoutes(routes, "/runs/q01-on-s1")

    await user.click(await screen.findByRole("button", { name: "Ask about this run" }, { timeout: 15_000 }))
    // the panel is a lazy chunk: a loading sheet first, then the thread
    const input = await screen.findByRole("textbox", { name: "Message" }, { timeout: 15_000 })
    const sheet = screen.getByRole("dialog", { name: "Chat about runs" })
    expect(within(sheet).getByText("q01-on-s1")).toBeInTheDocument()

    await user.type(input, "Which facts are unsourced?")
    await user.click(within(sheet).getByRole("button", { name: "Send" }))

    expect(await within(sheet).findByText("Which facts are unsourced?")).toBeInTheDocument()
    expect(await within(sheet).findByText(/\(mock reply\) Run \*\*q01-on-s1\*\* \(claim_on, seed 1\)/, {}, { timeout: 10_000 })).toBeInTheDocument()
    expect(within(sheet).getByText(/get_run\(/)).toBeInTheDocument()
    expect(bodies).toHaveLength(1)
    expect(bodies[0]).toMatchObject({ run_id: "q01-on-s1", trigger: "submit-message" })
    server.events.removeListener("request:start", record)
  })
})
