"""Style cards: code gives every paper its own layout and voice (22 Nov 2026).

Why: all 116 papers of the 40-paper pilot had the same five sections and one voice ("highlight" in 105 papers,
"nuanced" in 56; outside review). Now each paper gets a card: a template (section layout and paper type, chosen from
the genre's list for the field), a tone, a voice, an opening, a sentence rhythm and a length. No two papers of a
world share the same (template, tone, opening), and every value is used before any is used twice.

The axes and the template lists are data in genre.json ("templates", "style"); this file has no field or genre
names. The card goes into the paper's own guidelines.md (packs.render_paper_template), never as example sentences.
"""
from __future__ import annotations

import random
import re
from typing import Any

from paperfactory.packs import Field, Genre

AXES = ("tone", "voice", "opening", "rhythm", "pages")


def templates_for(g: Genre, f: Field) -> list[dict[str, Any]]:
    t = g.raw.get("templates", {}).get(f.name)
    if not t:
        raise ValueError(f"genre {g.name!r} has no templates for field {f.name!r}")
    return t


def cards(pids: list[str], f: Field, g: Genre, seed: Any) -> dict[str, dict[str, Any]]:
    """{pid: card} for the papers in this order. Each axis cycles through a shuffled list of its values, so values
    spread evenly; a card whose (template, tone, opening) is already used moves on to the next tone."""
    rng = random.Random(f"{seed}:style:{f.name}:{g.name}")
    st = g.raw.get("style", {})
    tmpl = templates_for(g, f)
    pools = {a: list(st.get(a, [None])) for a in AXES}
    pools["template"] = list(range(len(tmpl)))
    order = {a: rng.sample(v, len(v)) for a, v in pools.items()}
    out, used = {}, set()
    for i, pid in enumerate(pids):
        pick = {a: order[a][i % len(order[a])] for a in order}
        for j in range(len(order["tone"])):
            key = (pick["template"], pick["tone"], pick["opening"])
            if key not in used:
                break
            pick["tone"] = order["tone"][(i + j + 1) % len(order["tone"])]
        used.add((pick["template"], pick["tone"], pick["opening"]))
        t = tmpl[pick["template"]]
        out[pid] = {"template": t["name"], "paper_kind": t["paper_kind"], **{a: pick[a] for a in AXES}}
    return out


def card_text(card: dict[str, Any], banned: list[str]) -> str:
    """The card as guideline lines for the writer."""
    lines = ["## Style of this paper (follow it; other papers of this collection use other styles)",
             f"- Paper type: {card['paper_kind']}."]
    if card.get("tone"):
        lines.append(f"- Tone: {card['tone']}.")
    if card.get("voice"):
        lines.append(f"- Voice: {card['voice']}.")
    if card.get("opening"):
        lines.append(f"- The Introduction opens with {card['opening']}. Do not repeat the abstract's first sentence.")
    if card.get("rhythm"):
        lines.append(f"- Sentences: {card['rhythm']}.")
    if banned:
        lines.append("- Never use these words or phrases (code checks them): " + ", ".join(f'"{b}"' for b in banned)
                     + ".")
    return "\n".join(lines)


def banned_re(banned: list[str]) -> re.Pattern[str] | None:
    if not banned:
        return None
    return re.compile(r"(?<![\w-])(" + "|".join(re.escape(b) for b in sorted(banned, key=len, reverse=True))
                      + r")(?![\w-])", re.I)
