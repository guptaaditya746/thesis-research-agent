/** Ctrl/Cmd+K: jump to a question's flow, a page or a run; switch theme; refresh from disk. */
import { useQueryClient } from "@tanstack/react-query"
import { ListChecksIcon, ListOrderedIcon, MoonIcon, PlayIcon, SearchIcon, SunIcon } from "lucide-react"
import { useTheme } from "next-themes"
import { useEffect, useState } from "react"
import { useNavigate } from "react-router"

import { evKeys, useEvRuns, useQuestions } from "@/api/ev"
import { Button } from "@/components/ui/button"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command"
import { Kbd } from "@/components/ui/kbd"

import { HOME, VIEWER } from "./pages"

const PAGES = [HOME, ...VIEWER]

/** ⌘K on a Mac, Ctrl K elsewhere: the shortcut takes either, the hint shows the one the keyboard has. */
const SHORTCUT = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent) ? "⌘K" : "Ctrl K"

export function CommandMenu() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const client = useQueryClient()
  const { resolvedTheme, setTheme } = useTheme()
  const questions = useQuestions()
  const runs = useEvRuns()

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        setOpen((o) => !o)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  const go = (to: string) => {
    setOpen(false)
    navigate(to)
  }

  return (
    <>
      <Button variant="outline" size="sm" className="hidden w-48 justify-start text-muted-foreground md:inline-flex" onClick={() => setOpen(true)}>
        <SearchIcon data-icon="inline-start" />
        Search…
        <Kbd className="ml-auto">{SHORTCUT}</Kbd>
      </Button>
      <Button variant="ghost" size="icon-sm" className="md:hidden" aria-label="Search" onClick={() => setOpen(true)}>
        <SearchIcon />
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen} title="Search" description="Jump to a question, page or run">
        <CommandInput placeholder="Question, page or run id…" />
        <CommandList>
          <CommandEmpty>Nothing matches.</CommandEmpty>
          <CommandGroup heading="Questions">
            {questions.data?.map((q) => (
              <CommandItem key={q.id} value={`${q.id} ${q.question}`} onSelect={() => go(`/flow/${encodeURIComponent(q.id)}`)}>
                <ListOrderedIcon />
                <span className="truncate">{q.question}</span>
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandGroup heading="Pages">
            {PAGES.map((p) => (
              <CommandItem key={p.to} onSelect={() => go(p.to)}>
                <p.icon />
                {p.label}
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandGroup heading="Runs">
            {runs.data?.slice(0, 80).map((r) => (
              <CommandItem key={r.id} value={`${r.id} ${r.system}`} onSelect={() => go(`/runs/${encodeURIComponent(r.id)}`)}>
                <ListChecksIcon />
                <span className="font-mono">{r.id}</span>
                <CommandShortcut>{r.system}</CommandShortcut>
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandSeparator />
          <CommandGroup heading="Actions">
            <CommandItem
              onSelect={() => {
                setOpen(false)
                setTheme(resolvedTheme === "dark" ? "light" : "dark")
              }}
            >
              {resolvedTheme === "dark" ? <SunIcon /> : <MoonIcon />}
              Switch to {resolvedTheme === "dark" ? "light" : "dark"} theme
            </CommandItem>
            <CommandItem
              onSelect={() => {
                setOpen(false)
                void client.invalidateQueries({ queryKey: evKeys.all })
              }}
            >
              <PlayIcon />
              Refresh from disk
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  )
}
