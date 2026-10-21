"""Regex extractors, one per evidence type (kind regex, determinism exact).

They find the explicit cases: condition and metric names from fixed wording, measurements in sentences
("the retrieval-augmented model reaches 71%, compared with 62% for the closed-book model") and in
Markdown tables (row and column labels matched to the context's conditions and metrics, by label or by a
code the method section defines: "its retrieval-augmented variant (R)"), and author claims from effect
phrases. Paraphrased, distributed and complex renderings are expected to be missed; how much they miss is
measured on the synthetic benchmark, not hidden.
"""
from __future__ import annotations

from typing import Any

from gold.chunks import sections

from ..contract import ExtractionResult, ExtractionTask, ExtractorSpec, Item, RunContext, Span
from . import base, terms
from .measure import measurements

VERSION = 2
SOURCES = (base.HERE / "regex.py", base.HERE / "measure.py", base.HERE / "terms.py", *base.SHARED_SOURCES)
CODE_SHA256 = base.source_sha256(*SOURCES)
INJECTED = ("evidence_type", "field_schema", "links", "roles", "question_metrics", "compare")   # added by the engine


class RegexExtractor:
    """Common shape: spec from config, the task's parts, coverage per part."""
    evidence_type: str = ""
    name: str = ""

    def __init__(self, config: dict[str, Any]) -> None:
        given = {k: v for k, v in config.items() if k in INJECTED}
        self.given = given
        self.patterns = self.default_patterns() | {k: v for k, v in config.items() if k not in INJECTED}
        self.spec = ExtractorSpec(name=self.name, version=VERSION, kind="regex",
                                  evidence_types=(self.evidence_type,),  # type: ignore[arg-type]
                                  code_sha256=CODE_SHA256, config={**given, **self.patterns}, determinism="exact")

    def default_patterns(self) -> dict[str, Any]:
        return {}

    def extract(self, task: ExtractionTask, ctx: RunContext) -> ExtractionResult:
        text = ctx.text()
        parts = base.ranges(task, text)
        items = self.find(task, ctx, text, parts)
        return ExtractionResult(extractor_id=self.spec.extractor_id, task_sha256=task.task_sha256, status="ok",
                                items=tuple(items), coverage=base.coverage(parts, items)).canonical()

    def find(self, task: ExtractionTask, ctx: RunContext, text: str, parts: list[tuple[int, int]]) -> list[Item]:
        raise NotImplementedError


class ConditionRegex(RegexExtractor):
    evidence_type, name = "condition", "regex_condition"

    def default_patterns(self) -> dict[str, Any]:
        return {"conditions": terms.CONDITIONS, "alias": terms.ALIAS, "max_spans": 4}

    def find(self, task: ExtractionTask, ctx: RunContext, text: str, parts: list[tuple[int, int]]) -> list[Item]:
        patterns = terms.condition_patterns(self.patterns["conditions"])
        enum = self.given.get("field_schema", {}).get("properties", {}).get("role", {}).get("enum")
        roles = list(enum or self.patterns["conditions"])   # "other" (a qualified ablation) only if the type has it
        mentions = [m for a, b in parts for m in terms.find_conditions(text, patterns, roles, a, b)]
        defined = {m: (a, b) for m, _, a, b in terms.aliases(text, mentions)}
        found = []
        for role in dict.fromkeys([*self.patterns["conditions"], *(["other"] if "other" in roles else [])]):
            mine = [m for m in mentions if m.key == role]
            if not mine:
                continue
            chosen = [mine[0]] + [m for m in mine[1:] if m in defined]
            spans = [base.span(task, text, *defined.get(m, (m.start, m.end)), "condition_label")
                     for m in chosen[: self.patterns["max_spans"]]]
            found.append(({"label": " ".join(mine[0].text.split()), "role": role}, {}, spans))
        return base.group("condition", found)


class MetricRegex(RegexExtractor):
    evidence_type, name = "metric", "regex_metric"

    def default_patterns(self) -> dict[str, Any]:
        return {"metrics": [list(m) for m in terms.METRICS], "max_spans": 2}

    def find(self, task: ExtractionTask, ctx: RunContext, text: str, parts: list[tuple[int, int]]) -> list[Item]:
        patterns = [tuple(m) for m in self.patterns["metrics"]]
        by_name: dict[str, list[terms.Mention]] = {}
        for a, b in parts:
            for m in terms.find_all(text, patterns, a, b):  # type: ignore[arg-type]
                by_name.setdefault(terms.norm(m.text), []).append(m)
        found = []
        for mentions in by_name.values():
            first = mentions[0]
            spans = [base.span(task, text, m.start, m.end, "metric_label") for m in mentions[: self.patterns["max_spans"]]]
            fields = {"name": " ".join(first.text.split()), "canonical": first.key, "higher_is_better": first.higher_is_better}
            found.append((fields, {}, spans))
        return base.group("metric", found)


class MeasurementRegex(RegexExtractor):
    evidence_type, name = "measurement", "regex_measurement"

    def default_patterns(self) -> dict[str, Any]:
        return {"conditions": terms.CONDITIONS, "metrics": [list(m) for m in terms.METRICS], "alias": terms.ALIAS}

    def find(self, task: ExtractionTask, ctx: RunContext, text: str, parts: list[tuple[int, int]]) -> list[Item]:
        # the question metrics come from the protocol's synthesis block (the engine injects them), never from here
        found = measurements(task, text, parts, ctx.context_items(),
                             {**self.patterns, "question_metrics": self.given.get("question_metrics", [])})
        return base.group("measurement", found)


class AuthorClaimRegex(RegexExtractor):
    evidence_type, name = "author_claim", "regex_author_claim"

    def default_patterns(self) -> dict[str, Any]:
        return {"subject": terms.CLAIM_SUBJECT, "claims": [list(c) for c in terms.CLAIMS],
                "skip": r"(?i)\bwhether\b|\?|\bif\b|\bprior work\b|\bprevious work\b",
                "sections": list(terms.CLAIM_SECTIONS), "max_spans": 3}

    def find(self, task: ExtractionTask, ctx: RunContext, text: str, parts: list[tuple[int, int]]) -> list[Item]:
        compiled = terms._compiled
        heads = sections(text)
        candidates: list[tuple[int, int, int, str]] = []   # priority, start, end, direction
        for a, b in parts:
            for s, e in base.sentences(text, a, b):
                sentence = text[s:e]
                if not compiled(self.patterns["subject"]).search(sentence) or compiled(self.patterns["skip"]).search(sentence):
                    continue
                direction = next((d for p, d in self.patterns["claims"] if compiled(p).search(sentence)), None)
                if direction is not None:
                    candidates.append((self._priority(heads, s), s, e, direction))
        if not candidates:
            return []
        best = min(candidates)
        same = [c for c in sorted(candidates) if c[0] == best[0] and c[3] == best[3]][: self.patterns["max_spans"]]
        spans: list[Span] = [base.span(task, text, s, e, "claim") for _, s, e, _ in same]
        return base.group("author_claim", [({"direction": best[3]}, {}, spans)])

    def _priority(self, heads: list[tuple[int, int, str | None]], pos: int) -> int:
        """Index of the first preferred section word in the heading the position falls under."""
        heading = next((h for a, b, h in heads if a <= pos < b), None) or ""
        words = self.patterns["sections"]
        return next((n for n, w in enumerate(words) if w in heading.casefold()), len(words))


FACTORIES = {cls.name: cls for cls in (ConditionRegex, MetricRegex, MeasurementRegex, AuthorClaimRegex)}
