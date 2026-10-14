/**
 * Server-sent event streams of the backend (webapp/runs.py stream, webapp/jobs.py log_stream):
 * - GET /api/runs/{id}/stream: `event: record` per events.jsonl line (id = line number), then
 *   `event: done` when the agent no longer writes the run -> `useRunStream`, folded by the
 *   timeline reducer (src/lib/timeline.ts);
 * - GET /api/jobs/{id}/log: `event: line` per log line, then `event: done` -> `useJobLog`.
 *
 * Every record is sent with `id: <line>`, and the backend reads `Last-Event-ID`. So after a drop
 * (an SSH-tunnel hiccup, an idle proxy) the stream is left to EventSource's own reconnection,
 * which sends the last id, and the server resumes after that line: nothing is replayed and the
 * job log keeps its lines. Only when the browser gives up (readyState CLOSED: an HTTP error) is
 * the stream an error, and `reconnect()` opens a new one, which the server replays from the first
 * line (the run's records are deduplicated by task id, and the job log starts an empty buffer).
 * A finished stream would be reopened forever by the browser, so it is closed on `done`.
 */
import { useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react"

import type { EventRecord, Step } from "@/api/types"
import { initialTimeline, timelineReducer, type TimelineState } from "@/lib/timeline"

import { urls } from "./client"
import { keys } from "./hooks"

/** reconnecting: the connection dropped and EventSource is reconnecting by itself (Last-Event-ID). */
export type StreamStatus = "idle" | "connecting" | "open" | "reconnecting" | "done" | "error"

type Handlers = Record<string, (data: string) => void>

/** EventSource.CLOSED (2): the browser will not reconnect by itself. */
const CLOSED = 2

interface StreamOptions {
  enabled: boolean
  /** event names that end the stream */
  doneEvents?: string[]
}

/**
 * One EventSource for `url` with named-event handlers; returns its status and a reconnect action
 * (a new EventSource, for a stream the browser gave up on). `key` changes with every new one.
 */
export function useEventSource(url: string | null, handlers: Handlers, options: StreamOptions) {
  const { enabled } = options
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
    const finish = () => {
      source.close()
      setState({ key, status: "done" })
    }
    source.onopen = () => setState({ key, status: "open" })
    source.onerror = () => {
      // CONNECTING: the browser reconnects by itself and resumes after the last id; CLOSED: it gave up
      const status: StreamStatus = source.readyState === CLOSED ? "error" : "reconnecting"
      setState((s) => (s.key === key && s.status === "done" ? s : { key, status }))
    }
    const ends = doneEvents.split(",")
    for (const name of new Set([...names.split(","), ...ends])) {
      if (!name) continue
      source.addEventListener(name, (event) => {
        current.current[name]?.((event as MessageEvent<string>).data)
        if (ends.includes(name)) finish()
      })
    }
    return () => source.close()
  }, [url, enabled, key, names, doneEvents])

  const reconnect = useCallback(() => setAttempt((a) => a + 1), [])
  const status: StreamStatus = !url || !enabled ? "idle" : state.key === key ? state.status : "connecting"
  return { status, reconnect, key }
}

// --- run stream ---------------------------------------------------------------------------------

interface LiveState {
  records: EventRecord[]
  /** task ids already kept: a stream opened again replays from the first line, which adds nothing */
  seen: Record<string, true>
  done: boolean
}

type LiveAction = { type: "record"; record: EventRecord } | { type: "done" }

/** The live records of a run, each kept once (exported for its test). */
export function liveReducer(state: LiveState, action: LiveAction): LiveState {
  if (action.type === "done") return { ...state, done: true }
  const id = action.record.task_id
  if (id && state.seen[id]) return state
  return { ...state, records: [...state.records, action.record], seen: id ? { ...state.seen, [id]: true } : state.seen }
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
  const [liveState, dispatch] = useReducer(liveReducer, { records: [], seen: {}, done: false })
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
    { enabled: live && !liveState.done },
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
 * The live log of a job (`event: line` per line, `event: done` with the job). After a drop the
 * browser resumes after the last line (Last-Event-ID), so the lines carry on; a stream opened
 * again by hand (`reconnect`) is replayed from the first line, so its lines start empty. On
 * `done` the job's queries are refetched, so its state and steps catch up with the log.
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
