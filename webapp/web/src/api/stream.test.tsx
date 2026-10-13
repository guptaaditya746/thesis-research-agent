import { QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { LIVE_RECORDS, STEPS } from "@/mocks/fixtures"
import { summarize } from "@/lib/timeline"
import { testClient } from "@/test/render"

import { useJobLog, useRunStream } from "./stream"

/** EventSource stand-in: the test plays the server's side. */
class FakeEventSource {
  static instances: FakeEventSource[] = []
  readonly url: string
  closed = false
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  private listeners = new Map<string, ((event: MessageEvent) => void)[]>()

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }
  addEventListener(name: string, fn: (event: MessageEvent) => void) {
    this.listeners.set(name, [...(this.listeners.get(name) ?? []), fn])
  }
  close() {
    this.closed = true
  }
  emit(name: string, data: string) {
    for (const fn of this.listeners.get(name) ?? []) fn(new MessageEvent(name, { data }))
  }
  static last() {
    return FakeEventSource.instances.at(-1)!
  }
}

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={testClient()}>{children}</QueryClientProvider>
}

beforeEach(() => {
  FakeEventSource.instances = []
  vi.stubGlobal("EventSource", FakeEventSource)
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe("useRunStream", () => {
  it("folds the live records into the seeded steps and stops on done", () => {
    const { result } = renderHook(() => useRunStream("q01-on-s2", { live: true, seed: STEPS["q01-on-s2"] }), { wrapper })
    const source = FakeEventSource.last()
    expect(source.url).toBe("http://localhost:5173/api/runs/q01-on-s2/stream")
    expect(result.current.status).toBe("connecting")
    expect(summarize(result.current.timeline).steps).toHaveLength(3)

    act(() => source.onopen?.())
    expect(result.current.status).toBe("open")
    act(() => {
      for (const record of LIVE_RECORDS) source.emit("record", JSON.stringify(record))
      source.emit("record", "not json") // ignored
    })
    const summary = summarize(result.current.timeline)
    expect(summary.steps.map((s) => s.step)).toEqual([1, 2, 3, 4, 5, 6])
    expect(summary.phaseChanges).toEqual([{ at: "main:6", from: "research", to: "conclude" }])

    act(() => source.emit("done", ""))
    expect(result.current.status).toBe("done")
    expect(result.current.timeline.done).toBe(true)
    expect(source.closed).toBe(true)
    expect(FakeEventSource.instances).toHaveLength(1) // no reconnect after done
  })

  it("opens no stream for a finished run", () => {
    const { result } = renderHook(() => useRunStream("q01-on-s1", { live: false, seed: STEPS["q01-on-s1"] }), { wrapper })
    expect(FakeEventSource.instances).toHaveLength(0)
    expect(result.current.status).toBe("idle")
    expect(summarize(result.current.timeline).steps).toHaveLength(8)
  })

  it("reconnects after an error, and a replay adds nothing", () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useRunStream("q01-on-s2", { live: true, seed: undefined }), { wrapper })
    const first = FakeEventSource.last()
    act(() => first.emit("record", JSON.stringify(LIVE_RECORDS[0])))
    act(() => first.onerror?.())
    expect(result.current.status).toBe("error")
    expect(first.closed).toBe(true)
    act(() => vi.advanceTimersByTime(3_000))
    const second = FakeEventSource.last()
    expect(second).not.toBe(first)
    act(() => second.emit("record", JSON.stringify(LIVE_RECORDS[0])))
    expect(summarize(result.current.timeline).steps).toHaveLength(1)
    expect(result.current.timeline.records).toBe(1)
  })
})

describe("useJobLog", () => {
  it("collects log lines and ends on done; a replay starts from an empty buffer", () => {
    const { result } = renderHook(() => useJobLog("job-0006", true), { wrapper })
    const source = FakeEventSource.last()
    expect(source.url).toBe("http://localhost:5173/api/jobs/job-0006/log")
    act(() => {
      source.onopen?.()
      source.emit("message", "$ agent run")
      source.emit("message", "exit 0")
    })
    expect(result.current.lines).toEqual(["$ agent run", "exit 0"])
    act(() => source.emit("done", ""))
    expect(result.current.status).toBe("done")
    act(() => result.current.reconnect())
    expect(result.current.lines).toEqual([])
    act(() => FakeEventSource.last().emit("line", "$ agent run"))
    expect(result.current.lines).toEqual(["$ agent run"])
  })
})
