/** The app's top-level pages with their icons, shared by the sidebar and the command menu so both look alike. */
import { ActivityIcon, BarChart3Icon, ClipboardCheckIcon, DatabaseIcon, FileCode2Icon, FlaskConicalIcon, ListChecksIcon, ListOrderedIcon, WorkflowIcon, type LucideIcon } from "lucide-react"

export type Page = { to: string; label: string; icon: LucideIcon; end?: boolean }

export const HOME: Page = { to: "/", label: "Questions", icon: ListOrderedIcon, end: true }

export const VIEWER: Page[] = [
  { to: "/system", label: "System", icon: WorkflowIcon },
  { to: "/plan", label: "Plan", icon: ClipboardCheckIcon },
  { to: "/review", label: "Review", icon: ListChecksIcon },
  { to: "/protocol", label: "Protocols", icon: FileCode2Icon },
  { to: "/corpora", label: "Corpora", icon: DatabaseIcon },
  { to: "/runs", label: "Runs", icon: FlaskConicalIcon },
  { to: "/report", label: "Report", icon: BarChart3Icon },
  { to: "/jobs", label: "Jobs", icon: ActivityIcon },
]
