/**
 * The assistant's replies as Markdown (react-markdown with remark-gfm for tables, task lists and
 * strikethrough): the chat agent answers with tables, lists, bold and code. Safe by construction:
 * raw HTML in a reply is dropped (`skipHtml`, and no rehype-raw), and react-markdown's default URL
 * check keeps javascript: and other unsafe links out. Links open in a new tab.
 */
import ReactMarkdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

const COMPONENTS: Components = {
  a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noreferrer noopener" className="font-medium underline underline-offset-2" />,
  p: ({ node: _node, ...props }) => <p {...props} className="leading-relaxed" />,
  ul: ({ node: _node, ...props }) => <ul {...props} className="list-disc space-y-1 pl-5" />,
  ol: ({ node: _node, ...props }) => <ol {...props} className="list-decimal space-y-1 pl-5" />,
  h1: ({ node: _node, ...props }) => <h3 {...props} className="font-semibold" />,
  h2: ({ node: _node, ...props }) => <h3 {...props} className="font-semibold" />,
  h3: ({ node: _node, ...props }) => <h4 {...props} className="font-semibold" />,
  blockquote: ({ node: _node, ...props }) => <blockquote {...props} className="border-l-2 pl-3 text-muted-foreground" />,
  code: ({ node: _node, ...props }) => <code {...props} className="rounded bg-muted px-1 py-0.5 font-mono text-xs" />,
  pre: ({ node: _node, ...props }) => (
    <pre {...props} className="overflow-x-auto rounded-md bg-muted p-2 font-mono text-xs [&>code]:bg-transparent [&>code]:p-0" />
  ),
  table: ({ node: _node, ...props }) => (
    <div className="overflow-x-auto">
      <table {...props} className="w-full border-collapse text-xs" />
    </div>
  ),
  th: ({ node: _node, ...props }) => <th {...props} className="border bg-muted/50 px-2 py-1 text-left font-medium" />,
  td: ({ node: _node, ...props }) => <td {...props} className="border px-2 py-1 align-top" />,
}

const PLUGINS = [remarkGfm]

export function Markdown({ text }: { text: string }) {
  return (
    <div className="space-y-2 break-words" data-testid="markdown">
      <ReactMarkdown remarkPlugins={PLUGINS} components={COMPONENTS} skipHtml>
        {text}
      </ReactMarkdown>
    </div>
  )
}
