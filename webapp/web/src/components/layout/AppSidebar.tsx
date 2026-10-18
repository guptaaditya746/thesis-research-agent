/**
 * The app's sidebar (shadcn `sidebar`): the questions (each opens its guided flow), the viewer's pages, the
 * jobs with a count of the active ones, and the backend's state.
 */
import {
  ActivityIcon,
  BarChart3Icon,
  DatabaseIcon,
  FileCode2Icon,
  FlaskConicalIcon,
  ListOrderedIcon,
  NetworkIcon,
  type LucideIcon,
} from "lucide-react"
import { NavLink, useLocation } from "react-router"

import { isActiveJob, useEvConfig, useHealth, useJobs, useQuestions } from "@/api/ev"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarRail,
} from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"

type Page = { to: string; label: string; icon: LucideIcon; end?: boolean }

const VIEWER: Page[] = [
  { to: "/protocol", label: "Protocols", icon: FileCode2Icon },
  { to: "/corpora", label: "Corpora", icon: DatabaseIcon },
  { to: "/runs", label: "Runs", icon: FlaskConicalIcon },
  { to: "/scores", label: "Scores", icon: BarChart3Icon },
  { to: "/jobs", label: "Jobs", icon: ActivityIcon },
]

function Pages({ pages, badge }: { pages: Page[]; badge?: (to: string) => number }) {
  const { pathname } = useLocation()
  const active = (p: Page) => (p.end ? pathname === p.to : pathname === p.to || pathname.startsWith(`${p.to}/`))
  return (
    <SidebarMenu>
      {pages.map((p) => {
        const count = badge?.(p.to) ?? 0
        return (
          <SidebarMenuItem key={p.to}>
            {/* a proposal belongs to the protocol page */}
            <SidebarMenuButton asChild tooltip={p.label} isActive={active(p) || (p.to === "/protocol" && pathname.startsWith("/proposals"))}>
              <NavLink to={p.to} end={p.end}>
                <p.icon />
                <span>{p.label}</span>
              </NavLink>
            </SidebarMenuButton>
            {count > 0 && <SidebarMenuBadge aria-label={`${count} active jobs`}>{count}</SidebarMenuBadge>}
          </SidebarMenuItem>
        )
      })}
    </SidebarMenu>
  )
}

export function AppSidebar() {
  const { pathname } = useLocation()
  const questions = useQuestions()
  const jobs = useJobs()
  const active = jobs.data?.filter(isActiveJob).length ?? 0

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild tooltip="Evidence-level synthesis">
              <NavLink to="/">
                <span className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <NetworkIcon className="size-4" />
                </span>
                <span className="grid flex-1 text-left leading-tight">
                  <span className="truncate font-semibold">Thesis</span>
                  <span className="truncate text-xs text-muted-foreground">evidence-level synthesis</span>
                </span>
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Questions</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {questions.isPending && (
                <SidebarMenuItem>
                  <SidebarMenuSkeleton />
                </SidebarMenuItem>
              )}
              {questions.data?.map((q) => (
                <SidebarMenuItem key={q.id}>
                  <SidebarMenuButton asChild tooltip={q.question} isActive={pathname.startsWith(`/flow/${q.id}`)}>
                    <NavLink to={`/flow/${encodeURIComponent(q.id)}`} title={q.question}>
                      <ListOrderedIcon />
                      <span className="truncate">{q.id}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>Viewer</SidebarGroupLabel>
          <SidebarGroupContent>
            <Pages pages={VIEWER} badge={(to) => (to === "/jobs" ? active : 0)} />
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <BackendStatus />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}

function BackendStatus() {
  const health = useHealth()
  const config = useEvConfig()
  const ok = health.data?.ok === true
  return (
    <div className="flex items-center gap-2 px-2 py-1 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden" role="status">
      <span className={cn("size-2 shrink-0 rounded-full", ok ? "bg-status-good" : health.isPending ? "bg-status-neutral" : "bg-status-critical")} aria-hidden="true" />
      <span className="truncate">
        {health.isPending ? "connecting…" : ok ? `backend ${health.data?.version ?? ""}` : "backend unreachable"}
        {config.data && !config.data.llm_key_set ? " · no LLM key" : ""}
      </span>
    </div>
  )
}
