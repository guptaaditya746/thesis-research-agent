"""Hybrid rendering: code owns factual passages; a model writes bounded context.

This is a separate corpus-generation mode, not a repair of frozen LLM corpora.
The model never receives results or claims. Final anchoring and fidelity checks
still run on the assembled paper, with offsets recomputed from its final bytes.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from synth.fidelity import added_claims
from synth.levels import Plan, plan_rng
from synth.render_template import render


class ProseReply(BaseModel):
    text: str = Field(min_length=40, max_length=2200)


def problems(text: str, plan: Plan) -> list[str]:
    bad = []
    if re.search(r"\d|[|#]", text):
        bad.append("Use prose without digits, tables, or headings.")
    if added_claims(text, plan, []):
        bad.append("Describe the comparison or its limitations without stating an effect.")
    return bad


def assemble(plan: Plan, seed: int, prose: dict[str, str], avoid_title: str | None = None) -> str:
    """Keep factual blocks and level difficulty fixed, replacing only context sections."""
    text, _, _ = render(plan, plan_rng(seed, plan.paper, plan.level + ":text"), avoid_title)
    for section, next_section in (("Introduction", "Method"), ("Discussion", "Conclusion")):
        if section not in prose:
            continue
        start = text.index(f"## {section}\n") + len(f"## {section}\n")
        end = text.index(f"\n## {next_section}\n", start)
        text = text[:start] + "\n" + prose[section].strip() + "\n" + text[end:]
    return text
