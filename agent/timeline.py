"""Trace timeline (row 1.14, P1): one static HTML page per run, from events.jsonl, for debugging.

Steps in order; per step the model call (tokens, parse mode, whether it was the final answer),
the command, the first lines of its output (from out/), the claims sent in that step (accepted
with id and quote, rejected with the reason) and any coverage record. No scripts, no external
files: open runs/<id>/timeline.html in a browser. Not the final viewer (that is 2.11).
"""
from __future__ import annotations

import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .rundir import RunDir

HEAD_LINES = 12
STYLE = """
:root{--bg:#fff;--fg:#1d1d1f;--muted:#6b6b70;--line:#d8d8dc;--code:#f4f4f6;--ok:#11703a;--bad:#a4161a;--warn:#8a5a00}
@media (prefers-color-scheme:dark){:root{--bg:#161618;--fg:#ececf0;--muted:#a0a0a8;--line:#3a3a40;--code:#222226;
--ok:#5fd38d;--bad:#ff7b7b;--warn:#f0b54a}}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0 auto;max-width:1000px;padding:16px}
h1{font-size:20px}.meta{color:var(--muted)}section{border-top:1px solid var(--line);padding:10px 0}
h2{font-size:15px;margin:0 0 6px}pre{background:var(--code);padding:8px;overflow-x:auto;white-space:pre-wrap;
word-break:break-word;margin:4px 0}.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}
.tag{font-size:12px;border:1px solid var(--line);border-radius:4px;padding:0 4px;margin-left:6px}
"""


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _head(run: RunDir, output_file: str | None) -> str:
    if not output_file:
        return ""
    try:
        text = (run.root / output_file).read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return "(output file missing)"
    lines = text.splitlines()
    more = f"\n... {len(lines) - HEAD_LINES} more lines in {output_file}" if len(lines) > HEAD_LINES else ""
    return "\n".join(lines[:HEAD_LINES]) + more


def render(run: RunDir) -> str:
    records = [json.loads(raw) for raw in run.events.read_bytes().splitlines()]
    steps: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        steps[record["step_id"]].append(record)
    config = run.load_config() if run.config.exists() else {}
    parts = [f"<!doctype html><html lang=en><head><meta charset=utf-8>"
             f"<meta name=viewport content='width=device-width,initial-scale=1'>"
             f"<title>Trace {_e(run.run_id)}</title><style>{STYLE}</style></head><body>",
             f"<h1>Trace {_e(run.run_id)}</h1><p class=meta>condition {_e(config.get('condition', '?'))} · "
             f"{len(records)} records · {len(steps)} steps</p>"]
    for step in sorted(steps):
        agents = sorted({r["agent_id"] for r in steps[step]} - {"main", "batch"})  # a subagent's step (row 2.12)
        tag = "".join(f"<span class=tag>{_e(a)}</span>" for a in agents)
        parts.append(f"<section id=step-{step}><h2>Step {step}{tag}</h2>")
        for r in steps[step]:
            meta, gen, used = r["custom_metadata"], r["generated"], r["used"]
            kind = r["subtype"]
            if kind == "ai_model_invocation":
                tokens = (gen.get("usage") or {}).get("total_tokens", "-")
                tags = ("<span class=tag>final answer</span>" if meta.get("final_answer") else
                        "<span class=tag>subagent result</span>" if meta.get("result") else "")  # row 2.12
                if used.get("decoding", "free") != "free":  # conclude reply decoded under the answer schema
                    tags += f"<span class=tag>{_e(used['decoding'])}</span>"
                if meta.get("masked_observations"):  # row 1.15: outputs shown as stubs in this prompt
                    tags += f"<span class=tag>{_e(meta['masked_observations'])} outputs masked</span>"
                status = "" if r["status"] == "finished" else f" <span class=bad>{_e(gen.get('error', r['status']))}</span>"
                parts.append(f"<div>model call {_e(r['task_id'])}: {_e(tokens)} tokens, reply "
                             f"{_e(gen.get('reply', '-'))} ({_e(gen.get('parse', '-'))}), phase "
                             f"{_e(meta.get('phase', '-'))}{tags}{status}</div>")
            elif kind == "agent_tool":
                flags = []
                if meta.get("claim_step"):
                    flags.append(f"<span class=tag>claims {meta.get('claims')}</span>")
                if meta.get("repeat", 1) > 1:
                    flags.append(f"<span class='tag warn'>repeat {meta['repeat']}</span>")
                if gen.get("timed_out"):
                    flags.append("<span class='tag bad'>timeout</span>")
                parts.append(f"<div>command, exit {_e(gen.get('exit_code'))}, {_e(gen.get('output_bytes'))} bytes"
                             f"{''.join(flags)}</div><pre>{_e(used.get('command', ''))}</pre>"
                             f"<pre class=meta>{_e(_head(run, gen.get('output_file')))}</pre>")
            elif kind == "claim":
                if r["status"] == "accepted":
                    quote = (used.get("anchor") or {}).get("exact", "")
                    parts.append(f"<div class=ok>claim {_e(gen.get('claim_id'))} accepted: "
                                 f"({_e(meta.get('s'))}, {_e(meta.get('p'))}, {_e(meta.get('o'))}) in "
                                 f"{_e((used.get('anchor') or {}).get('file'))}</div><pre>{_e(quote)}</pre>")
                else:
                    parts.append(f"<div class=bad>claim rejected: {_e(meta.get('reason'))}</div>"
                                 f"<pre>{_e(meta.get('quote', used.get('quote', '')))}</pre>")
            elif kind == "spawn":  # row 2.12: a subagent started, returned, or a request refused
                event = meta.get("event", "spawn")
                who = gen.get("agent_id", "")
                what = (f"task: {used.get('task', '')}" if event == "start" else
                        f"exit {gen.get('exit_status')}, claims {', '.join(gen.get('claims', [])) or 'none'}"
                        if event == "return" else gen.get("reason", ""))
                parts.append(f"<div class=warn>spawn {_e(event)} {_e(who)}: {_e(what)}</div>")
            elif kind == "coverage":
                parts.append(f"<div class=warn>coverage: {_e(gen.get('reason'))}"
                             f"{' — ' + _e(json.dumps(gen['detail'], ensure_ascii=False)) if 'detail' in gen else ''}"
                             f"</div>")
            else:
                parts.append(f"<div>{_e(kind)} {_e(r['task_id'])}</div>")
        parts.append("</section>")
    parts.append("</body></html>\n")
    return "".join(parts)


def write_timeline(run: RunDir, path: Path | None = None) -> Path:
    target = path or run.root / "timeline.html"
    target.write_bytes(render(run).encode("utf-8"))
    return target
