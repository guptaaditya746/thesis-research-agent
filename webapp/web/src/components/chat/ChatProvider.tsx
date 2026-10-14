/**
 * Chat about runs (plan "Frontend pages" 9): whether the chat sheet is open and which run it is
 * scoped to (the run page in view). Light on purpose: the chat itself (assistant-ui and the AI
 * SDK) loads with the sheet the first time it opens (ChatSheet.tsx).
 */
import { useEffect, useMemo, useState, type ReactNode } from "react"
import { useMatch } from "react-router"

import { ChatContext } from "./context"
import { setChatRun } from "./scope"

export function ChatProvider({ children }: { children: ReactNode }) {
  const runId = useMatch("/runs/:runId")?.params.runId ?? null
  useEffect(() => setChatRun(runId), [runId])
  const [open, setOpen] = useState(false)
  const value = useMemo(() => ({ open, setOpen, runId }), [open, runId])
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}
