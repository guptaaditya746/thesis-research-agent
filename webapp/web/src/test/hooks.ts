/**
 * What every test file gets: jest-dom matchers, the MSW server with the app's handlers (fresh
 * in-memory state and instant streams per test), and stubs for what jsdom lacks
 * (ResizeObserver, matchMedia, scrollIntoView, pointer capture) that Radix, React Flow and the
 * sidebar use. `registerHooks` runs once per file (the module itself is cached across files).
 */
import "@testing-library/jest-dom/vitest"

import { cleanup, configure } from "@testing-library/react"
import { afterAll, afterEach, beforeAll } from "vitest"

import { resetDb, timing } from "@/mocks/handlers"
import { server } from "@/mocks/node"

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

function stubBrowserGaps() {
  globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver
  if (!window.matchMedia) {
    window.matchMedia = (query: string) =>
      ({
        matches: false, media: query, onchange: null,
        addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
        dispatchEvent: () => false,
      }) as MediaQueryList
  }
  Element.prototype.scrollIntoView ??= function scrollIntoView() {}
  Element.prototype.scrollTo ??= function scrollTo() {}
  Element.prototype.hasPointerCapture ??= () => false
  Element.prototype.releasePointerCapture ??= () => {}
}

export function registerHooks() {
  timing.streamMs = 0
  configure({ asyncUtilTimeout: 5_000 })
  stubBrowserGaps()
  beforeAll(() => server.listen({ onUnhandledRequest: "error" }))
  afterEach(() => {
    cleanup()
    server.resetHandlers()
    resetDb()
  })
  afterAll(() => server.close())
}
