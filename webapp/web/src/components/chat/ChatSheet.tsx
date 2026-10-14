/**
 * The chat sheet, reachable from every page (header button, or Ctrl/Cmd+J). Its panel, with
 * assistant-ui and the AI SDK, is a separate chunk loaded on first open and kept mounted
 * afterwards, so the thread survives closing and reopening.
 */
import { lazy, Suspense, useEffect, useState } from "react"

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Spinner } from "@/components/ui/spinner"

import { useChat } from "./context"

const ChatPanel = lazy(() => import("./ChatPanel"))

export function ChatSheet() {
  const { open, setOpen } = useChat()
  const [opened, setOpened] = useState(false)
  if (open && !opened) setOpened(true) // remember the first opening (state from the previous render)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "j" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        setOpen(!open)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, setOpen])

  if (!opened) return null
  return (
    <Suspense
      fallback={
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetContent side="right" className="items-center justify-center">
            <SheetHeader className="sr-only">
              <SheetTitle>Chat about runs</SheetTitle>
              <SheetDescription>Loading the chat</SheetDescription>
            </SheetHeader>
            <Spinner aria-label="Loading the chat" />
          </SheetContent>
        </Sheet>
      }
    >
      <ChatPanel />
    </Suspense>
  )
}
