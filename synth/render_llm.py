"""LLM renderer: a model writes the paper from the rendering plan; the placements are then located.

The model gets the plan (the facts, the level's instructions, the exact strings each rendering must use)
and returns Markdown. Values, claim sentences and the decoy are located with `anchor.find` (missing or
ambiguous is a fidelity failure); names are located at every word-bounded occurrence. A failed attempt's
reasons go into the next prompt, up to `attempts` times. Every call is cached in a JsonlCache keyed by
prompt hash, model identity and the full prompt (which holds the plan), so a rebuild costs no call.
The model is injected: tests pass a FunctionModel, real runs `modelcall.openai_model(alias)`, whose key
comes only from $LITELLM_MASTER_KEY and is never logged; every call is `modelcall.ask`, whose errors are redacted.
With `statements` (the default) each value the level writes in prose is first written and checked as one
sentence (synth/statements.py) and the paper (render-v2.txt) must hold the accepted sentences verbatim;
without it the calls are exactly those of render.txt.
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic_ai.models import Model

from agent import anchor
import modelcall
from synth import levelcheck, statements as statements_module
from synth.corpus import Rendered
from synth.fidelity import BlindExtraction, Check, PaperFidelity, blind_check, check_paper
from synth.levels import MISSING_CELL, Plan, make_plan, plan_rng
from synth.render_template import render_study as render_with_template
from synth.text import Decoy, Placement
from synth.truth import Study

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
INSTRUCTIONS = modelcall.load_prompt(PROMPT_DIR / "render.txt").text
INSTRUCTIONS_V2 = modelcall.load_prompt(PROMPT_DIR / "render-v2.txt").text
STATEMENT_INSTRUCTIONS = modelcall.load_prompt(PROMPT_DIR / "statements-v1.txt").text
BLIND_INSTRUCTIONS = modelcall.load_prompt(PROMPT_DIR / "blind-v2.txt").text

LEVEL_INSTRUCTIONS = {
    "explicit": "Report each value in its own Results sentence that contains the condition name, the metric name "
                "and the dataset exactly as given. No tables anywhere.",
    "paraphrased": "Call conditions and the metric only by the names given (they are descriptions; never use a "
                   "shorter or more technical name). Report each value in a prose sentence of the Results section "
                   "in exactly the form given. No tables anywhere.",
    "distributed": "In the Method section introduce each condition with its name and say that it is denoted by its "
                   "code, and introduce the metric with its name and its abbreviation. Then write at least two "
                   f"paragraphs of other method details, with at least {levelcheck.DISTANCE} characters between the "
                   "last code or metric-abbreviation definition and the table. Define each code and abbreviation "
                   "only once, early in Method; do not repeat the definitions near the table. "
                   "In Results, put every value ONLY in one Markdown table whose "
                   "first column header is 'System', whose rows are the codes, and whose value column header is "
                   "'<abbreviation> (%)'. Never state a value in a sentence; never write a full condition name in the "
                   "table.",
    "complex": "In Results, write one Markdown table with the columns 'System', 'Dataset' and one column per metric "
               "headed '<metric name> (<unit>)', one row per dataset and condition, using the full condition names. "
               "The cell marked 'see text' must contain exactly 'see text'; that value is given instead in one "
               "Results sentence, using its exact relative string and naming both conditions and the metric.",
    "contradictory": "In Results, write one Markdown table headed 'System' and '<metric name> (%)' with the full "
                     "condition names. Use the claim sentences exactly as given in the Abstract and the Conclusion, "
                     "even though they disagree with the table; do not comment on the disagreement. If a decoy "
                     "sentence is given, put it in the Abstract exactly as given.",
}


class PaperReply(BaseModel):
    markdown: str


def title_of(text: str) -> str:
    """The paper's title: its first line without the heading mark."""
    return text.split("\n", 1)[0].lstrip("#").strip()


