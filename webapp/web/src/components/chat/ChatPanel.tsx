/**
 * The chat panel (lazy chunk, loaded the first time the chat opens, then kept mounted so the
 * thread survives closing the sheet): one assistant-ui runtime over AI SDK v5's transport to
 * POST /api/chat, which the backend answers with pydantic-ai's VercelAIAdapter (UI message
 * stream v1). Built from assistant-ui primitives; the assistant's tool calls (list_runs,
 * get_run, sparql, ...) show as one line each, so it is clear what an answer was read from.
 */
import {
  ActionBarPrimitive,
  AssistantIf,
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  type TextMessagePartProps,
  type ToolCallMessagePartProps,
} from "@assistant-ui/react"
import { useChatRuntime } from "@assistant-ui/react-ai-sdk"
import { ArrowDownIcon, CheckIcon, CopyIcon, Loader2Icon, SendHorizonalIcon, SquareIcon, WrenchIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"

import { useChat } from "./context"
import { chatTransport } from "./transport"

const SUGGESTIONS_RUN = [
  "Summarise this run: answer, claims and cost.",
  "Which answer facts have no claim behind them?",
  "Show the passage behind the first fact.",
]
const SUGGESTIONS = ["Which runs ended without an answer?", "Compare claim_on and claim_off for q01.", "What is the primary test result?"]

export default function ChatPanel() {
  const { open, setOpen, runId } = useChat()
  const runtime = useChatRuntime({ transport: chatTransport() })
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="right" className="gap-0 p-0 data-[side=right]:w-full data-[side=right]:sm:max-w-lg">
          <SheetHeader className="border-b pr-12">
            <SheetTitle>Chat about runs</SheetTitle>
            <SheetDescription className="flex flex-wrap items-center gap-2">
              {runId ? (
                <>
                  Scoped to run <Badge variant="secondary" className="font-mono">{runId}</Badge>
                </>
              ) : (
                "All runs. Open a run page to ask about one run."
              )}
            </SheetDescription>
          </SheetHeader>
          <Thread suggestions={runId ? SUGGESTIONS_RUN : SUGGESTIONS} />
        </SheetContent>
      </Sheet>
    </AssistantRuntimeProvider>
  )
}

function Thread({ suggestions }: { suggestions: string[] }) {
  return (
    <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col">
      <ThreadPrimitive.Viewport className="relative flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-4" aria-live="polite">
        <AssistantIf condition={({ thread }) => thread.isEmpty}>
          <div className="my-auto space-y-3 text-center">
            <p className="text-sm text-muted-foreground">
              Ask about answers, claims, passages and scores. The assistant reads the run files and the provenance store; it changes nothing.
            </p>
            <div className="flex flex-col gap-2">
              {suggestions.map((prompt) => (
                <ThreadPrimitive.Suggestion key={prompt} prompt={prompt} send asChild>
                  <Button variant="outline" size="sm" className="h-auto justify-start py-2 text-left whitespace-normal">
                    {prompt}
                  </Button>
                </ThreadPrimitive.Suggestion>
              ))}
            </div>
          </div>
        </AssistantIf>
        <ThreadPrimitive.Messages components={{ UserMessage, AssistantMessage }} />
        <ThreadPrimitive.ScrollToBottom asChild>
          <Button variant="outline" size="icon-sm" className="sticky bottom-0 mx-auto rounded-full disabled:invisible" aria-label="Scroll to the latest message">
            <ArrowDownIcon />
          </Button>
        </ThreadPrimitive.ScrollToBottom>
      </ThreadPrimitive.Viewport>
      <Composer />
    </ThreadPrimitive.Root>
  )
}

function Composer() {
  return (
    <ComposerPrimitive.Root className="flex items-end gap-2 border-t p-3">
      <ComposerPrimitive.Input
        autoFocus
        rows={1}
        placeholder="Ask about a run…"
        aria-label="Message"
        className="max-h-40 min-h-9 flex-1 resize-none rounded-md border bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
      />
      <AssistantIf condition={({ thread }) => !thread.isRunning}>
        <ComposerPrimitive.Send asChild>
          <Button size="icon" aria-label="Send">
            <SendHorizonalIcon />
          </Button>
        </ComposerPrimitive.Send>
      </AssistantIf>
      <AssistantIf condition={({ thread }) => thread.isRunning}>
        <ComposerPrimitive.Cancel asChild>
          <Button size="icon" variant="outline" aria-label="Stop">
            <SquareIcon />
          </Button>
        </ComposerPrimitive.Cancel>
      </AssistantIf>
    </ComposerPrimitive.Root>
  )
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="ml-8 self-end rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground">
      <MessagePrimitive.Parts components={{ Text: TextPart }} />
    </MessagePrimitive.Root>
  )
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="group mr-8 space-y-2 text-sm">
      <MessagePrimitive.Parts components={{ Text: TextPart, tools: { Fallback: ToolCall } }} />
      <MessagePrimitive.Error>
        <p className="text-destructive" role="alert">The assistant could not answer (backend or model error).</p>
      </MessagePrimitive.Error>
      <ActionBarPrimitive.Root hideWhenRunning autohide="not-last" className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
        <ActionBarPrimitive.Copy asChild>
          <Button variant="ghost" size="icon-xs" aria-label="Copy">
            <AssistantIf condition={({ message }) => message.isCopied}>
              <CheckIcon />
            </AssistantIf>
            <AssistantIf condition={({ message }) => !message.isCopied}>
              <CopyIcon />
            </AssistantIf>
          </Button>
        </ActionBarPrimitive.Copy>
      </ActionBarPrimitive.Root>
    </MessagePrimitive.Root>
  )
}

function TextPart({ text }: TextMessagePartProps) {
  return <p className="leading-relaxed whitespace-pre-wrap">{text}</p>
}

function ToolCall({ toolName, argsText, status }: ToolCallMessagePartProps) {
  const running = status.type === "running"
  return (
    <div className="flex items-center gap-2 rounded-md border bg-muted/40 px-2 py-1 font-mono text-xs text-muted-foreground">
      {running ? <Loader2Icon className="size-3 animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <WrenchIcon className="size-3" aria-hidden="true" />}
      <span className="truncate" title={argsText}>
        {toolName}({argsText && argsText !== "{}" ? argsText : ""})
      </span>
    </div>
  )
}
