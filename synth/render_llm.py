"""LLM renderer: a model writes the paper from the rendering plan; the placements are then located.

The model gets the plan (the facts, the level's instructions, the exact strings each rendering must use)
and returns Markdown. Values, claim sentences and the decoy are located with `anchor.find` (missing or
ambiguous is a fidelity failure); names are located at every word-bounded occurrence. A failed attempt's
reasons go into the next prompt, up to `attempts` times. Every call is cached in a JsonlCache keyed by
prompt hash, model identity and the full prompt (which holds the plan), so a rebuild costs no call.
The model is injected: tests pass a FunctionModel, real runs `gold.llm.openai_model(alias)`, whose key
comes only from $LITELLM_MASTER_KEY and is never logged; error text goes through `gold.llm.redact`.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic_ai.models import Model

from agent import anchor
from gold import llm
from synth import levelcheck
from synth.corpus import Rendered
from synth.fidelity import BlindExtraction, Check, PaperFidelity, blind_check, check_paper
from synth.levels import Plan, make_plan, plan_rng
from synth.text import Decoy, Placement
from synth.truth import Study

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
INSTRUCTIONS = (PROMPT_DIR / "render.txt").read_text(encoding="utf-8").replace("\r\n", "\n")
BLIND_INSTRUCTIONS = (PROMPT_DIR / "blind.txt").read_text(encoding="utf-8").replace("\r\n", "\n")

LEVEL_INSTRUCTIONS = {
    "explicit": "Report each value in its own Results sentence that contains the condition name, the metric name "
                "and the dataset exactly as given. No tables anywhere.",
    "paraphrased": "Call conditions and the metric only by the names given (they are descriptions; never use a "
                   "shorter or more technical name). Report each value in a prose sentence of the Results section "
                   "in exactly the form given. No tables anywhere.",
    "distributed": "In the Method section introduce each condition with its name and say that it is denoted by its "
                   "code, and introduce the metric with its name and its abbreviation. Then write at least two "
                   "paragraphs of other method details. In Results, put every value ONLY in one Markdown table whose "
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


def plan_json(plan: Plan) -> dict[str, Any]:
    """What the model is told: facts, names and the exact strings, never the effect or the answer."""
    units = {"fraction": "%", "seconds": "s"}
    rag = plan.study.condition("rag").id
    decoy = None
    if plan.decoy is not None:
        decoy = (f"On {plan.datasets[0]}, the {plan.cond_name[rag]} reaches {plan.decoy.exact} "
                 f"{plan.metric_name[plan.metrics[0].id]}.")
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
    }


def locate(text: str, plan: Plan) -> tuple[list[Placement], list[Decoy], list[str]]:
    """Placements in the model's text; problems for every required string missing or ambiguous."""
    index, ps, decoys, problems = anchor.Index(text), [], [], []

    def find_once(fact: str, role: str, quote: str, fmt: str | None = None) -> None:
        try:
            sel = anchor.find(index, quote)
        except anchor.AnchorError as exc:
            problems.append(f"{fact}/{role}: required string {quote!r} is {exc.reason}")
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
    names = [(c, "condition_label", n, n == plan.cond_name[c]) for c in plan.cond_name
             for n in (plan.cond_name[c], *plan.cond_aliases[c])]
    names += [(k, "metric_label", n, n == plan.metric_name[k]) for k in plan.metric_name
              for n in (plan.metric_name[k], *plan.metric_aliases[k])]
    for fact, role, name, required in names:
        spans = levelcheck.occurs(text, name)
        if required and not spans:
            problems.append(f"{fact}/{role}: name {name!r} not found")
        ps += [Placement(fact, role, plan.paper, a, b, text[a:b]) for a, b in spans]
    return sorted(ps, key=lambda p: (p.start, p.end, p.fact)), decoys, problems


