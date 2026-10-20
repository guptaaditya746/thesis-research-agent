"""Single-call LLM extractors, one per evidence type (kind llm, determinism near_exact).

Per chunk of the task's scope (gold/chunks.py, section-aware) one schema-constrained call
(modelcall.structured_reply through the run's recorder, temperature 0, fixed seed) lists the items with
their fields, links to context items and a verbatim quote per span role. Every quote is anchored with
agent/anchor.find against the whole document; quotes rejected for a reason a new quote can fix get one
retry call per chunk with the reason (as gold/extract.py does). A `value` span is narrowed to the number
inside its quote. What still fails is returned as rejected, never dropped.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agent.anchor import AnchorError, Selector, find, selector_at
import modelcall
from gold.chunks import split

from ..contract import (Coverage, ExtractionError, ExtractionResult, ExtractionTask, ExtractorSpec, Item, Rejected,
                        RunContext, Span)
from ..recording import ModelCallError
from . import base, llm_schema

VERSION = 1
QUOTE_REASONS = ("not_found", "ambiguous", "partial_number", "empty_quote")
# `model`: orch-model, the one model of every extractor and both baselines (docs/evidence-system.md Part G.3).
DEFAULTS: dict[str, Any] = {"model": "orch-model", "prompt": "extract-v1.md", "retry_prompt": "retry-v1.md",
                            "temperature": 0.0, "seed": 0, "max_tokens": 4096, "retry_max_tokens": 2048,
                            "chunk_chars": 12000, "quote_retry": 1}
SOURCES = (base.HERE / "llm.py", base.HERE / "llm_schema.py", llm_schema.PROMPT_DIR / "extract-v1.md",
           llm_schema.PROMPT_DIR / "retry-v1.md", base.ROOT / "modelcall" / "gateway.py",
           base.ROOT / "modelcall" / "prompt.py", base.ROOT / "evidence" / "recording.py", *base.SHARED_SOURCES)
CODE_SHA256 = base.source_sha256(*SOURCES)


@dataclass
class Proposal:
    fields: dict[str, Any]
    links: dict[str, str]
    quotes: dict[str, str]                                   # role -> quote
    anchored: dict[str, Selector] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)     # role -> reason


class LLMExtractor:
    def __init__(self, evidence_type: str, config: dict[str, Any]) -> None:
        cfg = DEFAULTS | config
        if cfg.get("evidence_type", evidence_type) != evidence_type:
            raise ValueError(f"llm_{evidence_type} built for evidence type {cfg['evidence_type']}")
        self.evidence_type = evidence_type
        self.cfg = cfg
        self.roles = list(cfg.get("roles") or ["quote"])
        self.links = dict(cfg.get("links") or {})
        schema = cfg.get("field_schema") or {"type": "object", "properties": {}}
        self.output_type = llm_schema.output_model(evidence_type, schema, self.links, self.roles)
        template = cfg.get("instructions") or llm_schema.read_prompt(cfg["prompt"])
        self.instructions = llm_schema.instructions(template, evidence_type, cfg.get("description", ""), schema,
                                                    self.links, self.roles)
        self.retry_instructions = llm_schema.read_prompt(cfg["retry_prompt"])
        config_out = {k: cfg[k] for k in ("model", "prompt", "retry_prompt", "temperature", "seed", "max_tokens",
                                          "retry_max_tokens", "chunk_chars", "quote_retry")}
        config_out |= {"evidence_type": evidence_type,
                       "prompt_sha256": modelcall.prompt_sha256(self.instructions, self.output_type),
                       "retry_prompt_sha256": modelcall.prompt_sha256(self.retry_instructions, llm_schema.Retry),
                       # what every call sends (thinking off via extra_body): a change is a new extractor id
                       "model_settings": dict(modelcall.settings(temperature=cfg["temperature"], seed=cfg["seed"],
                                                                max_tokens=cfg["max_tokens"])),
                       "retry_model_settings": dict(modelcall.settings(temperature=cfg["temperature"], seed=cfg["seed"],
                                                                      max_tokens=cfg["retry_max_tokens"]))}
        self.spec = ExtractorSpec(name=f"llm_{evidence_type}", version=VERSION, kind="llm",
                                  evidence_types=(evidence_type,),  # type: ignore[arg-type]
                                  code_sha256=CODE_SHA256, config=config_out, determinism="near_exact")

    def _ask(self, ctx: Any, instructions: str, prompt: str, output_type: Any, max_tokens: int) -> tuple[Any, str]:
        return ctx.llm().structured(self.cfg["model"], instructions, prompt, output_type,
                                    temperature=self.cfg["temperature"], seed=self.cfg["seed"], max_tokens=max_tokens)

    def extract(self, task: ExtractionTask, ctx: RunContext) -> ExtractionResult:
        text, index = ctx.text(), ctx.index()
        context = llm_schema.local_ids(ctx.context_items())
        chunks = [(a + ca, a + cb) for a, b in base.ranges(task, text)
                  for ca, cb, _ in split(text[a:b], self.cfg["chunk_chars"])]
        found: list[tuple[dict[str, Any], dict[str, str], list[Span]]] = []
        rejected: list[Rejected] = []
        coverage = []
        model_calls: list[str] = []
        errors: list[str] = []
        retry_errors: list[str] = []
        for n, (a, b) in enumerate(chunks, 1):
            prompt = llm_schema.user_prompt(task.document.id, n, len(chunks), a, b, text[a:b], context, task.focus)
            try:
                reply, call = self._ask(ctx, self.instructions, prompt, self.output_type, self.cfg["max_tokens"])
                model_calls.append(call)
            except ModelCallError as exc:
                model_calls += [exc.call_id] if exc.call_id else []
                errors.append(exc.reason)
                coverage.append(Coverage(range=(a, b), status="error", reason=exc.reason))
                continue
            proposals = [self._proposal(row.model_dump(mode="json")) for row in reply.items]
            for p in proposals:
                self._anchor(index, task, p)
            failed = [(p, role) for p in proposals for role, reason in p.failed.items() if reason in QUOTE_REASONS]
            if failed and self.cfg["quote_retry"]:
                calls, retry_error = self._retry(ctx, index, task, prompt, failed)
                model_calls.extend(calls)
                if retry_error:
                    retry_errors.append(f"retry: {retry_error}")
            kept = 0
            for p in proposals:
                item, rejects = self._finish(task, text, p, context)
                rejected.extend(rejects)
                if item is not None:
                    found.append(item)
                    kept += 1
            coverage.append(Coverage(range=(a, b), status="found" if kept else "none", found=kept))
        items = base.group(self.evidence_type, found)
        status = "ok" if not errors else ("error" if len(errors) == len(chunks) else "partial")
        if retry_errors and status == "ok":
            status = "partial"   # the retry failed: its quotes stay rejected, but the call is not clean
        problems = errors + retry_errors
        error = ExtractionError(reason="model_call", detail="; ".join(sorted(set(problems)))[:300]) if problems else None
        return ExtractionResult(extractor_id=self.spec.extractor_id, task_sha256=task.task_sha256, status=status,
                                error=error, items=tuple(items), rejected=tuple(rejected), coverage=tuple(coverage),
                                model_calls=tuple(model_calls)).canonical()

    @staticmethod
    def _proposal(row: dict[str, Any]) -> Proposal:
        quotes = {role: q for role, q in (row.get("quotes") or {}).items() if q is not None}
        return Proposal(fields=row["fields"], links=row.get("links") or {}, quotes=quotes)

    def _anchor(self, index: Any, task: ExtractionTask, p: Proposal, roles: list[str] | None = None) -> None:
        for role in roles or list(p.quotes):
            try:
                p.anchored[role] = find(index, p.quotes[role], file=task.document.file)
                p.failed.pop(role, None)
            except AnchorError as exc:
                p.failed[role] = exc.reason

    def _retry(self, ctx: Any, index: Any, task: ExtractionTask, prompt: str,
               failed: list[tuple[Proposal, str]]) -> tuple[list[str], str | None]:
        """One call for every rejected quote of the chunk, then the check again: (model call ids, error)."""
        listing = [{"id": f"q{n}", "role": role, "fields": p.fields, "quote": p.quotes[role], "reason": p.failed[role]}
                   for n, (p, role) in enumerate(failed, 1)]
        extra = prompt + "\n\nRejected quotes:\n" + json.dumps(listing, ensure_ascii=False, indent=1)
        try:
            reply, call = self._ask(ctx, self.retry_instructions, extra, llm_schema.Retry, self.cfg["retry_max_tokens"])
        except ModelCallError as exc:
            return ([exc.call_id] if exc.call_id else []), exc.reason
        new = {q.id: q.quote for q in reply.quotes}
        for n, (p, role) in enumerate(failed, 1):
            if f"q{n}" in new:
                p.quotes[role] = new[f"q{n}"]
                self._anchor(index, task, p, [role])
        return [call], None

    def _finish(self, task: ExtractionTask, text: str, p: Proposal,
                context: dict[str, Item]) -> tuple[tuple[dict[str, Any], dict[str, str], list[Span]] | None, list[Rejected]]:
        """The item (fields, links, spans), or a rejection; a failing optional quote is dropped and reported."""
        quotes = tuple(p.quotes.values())
        required = self.roles[0]
        if required not in p.anchored:
            reason = p.failed.get(required, "empty_quote")
            return None, [Rejected(evidence_type=self.evidence_type, fields=p.fields, quotes=quotes,  # type: ignore[arg-type]
                                   reason=reason, detail=f"{required} quote")]  # type: ignore[arg-type]
        links: dict[str, str] = {}
        for name in self.links:
            local = p.links.get(name)
            if local not in context or context[local].evidence_type != self.links[name]:
                return None, [Rejected(evidence_type=self.evidence_type, fields=p.fields, quotes=quotes,  # type: ignore[arg-type]
                                       reason="dangling_link", detail=f"{name}={local!r}")]
            links[name] = context[local].item_id
        fields = dict(p.fields)
        rejects = [Rejected(evidence_type=self.evidence_type, fields=p.fields, quotes=(p.quotes[role],),  # type: ignore[arg-type]
                            reason=reason, detail=f"optional {role} quote dropped; item kept")  # type: ignore[arg-type]
                   for role, reason in p.failed.items() if role != required]
        spans = []
        for role, sel in p.anchored.items():
            if role == "value" and isinstance(fields.get("value"), (int, float)):
                sel, fields["value"] = _narrow(text, sel, float(fields["value"]))
            spans.append(Span.of(role, sel))
        return (fields, links, spans), rejects


def _narrow(text: str, sel: Selector, value: float) -> tuple[Selector, float]:
    """The number inside a value quote that the value was read from, and the value as a fraction when the
    quote writes it as a percentage."""
    exact = sel.exact
    for hit in base.NUMBER.finditer(exact):
        number = float(hit.group(1))
        pct = bool(hit.group(2))
        if abs(number - value) < 1e-9 or (pct and abs(number / 100 - value) < 1e-9):
            end = hit.end(2) if pct else hit.end(1)
            narrowed = selector_at(text, sel.start + hit.start(1), sel.start + end, file=sel.file, sha256=sel.sha256)
            return narrowed, round(number / 100, 6) if pct else round(value, 6)
    return sel, round(value, 6)


def _factory(evidence_type: str) -> Any:
    return lambda config: LLMExtractor(evidence_type, config)


FACTORIES = {f"llm_{t}": _factory(t) for t in ("condition", "metric", "measurement", "author_claim")}
