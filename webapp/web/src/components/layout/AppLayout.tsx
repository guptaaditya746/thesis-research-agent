/** The frame of every page: sidebar, the mock-mode banner, a header with search and theme, and the page. */
import { Suspense } from "react"
import { Outlet } from "react-router"

import { CardsSkeleton } from "@/components/states"
import { Separator } from "@/components/ui/separator"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"

import { AppSidebar } from "./AppSidebar"
import { CommandMenu } from "./CommandMenu"
import { JobWatcher } from "./JobWatcher"
import { MockBanner } from "./MockBanner"
import { ThemeToggle } from "./ThemeToggle"

export function AppLayout() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="min-w-0">
        <MockBanner />
        <header className="sticky top-0 z-10 flex h-12 shrink-0 items-center gap-2 border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/80">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-1 data-[orientation=vertical]:h-4" />
          <div className="flex-1" />
          <CommandMenu />
          <ThemeToggle />
        </header>
        <main id="main" className="min-w-0 flex-1 p-4 md:p-6">
          <Suspense fallback={<CardsSkeleton />}>
            <Outlet />
          </Suspense>
        </main>
      </SidebarInset>
      <JobWatcher />
    </SidebarProvider>
  )
}
