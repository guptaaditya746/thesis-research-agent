"""World -> PaperOrchestra inputs per paper (idea_sparse.md + experimental_log.md). Code only.

Holdings go in as DATA (subject | action | source), never as finished sentences: in the law pilot a fixed sentence
per relation was copied by the writer 10-13 times per paper and made planted sentences easy to spot.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from paperfactory.packs import Field, Genre, fill


def _name(w: dict[str, Any], eid: str) -> str:
    return w["entities"][eid]["label"]


def _attrs(w: dict[str, Any], f: Field, eid: str) -> str:
    e = w["entities"][eid]
    parts = []
    for a, typ in f.kinds[e["kind"]].get("attrs", {}).items():
        v = e["attrs"][a]
        parts.append(f"{a}: {_name(w, v) if typ.startswith('ref:') else v}")
    return "; ".join(parts)


def materials(w: dict[str, Any], f: Field, g: Genre, pid: str) -> tuple[str, str]:
    p = w["papers"][pid]
    words = f.words
    facts = p["claims"] + p["decoys"]
    ents = sorted({x for s, _, o in facts for x in (s, o)})
    idea = f"""# {p['title_hint']}

## Problem Statement
{p['issue']}

## Core Thesis
{p['thesis']}

## Approach
An analysis of the {words['subject_plural']} listed in the log, read against the sources they deal with.

## Expected Contribution
A clear account of how the {words['subject_plural']} treated these sources, and an argued view on which line of
authority should be followed.
"""
    lines = ["# Argument Log", "", "## 1. Setting",
             f"* **Genre:** argument paper ({words['paper_kind']}).",
             f"* **Setting:** {f.raw['setting']}",
             f"* **Issue:** {p['issue']}", f"* **Thesis to defend:** {p['thesis']}", "", "## 2. Sources"]
    for kind in f.kinds:
        ids = [e for e in ents if w["entities"][e]["kind"] == kind]
        if ids:
            lines += [f"### {kind.replace('_', ' ').capitalize()}", "| Name | Short names | Details |", "|---|---|---|"]
            lines += [f"| {_name(w, e)} | {', '.join(w['entities'][e].get('alt', []))} | {_attrs(w, f, e)} |"
                      for e in ids]
            lines.append("")
    lines += ["## 3. Holdings (data; state each in your own words)",
              "Action meanings: " + "; ".join(f"{d['words']} = {d['meaning']}" for d in f.relations.values()) + ".",
              "", f"| {words['subject_kind'].capitalize()} | Action | Source |", "|---|---|---|"]
    lines += [f"| {_name(w, s)} | {f.rel_words(r)} | {_name(w, o)} |" for s, r, o in facts]
    if p.get("conflict"):
        (s1, r1, o1), (s2, r2, _) = p["conflict"]
        lines += ["", "## 4. Conflict", f"* {_name(w, s1)} ({f.rel_words(r1)}) and {_name(w, s2)} ({f.rel_words(r2)}) "
                  f"disagree about {_name(w, o1)}."]
    plan = [fill(x, {k.upper(): v for k, v in words.items()}) for x in g.raw.get("argument_plan", [])]
    lines += ["", "## 5. Argument Plan"] + [f"* {x}" for x in plan] + [
        "", "## 6. Rules",
        f"* Do not invent {words['source_kinds']}, holdings, dates or quotations.",
        "* Keep the meaning of every action exact, but phrase it in your own words and vary the wording; never reuse "
        "one phrase for several holdings and never copy this log's wording.",
        f"* State each holding at least once and at most {g.raw.get('max_mentions_per_fact', 3)} times."]
    return idea, "\n".join(lines) + "\n"


def write_all(w: dict[str, Any], f: Field, g: Genre, out: Path) -> list[str]:
    done = []
    for pid in w["papers"]:
        d = out / "papers" / pid
        d.mkdir(parents=True, exist_ok=True)
        idea, log = materials(w, f, g, pid)
        (d / "idea_sparse.md").write_text(idea, encoding="utf-8")
        (d / "experimental_log.md").write_text(log, encoding="utf-8")
        done.append(pid)
    return done
