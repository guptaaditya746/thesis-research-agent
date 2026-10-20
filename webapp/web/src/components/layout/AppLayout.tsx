/** The frame of every page: sidebar, the mock-mode banner, a header with search and theme, and the page. */
import { Suspense, useEffect, useRef } from "react"
import { Outlet, useLocation } from "react-router"

import { CardsSkeleton } from "@/components/states"
import { Separator } from "@/components/ui/separator"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"

import { AppSidebar } from "./AppSidebar"
import { CommandMenu } from "./CommandMenu"
import { JobWatcher } from "./JobWatcher"
import { MockBanner } from "./MockBanner"
import { ThemeToggle } from "./ThemeToggle"

/**
 * After a client-side navigation, focus the page (a screen reader otherwise stays on the link that was
 * clicked and hears nothing change); not on the first load, where focus belongs to the document.
 */
function useFocusOnNavigate() {
  const { pathname } = useLocation()
  const main = useRef<HTMLElement>(null)
  const shown = useRef(pathname)   // the path last focused for; StrictMode's double effect must not count as a navigation
  useEffect(() => {
    if (shown.current === pathname) return
    shown.current = pathname
    main.current?.focus({ preventScroll: true })
  }, [pathname])
  return main
}

export function AppLayout() {
  const main = useFocusOnNavigate()
  return (
    <SidebarProvider>
      <a href="#main" className="sr-only rounded-md bg-background px-3 py-2 text-sm font-medium shadow focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50">Skip to content</a>
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
        <main id="main" ref={main} tabIndex={-1} className="min-w-0 flex-1 p-4 outline-none md:p-6">
          <Suspense fallback={<CardsSkeleton />}>
            <Outlet />
          </Suspense>
        </main>
      </SidebarInset>
      <JobWatcher />
    </SidebarProvider>
  )
}
