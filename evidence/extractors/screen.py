"""Screening extractors of the funnel (docs/evidence-system.md Part D; our design, not the supervisor's): is
the paper one the protocol can use at all?

Both run on the pseudo evidence type `screen` (protocol.SCREEN_FIELDS) and return at most one item,
`{relevant, reason}` with one span of role `evidence`, so the decision is checked, cached and replayed exactly
like an extractor call:

- `regex_screen` (kind regex, exact): the document holds a word-bounded term of the protocol's `screen.terms`
  -> relevant, the span on the first hit (the earliest position; ties go to the earlier term in the list);
  no term -> not relevant, the reason names the terms, the span on the document's first non-empty line (its
  title), because every item carries a checked span (R1) and there is no term to point at. A term written in
  capitals only (an acronym such as RAG) is matched in capitals; any other term in any case; a space in a
  term matches any run of white space. An empty document gives no item.
- `llm_screen` (kind llm, near_exact): one schema-constrained call over the HEAD of the task's scope (the
  first `head_chars` characters, default 12000, the LLM extractors' chunk size) with the protocol's
  `screen.question` (prompts/screen-v1.md, temperature 0, seed 0), output `{relevant, reason, quote}`. The
  head is enough because the screening question asks what kind of paper this is, which the title, abstract
  and introduction state; the result's coverage names the range actually sent, so a decision on a cut
  document is visible. The quote is anchored like the LLM extractors' quotes (agent/anchor.find over the whole document). A quote
  that cannot be anchored is rejected with the anchor's reason, and the item falls back to the regex decision
  the engine gives as context (the earlier screen item): its `relevant`, the reason "unanchored: <the model's
  reason>", and the regex item's span. Without a context item there is no fallback item. A failed model call
  is an error result without an item.

The cascade semantics live in the engine (engine.Execution.screen): an extractor that says "not relevant"
stops the cascade; "relevant" passes the decision on to the next extractor when there is one; a call without
an item leaves the earlier decision standing, and a cascade without any decision counts as relevant, so a
paper is never skipped because a check failed.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from agent.anchor import AnchorError, find
import modelcall

from ..contract import (Coverage, ExtractionError, ExtractionResult, ExtractionTask, ExtractorSpec, Item, Rejected,
                        RunContext, Span)
from ..protocol import SCREEN_FIELDS, SCREEN_ROLES, SCREEN_TYPE
from ..recording import ModelCallError
from . import base, llm_schema

VERSION = 1
ROLE = SCREEN_ROLES[0]
# Keys the engine injects into every extractor's config (engine.build_extractors); not patterns of the screen.
INJECTED = ("evidence_type", "field_schema", "links", "roles", "description", "question_metrics", "compare")
REGEX_SOURCES = (base.HERE / "screen.py", *base.SHARED_SOURCES)
LLM_SOURCES = (base.HERE / "screen.py", base.HERE / "llm_schema.py", llm_schema.PROMPT_DIR / "screen-v1.md",
               base.ROOT / "modelcall" / "gateway.py", base.ROOT / "modelcall" / "call.py",
               base.ROOT / "modelcall" / "prompt.py",
               base.ROOT / "evidence" / "recording.py", *base.SHARED_SOURCES)
LLM_DEFAULTS: dict[str, Any] = {"model": "orch-model", "prompt": "screen-v1.md", "temperature": 0.0, "seed": 0,
                                "max_tokens": 1024, "head_chars": 12000}


def term_pattern(term: str) -> str:
    """Word-bounded; capitals-only terms (acronyms) in capitals, the others in any case; a space is any white space."""
    body = re.escape(" ".join(term.split())).replace(r"\ ", r"\s+")
    flags = "" if term.strip().isupper() and len(term.strip()) > 1 else "(?i)"
    return rf"{flags}(?<!\w){body}(?!\w)"


def first_hit(text: str, terms: list[str], parts: list[tuple[int, int]]) -> tuple[int, int] | None:
    """(start, end) of the earliest occurrence of any term inside the parts; ties by the terms' order."""
    best: tuple[int, int, int] | None = None   # start, term index, end
    for n, term in enumerate(terms):
        pattern = re.compile(term_pattern(term))
        for a, b in parts:
            hit = pattern.search(text, a, b)
            if hit and hit.end() <= b and (best is None or (hit.start(), n) < best[:2]):
                best = (hit.start(), n, hit.end())
    return (best[0], best[2]) if best else None


def title_line(text: str, parts: list[tuple[int, int]]) -> tuple[int, int] | None:
    """The first non-empty line inside the parts, without its heading marks: the span of a negative decision."""
    for a, b in parts:
        for m in re.finditer(r"[^\n]+", text[a:b]):
            raw = m.group()
            stripped = raw.lstrip("# ").rstrip()
            if stripped:
                start = a + m.start() + (len(raw) - len(raw.lstrip("# ")))
                return start, start + len(stripped)
    return None


def decision_item(task: ExtractionTask, text: str, relevant: bool, reason: str, where: tuple[int, int]) -> Item:
    return Item.build(SCREEN_TYPE, {"relevant": relevant, "reason": reason},
                      [base.span(task, text, where[0], where[1], ROLE)])


