"""The corpus tool server: six MCP tools a pack-builder agent searches and reads one corpus with.

Ported from research-harness-ui `packages/mcp_corpus` (server.py `create_server`), cut to the six tools the pack
builder needs and rebuilt on this repo's corpus reader. Hard rule (docs/evidence-system.md Part A): the server reads
the corpus through `evaluation.baselines.common.SystemCorpus` only, once, when it is made: `manifest.json` and the
files it lists directly in `papers/`, each checked against its sha256. A manifest that lists anything else (say
ground_truth.json) is refused there, and no tool opens a file afterwards, so no gold file can be read.

| Tool | Returns |
|---|---|
| list_papers() | [{id, title, chars}], title = the paper's first `# ` line |
| read_paper(paper_id, offset=0, limit=20000) | {id, text, offset, total} |
| read_section(paper_id, heading) | {id, heading, start, end, text}: the `## heading` block up to the next `#`/`##` heading |
| search(query, k=10) | BM25 (rank_bm25.BM25Okapi) over paragraphs: [{paper, start, end, score, text}] |
| grep(regex, limit=50) | [{paper, line, start, text}]: matching lines, text cut to 200 characters |
| tables(paper_id) | [{header, rows, start, end}]: the paper's Markdown tables |

Search is word search only, no embeddings: paragraphs are the runs of text between blank lines (as
`rag.paragraph`, `rag.BLANK_LINE`), tokens are `\\w+` lower-cased (`rag.tokens`); only paragraphs sharing a word with
the query (score > 0) are returned, best first. Offsets are character offsets into the paper text, so
`text == paper[start:end]`. An unknown paper_id, an unknown heading or an invalid regex is an error (a ToolError
whose message names the known ids or headings), never an empty result. `grep` runs the model's regex with the `regex`
package and a time limit for the whole call (GREP_SECONDS): a pattern that backtracks without end, such as `(a+)+$`,
is an error instead of a hung agent (the exchange timeout does not cover tools run in process).

The server is an MCP `MCPServer` (mcp 2.x's name for FastMCP; `mcp.server.fastmcp` is gone there). It serves over
stdio (`packbuilder serve --corpus DIR`) or in process: `pydantic_ai.mcp.MCPToolset(create_server(corpus))`
(preflight P21), which tests and the pack-builder agent use without a subprocess.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import regex as _regex
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from rank_bm25 import BM25Okapi

from evaluation.baselines.common import Paper, SystemCorpus
from evaluation.baselines.rag import BLANK_LINE, tokens

GREP_TEXT = 200
GREP_SECONDS = 5.0      # the time limit of one grep call, over all lines of all papers
HEADING = re.compile(r"^(#{1,2}) +(.+?) *#*[ \t]*$", re.MULTILINE)   # a `#` or `##` heading line
TABLE_ROW = re.compile(r"^[ \t]*\|.*\|[ \t]*$")
TABLE_RULE = re.compile(r"^[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*(\|[ \t]*:?-{3,}:?[ \t]*)*\|?[ \t]*$")


@dataclass(frozen=True)
class Paragraph:
    paper: str
    start: int
    end: int
    text: str


def paragraphs(paper: Paper) -> list[Paragraph]:
    """The paper's runs of text between blank lines, without surrounding whitespace; empty runs are dropped."""
    out, a = [], 0
    for brk in [*BLANK_LINE.finditer(paper.text), None]:
        b = brk.start() if brk else len(paper.text)
        chunk = paper.text[a:b]
        if chunk.strip():
            lead = len(chunk) - len(chunk.lstrip())
            s, e = a + lead, a + len(chunk.rstrip())
            out.append(Paragraph(paper.id, s, e, paper.text[s:e]))
        a = brk.end() if brk else b
    return out


def title(text: str) -> str:
    """The text of the paper's first `# ` line, else ''."""
    return next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), "")


def lines(text: str) -> list[tuple[int, str]]:
    """(start offset, line without its line break) for every line of `text`."""
    out, pos = [], 0
    for raw in text.splitlines(keepends=True):
        out.append((pos, raw.rstrip("\r\n")))
        pos += len(raw)
    return out


def cells(row: str) -> list[str]:
    row = row.strip()
    row = row[1:] if row.startswith("|") else row
    row = row[:-1] if row.endswith("|") else row
    return [c.strip() for c in row.split("|")]


def markdown_tables(text: str) -> list[dict[str, Any]]:
    """Each Markdown table: a header row, a `|---|` rule, then the following `|...|` rows."""
    rows, out, i = lines(text), [], 0
    while i + 1 < len(rows):
        (start, head), (_, rule) = rows[i], rows[i + 1]
        if not (TABLE_ROW.match(head) and TABLE_RULE.match(rule)):
            i += 1
            continue
        j = i + 2
        while j < len(rows) and TABLE_ROW.match(rows[j][1]):
            j += 1
        last_start, last = rows[j - 1]
        out.append({"header": cells(head), "rows": [cells(r) for _, r in rows[i + 2:j]],
                    "start": start, "end": last_start + len(last.rstrip())})
        i = j
    return out