def plan_json(plan: Plan, avoid_title: str | None = None) -> dict[str, Any]:
    """What the model is told: facts, names and the exact strings, never the effect or the answer. A
    duplicate paper (--duplicates) is told its original's title (`avoid_title`) so it takes another."""
    units = {"fraction": "%", "seconds": "s"}
    rag = plan.study.conditions[1].id
    decoy = None
    if plan.decoy is not None:
        decoy = (f"On {plan.datasets[0]}, the {plan.cond_name[rag]} reaches {plan.decoy.exact} "
                 f"{plan.metric_name[plan.metrics[0].id]}.")
    not_reported = None
    if plan.study.missing is not None:          # a --missing study: the key is present only then
        role = plan.study.control_role if plan.study.missing == "control" else plan.study.treatment_role
        gone = plan.study.condition(role).id
        not_reported = {
            "cells": [{"condition": plan.cond_name[gone], "metric": plan.metric_name[plan.metrics[0].id],
                       "dataset": d} for d in plan.datasets],
            "instruction": f"This value was not measured: never state it in any form; in a table write "
                           f"exactly '{MISSING_CELL}' in its cell."}
    return {
        "paper": plan.paper, "level_instructions": LEVEL_INSTRUCTIONS[plan.level],
        "datasets": [{"name": d, "main": i == 0, "size": "1,000 questions"} for i, d in enumerate(plan.datasets)],
        "conditions": [{"name": plan.cond_name[c.id], "does": c.description,
                        **({"code": plan.cond_aliases[c.id][0]} if plan.cond_aliases[c.id] else {})}
                       for c in plan.conditions],
        "metrics": [{"name": plan.metric_name[k.id], "unit": units[k.unit],
                     **({"abbreviation": k.abbr} if plan.level == "distributed" else {}),
                     **({"description": k.description} if plan.level != "paraphrased" else {})}
                    for k in plan.metrics],
        "results": [{"condition": plan.cond_name[m.condition], "metric": plan.metric_name[m.metric],
                     "dataset": m.dataset, "write_exactly": "see text" if plan.values[m.id].fmt == "relative"
                     else plan.values[m.id].text} for m in plan.measurements],
        "relative_value": next(({"string": v.text, "of": plan.cond_name[rag]} for v in plan.values.values()
                                if v.fmt == "relative"), None),
        "claim_sentences": {"abstract": plan.claim_sentences[0], "conclusion": plan.claim_sentences[1]},
        "decoy_sentence": decoy,
        **({"not_reported": not_reported} if not_reported else {}),
        **({"title": {"must_differ_from": avoid_title,
                      "instruction": "Another paper already carries this title; give this one a different title."}}
           if avoid_title is not None else {}),
    }


def section_at(text: str, offset: int) -> str:
    """The name of the '## ' section an offset falls in ('title' before the first one)."""
    head = text.rfind("\n## ", 0, offset + 1)
    if head < 0:
        return "title"
    end = text.find("\n", head + 4)
    return text[head + 4:end if end >= 0 else len(text)].strip()