class RegexScreen:
    """`regex_screen`: a term of the protocol's `screen.terms` in the document, or not."""
    name = "regex_screen"

    def __init__(self, config: dict[str, Any]) -> None:
        self.terms = [str(t) for t in config.get("terms") or []]
        config_out = {"terms": list(self.terms), "evidence_type": SCREEN_TYPE}
        self.spec = ExtractorSpec(name=self.name, version=VERSION, kind="regex", evidence_types=(SCREEN_TYPE,),
                                  code_sha256=base.source_sha256(*REGEX_SOURCES), config=config_out, determinism="exact")

    def extract(self, task: ExtractionTask, ctx: RunContext) -> ExtractionResult:
        text = ctx.text()
        parts = base.ranges(task, text)
        hit = first_hit(text, self.terms, parts) if self.terms else None
        items: list[Item] = []
        if hit is not None:
            items.append(decision_item(task, text, True, f"the paper mentions {text[hit[0]:hit[1]]!r}", hit))
        elif (title := title_line(text, parts)) is not None:
            named = ", ".join(self.terms) or "(no terms)"
            items.append(decision_item(task, text, False, f"none of the terms {named} occurs in the paper", title))
        return ExtractionResult(extractor_id=self.spec.extractor_id, task_sha256=task.task_sha256, status="ok",
                                items=tuple(items), coverage=base.coverage(parts, items)).canonical()


class ScreenReply(BaseModel):
    relevant: bool = Field(description="true when the paper is one the protocol can use, per the screening question")
    reason: str = Field(description="one sentence: why")
    quote: str = Field(description="a verbatim passage of the paper the decision rests on")


class LLMScreen:
    """`llm_screen`: one call answering the protocol's screening question, with the quote anchored."""
    name = "llm_screen"

    def __init__(self, config: dict[str, Any]) -> None:
        cfg = LLM_DEFAULTS | {k: v for k, v in config.items() if k not in INJECTED}
        self.cfg = cfg
        self.question = " ".join(str(cfg.get("question") or config.get("description") or "").split())
        template = cfg.get("instructions") or llm_schema.read_prompt(cfg["prompt"])
        self.instructions = template.format(question=self.question)
        if int(cfg["head_chars"]) < 1:
            raise ValueError("llm_screen: head_chars must be positive")
        config_out = {k: cfg[k] for k in ("model", "prompt", "temperature", "seed", "max_tokens", "head_chars")}
        config_out |= {"evidence_type": SCREEN_TYPE, "question": self.question,
                       "prompt_sha256": modelcall.prompt_sha256(self.instructions, ScreenReply),
                       "model_settings": dict(modelcall.settings(temperature=cfg["temperature"], seed=cfg["seed"],
                                                                max_tokens=cfg["max_tokens"]))}
        self.spec = ExtractorSpec(name=self.name, version=VERSION, kind="llm", evidence_types=(SCREEN_TYPE,),
                                  code_sha256=base.source_sha256(*LLM_SOURCES), config=config_out,
                                  determinism="near_exact")

    def extract(self, task: ExtractionTask, ctx: RunContext) -> ExtractionResult:
        text, index = ctx.text(), ctx.index()
        parts = base.ranges(task, text)
        a, b = (parts[0][0], min(parts[-1][1], parts[0][0] + int(self.cfg["head_chars"]))) if parts else (0, 0)
        prompt = llm_schema.user_prompt(task.document.id, 1, 1, a, b, text[a:b], {})   # the head only; coverage says so
        base_result = {"extractor_id": self.spec.extractor_id, "task_sha256": task.task_sha256}
        try:
            reply, call = ctx.llm().structured(self.cfg["model"], self.instructions, prompt, ScreenReply,
                                               temperature=self.cfg["temperature"], seed=self.cfg["seed"],
                                               max_tokens=self.cfg["max_tokens"])
        except ModelCallError as exc:
            return ExtractionResult(**base_result, status="error", error=ExtractionError(reason="model_call", detail=exc.reason),
                                    coverage=(Coverage(range=(a, b), status="error", reason=exc.reason),),
                                    model_calls=tuple([exc.call_id] if exc.call_id else [])).canonical()
        fields = {"relevant": bool(reply.relevant), "reason": " ".join(reply.reason.split()) or "no reason given"}
        items: list[Item] = []
        rejected: list[Rejected] = []
        try:
            sel = find(index, reply.quote, file=task.document.file)
            items.append(Item.build(SCREEN_TYPE, fields, [Span.of(ROLE, sel)]))
        except AnchorError as exc:
            rejected.append(Rejected(evidence_type=SCREEN_TYPE, fields=fields, quotes=(reply.quote,),
                                     reason=exc.reason, detail=str(exc)[:300]))  # type: ignore[arg-type]
            earlier = next((i for i in ctx.context_items() if i.evidence_type == SCREEN_TYPE), None)
            if earlier is not None:   # the regex decision stands, with the model's reason on record
                items.append(Item.build(SCREEN_TYPE, {"relevant": bool(earlier.fields["relevant"]),
                                                      "reason": f"unanchored: {fields['reason']}"}, [earlier.spans[0]]))
        return ExtractionResult(**base_result, status="ok", items=tuple(items), rejected=tuple(rejected),
                                coverage=base.coverage([(a, b)], items) if parts else (),
                                model_calls=(call,)).canonical()


FACTORIES = {RegexScreen.name: RegexScreen, LLMScreen.name: LLMScreen}
