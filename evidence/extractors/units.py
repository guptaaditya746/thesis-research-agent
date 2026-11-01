"""`regex_measurement_units`: regex_measurement for protocols whose question metric is not a fraction (latency).

regex_measurement treats every question metric as an accuracy or a rate, so a bare 1 < x <= 100 is read as a
percentage (1.8 s becomes 0.018). This extractor finds the same tables and sentences (evidence/extractors/
measure.py), but only the metrics in `fraction_metrics` (the pack's, or the protocol's: the canonicals a
protocol bounds to [0, 1]) are rate-like. Any other value stays in its own unit: a table cell as
written (a cell under a millisecond header, "Latency (ms)", is divided by 1000, so values are seconds), and in a
sentence a number with a time unit ("1.80 s", "655 ms", "2 seconds") becomes a value of the nearest non-fraction
metric, linked to a condition as measure.py links sentence values; a difference ("0.45 s slower than") is no
value. A percentage (a % sign, a % header or
caption) is still a fraction. It lives in its own module so every existing extractor keeps its id.
"""
from __future__ import annotations

import re
from typing import Any

from ..contract import ExtractionResult, ExtractionTask, ExtractorSpec, Item, RunContext
from . import base, regex, terms
from .measure import (AFTER, BLOCKERS, DELTA_BEFORE, FROM_TO, HEAD_NOUN, SIGNED, Found, Resolver, measurements)

VERSION = 1
SOURCES = (base.HERE / "units.py", base.HERE / "measure.py", base.HERE / "numreader.py", base.HERE / "terms.py", *base.SHARED_SOURCES)
CODE_SHA256 = base.source_sha256(*SOURCES)
TIME = re.compile(r"(?<![\w.,])(\d+(?:\.\d+)?|\.\d+)\s?(ms|milliseconds?|s|secs?|seconds?)\b")
# "0.45 s slower than": a difference between two conditions, not a value of either
DIFFERENCE_AFTER = re.compile(r"(?i)\s+(?:slower|faster|longer|shorter|more|less)\b")
UNIT_AFTER = re.compile(r"\s?(?:ms|milliseconds?|s|secs?|seconds?)\b")
MS_HEADER = re.compile(r"(?i)\(\s*(?:ms|milliseconds?)\s*\)")


class MeasurementUnitsRegex:
    evidence_type, name = "measurement", "regex_measurement_units"

    def __init__(self, config: dict[str, Any]) -> None:
        self.given = {k: v for k, v in config.items() if k in regex.INJECTED}
        rest = {k: v for k, v in config.items() if k not in regex.INJECTED}
        self.fractions = [str(m) for m in rest.pop("fraction_metrics")]   # the pack's, or the protocol's
        self.patterns = {"alias": terms.ALIAS} | rest
        self.emits = base.emitted(self.given, self.evidence_type)
        self.slots = base.Slots.of(self.given)
        self.spec = ExtractorSpec(name=self.name, version=VERSION, kind="regex", evidence_types=(self.emits,),
                                  code_sha256=CODE_SHA256,
                                  config={**self.given, **self.patterns, "fraction_metrics": self.fractions},
                                  determinism="exact")

    def extract(self, task: ExtractionTask, ctx: RunContext) -> ExtractionResult:
        text = ctx.text()
        parts = base.ranges(task, text)
        context = ctx.context_items()
        patterns = {**self.patterns, "question_metrics": self.fractions,   # rate-like: the fraction metrics only
                    "treatment": (self.given.get("compare") or {}).get("treatment"), "slots": self.slots}
        found = [self._seconds(f, context) for f in measurements(task, text, parts, context, patterns)
                 if not self._difference(f, text, context)]
        resolver = Resolver(text, context, patterns)
        if resolver.conditions and resolver.metrics:
            for a, b in parts:
                for s, e in base.sentences(text, a, b):
                    found.extend(self._timed(task, text, s, e, resolver))
        items: list[Item] = base.group(self.emits, found)
        return ExtractionResult(extractor_id=self.spec.extractor_id, task_sha256=task.task_sha256, status="ok",
                                items=tuple(items), coverage=base.coverage(parts, items)).canonical()

    def _difference(self, found: Found, text: str, context: list[Item]) -> bool:
        """A non-fraction value measure.py read in a sentence that is a difference ("0.45 s slower than")."""
        metric = next((i for i in context if i.item_id == found[1].get(self.slots.to_metric)), None)
        if metric is None or metric.fields.get("canonical") in self.fractions:
            return False
        end = next((int(s.selector["end"]) for s in found[2] if s.role == "value"), None)
        unit = UNIT_AFTER.match(text, end) if end is not None else None
        return unit is not None and DIFFERENCE_AFTER.match(text, unit.end()) is not None

    def _seconds(self, found: Found, context: list[Item]) -> Found:
        """A non-fraction value under a millisecond header, in seconds."""
        fields, links, spans = found
        metric = next((i for i in context if i.item_id == links.get(self.slots.to_metric)), None)
        label = next((s.selector.get("exact", "") for s in spans if s.role == "metric_label"), "")
        if metric is not None and metric.fields.get("canonical") not in self.fractions and MS_HEADER.search(label):
            fields = {**fields, "value": round(float(fields["value"]) / 1000, 6)}
        return fields, links, spans

    def _timed(self, task: ExtractionTask, text: str, s: int, e: int, r: Resolver) -> list[Found]:
        """Numbers with a time unit in one sentence, as values of a non-fraction metric (measure._sentence's rules)."""
        conditions = [(m, i) for m, i in ((m, r.condition_for(m)) for m in r.mentions(text, s, e)) if i is not None]
        metrics = [(m, i) for m, i in ((m, r.metric_for(m)) for m in terms.find_all(text, r.metric_patterns, s, e))  # type: ignore[arg-type]
                   if i is not None and i.fields.get("canonical") not in self.fractions]
        if not conditions or not metrics:
            return []
        changes = [(m.start(), m.end()) for m in FROM_TO.finditer(text, s, e)]
        out: list[Found] = []
        for hit in TIME.finditer(text, s, e):
            before = text[max(s, hit.start() - 20):hit.start()]
            if DELTA_BEFORE.search(before) or SIGNED.search(before) or any(a <= hit.start() < b for a, b in changes):
                continue
            if DIFFERENCE_AFTER.match(text, hit.end(), e):
                continue
            after = AFTER.match(text, hit.end(), e)
            following = next(((m, i) for m, i in conditions if after and m.start == after.end()), None)
            preceding = [(m, i) for m, i in conditions if m.end <= hit.start()]
            head = HEAD_NOUN.match(text, preceding[-1][0].end) if preceding else None
            if preceding and BLOCKERS.search(text, head.end() if head else preceding[-1][0].end, hit.start()):
                preceding = []
            cond = following or (preceding[-1] if preceding else None)
            before_metrics = [(m, i) for m, i in metrics if m.end <= hit.start()]
            met = before_metrics[-1] if before_metrics else next(((m, i) for m, i in metrics if m.start >= hit.end()), None)
            if cond is None or met is None:
                continue
            value = float(hit.group(1)) / (1000 if hit.group(2).startswith("m") else 1)
            spans = [base.span(task, text, hit.start(1), hit.end(1), "value"),
                     base.span(task, text, cond[0].start, cond[0].end, "condition_label"),
                     base.span(task, text, met[0].start, met[0].end, "metric_label")]
            out.append(({"value": round(value, 6), "dataset": None}, r.slots.links(cond[1], met[1]), spans))
        return out


FACTORIES = {"regex_measurement_units": MeasurementUnitsRegex}