def locate(text: str, plan: Plan) -> tuple[list[Placement], list[Decoy], list[str]]:
    """Placements in the model's text; problems for every required string missing or ambiguous. Codes and
    abbreviations count only where the plan puts them: table lines and their definitions."""
    index, ps, decoys, problems = anchor.Index(text), [], [], []

    def where(quote: str, reason: str) -> str:
        """For an ambiguous string, how often and in which sections it occurs, so the retry can fix it."""
        if reason != "ambiguous":
            return ""
        spans = index.spans(anchor.normalize(quote))
        sections = [section_at(text, start) for start, _ in spans]
        return (f": it occurs {len(spans)} times (in {', '.join(sections)}); write it exactly once, where the "
                f"level instructions put it, and nowhere else")

    def find_once(fact: str, role: str, quote: str, fmt: str | None = None) -> None:
        try:
            sel = anchor.find(index, quote)
        except anchor.AnchorError as exc:
            problems.append(f"{fact}/{role}: required string {quote!r} is {exc.reason}{where(quote, exc.reason)}")
            return
        ps.append(Placement(fact, role, plan.paper, sel.start, sel.end, sel.exact, fmt))

    for m in plan.measurements:
        seg = plan.values[m.id]
        find_once(m.id, "value", seg.text, seg.fmt)
    for sentence in dict.fromkeys(plan.claim_sentences):
        find_once(f"{plan.paper}.a1", "claim", sentence)
    if plan.decoy is not None:
        try:
            sel = anchor.find(index, plan.decoy.exact)
            decoys.append(Decoy(plan.decoy.measurement, plan.decoy.stated_value, sel.exact, sel.start, sel.end))
        except anchor.AnchorError as exc:
            problems.append(f"decoy {plan.decoy.exact!r} is {exc.reason}")
    found = levelcheck.renderings(text, plan)
    have = {fact for fact, _, _, _, main in found if main}
    problems += [f"{c}/condition_label: name {plan.cond_name[c]!r} not found" for c in plan.cond_name if c not in have]
    problems += [f"{k}/metric_label: name {plan.metric_name[k]!r} not found" for k in plan.metric_name if k not in have]
    ps += [Placement(fact, role, plan.paper, a, b, text[a:b]) for fact, role, a, b, _ in found]
    return sorted(ps, key=lambda p: (p.start, p.end, p.fact)), decoys, problems


