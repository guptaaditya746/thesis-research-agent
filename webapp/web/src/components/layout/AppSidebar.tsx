/** The app's sidebar (shadcn `sidebar`): pages, the 12 questions, and the backend's state. */
import {
  ActivityIcon,
  AwardIcon,
  BarChart3Icon,
  BotIcon,
  CircleIcon,
  LayoutDashboardIcon,
  ListChecksIcon,
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

const PAGES: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: "/", label: "Overview", icon: LayoutDashboardIcon, end: true },
  { to: "/runs", label: "Runs", icon: ListChecksIcon },
  { to: "/results", label: "Results", icon: BarChart3Icon },
  { to: "/gold", label: "Gold", icon: AwardIcon },
  { to: "/jobs", label: "Jobs", icon: ActivityIcon },
]

const CONCEPT_DOT = { picked: "text-status-good", proposed: "text-status-warning", none: "text-muted-foreground/50" }

export function AppSidebar() {
  const { pathname } = useLocation()
  const questions = useQuestions()
  const jobs = useJobs()
  const active = jobs.data?.filter((j) => j.state === "running" || j.state === "queued").length ?? 0

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild tooltip="Thesis agent">
              <NavLink to="/">
                <span className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <BotIcon className="size-4" />
                </span>
                <span className="grid flex-1 text-left leading-tight">
                  <span className="truncate font-semibold">Thesis agent</span>
                  <span className="truncate text-xs text-muted-foreground">provenance while researching</span>
                </span>
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Pages</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {PAGES.map(({ to, label, icon: Icon, end }) => (
                <SidebarMenuItem key={to}>
                  <SidebarMenuButton
                    asChild
                    tooltip={label}
                    isActive={end ? pathname === to : pathname.startsWith(to)}
                  >
                    <NavLink to={to} end={end}>
                      <Icon />
                      <span>{label}</span>
                    </NavLink>
                  </SidebarMenuButton>
                  {to === "/jobs" && active > 0 && <SidebarMenuBadge aria-label={`${active} active jobs`}>{active}</SidebarMenuBadge>}
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>Questions</SidebarGroupLabel>
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
                    isActive={pathname === `/questions/${q.id}` || pathname === `/compare/${q.id}`}
                  >
                    <NavLink to={`/questions/${q.id}`} title={q.question}>
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
