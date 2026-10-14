import { QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { LIVE_RECORDS, RUN, STEPS } from "@/mocks/fixtures"
import { summarize } from "@/lib/timeline"
import { testClient } from "@/test/render"

import { liveReducer, useJobLog, useRunStream } from "./stream"

/** EventSource stand-in: the test plays the server's side. */
class FakeEventSource {
  static instances: FakeEventSource[] = []
  readonly url: string
  closed = false
  /** 0 CONNECTING, 1 OPEN, 2 CLOSED, as EventSource */
  readyState = 0
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
    this.readyState = 2
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
    const { result } = renderHook(() => useRunStream("q01-on-s2", { live: true, seed: STEPS[RUN.live] }), { wrapper })
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
    const { result } = renderHook(() => useRunStream("q01-on-s1", { live: false, seed: STEPS[RUN.on] }), { wrapper })
    expect(FakeEventSource.instances).toHaveLength(0)
    expect(result.current.status).toBe("idle")
    expect(summarize(result.current.timeline).steps).toHaveLength(8)
  })

  it("leaves a dropped connection to EventSource's own reconnection (Last-Event-ID), keeping the same source", () => {
    const { result } = renderHook(() => useRunStream("q01-on-s2", { live: true, seed: undefined }), { wrapper })
    const source = FakeEventSource.last()
    act(() => {
      source.onopen?.()
      source.emit("record", JSON.stringify(LIVE_RECORDS[0]))
    })
    // a network blip: the browser is reconnecting by itself (readyState CONNECTING)
    act(() => {
      source.readyState = 0
      source.onerror?.()
    })
    expect(result.current.status).toBe("reconnecting")
    expect(source.closed).toBe(false)
    expect(FakeEventSource.instances).toHaveLength(1)
    // it resumes after the last id: the next record, not a replay
    act(() => {
      source.readyState = 1
      source.onopen?.()
      source.emit("record", JSON.stringify(LIVE_RECORDS[1]))
    })
    expect(result.current.status).toBe("open")
    expect(result.current.timeline.records).toBe(2)
  })

  it("is an error only when the browser gives up; reconnecting by hand replays, and the replay adds nothing", () => {
    const { result } = renderHook(() => useRunStream("q01-on-s2", { live: true, seed: undefined }), { wrapper })
    const first = FakeEventSource.last()
    act(() => first.emit("record", JSON.stringify(LIVE_RECORDS[0])))
    act(() => {
      first.readyState = 2 // CLOSED: an HTTP error, no automatic reconnection
      first.onerror?.()
    })
    expect(result.current.status).toBe("error")
    act(() => result.current.reconnect())
    const second = FakeEventSource.last()
    expect(second).not.toBe(first)
    expect(first.closed).toBe(true)
    act(() => {
      for (const record of LIVE_RECORDS.slice(0, 2)) second.emit("record", JSON.stringify(record))
    })
    expect(summarize(result.current.timeline).steps).toHaveLength(1) // both records are step 4's
    expect(result.current.timeline.records).toBe(2) // the replayed first record is not folded twice
  })

  it("keeps each live record once, so a replay does not grow the buffer", () => {
    type Live = Parameters<typeof liveReducer>[0]
    const empty: Live = { records: [], seen: {}, done: false }
    const once = LIVE_RECORDS.reduce<Live>((s, record) => liveReducer(s, { type: "record", record }), empty)
    const twice = LIVE_RECORDS.reduce<Live>((s, record) => liveReducer(s, { type: "record", record }), once)
    expect(twice.records).toHaveLength(LIVE_RECORDS.length)
    expect(twice).toBe(once)
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

  it("keeps its lines through a dropped connection: the browser resumes after the last line", () => {
    const { result } = renderHook(() => useJobLog("job-0006", true), { wrapper })
    const source = FakeEventSource.last()
    act(() => {
      source.onopen?.()
      source.emit("line", "step 1")
    })
    act(() => {
      source.readyState = 0
      source.onerror?.()
    })
    expect(result.current.status).toBe("reconnecting")
    act(() => {
      source.onopen?.()
      source.emit("line", "step 2")
    })
    expect(result.current.lines).toEqual(["step 1", "step 2"])
    expect(FakeEventSource.instances).toHaveLength(1)
  })
})