class LlmRenderer:
    name = "llm"

    def __init__(self, model: Model, cache: Path | str, *, attempts: int = 3, verify_model: Model | None = None,
                 concurrency: int = 4, max_tokens: int = 6000, statements: bool = True) -> None:
        self.model, self.verify_model, self.statements = model, verify_model, statements
        self.cache = modelcall.JsonlCache(cache)
        self.attempts, self.concurrency, self.max_tokens = attempts, concurrency, max_tokens
        self.served: set[str] = set()

    def models(self) -> dict[str, Any]:
        """Model identities, and the pipeline: `statements` on or off and the paper prompt file it uses (a
        corpus.json without these keys predates the statement stage: off, render.txt)."""
        return {"renderer": modelcall.model_identity([self.model]),
                "verifier": modelcall.model_identity([self.verify_model]) if self.verify_model else None,
                "served": sorted(self.served), "statements": self.statements,
                "paper_prompt": "render-v2.txt" if self.statements else "render.txt"}

    async def _call(self, instructions: str, prompt: str, output: type[BaseModel], model: Model, seed: int) -> dict:
        key = {"prompt_sha256": modelcall.prompt_sha256(instructions, output),
               "model": modelcall.model_identity([model]), "prompt": prompt, "seed": seed}
        answer = await modelcall.ask(modelcall.Prompt.inline(instructions, output), prompt, model=model,
                                     settings=modelcall.CallSettings(seed=seed, max_tokens=self.max_tokens),
                                     cache=self.cache, key=key)
        self.served.add(answer.served_model or answer.model)
        return answer.output.model_dump()

    async def _blind(self, text: str, seed: int) -> BlindExtraction:
        out = await self._call(BLIND_INSTRUCTIONS, "Paper:\n\n" + text, BlindExtraction, self.verify_model, seed)
        return BlindExtraction.model_validate(out)

    async def render_one(self, study: Study, level: str, seed: int, avoid_title: str | None = None) -> Rendered:
        """`avoid_title`: for a duplicate, the title its original got at this level (`title_differs` check)."""
        if not study.relevant:          # nothing to place: the fixed template writes it, no model call
            return render_with_template(study, level, seed)
        plan = make_plan(study, level, plan_rng(seed, study.study_id, level))
        instructions, accepted, record = INSTRUCTIONS, {}, None
        planned = plan_json(plan, avoid_title)
        if self.statements:
            async def call(prompt: str, s: int) -> dict:
                reply = statements_module.StatementReply
                return await self._call(STATEMENT_INSTRUCTIONS, prompt, reply, self.model, s)
            accepted, record = await statements_module.write(plan, call, self.attempts, seed)
            print(f"synth {plan.paper}/{level}: statements {record['rounds']} round(s), failed {record['failed']}",
                  file=sys.stderr, flush=True)
            instructions = INSTRUCTIONS_V2
            if accepted:
                planned["statements"] = list(accepted.values())
        base = json.dumps(planned, indent=2, ensure_ascii=False)
        history: list[dict] = []
        feedback: list[str] = []
        text, ps, decoys, checks = "", [], [], []
        for attempt in range(1, self.attempts + 1):
            prompt = "Rendering plan:\n" + base
            if feedback:
                prompt += "\n\nYour previous paper was rejected for these reasons; fix them:\n- " + "\n- ".join(feedback)
                prompt += (f"\n\nRevision attempt {attempt} of {self.attempts}. Correct the rejected draft below, "
                           "preserving facts and passages that already satisfy the plan. Return the whole corrected paper."
                           "\n\nRejected draft:\n" + text)
            try:
                # A failed reply can produce identical feedback and therefore an identical prompt. Give
                # each retry a distinct seed so the content-addressed cache cannot replay that same reply.
                text = (await self._call(instructions, prompt, PaperReply, self.model, seed + attempt - 1))["markdown"]
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                text = text if text.endswith("\n") else text + "\n"
                ps, decoys, problems = locate(text, plan)
                problems += statements_module.missing(text, accepted)
                checks = [Check("required_strings", not problems, "; ".join(problems))]
                if avoid_title is not None:
                    same = title_of(text) == avoid_title
                    checks.append(Check("title_differs", not same, f"the title {avoid_title!r} is the original's" if same else ""))
                checks += check_paper(text, plan, ps, decoys) if not problems else []
                if self.verify_model is not None and all(c.ok for c in checks):
                    checks += await blind_check(text, plan, lambda t: self._blind(t, seed))
            except modelcall.ModelCallError as exc:  # a dead server or a malformed reply is one failed attempt
                checks = [Check("model_call", False, exc.reason)]
            except Exception as exc:  # a cached reply that no longer decodes, too
                checks = [Check("model_call", False, modelcall.redact(f"{type(exc).__name__}: {exc}"))]
            failed = [c for c in checks if not c.ok]
            status = "passed" if not failed else "failed " + ", ".join(c.name for c in failed)
            print(f"synth {plan.paper}/{level}: attempt {attempt}/{self.attempts} {status}",
                  file=sys.stderr, flush=True)
            if not failed:
                return Rendered(study, plan, text, ps, decoys,
                                PaperFidelity(study.study_id, True, checks, attempt, history, statements=record))
            history.append({"attempt": attempt, "failed": [{"name": c.name, "detail": c.detail} for c in failed]})
            feedback = [f"{c.name}: {c.detail}" for c in failed]
        return Rendered(study, plan, text, ps, decoys, PaperFidelity(study.study_id, False, checks, self.attempts,
                                                                     history, statements=record))

    def render_all(self, jobs: Sequence[tuple[Study, str]], seed: int) -> dict[tuple[str, str], Rendered]:
        """Originals first, then the duplicates, each told the title its original got at that level."""
        async def run() -> list[Rendered]:
            gate = asyncio.Semaphore(self.concurrency)

            async def one(study: Study, level: str, avoid_title: str | None = None) -> Rendered:
                async with gate:
                    return await self.render_one(study, level, seed, avoid_title)
            originals = await asyncio.gather(*(one(s, lv) for s, lv in jobs if not s.duplicate_of))
            titles = {(r.study.study_id, r.plan.level): title_of(r.text) for r in originals}
            duplicates = await asyncio.gather(*(one(s, lv, titles.get((s.duplicate_of, lv)))
                                                for s, lv in jobs if s.duplicate_of))
            return [*originals, *duplicates]
        return {(r.study.study_id, r.plan.level): r for r in modelcall.run_sync(run())}
