/**
 * The app's sidebar (shadcn `sidebar`): the evidence-level flow's pages, then the earlier work, labelled as
 * such (with its 12 questions while one of its pages is open), and the backend's state.
 */
import {
  ActivityIcon,
  ArchiveIcon,
  AwardIcon,
  BarChart3Icon,
  CircleIcon,
  DatabaseIcon,
  FileCode2Icon,
  FlaskConicalIcon,
  LayoutDashboardIcon,
  ListChecksIcon,
  NetworkIcon,
  type LucideIcon,
} from "lucide-react"
import { NavLink, useLocation } from "react-router"

import { useConfig, useHealth, useJobs, useQuestions } from "@/api/hooks"
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

const FLOW: Page[] = [
  { to: "/", label: "Flow", icon: LayoutDashboardIcon, end: true },
  { to: "/protocol", label: "Protocol", icon: FileCode2Icon },
  { to: "/corpora", label: "Corpora", icon: DatabaseIcon },
  { to: "/runs", label: "Runs", icon: FlaskConicalIcon },
  { to: "/scores", label: "Scores", icon: BarChart3Icon },
]

const EARLIER: Page[] = [
  { to: "/earlier", label: "Questions", icon: ArchiveIcon, end: true },
  { to: "/earlier/runs", label: "Agent runs", icon: ListChecksIcon },
  { to: "/earlier/results", label: "Results", icon: NetworkIcon },
  { to: "/earlier/gold", label: "Gold", icon: AwardIcon },
  { to: "/earlier/jobs", label: "Jobs", icon: ActivityIcon },
]

const CONCEPT_DOT = { picked: "text-status-good", proposed: "text-status-warning", none: "text-muted-foreground/50" }

function Pages({ pages, badge }: { pages: Page[]; badge?: (to: string) => number }) {
  const { pathname } = useLocation()
  // a proposal belongs to the protocol page
  const active = (p: Page) => (p.end ? pathname === p.to : pathname === p.to || pathname.startsWith(`${p.to}/`))
  return (
    <SidebarMenu>
      {pages.map((p) => {
        const count = badge?.(p.to) ?? 0
        return (
          <SidebarMenuItem key={p.to}>
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
  const earlier = pathname.startsWith("/earlier")
  const questions = useQuestions()
  const jobs = useJobs()
  const active = jobs.data?.filter((j) => j.state === "running" || j.state === "queued").length ?? 0

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
          <SidebarGroupLabel>Evidence-level flow</SidebarGroupLabel>
          <SidebarGroupContent>
            <Pages pages={FLOW} />
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>Earlier work</SidebarGroupLabel>
          <SidebarGroupContent>
            <Pages pages={EARLIER} badge={(to) => (to === "/earlier/jobs" ? active : 0)} />
          </SidebarGroupContent>
        </SidebarGroup>
        {earlier && (
          <SidebarGroup>
            <SidebarGroupLabel>Earlier work: questions</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {questions.isPending &&
                  Array.from({ length: 6 }, (_, i) => (
                    <SidebarMenuItem key={i}>
                      <SidebarMenuSkeleton />
                    </SidebarMenuItem>
                  ))}
                {questions.data?.map((q) => (
                  <SidebarMenuItem key={q.id}>
                    <SidebarMenuButton
                      asChild
                      size="sm"
                      tooltip={q.question}
                      isActive={pathname === `/earlier/questions/${q.id}` || pathname === `/earlier/compare/${q.id}`}
                    >
                      <NavLink to={`/earlier/questions/${q.id}`} title={q.question}>
                        <CircleIcon className={cn("fill-current", CONCEPT_DOT[q.concept.status])} aria-label={`concept ${q.concept.status}`} />
                        <span className="font-mono text-xs">{q.id}</span>
                        <span className="truncate text-muted-foreground">{q.question}</span>
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
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
  const config = useConfig()
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