def sections(text: str) -> list[tuple[str, int, int]]:
    """(heading, start, end) of each `## ` block: from its heading line to the next `#` or `##` heading."""
    heads = list(HEADING.finditer(text))
    out = []
    for n, m in enumerate(heads):
        if m.group(1) == "##":
            end = heads[n + 1].start() if n + 1 < len(heads) else len(text)
            out.append((m.group(2).strip(), m.start(), m.start() + len(text[m.start():end].rstrip())))
    return out


def create_server(corpus: Path) -> MCPServer:
    """The corpus tool server over `corpus` (its manifest.json and papers/, read once, now)."""
    papers = {p.id: p for p in SystemCorpus(Path(corpus)).papers}
    chunks = [para for p in papers.values() for para in paragraphs(p)]
    bm25 = BM25Okapi([tokens(c.text) or ["\0"] for c in chunks]) if chunks else None
    mcp = MCPServer("corpus")
    ID = "paper_id is an id from list_papers; an unknown id is an error, not an empty result."

    def paper(paper_id: str) -> Paper:
        if paper_id not in papers:
            raise ToolError(f"unknown paper_id {paper_id!r}; known: {', '.join(papers)}")
        return papers[paper_id]

    @mcp.tool(description="List the corpus's papers: id, title (the first '# ' line) and length in characters.")
    def list_papers() -> list[dict[str, Any]]:
        return [{"id": p.id, "title": title(p.text), "chars": len(p.text)} for p in papers.values()]

    @mcp.tool(description="Read a paper's text from character `offset`, at most `limit` characters; `total` is the "
                          "paper's length, so read on from offset + limit while it is below total. " + ID)
    def read_paper(paper_id: str, offset: int = 0, limit: int = 20000) -> dict[str, Any]:
        text = paper(paper_id).text
        if offset < 0 or limit < 1:
            raise ToolError("offset must be >= 0 and limit >= 1")
        return {"id": paper_id, "text": text[offset:offset + limit], "offset": offset, "total": len(text)}

    @mcp.tool(description="Read one '## heading' section of a paper, from its heading to the next heading; an unknown "
                          "heading is an error that lists the paper's headings. " + ID)
    def read_section(paper_id: str, heading: str) -> dict[str, Any]:
        text = paper(paper_id).text
        found = sections(text)
        want = " ".join(heading.lstrip("#").split())
        match = (next((s for s in found if s[0] == want), None)
                 or next((s for s in found if s[0].casefold() == want.casefold()), None))
        if match is None:
            raise ToolError(f"paper {paper_id!r} has no section {heading!r}; its headings: "
                            f"{', '.join(h for h, _, _ in found) or '(none)'}")
        name, start, end = match
        return {"id": paper_id, "heading": name, "start": start, "end": end, "text": text[start:end]}

    @mcp.tool(description="Ranked word search (BM25) over the corpus's paragraphs, best first: the k best paragraphs "
                          "sharing a word with the query, with their paper, character offsets and score. Words "
                          "match exactly, ignoring case (no stemming): 'trial' does not find 'trials'.")
    def search(query: str, k: int = 10) -> list[dict[str, Any]]:
        words = tokens(query)
        if bm25 is None or not words or k < 1:
            return []
        scored = sorted(((float(s), n) for n, s in enumerate(bm25.get_scores(words)) if s > 0),
                        key=lambda sn: (-sn[0], sn[1]))
        return [{"paper": chunks[n].paper, "start": chunks[n].start, "end": chunks[n].end, "score": s,
                 "text": chunks[n].text} for s, n in scored[:k]]

    @mcp.tool(description="Regular-expression search (Python syntax, case-sensitive; use (?i) to ignore case) over "
                          "every line of every paper: up to `limit` matching lines with their paper, line number "
                          "(from 1), character offset of the match and the line (at most 200 characters). An "
                          "invalid regex, or one that runs too long (nested quantifiers such as (a+)+), is an error.")
    def grep(regex: str, limit: int = 50) -> list[dict[str, Any]]:     # `regex`: the tool's argument name
        try:
            pattern = _regex.compile(regex)
        except _regex.error as exc:
            raise ToolError(f"invalid regex {regex!r}: {exc}") from None
        deadline = time.monotonic() + GREP_SECONDS
        out: list[dict[str, Any]] = []
        for p in papers.values():
            for number, (start, line) in enumerate(lines(p.text), 1):
                if len(out) >= limit:
                    return out
                try:
                    m = pattern.search(line, timeout=max(deadline - time.monotonic(), 0.0))
                except TimeoutError:
                    raise ToolError(f"regex {regex!r} ran longer than {GREP_SECONDS:g} s; write it without nested "
                                    "quantifiers such as (a+)+") from None
                if m:
                    out.append({"paper": p.id, "line": number, "start": start + m.start(), "text": line[:GREP_TEXT]})
        return out

    @mcp.tool(description="A paper's Markdown tables: header cells, rows of cells, and the table's character "
                          "offsets. " + ID)
    def tables(paper_id: str) -> list[dict[str, Any]]:
        return markdown_tables(paper(paper_id).text)

    return mcp
