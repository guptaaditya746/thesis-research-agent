/** The frame of every page: sidebar, a header with search, chat and theme, and the page. */
import { MessageSquareIcon } from "lucide-react"
import { Suspense } from "react"
import { Outlet } from "react-router"

import { ChatProvider } from "@/components/chat/ChatProvider"
import { ChatSheet } from "@/components/chat/ChatSheet"
import { useChat } from "@/components/chat/context"
import { CardsSkeleton } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"

import { AppSidebar } from "./AppSidebar"
import { CommandMenu } from "./CommandMenu"
import { JobWatcher } from "./JobWatcher"
import { ThemeToggle } from "./ThemeToggle"

export function AppLayout() {
  return (
    <ChatProvider>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset className="min-w-0">
          <header className="sticky top-0 z-10 flex h-12 shrink-0 items-center gap-2 border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/80">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-1 data-[orientation=vertical]:h-4" />
            <div className="flex-1" />
            <CommandMenu />
            <ChatButton />
            <ThemeToggle />
          </header>
          <main id="main" className="min-w-0 flex-1 p-4 md:p-6">
            <Suspense fallback={<CardsSkeleton />}>
              <Outlet />
            </Suspense>
          </main>
        </SidebarInset>
        <ChatSheet />
        <JobWatcher />
      </SidebarProvider>
    </ChatProvider>
  )
}

function ChatButton() {
  const { setOpen, runId } = useChat()
  return (
    <Button variant="ghost" size="sm" onClick={() => setOpen(true)} aria-label={runId ? `Chat about run ${runId}` : "Chat about runs"}>
      <MessageSquareIcon data-icon="inline-start" />
      <span className="hidden sm:inline">Chat</span>
    </Button>
  )
}
