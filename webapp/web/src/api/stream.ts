/**
 * Server-sent event streams of the backend (webapp/runs.py stream, webapp/jobs.py log_stream):
 * - GET /api/runs/{id}/stream: `event: record` per events.jsonl line (id = line number), then
 *   `event: done` when the agent no longer writes the run -> `useRunStream`, folded by the
 *   timeline reducer (src/lib/timeline.ts);
 * - GET /api/jobs/{id}/log: `event: line` per log line, then `event: done` -> `useJobLog`.
 *
 * EventSource reconnects by itself after any drop, and a finished stream would then replay
 * forever. So a stream is closed on `done` and on error; the run stream reconnects after a
 * pause while the run is live with a new EventSource, which the server replays from the first
 * line (the reducer is idempotent, a replay is harmless); the job log starts again from an empty
 * buffer when reconnected by hand.
 */
import { useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react"

import type { EventRecord, Step } from "@/api/types"
import { initialTimeline, timelineReducer, type TimelineState } from "@/lib/timeline"

import { urls } from "./client"
import { keys } from "./hooks"

export type StreamStatus = "idle" | "connecting" | "open" | "done" | "error"

type Handlers = Record<string, (data: string) => void>

interface StreamOptions {
  enabled: boolean
  /** reconnect this long after an error; null = stay closed until `reconnect()` */
  reconnectMs?: number | null
  /** event names that end the stream */
  doneEvents?: string[]
}

/** One EventSource for `url` with named-event handlers; returns its status and a reconnect action. */
export function useEventSource(url: string | null, handlers: Handlers, options: StreamOptions) {
  const { enabled, reconnectMs = null } = options
  const doneEvents = (options.doneEvents ?? ["done"]).join(",")
  const names = Object.keys(handlers).sort().join(",")
  const current = useRef(handlers)
  useEffect(() => {
    current.current = handlers
  })
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<{ key: string; status: StreamStatus }>({ key: "", status: "connecting" })
  const key = `${url}#${attempt}`

  useEffect(() => {
    if (!url || !enabled) return
    if (typeof EventSource === "undefined") {
      queueMicrotask(() => setState({ key, status: "error" }))
      return
    }
    const source = new EventSource(url)
    let timer: ReturnType<typeof setTimeout> | undefined
    const finish = () => {
      source.close()
      setState({ key, status: "done" })
    }
    source.onopen = () => setState({ key, status: "open" })
    source.onerror = () => {
      source.close()
      setState((s) => (s.key === key && s.status === "done" ? s : { key, status: "error" }))
      if (reconnectMs !== null) timer = setTimeout(() => setAttempt((a) => a + 1), reconnectMs)
    }
    const ends = doneEvents.split(",")
    for (const name of new Set([...names.split(","), ...ends])) {
      if (!name) continue
      source.addEventListener(name, (event) => {
        current.current[name]?.((event as MessageEvent<string>).data)
        if (ends.includes(name)) finish()
      })
    }
    return () => {
      clearTimeout(timer)
      source.close()
    }
  }, [url, enabled, key, names, doneEvents, reconnectMs])

  const reconnect = useCallback(() => setAttempt((a) => a + 1), [])
  const status: StreamStatus = !url || !enabled ? "idle" : state.key === key ? state.status : "connecting"
  return { status, reconnect, key }
}

// --- run stream ---------------------------------------------------------------------------------

interface LiveState {
  records: EventRecord[]
  done: boolean
}

type LiveAction = { type: "record"; record: EventRecord } | { type: "done" }

function liveReducer(state: LiveState, action: LiveAction): LiveState {
  return action.type === "done" ? { ...state, done: true } : { ...state, records: [...state.records, action.record] }
}

function parseRecord(data: string): EventRecord | null {
  try {
    const value: unknown = JSON.parse(data)
    return value && typeof value === "object" && "subtype" in value ? (value as EventRecord) : null
  } catch {
    return null
  }
}

/**
 * The timeline of a run: the steps the backend summarised (`seed`) folded with the live
 * records. While `live`, the stream is open; on `done` the run's queries are refetched.
 */
export function useRunStream(runId: string, { live, seed }: { live: boolean; seed: Step[] | undefined }) {
  const client = useQueryClient()
  const [liveState, dispatch] = useReducer(liveReducer, { records: [], done: false })
  const { status, reconnect } = useEventSource(
    live ? urls.runStream(runId) : null,
    {
      record: (data) => {
        const record = parseRecord(data)
        if (record) dispatch({ type: "record", record })
      },
      done: () => {
        dispatch({ type: "done" })
        void client.invalidateQueries({ queryKey: keys.run(runId) })
        void client.invalidateQueries({ queryKey: keys.runs, exact: false })
      },
    },
    { enabled: live && !liveState.done, reconnectMs: 3_000 },
  )
  const timeline: TimelineState = useMemo(() => {
    const seeded = seed ? timelineReducer(initialTimeline, { type: "seed", steps: seed }) : initialTimeline
    const folded = liveState.records.reduce((s, record) => timelineReducer(s, { type: "record", record }), seeded)
    return liveState.done ? timelineReducer(folded, { type: "done" }) : folded
  }, [seed, liveState])
  return { timeline, status: liveState.done ? ("done" as const) : status, reconnect }
}

// --- job log ------------------------------------------------------------------------------------

const MAX_LINES = 5_000

/**
 * The live log of a job (`event: line` per line, `event: done` with the job); lines restart empty
 * on every (re)connection, since a new EventSource is replayed from the first line. On `done` the
 * job's queries are refetched, so its state and steps catch up with the log.
 */
export function useJobLog(jobId: string | null, enabled: boolean) {
  const client = useQueryClient()
  const [buffer, setBuffer] = useState<{ key: string; lines: string[] }>({ key: "", lines: [] })
  const keyRef = useRef("")
  const append = (line: string) =>
    setBuffer((b) => {
      const lines = b.key === keyRef.current ? b.lines : []
      const next = lines.length >= MAX_LINES ? [...lines.slice(lines.length - MAX_LINES + 1), line] : [...lines, line]
      return { key: keyRef.current, lines: next }
    })
  const { status, reconnect, key } = useEventSource(
    jobId ? urls.jobLog(jobId) : null,
    { message: append, line: append, done: () => void client.invalidateQueries({ queryKey: keys.jobs }) },
    { enabled: !!jobId && enabled, doneEvents: ["done"] },
  )
  useEffect(() => {
    keyRef.current = key
  }, [key])
  return { lines: buffer.key === key ? buffer.lines : [], status, reconnect }
}
