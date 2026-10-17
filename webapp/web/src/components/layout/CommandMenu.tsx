/** Ctrl/Cmd+K: jump to a page or a run (and, under earlier work, a question or an agent run); open the chat; switch theme. */
import { useQueryClient } from "@tanstack/react-query"
import { BarChart3Icon, FileQuestionIcon, ListChecksIcon, MessageSquareIcon, MoonIcon, PlayIcon, SearchIcon, SunIcon } from "lucide-react"
import { useTheme } from "next-themes"
import { useEffect, useState } from "react"
import { useNavigate } from "react-router"

import { evKeys, useEvRuns } from "@/api/ev"
import { keys, useQuestions, useRuns } from "@/api/hooks"
import { useChat } from "@/components/chat/context"
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

const PAGES = [
  { to: "/", label: "Evidence-level flow" },
  { to: "/protocol", label: "Protocol" },
  { to: "/corpora", label: "Corpora" },
  { to: "/runs", label: "Runs" },
  { to: "/scores", label: "Scores" },
  { to: "/earlier", label: "Earlier work: questions" },
  { to: "/earlier/runs", label: "Earlier work: runs" },
  { to: "/earlier/results", label: "Earlier work: results" },
  { to: "/earlier/gold", label: "Earlier work: gold" },
  { to: "/earlier/jobs", label: "Earlier work: jobs" },
]

export function CommandMenu() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const client = useQueryClient()
  const { setOpen: setChat } = useChat()
  const { resolvedTheme, setTheme } = useTheme()
  const questions = useQuestions()
  const runs = useRuns()
  const evRuns = useEvRuns()

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
        <Kbd className="ml-auto">Ctrl K</Kbd>
      </Button>
      <Button variant="ghost" size="icon-sm" className="md:hidden" aria-label="Search" onClick={() => setOpen(true)}>
        <SearchIcon />
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen} title="Search" description="Jump to a page, question or run">
        <CommandInput placeholder="Page, question id or run id…" />
        <CommandList>
          <CommandEmpty>Nothing matches.</CommandEmpty>
          <CommandGroup heading="Pages">
            {PAGES.map((p) => (
              <CommandItem key={p.to} onSelect={() => go(p.to)}>
                <BarChart3Icon />
                {p.label}
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandGroup heading="Runs">
            {evRuns.data?.slice(0, 80).map((r) => (
              <CommandItem key={r.id} value={`${r.id} ${r.system}`} onSelect={() => go(`/runs/${encodeURIComponent(r.id)}`)}>
                <ListChecksIcon />
                <span className="font-mono">{r.id}</span>
                <CommandShortcut>{r.system}</CommandShortcut>
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandGroup heading="Earlier work: questions">
            {questions.data?.map((q) => (
              <CommandItem key={q.id} value={`${q.id} ${q.question}`} onSelect={() => go(`/earlier/questions/${q.id}`)}>
                <FileQuestionIcon />
                <span className="font-mono">{q.id}</span>
                <span className="truncate text-muted-foreground">{q.question}</span>
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandGroup heading="Earlier work: runs">
            {runs.data?.slice(0, 50).map((r) => (
              <CommandItem key={r.run_id} value={`${r.run_id} ${r.qid} ${r.condition}`} onSelect={() => go(`/earlier/runs/${encodeURIComponent(r.run_id)}`)}>
                <ListChecksIcon />
                <span className="font-mono">{r.run_id}</span>
                <CommandShortcut>{r.condition}</CommandShortcut>
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandSeparator />
          <CommandGroup heading="Actions">
            <CommandItem
              onSelect={() => {
                setOpen(false)
                setChat(true)
              }}
            >
              <MessageSquareIcon />
              Open chat
              <CommandShortcut>Ctrl J</CommandShortcut>
            </CommandItem>
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
                void client.invalidateQueries({ queryKey: keys.runs })
                void client.invalidateQueries({ queryKey: keys.questions })
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
