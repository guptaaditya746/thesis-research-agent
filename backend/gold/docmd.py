"""doc.md: the evidence document D for people (M3, plan "Gold"); doc.json stays the source.

One page per question: what was built and how, the coverage over papers (absence recorded, not
assumed), every merged row with the facts behind it and each fact's quote and anchor status, and the
papers by status, so a reviewer can see what the screening found relevant and what failed.
"""
from __future__ import annotations

from typing import Any


def _value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, list):
        return "[" + ", ".join(map(str, value)) + "]"
    return str(value)


def row_title(doc: dict[str, Any], cells: dict[str, Any]) -> str:
    if doc["kind"] == "graph":
        attrs = ", ".join(f"{k}: {_value(v)}" for k, v in (cells.get("attributes") or {}).items())
        return (f"{cells['source']} ({cells['source_type']}) —{cells['predicate']}→ "
                f"{cells['target']} ({cells['target_type']})" + (f" [{attrs}]" if attrs else ""))
    return "; ".join(f"{k}: {_value(v)}" for k, v in cells.items())


def _fact(c: dict[str, Any]) -> str:
    quote = " ".join(str(c["quote"]).split())
    status = c["anchor_status"]
    where = f"{c['paper_id']} part {c['chunk'] + 1}" + (f" piece {'.'.join(c['piece'])}" if c.get("piece") else "")
    retry = f", first quote rejected ({c['first_reason']})" if c.get("first_reason") else ""
    if (c.get("retry") or {}).get("error"):
        retry += f", retry call failed ({c['retry']['error']})"
    return f"- `{c['id']}` {where} · {c['s']} — {c['p']} — {c['o']} · \"{quote}\" [{status}{retry}]"


def render(doc: dict[str, Any], candidates: list[dict[str, Any]], screening: list[dict[str, Any]]) -> str:
    built, cov, counts = doc["built"], doc["coverage"], doc["counts"]
    concept = doc["concept"]
    settings = built["settings"]
    served = ", ".join(built["models"]["served"]) or "served name unknown"
    lines = [f"# {doc['qid']}: {doc.get('question') or concept['title']}", "",
             f"Concept: **{concept['title']}**. {concept['definition']}", "",
             f"Built {built['ended_at']} from commit {built.get('git_commit') or 'unknown'} with "
             f"{', '.join(built['models']['aliases'])} ({served}); "
             f"chunks of at most {settings['chunk_chars']} characters, temperature {settings['temperature']}, "
             f"seed {settings['seed']}.", "",
             f"Screening: {built['screening_scope']}. Extraction: {built['extraction_scope']}. Every quote is "
             "checked as the agent's claims are (agent/anchor.py).", "",
             "## Coverage", "",
             "| papers | relevant | not relevant | no text | error |", "|---|---|---|---|---|",
             f"| {cov['papers']} | {cov['relevant']} | {cov['not_relevant']} | {cov['no_text']} | {cov['error']} |", ""]
    if cov.get("partial"):
        lines += [f"Partial build: {cov['papers']} of {cov['papers_in_corpus']} papers in the corpus "
                  f"(max_papers {settings['max_papers']}, only_papers {settings['only_papers'] or 'all'}).", ""]
    rejected = ", ".join(f"{reason} {n}" for reason, n in counts["rejected"].items()) or "none"
    lines += [f"{counts['candidates']} candidate facts from {counts['chunks_relevant']} relevant of "
              f"{counts['chunks']} chunks: {counts['anchored']} anchored, rejected: {rejected}; "
              f"{counts['retried']} quotes retried, {counts['fixed_by_retry']} fixed by the retry. "
              f"{counts['rows']} rows after merging.", ""]
    retry_errors, too_long = counts.get("retry_errors", 0), counts.get("too_long", 0)
    if counts["chunks_error"] or counts["extraction_errors"] or retry_errors:
        lines += [f"Failed calls: {counts['chunks_error']} chunk screenings, {counts['extraction_errors']} "
                  f"extractions, {retry_errors} facts whose quote retry failed. "
                  + (f"{too_long} of the chunks are too long for one call even in pieces: a rerun cannot fix "
                     "those, a smaller GOLD_CHUNK_CHARS can. " if too_long else "")
                  + "Run the build again to retry the others.", ""]
    if counts.get("split_chunks"):
        lines += [f"{counts['split_chunks']} chunks were too long for one call and were read in halves.", ""]

    by_id = {c["id"]: c for c in candidates}
    lines += ["## Rows", ""]
    for n, row in enumerate(doc["rows"], 1):
        lines += [f"### {n}. {row_title(doc, row['cells'])}", "",
                  f"Papers: {', '.join(row['papers'])} · {len(row['candidates'])} facts, "
                  f"{row['anchored']} anchored", ""]
        for name, values in (row.get("conflicts") or {}).items():
            lines.append(f"Conflicting values for {name}: {', '.join(map(_value, values))} (the first is kept).")
        if row.get("conflicts"):
            lines.append("")
        lines += [_fact(by_id[i]) for i in row["candidates"]] + [""]
    if not doc["rows"]:
        lines += ["No rows.", ""]

    lines += ["## Papers", ""]
    for status, title in (("relevant", "Relevant"), ("error", "Not fully read (error)"), ("no_text", "No text"),
                          ("not_relevant", "Not relevant")):
        group = [r for r in screening if r["status"] == status]
        if not group:
            continue
        lines += [f"### {title} ({len(group)})", ""]
        for r in group:
            if status == "relevant":
                extra = f" · {r['candidates']} candidates" + (" · nothing extracted" if not r["candidates"] else "")
                errors = f" · failed chunks {r['chunks_error']}" if r["chunks_error"] else ""
                if r.get("extraction_errors"):
                    errors += f" · extraction failed in chunks {r['extraction_errors']}"
                if r.get("retry_errors"):
                    errors += f" · quote retry failed in chunks {r['retry_errors']}"
                lines.append(f"- {r['paper_id']}: relevant parts {[c + 1 for c in r['chunks_relevant']]} of "
                             f"{r['chunks']}{extra}{errors}")
                lines += [f"  - {finding}" for finding in r["findings"]]
            elif status == "not_relevant":
                lines.append(f"- {r['paper_id']} ({r['chunks']} parts)")
            else:
                lines.append(f"- {r['paper_id']}: {r.get('error') or r.get('reason') or ''}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