class LlmRenderer:
    name = "llm"

    def __init__(self, model: Model, cache: Path | str, *, attempts: int = 3, verify_model: Model | None = None,
                 concurrency: int = 4, max_tokens: int = 6000) -> None:
        self.model, self.verify_model = model, verify_model
        self.cache = llm.JsonlCache(cache)
        self.attempts, self.concurrency, self.max_tokens = attempts, concurrency, max_tokens
        self.served: set[str] = set()

    def models(self) -> dict[str, Any]:
        return {"renderer": llm.model_identity([self.model]),
                "verifier": llm.model_identity([self.verify_model]) if self.verify_model else None,
                "served": sorted(self.served)}

    async def _call(self, instructions: str, prompt: str, output: type[BaseModel], model: Model, seed: int) -> dict:
        key = llm.cache_key({"prompt_sha256": llm.prompt_sha256(instructions, output),
                             "model": llm.model_identity([model]), "prompt": prompt, "seed": seed})
        hit = self.cache.get(key)
        if hit is None:
            reply = await llm.structured_reply(instructions, prompt, output, model=model,
                                               model_settings=llm.settings(seed=seed, max_tokens=self.max_tokens))
            hit = {"output": reply.output.model_dump(), "model": reply.model, "served_model": reply.served_model,
                   "input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens}
            self.cache.put(key, hit)
        self.served.add(hit["served_model"] or hit["model"])
        return hit["output"]

    async def _blind(self, text: str, seed: int) -> BlindExtraction:
        out = await self._call(BLIND_INSTRUCTIONS, "Paper:\n\n" + text, BlindExtraction, self.verify_model, seed)
        return BlindExtraction.model_validate(out)

    async def render_one(self, study: Study, level: str, seed: int) -> Rendered:
        plan = make_plan(study, level, plan_rng(seed, study.study_id, level))
        base = json.dumps(plan_json(plan), indent=2, ensure_ascii=False)
        history: list[dict] = []
        feedback: list[str] = []
        text, ps, decoys, checks = "", [], [], []
        for attempt in range(1, self.attempts + 1):
            prompt = "Rendering plan:\n" + base
            if feedback:
                prompt += "\n\nYour previous paper was rejected for these reasons; fix them:\n- " + "\n- ".join(feedback)
            try:
                text = (await self._call(INSTRUCTIONS, prompt, PaperReply, self.model, seed))["markdown"]
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                text = text if text.endswith("\n") else text + "\n"
                ps, decoys, problems = locate(text, plan)
                checks = [Check("required_strings", not problems, "; ".join(problems))]
                checks += check_paper(text, plan, ps, decoys) if not problems else []
                if self.verify_model is not None and all(c.ok for c in checks):
                    checks.append(await blind_check(text, plan, lambda t: self._blind(t, seed)))
            except Exception as exc:  # a dead server or a malformed reply is one failed attempt
                checks = [Check("model_call", False, llm.redact(f"{type(exc).__name__}: {exc}"))]
            failed = [c for c in checks if not c.ok]
            if not failed:
                return Rendered(study, plan, text, ps, decoys,
                                PaperFidelity(study.study_id, True, checks, attempt, history))
            history.append({"attempt": attempt, "failed": [{"name": c.name, "detail": c.detail} for c in failed]})
            feedback = [f"{c.name}: {c.detail}" for c in failed]
        return Rendered(study, plan, text, ps, decoys,
                        PaperFidelity(study.study_id, False, checks, self.attempts, history))

    def render_all(self, jobs: Sequence[tuple[Study, str]], seed: int) -> dict[tuple[str, str], Rendered]:
        async def run() -> list[Rendered]:
            gate = asyncio.Semaphore(self.concurrency)

            async def one(study: Study, level: str) -> Rendered:
                async with gate:
                    return await self.render_one(study, level, seed)
            return await asyncio.gather(*(one(s, lv) for s, lv in jobs))
        return {(r.study.study_id, r.plan.level): r for r in asyncio.run(run())}
